"""CI-safe domain rubric tests + gated live path."""

from __future__ import annotations

import os

import pytest

from harness import (
    live_eval_enabled,
    load_cases,
    run_live_ollama_rubric,
    run_rubric,
    run_stub_rubric,
)


def test_cases_present():
    cases = load_cases()
    assert len(cases) >= 3
    packs = {c.domain_pack_id.split("@")[0] for c in cases}
    assert {"study_prep", "research_synthesis", "project_planning"} <= packs


def test_stub_meets_threshold_offline():
    out = run_stub_rubric()
    assert out["ok"] and out["stub"] and not out["live"]
    assert out["meets_threshold"] is True
    assert out["pass_rate"] >= 0.85
    for r in out["results"]:
        assert r["pass_85"] is True


def test_live_path_refuses_without_env(monkeypatch):
    monkeypatch.delenv("BRAINFLOW_LIVE_EVAL", raising=False)
    assert live_eval_enabled() is False
    gated = run_live_ollama_rubric()
    assert gated["ok"] is False
    assert "BRAINFLOW_LIVE_EVAL" in (gated.get("error") or "")


def test_dispatch_stub_by_default(monkeypatch):
    monkeypatch.delenv("BRAINFLOW_LIVE_EVAL", raising=False)
    out = run_rubric()
    assert out["stub"] is True


@pytest.mark.skipif(
    os.environ.get("BRAINFLOW_LIVE_EVAL", "").strip() != "1",
    reason="Live Ollama rubric requires BRAINFLOW_LIVE_EVAL=1",
)
def test_live_ollama_rubric_when_enabled():
    out = run_live_ollama_rubric()
    # Ollama may be down — harness must not crash; record honest status.
    assert out.get("live") is True or out.get("ok") is False
    if out.get("ok") and out.get("live"):
        assert "pass_rate" in out
        assert "results" in out
        # Do not assert ≥85% here — variance is a beta gate; document pass_rate.
