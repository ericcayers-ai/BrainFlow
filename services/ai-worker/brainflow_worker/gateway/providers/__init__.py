from __future__ import annotations

import os
from typing import Any

from brainflow_worker.gateway.providers.anthropic import AnthropicAdapter
from brainflow_worker.gateway.providers.gemini import GeminiAdapter
from brainflow_worker.gateway.providers.ollama import OllamaAdapter
from brainflow_worker.gateway.providers.openai_compat import OpenAIAdapter, OpenAICompatAdapter
from brainflow_worker.gateway.providers.openrouter import (
    CustomOpenAICompatAdapter,
    OpenRouterAdapter,
    custom_from_env,
)


def default_adapters() -> list[Any]:
    adapters: list[Any] = [OllamaAdapter()]
    openai_compat = os.environ.get("BRAINFLOW_OPENAI_COMPAT_BASE")
    if openai_compat and not os.environ.get("BRAINFLOW_CUSTOM_BASE"):
        adapters.append(
            OpenAICompatAdapter(
                base_url=openai_compat,
                api_key_ref=os.environ.get("BRAINFLOW_OPENAI_COMPAT_SECRET_REF", "openai_compat"),
            )
        )
    if os.environ.get("BRAINFLOW_ENABLE_OPENAI") == "1":
        adapters.append(OpenAIAdapter())
    # Always register cloud adapters — health fails closed without secrets (no live keys in CI).
    adapters.append(AnthropicAdapter())
    adapters.append(GeminiAdapter())
    adapters.append(OpenRouterAdapter())
    custom = custom_from_env()
    if custom:
        adapters.append(custom)
    else:
        # Placeholder custom slot for UI discovery; health reports not configured.
        adapters.append(
            CustomOpenAICompatAdapter(
                base_url=os.environ.get("BRAINFLOW_CUSTOM_BASE_HINT", "https://127.0.0.1:0/v1"),
                provider_id="custom",
                require_tls=False,
            )
        )
    return adapters


def get_adapter(provider_id: str) -> Any | None:
    for a in default_adapters():
        if getattr(a, "id", None) == provider_id:
            return a
    return None


def aggregate_health(*, timeout_s: float = 3.0) -> dict[str, Any]:
    providers = []
    any_ok = False
    preferred = None
    for adapter in default_adapters():
        h = adapter.health(timeout_s=timeout_s)
        providers.append(h)
        if h.get("ok") and not preferred:
            preferred = {
                "provider": h.get("provider"),
                "model": h.get("preferred_model"),
                "base_url": h.get("base_url"),
            }
            any_ok = True
        elif h.get("ok"):
            any_ok = True
    # Back-compat fields used by existing desktop UI / workflow.generate
    ollama = next((p for p in providers if p.get("provider") == "ollama"), {})
    return {
        "ok": any_ok,
        "provider": (preferred or {}).get("provider") or "none",
        "preferred_model": (preferred or {}).get("model") or ollama.get("preferred_model"),
        "models": ollama.get("models") or [],
        "model_count": ollama.get("model_count") or 0,
        "base_url": ollama.get("base_url"),
        "digests": ollama.get("digests") or {},
        "providers": providers,
        "error": None if any_ok else "No validated LLM provider available",
    }
