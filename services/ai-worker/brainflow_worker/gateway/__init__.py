"""Capability-oriented LLM gateway (model intelligence).

Provider-specific calls live here only. See docs/MODEL_SELECTION.md.
"""

from brainflow_worker.gateway.hardware import profile_hardware
from brainflow_worker.gateway.recommend import build_recommendation
from brainflow_worker.gateway.registry import (
    load_registry,
    registry_cache_dir,
    rollback_registry,
    verify_manifest,
)
from brainflow_worker.gateway.select import select_models
from brainflow_worker.gateway.types import RecommendationCard, SelectionPolicy

__all__ = [
    "RecommendationCard",
    "SelectionPolicy",
    "build_recommendation",
    "load_registry",
    "profile_hardware",
    "registry_cache_dir",
    "rollback_registry",
    "select_models",
    "verify_manifest",
]
