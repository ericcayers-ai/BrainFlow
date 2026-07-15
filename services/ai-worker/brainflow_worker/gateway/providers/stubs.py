"""Legacy stub constructors — re-export real adapters for backward compatibility.

Prefer importing AnthropicAdapter / GeminiAdapter / OpenRouterAdapter / CustomOpenAICompatAdapter
directly. These helpers keep older call sites working.
"""

from __future__ import annotations

from brainflow_worker.gateway.providers.anthropic import AnthropicAdapter
from brainflow_worker.gateway.providers.gemini import GeminiAdapter
from brainflow_worker.gateway.providers.openrouter import (
    CustomOpenAICompatAdapter,
    OpenRouterAdapter,
    custom_from_env,
)


def anthropic_stub() -> AnthropicAdapter:
    return AnthropicAdapter()


def gemini_stub() -> GeminiAdapter:
    return GeminiAdapter()


def openrouter_stub() -> OpenRouterAdapter:
    return OpenRouterAdapter()


def custom_stub(*, provider_id: str = "custom", base_url_hint: str = "") -> CustomOpenAICompatAdapter:
    """Custom endpoint. Without base_url, health fails closed with setup guidance."""
    base = base_url_hint or "https://127.0.0.1:0/v1"
    return CustomOpenAICompatAdapter(
        base_url=base,
        provider_id=provider_id,
        api_key_ref=f"custom:{provider_id}",
        require_tls=False if "127.0.0.1" in base or "localhost" in base else True,
    )


__all__ = [
    "anthropic_stub",
    "custom_from_env",
    "custom_stub",
    "gemini_stub",
    "openrouter_stub",
]
