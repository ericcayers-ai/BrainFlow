from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProviderAdapter(ABC):
    """Base provider adapter. Marketing metadata alone is never eligibility."""

    id: str
    kind: str  # local | cloud | openai_compat

    @abstractmethod
    def health(self, *, timeout_s: float = 3.0) -> dict[str, Any]:
        """Connectivity + installed/available models. Fail-closed."""

    @abstractmethod
    def list_models(self, *, timeout_s: float = 5.0) -> list[dict[str, Any]]:
        ...

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_s: float = 60.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        raise NotImplementedError(f"{self.id} chat not implemented")

    def embeddings(
        self,
        *,
        model: str,
        inputs: list[str],
        timeout_s: float = 30.0,
    ) -> dict[str, Any]:
        raise NotImplementedError(f"{self.id} embeddings not implemented")

    def capability_probe_hooks(self) -> dict[str, bool]:
        """Declare which probes this adapter can attempt."""
        return {
            "json_schema": False,
            "tools": False,
            "vision": False,
            "embeddings": False,
            "streaming": False,
            "cancellation": False,
        }
