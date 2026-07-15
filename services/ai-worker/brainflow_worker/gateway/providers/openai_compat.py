from __future__ import annotations

from typing import Any

import httpx

from brainflow_worker.gateway.budget import RequestBudget, extract_usage_tokens
from brainflow_worker.gateway.providers.base import ProviderAdapter
from brainflow_worker.gateway.providers.http_util import is_loopback, make_client
from brainflow_worker.gateway.secrets import get_secret


class OpenAICompatAdapter(ProviderAdapter):
    """OpenAI Chat Completions-compatible endpoints (LM Studio, llama.cpp, vLLM, custom)."""

    id = "openai_compat"
    kind = "openai_compat"

    def __init__(
        self,
        *,
        base_url: str,
        api_key_ref: str = "openai_compat",
        provider_id: str = "openai_compat",
        require_tls: bool = True,
        transport: httpx.BaseTransport | None = None,
        default_budget: RequestBudget | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_ref = api_key_ref
        self.id = provider_id
        self.require_tls = require_tls and not is_loopback(self.base_url)
        self.transport = transport
        self.default_budget = default_budget

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key = get_secret(self.api_key_ref)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _ensure_tls(self) -> None:
        if self.require_tls and not self.base_url.lower().startswith("https://"):
            raise RuntimeError(
                f"{self.id}: TLS required for non-loopback OpenAI-compatible endpoints"
            )

    def _client(self, timeout_s: float) -> httpx.Client:
        return make_client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=timeout_s,
            transport=self.transport,
        )

    def health(self, *, timeout_s: float = 3.0) -> dict[str, Any]:
        try:
            self._ensure_tls()
            with self._client(timeout_s) as client:
                r = client.get("/models")
                r.raise_for_status()
                payload = r.json()
                data = payload.get("data") or payload.get("models") or []
                names = [m.get("id") or m.get("name") for m in data if isinstance(m, dict)]
                names = [n for n in names if n]
                if not names:
                    return {
                        "ok": False,
                        "provider": self.id,
                        "kind": self.kind,
                        "base_url": self.base_url,
                        "error": "Endpoint reachable but no models listed",
                        "models": [],
                    }
                return {
                    "ok": True,
                    "provider": self.id,
                    "kind": self.kind,
                    "base_url": self.base_url,
                    "models": names,
                    "preferred_model": names[0],
                    "model_count": len(names),
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "provider": self.id,
                "kind": self.kind,
                "base_url": self.base_url,
                "error": f"OpenAI-compatible probe failed: {exc}",
                "models": [],
            }

    def list_models(self, *, timeout_s: float = 5.0) -> list[dict[str, Any]]:
        h = self.health(timeout_s=timeout_s)
        return [
            {
                "provider": self.id,
                "name": n,
                "digest": None,
                "local": is_loopback(self.base_url),
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
        self._ensure_tls()
        budget: RequestBudget | None = kwargs.pop("budget", None) or self.default_budget
        planned = kwargs.get("max_tokens")
        if budget is not None:
            max_tokens = budget.clamp_max_tokens(
                int(planned) if planned is not None else None, default=1024
            )
            budget.check_before_request(planned_max_tokens=max_tokens)
        else:
            max_tokens = int(planned) if planned is not None else None

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": bool(kwargs.get("stream", False)),
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if kwargs.get("response_format") is not None:
            body["response_format"] = kwargs["response_format"]
        if kwargs.get("tools") is not None:
            body["tools"] = kwargs["tools"]
        with self._client(timeout_s) as client:
            r = client.post("/chat/completions", json=body)
            r.raise_for_status()
            data = r.json()
        if budget is not None:
            budget.record_usage(
                tokens=extract_usage_tokens(data) or (max_tokens or 0),
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
        self._ensure_tls()
        with self._client(timeout_s) as client:
            r = client.post(
                "/embeddings",
                json={"model": model, "input": inputs},
            )
            r.raise_for_status()
            data = r.json()
            vectors = [row.get("embedding") for row in (data.get("data") or [])]
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


class OpenAIAdapter(OpenAICompatAdapter):
    """First-party OpenAI cloud (same wire protocol as openai_compat)."""

    def __init__(
        self,
        *,
        api_key_ref: str = "openai",
        base_url: str = "https://api.openai.com/v1",
        transport: httpx.BaseTransport | None = None,
        default_budget: RequestBudget | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key_ref=api_key_ref,
            provider_id="openai",
            require_tls=True,
            transport=transport,
            default_budget=default_budget,
        )
        self.kind = "cloud"
        self.display = "OpenAI"
        self.docs_url = "https://platform.openai.com/docs"
        self.secret_ref = api_key_ref

    def health(self, *, timeout_s: float = 3.0) -> dict[str, Any]:
        if not get_secret(self.api_key_ref) and self.transport is None:
            return {
                "ok": False,
                "provider": self.id,
                "kind": self.kind,
                "display": self.display,
                "docs_url": self.docs_url,
                "secret_ref": self.secret_ref,
                "error": "OpenAI API key missing (secrets ref 'openai')",
                "models": [],
            }
        return super().health(timeout_s=timeout_s)
