from __future__ import annotations

import os
from typing import Any

import httpx

from brainflow_worker.gateway.budget import RequestBudget, extract_usage_tokens
from brainflow_worker.gateway.providers.base import ProviderAdapter
from brainflow_worker.gateway.providers.http_util import make_client

DEFAULT_OLLAMA_BASE = "http://127.0.0.1:11434"


def ollama_base_url() -> str:
    return os.environ.get("BRAINFLOW_OLLAMA_BASE", DEFAULT_OLLAMA_BASE).rstrip("/")


class OllamaAdapter(ProviderAdapter):
    id = "ollama"
    kind = "local"

    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        default_budget: RequestBudget | None = None,
    ) -> None:
        self.base_url = (base_url or ollama_base_url()).rstrip("/")
        self.transport = transport
        self.default_budget = default_budget

    def _client(self, timeout_s: float) -> httpx.Client:
        return make_client(
            base_url=self.base_url,
            timeout=timeout_s,
            transport=self.transport,
        )

    def health(self, *, timeout_s: float = 3.0) -> dict[str, Any]:
        try:
            with self._client(timeout_s) as client:
                r = client.get("/api/tags")
                r.raise_for_status()
                payload = r.json()
                models = payload.get("models") or []
                names = [m.get("name") for m in models if m.get("name")]
                digests = {
                    m.get("name"): (m.get("digest") or m.get("details", {}).get("parent_model"))
                    for m in models
                    if m.get("name")
                }
                if not names:
                    return {
                        "ok": False,
                        "provider": self.id,
                        "kind": self.kind,
                        "base_url": self.base_url,
                        "error": "Ollama is reachable but no models are installed",
                        "models": [],
                    }
                preferred = _prefer_model(names)
                return {
                    "ok": True,
                    "provider": self.id,
                    "kind": self.kind,
                    "base_url": self.base_url,
                    "models": names,
                    "digests": {k: v for k, v in digests.items() if v},
                    "preferred_model": preferred,
                    "model_count": len(names),
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "provider": self.id,
                "kind": self.kind,
                "base_url": self.base_url,
                "error": f"Ollama probe failed: {exc}",
                "models": [],
            }

    def list_models(self, *, timeout_s: float = 5.0) -> list[dict[str, Any]]:
        h = self.health(timeout_s=timeout_s)
        digests = h.get("digests") or {}
        return [
            {
                "provider": self.id,
                "name": n,
                "digest": digests.get(n),
                "local": True,
            }
            for n in (h.get("models") or [])
        ]

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_s: float = 60.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        budget: RequestBudget | None = kwargs.pop("budget", None) or self.default_budget
        options = dict(kwargs.get("options") or {"temperature": 0.2})
        planned = kwargs.get("max_tokens")
        if budget is not None:
            max_tokens = budget.clamp_max_tokens(
                int(planned) if planned is not None else None, default=256
            )
            budget.check_before_request(planned_max_tokens=max_tokens)
            options["num_predict"] = max_tokens
        elif planned is not None:
            options["num_predict"] = int(planned)

        body: dict[str, Any] = {
            "model": model,
            "stream": bool(kwargs.get("stream", False)),
            "messages": messages,
            "options": options,
        }
        if kwargs.get("format") is not None:
            body["format"] = kwargs["format"]
        with self._client(timeout_s) as client:
            r = client.post("/api/chat", json=body)
            r.raise_for_status()
            data = r.json()
        if budget is not None:
            budget.record_usage(
                tokens=extract_usage_tokens(data) or int(options.get("num_predict") or 0),
                meta={"provider": self.id, "model": model},
            )
        return data

    def embeddings(
        self,
        *,
        model: str,
        inputs: list[str],
        timeout_s: float = 30.0,
    ) -> dict[str, Any]:
        # Ollama embeddings endpoint accepts one prompt at a time.
        vectors: list[list[float]] = []
        with self._client(timeout_s) as client:
            for text in inputs:
                r = client.post("/api/embeddings", json={"model": model, "prompt": text})
                r.raise_for_status()
                data = r.json()
                vectors.append(list(data.get("embedding") or []))
        return {"embeddings": vectors, "model": model, "provider": self.id}

    def capability_probe_hooks(self) -> dict[str, bool]:
        return {
            "json_schema": True,
            "tools": True,
            "vision": True,
            "embeddings": True,
            "streaming": True,
            "cancellation": True,
        }


def _prefer_model(names: list[str]) -> str:
    for candidate in ("llama3.2:3b", "llama3.2", "llama3.1", "qwen2.5", "mistral"):
        for n in names:
            if n == candidate or n.startswith(candidate):
                return n
    return sorted(names, key=len)[0]
