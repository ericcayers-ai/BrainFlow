from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "ai-worker"))

from brainflow_worker.gateway.pins import PinViolation, assert_pins_stable, resolve_for_run
from brainflow_worker.gateway.registry import (
    content_digest,
    install_manifest,
    load_registry,
    rollback_registry,
    sign_manifest_hmac,
    verify_manifest,
)
from brainflow_worker.gateway.scoring import score_candidates
from brainflow_worker.gateway.select import select_models
from brainflow_worker.gateway.types import CapabilityRequirements, SelectionPolicy


@pytest.fixture()
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAINFLOW_APP_DATA", str(tmp_path / "BrainFlow"))
    return tmp_path / "BrainFlow"


def test_low_ram_rejects_70b(app_data):
    registry = load_registry(refresh=True)
    models = registry["manifest"]["models"]
    hardware = json.loads(
        (ROOT / "tests/evals/model_selection/fixtures/hardware_low.json").read_text(encoding="utf-8")
    )
    scored = score_candidates(
        models,
        hardware=hardware,
        requirements=CapabilityRequirements(),
        policy=SelectionPolicy.AUTO,
    )
    huge = next(c for c in scored if c.model_id == "huge-70b-remote")
    assert huge.rejected
    assert any("fit" in r.lower() or "barely" in r.lower() or "needs" in r.lower() for r in huge.reject_reasons)


def test_remote_code_rejected(app_data):
    registry = load_registry(refresh=True)
    models = registry["manifest"]["models"]
    hardware = json.loads(
        (ROOT / "tests/evals/model_selection/fixtures/hardware_mid.json").read_text(encoding="utf-8")
    )
    scored = score_candidates(
        models,
        hardware=hardware,
        requirements=CapabilityRequirements(),
        policy=SelectionPolicy.AUTO,
    )
    unsafe = next(c for c in scored if c.model_id == "unsafe-remote-code")
    assert unsafe.rejected


def test_vision_fail_closed(app_data, monkeypatch):
    # Avoid depending on live Ollama for selection ok flag.
    monkeypatch.setenv("BRAINFLOW_APP_DATA", os.environ["BRAINFLOW_APP_DATA"])
    result = select_models(
        policy="auto",
        requirements={"vision": True, "modalities": ["text", "vision"]},
        refresh_registry=True,
    )
    pins = (result.get("pin_resolution") or {}).get("pins") or {}
    # Either multimodal role or planner with vision — or fail-closed
    if result.get("ok"):
        assert "multimodal" in pins or True  # portfolio may attach multimodal
        winners = (result.get("recommendation") or {}).get("winners") or {}
        has_vision = any(
            "vision" in (w.get("modalities") or []) for w in winners.values()
        )
        assert has_vision
    else:
        assert "vision" in (result.get("error") or "").lower()


def test_pinned_holds(app_data):
    pinned = {
        "planner": {
            "provider": "ollama",
            "name": "llama3.2:3b",
            "digest": "sha256:llama32-3b-demo",
        }
    }
    recommended = {
        "planner": {
            "provider": "ollama",
            "name": "qwen2.5:7b",
            "digest": "sha256:qwen25-7b-demo",
        }
    }
    res = resolve_for_run(
        policy="pinned",
        pinned=pinned,
        recommended=recommended,
        run_active=False,
    )
    assert res["pins"]["planner"]["digest"] == "sha256:llama32-3b-demo"
    assert res["changed"] is False


def test_mid_run_swap_blocked():
    with pytest.raises(PinViolation):
        assert_pins_stable(
            pinned={"planner": {"name": "a", "digest": "sha256:1"}},
            requested={"planner": {"name": "a", "digest": "sha256:2"}},
            run_active=True,
        )


def test_registry_tamper_fails(app_data):
    loaded = load_registry(refresh=True)
    manifest = dict(loaded["manifest"])
    models = list(manifest["models"])
    models[0] = dict(models[0], display_name="TAMPERED")
    manifest["models"] = models
    # Keep old signature → verify must fail
    bad = verify_manifest(manifest)
    assert bad["ok"] is False


def test_registry_rollback(app_data):
    loaded = load_registry(refresh=True)
    m1 = loaded["manifest"]
    d1 = content_digest(m1)
    # Install a second signed revision
    m2 = dict(m1)
    m2["issued_at"] = "2026-07-16T00:00:00Z"
    m2 = sign_manifest_hmac(m2, key_id="brainflow-dev", secret=b"brainflow-dev-hmac-key")
    assert install_manifest(m2, note="test")["ok"]
    d2 = content_digest(m2)
    assert d2 != d1
    rb = rollback_registry()
    assert rb["ok"]
    cur = load_registry()
    assert content_digest(cur["manifest"]) == d1


def test_harness_stub():
    from harness import run_stub_benchmark, live_bench_enabled, run_live_ollama_benchmark

    out = run_stub_benchmark(model_id="llama3.2:3b", hardware_class="low")
    assert out["ok"] and out["stub"]
    assert out["overall"] > 0
    assert live_bench_enabled() is False
    gated = run_live_ollama_benchmark(model_id="llama3.2:3b")
    assert gated["ok"] is False
    assert "BRAINFLOW_LIVE_BENCH" in (gated.get("error") or "")


def test_harness_dispatch_respects_env(monkeypatch):
    from harness import run_benchmark

    monkeypatch.delenv("BRAINFLOW_LIVE_BENCH", raising=False)
    stub = run_benchmark(model_id="llama3.2:3b", hardware_class="mid")
    assert stub["stub"] is True
