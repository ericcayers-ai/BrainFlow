from __future__ import annotations

from typing import Any

from brainflow_worker.gateway.hardware import profile_hardware
from brainflow_worker.gateway.pins import resolve_for_run
from brainflow_worker.gateway.providers import aggregate_health
from brainflow_worker.gateway.recommend import build_recommendation
from brainflow_worker.gateway.registry import load_registry
from brainflow_worker.gateway.scoring import score_candidates
from brainflow_worker.gateway.types import CapabilityRequirements, ScoredCandidate, SelectionPolicy


def select_models(
    *,
    policy: str = "auto",
    requirements: dict[str, Any] | None = None,
    pinned: dict[str, dict[str, Any]] | None = None,
    run_active: bool = False,
    allow_auto_reselect: bool = False,
    single_model_only: bool = False,
    refresh_registry: bool = False,
) -> dict[str, Any]:
    """
    Auto selection pipeline (MODEL_SELECTION.md):
    hardware → registry → capability gates → fit → rank → recommendation card → pins.
    Never silently swaps mid-run.
    """
    try:
        pol = SelectionPolicy(policy)
    except ValueError:
        pol = SelectionPolicy.AUTO

    req_raw = requirements or {}
    req = CapabilityRequirements(
        modalities=list(req_raw.get("modalities") or ["text"]),
        tools=bool(req_raw.get("tools", False)),
        json_schema=bool(req_raw.get("json_schema", True)),
        embeddings=bool(req_raw.get("embeddings", False)),
        vision=bool(req_raw.get("vision", False)),
        min_context=int(req_raw.get("min_context") or 4096),
    )
    if req.vision and "vision" not in req.modalities:
        req.modalities.append("vision")

    hardware = profile_hardware()
    health = aggregate_health()
    registry = load_registry(refresh=refresh_registry)
    manifest = registry.get("manifest") or {}
    models = [dict(m) for m in (manifest.get("models") or [])]

    installed = set(health.get("models") or [])
    digests_local = health.get("digests") or {}
    for m in models:
        runtime = m.get("runtime_name") or m.get("id")
        if runtime in installed:
            m["preferred_provider"] = "ollama"
            if digests_local.get(runtime):
                digs = list(m.get("digests") or [])
                if digests_local[runtime] not in digs:
                    digs.insert(0, digests_local[runtime])
                m["digests"] = digs

    scored = score_candidates(
        models,
        hardware=hardware,
        requirements=req,
        policy=pol if pol != SelectionPolicy.PINNED else SelectionPolicy.AUTO,
    )
    eligible = [c for c in scored if not c.rejected]

    winners: dict[str, ScoredCandidate] = {}
    if pol == SelectionPolicy.PINNED and pinned:
        for role, ref in pinned.items():
            match = next(
                (
                    c
                    for c in scored
                    if c.name == ref.get("name") or c.digest == ref.get("digest")
                ),
                None,
            )
            if match:
                winners[role] = match
            else:
                winners[role] = ScoredCandidate(
                    model_id=str(ref.get("name")),
                    display_name=str(ref.get("name")),
                    provider=str(ref.get("provider") or "ollama"),
                    name=str(ref.get("name")),
                    digest=str(ref.get("digest") or "unknown"),
                    score=1.0,
                    quality=1.0,
                    fit=1.0,
                    context_fit=1.0,
                    capability=1.0,
                    reasons_won=["pinned by user/workflow"],
                    license=None,
                )
    elif eligible:
        planner = eligible[0]
        winners["planner"] = planner
        if not single_model_only:
            vision = next((c for c in eligible if "vision" in c.modalities), None)
            emb = next((c for c in eligible if c.capabilities.get("embeddings")), None)
            if (req.vision or vision) and vision and vision.model_id != planner.model_id:
                winners["multimodal"] = vision
            if emb and emb.model_id != planner.model_id:
                if req.embeddings or not single_model_only:
                    winners["embeddings"] = emb

    card = build_recommendation(
        policy=pol.value,
        hardware=hardware,
        scored=scored,
        winners=winners,
        registry_digest=registry.get("digest"),
        portfolio=not single_model_only and len(winners) > 1,
    )

    recommended_pins = card.pins
    pin_resolution = resolve_for_run(
        policy=pol.value,
        pinned=pinned,
        recommended=recommended_pins,
        allow_auto_reselect=allow_auto_reselect,
        run_active=run_active,
    )

    ok = bool(pin_resolution.get("pins"))
    if req.vision:
        pins = pin_resolution.get("pins") or {}
        planner_cand = winners.get("planner")
        planner_vision = bool(planner_cand and "vision" in planner_cand.modalities)
        if "multimodal" not in pins and not planner_vision:
            ok = False

    if pol == SelectionPolicy.PINNED and pinned:
        ok = True

    error = None
    if not ok:
        if req.vision:
            error = "Vision workflow requires a vision-capable model (selection error, not silent text-only)"
        elif not eligible:
            error = "No model satisfied capability + fit gates"
        else:
            error = "Selection failed"

    return {
        "ok": ok,
        "policy": pol.value,
        "health": health,
        "hardware": hardware,
        "registry": {
            "ok": registry.get("ok"),
            "digest": registry.get("digest"),
            "path": registry.get("path"),
            "verify": registry.get("verify"),
        },
        "recommendation": card.to_dict(),
        "pin_resolution": pin_resolution,
        "eligible_count": len(eligible),
        "error": error,
    }
