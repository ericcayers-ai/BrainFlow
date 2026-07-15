from __future__ import annotations

from typing import Any

from brainflow_worker.gateway.hardware import fit_budget_mb
from brainflow_worker.gateway.types import (
    POLICY_WEIGHTS,
    CapabilityRequirements,
    ScoredCandidate,
    SelectionPolicy,
)


def score_candidates(
    models: list[dict[str, Any]],
    *,
    hardware: dict[str, Any],
    requirements: CapabilityRequirements,
    policy: SelectionPolicy,
    local_providers: set[str] | None = None,
) -> list[ScoredCandidate]:
    weights = POLICY_WEIGHTS[policy]
    budget = fit_budget_mb(hardware)
    local_providers = local_providers or {"ollama", "openai_compat"}
    scored: list[ScoredCandidate] = []

    for m in models:
        reasons: list[str] = []
        reject: list[str] = []
        caps = m.get("capabilities") or {}
        modalities = list(m.get("modalities") or [])
        ctxs = m.get("context_lengths") or [4096]
        max_ctx = max(int(c) for c in ctxs) if ctxs else 0
        quality = _best_quality(m)
        mem = _estimate_memory_mb(m, target_ctx=requirements.min_context)
        digests = m.get("digests") or []
        digest = digests[0] if digests else f"registry:{m.get('id')}"
        provider = str(m.get("preferred_provider") or m.get("source") or "ollama")
        name = str(m.get("runtime_name") or m.get("display_name") or m.get("id"))

        # Capability gates
        if requirements.vision or "vision" in requirements.modalities:
            if "vision" not in modalities:
                reject.append("missing vision modality")
        if requirements.tools and not caps.get("tools"):
            reject.append("tools required")
        if requirements.json_schema and not caps.get("json_schema", True):
            reject.append("json_schema required")
        if requirements.embeddings and not caps.get("embeddings"):
            reject.append("embeddings required")
        if max_ctx < requirements.min_context:
            reject.append(f"context {max_ctx} < required {requirements.min_context}")
        if m.get("remote_code_required"):
            reject.append("remote_code_required not eligible by default")
        if policy == SelectionPolicy.MAXIMUM_PRIVACY and provider not in local_providers:
            reject.append("cloud provider blocked by Maximum Privacy policy")

        # Fit
        fit = 1.0
        if mem is not None:
            if mem > budget:
                reject.append(f"fit fail: needs ~{mem:.0f}MB > budget {budget:.0f}MB")
                fit = 0.0
            else:
                fit = max(0.0, min(1.0, 1.0 - (mem / budget) * 0.5))
                if mem > budget * 0.9:
                    reject.append("barely allocates (safety margin)")
                    fit = 0.0

        context_fit = 0.0 if max_ctx <= 0 else min(1.0, max_ctx / max(requirements.min_context, 1))
        capability = 1.0 if not reject else 0.0
        reliability = float((m.get("eval_reliability") if m.get("eval_reliability") is not None else 0.7))
        perf = float(m.get("performance_floor") if m.get("performance_floor") is not None else 0.6)
        quant_penalty = float(m.get("quant_penalty") or 0.0)
        disk = float(m.get("download_size_mb") or 0.0)
        disk_pressure = min(1.0, disk / 20000.0) if disk else 0.0
        license_ok = 1.0 if m.get("license") not in {None, "unknown-proprietary"} else 0.4

        score = (
            weights.get("w_q", 0) * quality
            + weights.get("w_c", 0) * context_fit
            + weights.get("w_r", 0) * reliability
            + weights.get("w_p", 0) * perf
            + weights.get("w_f", 0) * fit
            - weights.get("w_z", 0) * quant_penalty
            - weights.get("w_d", 0) * disk_pressure
            + 0.05 * license_ok
        )
        if policy == SelectionPolicy.MAXIMUM_PRIVACY and provider in local_providers:
            score += 0.15
            reasons.append("local provider privacy bonus")
        if policy == SelectionPolicy.LOW_LATENCY:
            # Prefer smaller quants / higher perf floor already weighted.
            reasons.append("low-latency weights applied")

        rejected = bool(reject)
        if not rejected:
            reasons.append(f"quality={quality:.2f}")
            reasons.append(f"fit={fit:.2f} (~{mem:.0f}MB)" if mem else "fit=unknown")
            reasons.append(f"context={max_ctx}")

        scored.append(
            ScoredCandidate(
                model_id=str(m.get("id")),
                display_name=str(m.get("display_name") or m.get("id")),
                provider=provider,
                name=name,
                digest=str(digest),
                score=0.0 if rejected else float(score),
                quality=quality,
                fit=fit,
                context_fit=context_fit,
                capability=capability,
                rejected=rejected,
                reject_reasons=reject,
                reasons_won=reasons,
                expected_memory_mb=mem,
                context_length=max_ctx or None,
                license=m.get("license"),
                download_size_mb=m.get("download_size_mb"),
                quant=(m.get("quantizations") or [None])[0],
                modalities=modalities,
                capabilities={k: bool(v) for k, v in caps.items()},
            )
        )

    scored.sort(key=lambda c: (not c.rejected, c.score), reverse=True)
    return scored


def _best_quality(m: dict[str, Any]) -> float:
    scores = m.get("quality_scores") or []
    vals = []
    for s in scores:
        if isinstance(s, dict) and s.get("value") is not None:
            vals.append(float(s["value"]))
    if vals:
        return max(vals)
    return float(m.get("quality") or 0.5)


def _estimate_memory_mb(m: dict[str, Any], *, target_ctx: int) -> float | None:
    formula = m.get("memory_formula") or {}
    params = formula.get("params") or {}
    weights = params.get("weights_mb")
    if weights is None and m.get("download_size_mb") is not None:
        weights = float(m["download_size_mb"])
    if weights is None and m.get("parameter_count"):
        # Rough Q4 heuristic: ~0.55 bytes/param
        weights = float(m["parameter_count"]) * 0.55 / (1024 * 1024)
    if weights is None:
        return None
    kv_per_k = float(params.get("kv_mb_per_1k_ctx") or 8.0)
    overhead = float(params.get("runtime_overhead_mb") or 512.0)
    kv = kv_per_k * (target_ctx / 1000.0)
    return float(weights) + kv + overhead
