"""OpenRouter + custom OpenAI-compatible provider wrappers (real HTTP paths)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from brainflow_worker.gateway.budget import RequestBudget
from brainflow_worker.gateway.providers.openai_compat import OpenAICompatAdapter

DEFAULT_OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(OpenAICompatAdapter):
    """OpenRouter uses the OpenAI chat-completions wire protocol."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OPENROUTER_BASE,
        api_key_ref: str = "openrouter",
        transport: httpx.BaseTransport | None = None,
        default_budget: RequestBudget | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key_ref=api_key_ref,
            provider_id="openrouter",
            require_tls=True,
            transport=transport,
            default_budget=default_budget,
        )
        self.kind = "cloud"
        self.display = "OpenRouter"
        self.docs_url = "https://openrouter.ai/docs"
        self.secret_ref = api_key_ref

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        # OpenRouter optionally benefits from referer / title headers.
        headers.setdefault("HTTP-Referer", "https://brainflow.local")
        headers.setdefault("X-Title", "BrainFlow")
        return headers

    def health(self, *, timeout_s: float = 3.0) -> dict[str, Any]:
        from brainflow_worker.gateway.secrets import get_secret

        if not get_secret(self.api_key_ref) and self.transport is None:
            return {
                "ok": False,
                "provider": self.id,
                "kind": self.kind,
                "display": self.display,
                "docs_url": self.docs_url,
                "secret_ref": self.secret_ref,
                "error": "OpenRouter API key missing (secrets ref 'openrouter')",
                "models": [],
                "next_steps": [
                    f"Store API key via secrets.set under ref '{self.secret_ref}'",
                    f"See {self.docs_url}",
                ],
            }
        return super().health(timeout_s=timeout_s)


class CustomOpenAICompatAdapter(OpenAICompatAdapter):
    """User-configured OpenAI-compatible endpoint (LM Studio, vLLM, private)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key_ref: str = "custom",
        provider_id: str = "custom",
        require_tls: bool | None = None,
        transport: httpx.BaseTransport | None = None,
        default_budget: RequestBudget | None = None,
    ) -> None:
        if require_tls is None:
            require_tls = True
        super().__init__(
            base_url=base_url,
            api_key_ref=api_key_ref,
            provider_id=provider_id,
            require_tls=require_tls,
            transport=transport,
            default_budget=default_budget,
        )
        self.display = f"Custom provider ({provider_id})"
        self.docs_url = "https://brainflow.local/docs/MODEL_SELECTION.md"
        self.secret_ref = api_key_ref

    def health(self, *, timeout_s: float = 3.0) -> dict[str, Any]:
        h = super().health(timeout_s=timeout_s)
        h["display"] = self.display
        h["docs_url"] = self.docs_url
        h["secret_ref"] = self.secret_ref
        return h


def custom_from_env() -> CustomOpenAICompatAdapter | None:
    """Optional custom endpoint via BRAINFLOW_CUSTOM_BASE (or openai_compat env)."""
    base = os.environ.get("BRAINFLOW_CUSTOM_BASE") or os.environ.get("BRAINFLOW_OPENAI_COMPAT_BASE")
    if not base:
        return None
    return CustomOpenAICompatAdapter(
        base_url=base,
        api_key_ref=os.environ.get("BRAINFLOW_CUSTOM_SECRET_REF", "custom"),
        provider_id=os.environ.get("BRAINFLOW_CUSTOM_PROVIDER_ID", "custom"),
    )
