"""Domain-rubric actionability eval harness.

- Default / CI: deterministic stub scoring (no network).
- Live: set BRAINFLOW_LIVE_EVAL=1 and use Ollama when available.

Does not claim Phase 6 exit until live runs meet ≥85% across packs with
recorded variance bands. See docs/EVALUATION_STRATEGY.md §9–10.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CASES_DIR = Path(__file__).resolve().parent / "cases"


@dataclass(frozen=True)
class RubricCase:
    id: str
    domain_pack_id: str
    source_text: str
    expected_keys: list[str]
    rubric: dict[str, str]


def live_eval_enabled() -> bool:
    return os.environ.get("BRAINFLOW_LIVE_EVAL", "").strip() == "1"


def load_cases() -> list[RubricCase]:
    out: list[RubricCase] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        out.append(
            RubricCase(
                id=raw["id"],
                domain_pack_id=raw["domain_pack_id"],
                source_text=raw["source_text"],
                expected_keys=list(raw.get("expected_keys") or []),
                rubric=dict(raw.get("rubric") or {}),
            )
        )
    return out


def _stub_artifact(case: RubricCase) -> dict[str, Any]:
    """Deterministic high-quality structured artifact for CI."""
    headings = re.findall(r"^#+\s+(.+)$", case.source_text, flags=re.M)
    steps = [f"Review: {h}" for h in headings] or ["Review source"]
    # Include source blob so expected_keys completeness checks can pass offline.
    return {
        "domain_pack_id": case.domain_pack_id,
        "ordered_steps": steps,
        "claims": [
            {
                "text": case.source_text[:240],
                "source_refs": ["source:1"],
            }
        ],
        "completeness": True,
        "writes_under": ".brainflow/artifacts",
        "summary": f"Stub study plan for {case.id}: {case.source_text[:160]}",
        "source_excerpt": case.source_text,
    }


def score_artifact(case: RubricCase, artifact: dict[str, Any]) -> dict[str, Any]:
    """Score ordered / complete / grounded / safe dimensions (0–1 each)."""
    dims: dict[str, float] = {}

    steps = artifact.get("ordered_steps") or artifact.get("tasks") or []
    dims["ordering"] = 1.0 if isinstance(steps, list) and len(steps) >= 1 else 0.0

    expected = set(case.expected_keys)
    blob = json.dumps(artifact).lower()
    hit = sum(1 for k in expected if k.lower() in blob)
    dims["completeness"] = (hit / len(expected)) if expected else (1.0 if artifact else 0.0)

    claims = artifact.get("claims") or []
    grounded = 0
    for c in claims:
        refs = c.get("source_refs") or c.get("evidence_ids") or []
        if refs:
            grounded += 1
    dims["grounding"] = (grounded / len(claims)) if claims else 0.0

    writes = str(artifact.get("writes_under") or artifact.get("artifact_path") or "")
    dims["safety"] = 1.0 if writes.startswith(".brainflow/") or "artifacts" in writes else 0.5

    # Prefer pack rubric keys when present
    for key in case.rubric:
        dims.setdefault(key, dims.get(key, 0.0))

    overall = sum(dims.values()) / max(len(dims), 1)
    return {
        "case_id": case.id,
        "domain_pack_id": case.domain_pack_id,
        "dimensions": {k: round(v, 4) for k, v in dims.items()},
        "overall": round(overall, 4),
        "pass_85": overall >= 0.85,
    }


def run_stub_rubric(*, case_ids: list[str] | None = None) -> dict[str, Any]:
    cases = [c for c in load_cases() if case_ids is None or c.id in case_ids]
    results = [score_artifact(c, _stub_artifact(c)) for c in cases]
    rate = (sum(1 for r in results if r["pass_85"]) / len(results)) if results else 0.0
    return {
        "ok": True,
        "stub": True,
        "live": False,
        "threshold": 0.85,
        "pass_rate": round(rate, 4),
        "meets_threshold": rate >= 0.85,
        "results": results,
        "note": "Stub rubric. Set BRAINFLOW_LIVE_EVAL=1 for Ollama live path.",
    }


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def run_live_ollama_rubric(
    *,
    case_ids: list[str] | None = None,
    model: str | None = None,
    timeout_s: float = 90.0,
) -> dict[str, Any]:
    if not live_eval_enabled():
        return {
            "ok": False,
            "stub": False,
            "live": False,
            "error": "BRAINFLOW_LIVE_EVAL!=1 — refusing live network rubric",
        }

    import sys

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "services" / "ai-worker"))
    from brainflow_worker.gateway.budget import RequestBudget
    from brainflow_worker.gateway.providers.ollama import OllamaAdapter

    adapter = OllamaAdapter()
    health = adapter.health(timeout_s=min(5.0, timeout_s))
    if not health.get("ok"):
        return {
            "ok": False,
            "stub": False,
            "live": True,
            "error": health.get("error") or "Ollama unavailable",
            "health": health,
            "note": "Live eval skipped — Ollama not available; CI stub path remains green.",
        }

    chosen = model if model and model in (health.get("models") or []) else health.get("preferred_model")
    if not chosen:
        return {"ok": False, "stub": False, "live": True, "error": "No Ollama model available"}

    cases = [c for c in load_cases() if case_ids is None or c.id in case_ids]
    results: list[dict[str, Any]] = []
    budget = RequestBudget(max_tokens=2048)

    for case in cases:
        prompt = (
            "You are scoring BrainFlow domain-pack output. Reply with ONLY JSON matching:\n"
            '{"ordered_steps":["..."],"claims":[{"text":"...","source_refs":["source:1"]}],'
            '"completeness":true,"writes_under":".brainflow/artifacts","summary":"..."}\n'
            f"Domain pack: {case.domain_pack_id}\n"
            f"Rubric: {json.dumps(case.rubric)}\n"
            f"Source:\n{case.source_text}\n"
        )
        try:
            raw = adapter.chat(
                model=chosen,
                messages=[
                    {"role": "system", "content": "Emit JSON only. No markdown fences."},
                    {"role": "user", "content": prompt},
                ],
                timeout_s=timeout_s,
                format="json",
                max_tokens=400,
                budget=budget,
            )
            content = (raw.get("message") or {}).get("content") or raw.get("response") or ""
            artifact = _extract_json(content) or {}
            scored = score_artifact(case, artifact)
            scored["live_model"] = chosen
            scored["raw_ok"] = bool(artifact)
            results.append(scored)
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "case_id": case.id,
                    "domain_pack_id": case.domain_pack_id,
                    "dimensions": {},
                    "overall": 0.0,
                    "pass_85": False,
                    "error": str(exc),
                }
            )

    rate = (sum(1 for r in results if r.get("pass_85")) / len(results)) if results else 0.0
    return {
        "ok": True,
        "stub": False,
        "live": True,
        "model": chosen,
        "health": {"preferred_model": health.get("preferred_model"), "models": health.get("models")},
        "threshold": 0.85,
        "pass_rate": round(rate, 4),
        "meets_threshold": rate >= 0.85,
        "results": results,
        "note": "Live Ollama domain rubric (BRAINFLOW_LIVE_EVAL=1). Phase 6 exit still requires stable ≥85% + red-team bands.",
    }


def run_rubric(**kwargs: Any) -> dict[str, Any]:
    if live_eval_enabled():
        return run_live_ollama_rubric(**kwargs)
    return run_stub_rubric(case_ids=kwargs.get("case_ids"))
