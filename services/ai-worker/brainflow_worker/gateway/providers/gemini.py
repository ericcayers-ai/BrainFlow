"""Google Gemini generative language API adapter (mockable via transport)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from brainflow_worker.gateway.budget import RequestBudget, extract_usage_tokens
from brainflow_worker.gateway.providers.base import ProviderAdapter
from brainflow_worker.gateway.providers.http_util import make_client
from brainflow_worker.gateway.secrets import get_secret

DEFAULT_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiAdapter(ProviderAdapter):
    """List models + generateContent. Key via secret ref; unit tests inject transport."""

    id = "gemini"
    kind = "cloud"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_GEMINI_BASE,
        api_key_ref: str = "gemini",
        transport: httpx.BaseTransport | None = None,
        default_budget: RequestBudget | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_ref = api_key_ref
        self.transport = transport
        self.default_budget = default_budget
        self.display = "Google Gemini"
        self.docs_url = "https://ai.google.dev/"
        self.secret_ref = api_key_ref

    def _api_key(self) -> str | None:
        return get_secret(self.api_key_ref)

    def _client(self, timeout_s: float) -> httpx.Client:
        return make_client(
            base_url=self.base_url,
            headers={"Content-Type": "application/json"},
            timeout=timeout_s,
            transport=self.transport,
        )

    def health(self, *, timeout_s: float = 3.0) -> dict[str, Any]:
        key = self._api_key()
        if not key and self.transport is None:
            return {
                "ok": False,
                "provider": self.id,
                "kind": self.kind,
                "display": self.display,
                "docs_url": self.docs_url,
                "secret_ref": self.secret_ref,
                "error": "Gemini API key missing (secrets ref 'gemini')",
                "models": [],
                "next_steps": [
                    f"Store API key via secrets.set under ref '{self.secret_ref}'",
                    f"See {self.docs_url}",
                ],
            }
        try:
            with self._client(timeout_s) as client:
                params = {"key": key} if key else {}
                r = client.get("/models", params=params)
                r.raise_for_status()
                payload = r.json()
                models = payload.get("models") or []
                names: list[str] = []
                for m in models:
                    if not isinstance(m, dict):
                        continue
                    name = str(m.get("name") or "")
                    # API returns "models/gemini-1.5-flash"
                    if name.startswith("models/"):
                        name = name[len("models/") :]
                    methods = m.get("supportedGenerationMethods") or []
                    if name and ("generateContent" in methods or not methods):
                        names.append(name)
                if not names:
                    return {
                        "ok": False,
                        "provider": self.id,
                        "kind": self.kind,
                        "error": "Gemini reachable but no generative models listed",
                        "models": [],
                    }
                preferred = next((n for n in names if "flash" in n.lower()), names[0])
                return {
                    "ok": True,
                    "provider": self.id,
                    "kind": self.kind,
                    "base_url": self.base_url,
                    "models": names,
                    "preferred_model": preferred,
                    "model_count": len(names),
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "provider": self.id,
                "kind": self.kind,
                "base_url": self.base_url,
                "error": f"Gemini probe failed: {exc}",
                "models": [],
            }

    def list_models(self, *, timeout_s: float = 5.0) -> list[dict[str, Any]]:
        h = self.health(timeout_s=timeout_s)
        return [
            {"provider": self.id, "name": n, "digest": None, "local": False}
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
        key = self._api_key()
        if not key and self.transport is None:
            raise RuntimeError("Gemini API key missing")

        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []
        for m in messages:
            role = str(m.get("role") or "user")
            text = str(m.get("content") or "")
            if role == "system":
                system_parts.append(text)
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": text}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "ping"}]}]

        planned = kwargs.get("max_tokens")
        if budget is not None:
            max_tokens = budget.clamp_max_tokens(
                int(planned) if planned is not None else None, default=1024
            )
            budget.check_before_request(planned_max_tokens=max_tokens)
        else:
            max_tokens = int(planned) if planned is not None else 1024

        gen_cfg: dict[str, Any] = {"maxOutputTokens": max_tokens}
        if kwargs.get("response_format") is not None or kwargs.get("format") == "json":
            gen_cfg["responseMimeType"] = "application/json"

        body: dict[str, Any] = {"contents": contents, "generationConfig": gen_cfg}
        if system_parts:
            body["systemInstruction"] = {"parts": [{"text": "\n".join(system_parts)}]}

        model_path = model if model.startswith("models/") else f"models/{model}"
        path = f"/{quote(model_path, safe='/')}:generateContent"
        params = {"key": key} if key else {}

        with self._client(timeout_s) as client:
            r = client.post(path, params=params, json=body)
            r.raise_for_status()
            data = r.json()

        if budget is not None:
            budget.record_usage(
                tokens=extract_usage_tokens(data) or max_tokens,
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
        key = self._api_key()
        if not key and self.transport is None:
            raise RuntimeError("Gemini API key missing")
        model_path = model if model.startswith("models/") else f"models/{model}"
        path = f"/{quote(model_path, safe='/')}:embedContent"
        vectors: list[list[float]] = []
        with self._client(timeout_s) as client:
            for text in inputs:
                params = {"key": key} if key else {}
                r = client.post(
                    path,
                    params=params,
                    json={"content": {"parts": [{"text": text}]}},
                )
                r.raise_for_status()
                data = r.json()
                emb = (data.get("embedding") or {}).get("values") or data.get("values") or []
                vectors.append(list(emb))
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
