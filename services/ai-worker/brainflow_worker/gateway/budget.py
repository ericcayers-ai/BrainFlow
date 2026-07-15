"""Per-provider / per-run token and spend limits on the LLM request path."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class BudgetExceeded(RuntimeError):
    """Raised when a chat/embed request would violate or has violated a budget."""


@dataclass
class RequestBudget:
    """Mutable spend/token tracker. Fail-closed when limits would be exceeded."""

    max_tokens: int | None = None
    max_spend_usd: float | None = None
    max_requests: int | None = None
    tokens_used: int = 0
    spend_usd: float = 0.0
    requests_used: int = 0
    label: str = "default"
    history: list[dict[str, Any]] = field(default_factory=list)

    def remaining_tokens(self) -> int | None:
        if self.max_tokens is None:
            return None
        return max(0, int(self.max_tokens) - int(self.tokens_used))

    def check_before_request(self, *, planned_max_tokens: int | None = None) -> None:
        if self.max_requests is not None and self.requests_used >= self.max_requests:
            raise BudgetExceeded(
                f"budget[{self.label}] max_requests={self.max_requests} exhausted"
            )
        if self.max_spend_usd is not None and self.spend_usd >= self.max_spend_usd:
            raise BudgetExceeded(
                f"budget[{self.label}] max_spend_usd={self.max_spend_usd} exhausted"
            )
        rem = self.remaining_tokens()
        if rem is not None and rem <= 0:
            raise BudgetExceeded(
                f"budget[{self.label}] max_tokens={self.max_tokens} exhausted"
            )
        if rem is not None and planned_max_tokens is not None and planned_max_tokens > rem:
            raise BudgetExceeded(
                f"budget[{self.label}] planned_max_tokens={planned_max_tokens} > remaining={rem}"
            )

    def clamp_max_tokens(self, requested: int | None, *, default: int = 1024) -> int:
        """Return max_tokens for the outbound request, clamped to remaining budget."""
        base = int(requested if requested is not None else default)
        rem = self.remaining_tokens()
        if rem is None:
            return max(1, base)
        if rem <= 0:
            raise BudgetExceeded(
                f"budget[{self.label}] max_tokens={self.max_tokens} exhausted"
            )
        return max(1, min(base, rem))

    def record_usage(
        self,
        *,
        tokens: int = 0,
        spend_usd: float = 0.0,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.tokens_used += max(0, int(tokens))
        self.spend_usd += max(0.0, float(spend_usd))
        self.requests_used += 1
        self.history.append(
            {
                "tokens": int(tokens),
                "spend_usd": float(spend_usd),
                **(meta or {}),
            }
        )
        if self.max_tokens is not None and self.tokens_used > self.max_tokens:
            raise BudgetExceeded(
                f"budget[{self.label}] max_tokens exceeded after request "
                f"({self.tokens_used}/{self.max_tokens})"
            )
        if self.max_spend_usd is not None and self.spend_usd > self.max_spend_usd:
            raise BudgetExceeded(
                f"budget[{self.label}] max_spend_usd exceeded after request "
                f"({self.spend_usd}/{self.max_spend_usd})"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "max_tokens": self.max_tokens,
            "max_spend_usd": self.max_spend_usd,
            "max_requests": self.max_requests,
            "tokens_used": self.tokens_used,
            "spend_usd": self.spend_usd,
            "requests_used": self.requests_used,
            "remaining_tokens": self.remaining_tokens(),
        }


def budget_from_workflow(workflow: dict[str, Any], *, label: str = "workflow") -> RequestBudget:
    budgets = workflow.get("budgets") or {}
    return RequestBudget(
        max_tokens=_optional_int(budgets.get("max_tokens")),
        max_spend_usd=_optional_float(budgets.get("max_cost_usd") or budgets.get("max_spend_usd")),
        max_requests=_optional_int(budgets.get("max_llm_requests")),
        label=label,
    )


def budget_from_params(params: dict[str, Any] | None, *, label: str = "request") -> RequestBudget | None:
    """Optional budget from RPC/chat kwargs. Returns None when unset."""
    if not params:
        return None
    if not any(k in params for k in ("max_tokens", "max_spend_usd", "max_cost_usd", "max_llm_requests")):
        # Nested budget object
        nested = params.get("budget")
        if isinstance(nested, dict):
            return RequestBudget(
                max_tokens=_optional_int(nested.get("max_tokens")),
                max_spend_usd=_optional_float(nested.get("max_spend_usd") or nested.get("max_cost_usd")),
                max_requests=_optional_int(nested.get("max_llm_requests") or nested.get("max_requests")),
                label=str(nested.get("label") or label),
            )
        return None
    return RequestBudget(
        max_tokens=_optional_int(params.get("max_tokens_budget") or params.get("budget_max_tokens")),
        max_spend_usd=_optional_float(params.get("max_spend_usd") or params.get("max_cost_usd")),
        max_requests=_optional_int(params.get("max_llm_requests")),
        label=label,
    )


def extract_usage_tokens(raw: dict[str, Any]) -> int:
    """Best-effort token count from provider response envelopes."""
    usage = raw.get("usage") or {}
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if total is not None:
            return int(total)
        parts = [
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        ]
        nums = [int(p) for p in parts if p is not None]
        if nums:
            return sum(nums)
    meta = raw.get("usageMetadata") or {}
    if isinstance(meta, dict):
        total = meta.get("totalTokenCount")
        if total is not None:
            return int(total)
        parts = [meta.get("promptTokenCount"), meta.get("candidatesTokenCount")]
        nums = [int(p) for p in parts if p is not None]
        if nums:
            return sum(nums)
    # Ollama eval counts
    if raw.get("eval_count") is not None or raw.get("prompt_eval_count") is not None:
        return int(raw.get("eval_count") or 0) + int(raw.get("prompt_eval_count") or 0)
    return 0


def _optional_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    return int(v)


def _optional_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    return float(v)
