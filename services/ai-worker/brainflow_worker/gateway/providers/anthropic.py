"""Anthropic Messages API adapter (real HTTP path; mockable via transport)."""

from __future__ import annotations

from typing import Any

import httpx

from brainflow_worker.gateway.budget import RequestBudget, extract_usage_tokens
from brainflow_worker.gateway.providers.base import ProviderAdapter
from brainflow_worker.gateway.providers.http_util import make_client
from brainflow_worker.gateway.secrets import get_secret

DEFAULT_ANTHROPIC_BASE = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter(ProviderAdapter):
    """POST /v1/messages + GET /v1/models. No live keys required for unit tests."""

    id = "anthropic"
    kind = "cloud"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_ANTHROPIC_BASE,
        api_key_ref: str = "anthropic",
        transport: httpx.BaseTransport | None = None,
        default_budget: RequestBudget | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_ref = api_key_ref
        self.transport = transport
        self.default_budget = default_budget
        self.display = "Anthropic"
        self.docs_url = "https://docs.anthropic.com/"
        self.secret_ref = api_key_ref

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
        }
        key = get_secret(self.api_key_ref)
        if key:
            headers["x-api-key"] = key
        return headers

    def _client(self, timeout_s: float) -> httpx.Client:
        return make_client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=timeout_s,
            transport=self.transport,
        )

    def health(self, *, timeout_s: float = 3.0) -> dict[str, Any]:
        if not get_secret(self.api_key_ref) and self.transport is None:
            return {
                "ok": False,
                "provider": self.id,
                "kind": self.kind,
                "display": self.display,
                "docs_url": self.docs_url,
                "secret_ref": self.secret_ref,
                "error": "Anthropic API key missing (secrets ref 'anthropic')",
                "models": [],
                "next_steps": [
                    f"Store API key via secrets.set under ref '{self.secret_ref}'",
                    f"See {self.docs_url}",
                ],
            }
        try:
            with self._client(timeout_s) as client:
                r = client.get("/v1/models")
                r.raise_for_status()
                payload = r.json()
                data = payload.get("data") or []
                names = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                if not names:
                    return {
                        "ok": False,
                        "provider": self.id,
                        "kind": self.kind,
                        "error": "Anthropic reachable but no models listed",
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
                "error": f"Anthropic probe failed: {exc}",
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
        system_parts: list[str] = []
        api_messages: list[dict[str, Any]] = []
        for m in messages:
            role = str(m.get("role") or "user")
            content = m.get("content")
            if role == "system":
                system_parts.append(str(content or ""))
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            api_messages.append({"role": role, "content": content})
        if not api_messages:
            api_messages = [{"role": "user", "content": "ping"}]

        planned = kwargs.get("max_tokens")
        if budget is not None:
            max_tokens = budget.clamp_max_tokens(
                int(planned) if planned is not None else None, default=1024
            )
            budget.check_before_request(planned_max_tokens=max_tokens)
        else:
            max_tokens = int(planned) if planned is not None else 1024

        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": api_messages,
        }
        if system_parts:
            body["system"] = "\n".join(system_parts)
        if kwargs.get("tools") is not None:
            body["tools"] = kwargs["tools"]
        # Anthropic has no native json_object mode; ask via system + optional tool.
        if kwargs.get("response_format") is not None or kwargs.get("format") == "json":
            body["system"] = (
                (body.get("system") or "")
                + "\nRespond with valid JSON only."
            ).strip()

        with self._client(timeout_s) as client:
            r = client.post("/v1/messages", json=body)
            r.raise_for_status()
            data = r.json()

        if budget is not None:
            budget.record_usage(
                tokens=extract_usage_tokens(data) or max_tokens,
                meta={"provider": self.id, "model": model},
            )
        return data

    def capability_probe_hooks(self) -> dict[str, bool]:
        return {
            "json_schema": True,
            "tools": True,
            "vision": True,
            "embeddings": False,
            "streaming": True,
            "cancellation": True,
        }
