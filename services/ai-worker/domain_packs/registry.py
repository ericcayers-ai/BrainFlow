"""Domain pack registry — packs are data (schemas/rubrics/templates), not free prompts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PACKS_ROOT = Path(__file__).resolve().parent

INITIAL_PACK_IDS = ("study_prep", "research_synthesis", "project_planning")


@lru_cache(maxsize=1)
def list_packs() -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    for path in sorted(PACKS_ROOT.glob("*/pack.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        packs.append(doc)
    return packs


def get_pack(pack_id: str) -> dict[str, Any] | None:
    """Resolve pack_id or pack_id@version."""
    base = pack_id.split("@", 1)[0]
    for pack in list_packs():
        if pack.get("id") == base:
            return pack
    return None


def pack_ref(pack: dict[str, Any]) -> str:
    return f"{pack['id']}@{pack.get('version', '0.0.0')}"


def route_pack(goal_prompt: str, source_excerpt: str = "") -> dict[str, Any]:
    """Deterministic keyword router; LLM goal-router may override later."""
    text = f"{goal_prompt}\n{source_excerpt}".lower()
    scores = {
        "study_prep": 0,
        "research_synthesis": 0,
        "project_planning": 0,
    }
    for kw in ("study", "flashcard", "exam", "lecture", "quiz", "learn"):
        if kw in text:
            scores["study_prep"] += 2
    for kw in ("research", "literature", "paper", "evidence", "synthesize", "claim"):
        if kw in text:
            scores["research_synthesis"] += 2
    for kw in ("project", "milestone", "roadmap", "plan", "deadline", "sprint", "deliverable"):
        if kw in text:
            scores["project_planning"] += 2
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = "study_prep"
    pack = get_pack(best)
    assert pack is not None
    return {
        "pack": pack,
        "pack_ref": pack_ref(pack),
        "confidence": min(1.0, 0.35 + 0.15 * scores[best]),
        "scores": scores,
        "needs_user_choice": scores[best] < 2
        or sorted(scores.values(), reverse=True)[0] == sorted(scores.values(), reverse=True)[1],
    }
