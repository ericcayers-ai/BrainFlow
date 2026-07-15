from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SelectionPolicy(str, Enum):
    AUTO = "auto"
    BALANCED = "balanced"
    MAXIMUM_QUALITY = "maximum_quality"
    MAXIMUM_PRIVACY = "maximum_privacy"
    LOW_LATENCY = "low_latency"
    PINNED = "pinned"


@dataclass
class ModelRef:
    provider: str
    name: str
    digest: str | None = None
    role: str = "planner"

    def to_pin(self) -> dict[str, Any]:
        out: dict[str, Any] = {"provider": self.provider, "name": self.name}
        if self.digest:
            out["digest"] = self.digest
        return out


@dataclass
class CapabilityRequirements:
    modalities: list[str] = field(default_factory=lambda: ["text"])
    tools: bool = False
    json_schema: bool = True
    embeddings: bool = False
    vision: bool = False
    min_context: int = 4096


@dataclass
class ScoredCandidate:
    model_id: str
    display_name: str
    provider: str
    name: str
    digest: str
    score: float
    quality: float
    fit: float
    context_fit: float
    capability: float
    rejected: bool = False
    reject_reasons: list[str] = field(default_factory=list)
    reasons_won: list[str] = field(default_factory=list)
    expected_memory_mb: float | None = None
    context_length: int | None = None
    license: str | None = None
    download_size_mb: float | None = None
    quant: str | None = None
    modalities: list[str] = field(default_factory=list)
    capabilities: dict[str, bool] = field(default_factory=dict)


@dataclass
class RecommendationCard:
    policy: str
    hardware_summary: dict[str, Any]
    winners: dict[str, dict[str, Any]]
    alternatives: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    portfolio: bool
    explanation: str
    registry_digest: str | None = None
    pins: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


POLICY_WEIGHTS: dict[SelectionPolicy, dict[str, float]] = {
    SelectionPolicy.AUTO: {
        "w_q": 0.40,
        "w_c": 0.15,
        "w_r": 0.15,
        "w_p": 0.10,
        "w_f": 0.15,
        "w_z": 0.03,
        "w_d": 0.02,
    },
    SelectionPolicy.BALANCED: {
        "w_q": 0.30,
        "w_c": 0.15,
        "w_r": 0.15,
        "w_p": 0.20,
        "w_f": 0.15,
        "w_z": 0.03,
        "w_d": 0.02,
    },
    SelectionPolicy.MAXIMUM_QUALITY: {
        "w_q": 0.55,
        "w_c": 0.15,
        "w_r": 0.15,
        "w_p": 0.05,
        "w_f": 0.08,
        "w_z": 0.01,
        "w_d": 0.01,
    },
    SelectionPolicy.MAXIMUM_PRIVACY: {
        "w_q": 0.25,
        "w_c": 0.10,
        "w_r": 0.10,
        "w_p": 0.10,
        "w_f": 0.20,
        "w_z": 0.05,
        "w_d": 0.05,
        # privacy bonus applied separately for local providers
    },
    SelectionPolicy.LOW_LATENCY: {
        "w_q": 0.20,
        "w_c": 0.10,
        "w_r": 0.10,
        "w_p": 0.40,
        "w_f": 0.15,
        "w_z": 0.03,
        "w_d": 0.02,
    },
    SelectionPolicy.PINNED: {
        # Pin policy does not re-rank; scoring unused when pins present.
        "w_q": 1.0,
        "w_c": 0.0,
        "w_r": 0.0,
        "w_p": 0.0,
        "w_f": 0.0,
        "w_z": 0.0,
        "w_d": 0.0,
    },
}
