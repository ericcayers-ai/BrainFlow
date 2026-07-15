from __future__ import annotations

from typing import Any

from brainflow_worker.gateway.types import RecommendationCard, ScoredCandidate


def build_recommendation(
    *,
    policy: str,
    hardware: dict[str, Any],
    scored: list[ScoredCandidate],
    winners: dict[str, ScoredCandidate],
    registry_digest: str | None,
    portfolio: bool,
) -> RecommendationCard:
    winner_dicts = {
        role: {
            "model_id": c.model_id,
            "display_name": c.display_name,
            "provider": c.provider,
            "name": c.name,
            "digest": c.digest,
            "score": round(c.score, 4),
            "quality": round(c.quality, 4),
            "fit": round(c.fit, 4),
            "context_length": c.context_length,
            "expected_memory_mb": c.expected_memory_mb,
            "license": c.license,
            "download_size_mb": c.download_size_mb,
            "quant": c.quant,
            "why": c.reasons_won,
            "modalities": c.modalities,
            "capabilities": c.capabilities,
        }
        for role, c in winners.items()
    }
    alts = [
        {
            "model_id": c.model_id,
            "display_name": c.display_name,
            "digest": c.digest,
            "score": round(c.score, 4),
            "provider": c.provider,
            "name": c.name,
            "license": c.license,
        }
        for c in scored
        if not c.rejected and c.model_id not in {w.model_id for w in winners.values()}
    ][:5]
    rejected = [
        {
            "model_id": c.model_id,
            "display_name": c.display_name,
            "reasons": c.reject_reasons,
        }
        for c in scored
        if c.rejected
    ]
    pins = {
        role: {"provider": c.provider, "name": c.name, "digest": c.digest}
        for role, c in winners.items()
    }
    parts = [f"Policy={policy}."]
    for role, c in winners.items():
        digest = c.digest
        shown = f"{digest[:24]}…" if len(digest) > 24 else digest
        parts.append(f"{role}: {c.display_name} (digest {shown}, score {c.score:.3f})")
    if not winners:
        parts.append("No eligible model — fail-closed.")

    return RecommendationCard(
        policy=policy,
        hardware_summary={
            "arch": hardware.get("arch"),
            "ram_gb": (hardware.get("ram") or {}).get("total_gb"),
            "gpu": [
                {"name": g.get("name"), "vram_mb": g.get("vram_total_mb"), "vendor": g.get("vendor")}
                for g in (hardware.get("gpu") or [])
            ],
            "disk_free_gb": (hardware.get("disk") or {}).get("free_gb"),
        },
        winners=winner_dicts,
        alternatives=alts,
        rejected=rejected,
        portfolio=portfolio,
        explanation=" ".join(parts),
        registry_digest=registry_digest,
        pins=pins,
    )
