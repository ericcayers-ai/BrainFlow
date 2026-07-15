"""Bounded workflow kernel stages (plan proposes; deterministic code decides)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

_WORKER_ROOT = Path(__file__).resolve().parents[2]
if str(_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKER_ROOT))

from domain_packs.registry import get_pack, pack_ref, route_pack  # noqa: E402
from brainflow_worker.kernel.delimit import (  # noqa: E402
    SYSTEM_POLICY_IMMUTABLE,
    build_bounded_user_message,
)
from brainflow_worker.kernel.policy_gate import validate_workflow_policy  # noqa: E402
from brainflow_worker.kernel.provenance import (  # noqa: E402
    content_hash,
    new_run_provenance,
    utc_now,
)
from brainflow_worker.validate import validate_workflow_ir  # noqa: E402


STAGES = (
    "intake_analyst",
    "goal_router",
    "domain_planner",
    "compiler",
    "schema_validate",
    "critic",
    "policy",
    "executor",
    "outcome_verifier",
)


def intake_analyst(*, source_text: str, prompt: str) -> dict[str, Any]:
    """Summarize bundle quality (deterministic stub + length heuristics; LLM can enrich later)."""
    warnings: list[str] = []
    if not source_text.strip():
        warnings.append("empty_source")
    if len(source_text) > 100_000:
        warnings.append("large_source_truncated")
    sensitive_flags: list[str] = []
    lower = source_text.lower()
    for needle, flag in (
        ("password", "possible_secret"),
        ("api_key", "possible_secret"),
        ("ssn", "possible_pii"),
    ):
        if needle in lower:
            sensitive_flags.append(flag)
    return {
        "stage": "intake_analyst",
        "summary": f"Intake of {len(source_text)} chars for goal: {prompt[:120]}",
        "quality_warnings": warnings,
        "sensitive_data_flags": sensitive_flags,
        "provenance_coverage": "partial",
        "missing_information": [] if source_text.strip() else ["source_text"],
        "untrusted": True,
    }


def goal_router(*, prompt: str, source_text: str) -> dict[str, Any]:
    routed = route_pack(prompt, source_text)
    return {
        "stage": "goal_router",
        "pack_ref": routed["pack_ref"],
        "confidence": routed["confidence"],
        "needs_user_choice": routed["needs_user_choice"],
        "scores": routed["scores"],
        "inferred_outcomes": routed["pack"].get("default_goal_hints", [])[:3],
    }


def domain_planner(*, prompt: str, pack: dict[str, Any], intake: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": "domain_planner",
        "domain_pack_id": pack_ref(pack),
        "draft": {
            "goals": [prompt],
            "constraints": ["Do not modify immutable sources", "Auto-apply only safe_overlay"],
            "success_metrics": list(pack.get("rubric", {}).keys()),
            "artifacts": list((pack.get("templates") or {}).keys()),
            "tasks": pack.get("default_goal_hints", [])[:4],
            "review_points": ["human_approve if elevated permission"],
            "estimated_resources": {"max_steps": 12, "max_parallel_jobs": 1},
        },
        "intake_ref": intake.get("summary"),
    }


def critic_review(*, workflow: dict[str, Any], intake: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    """Bounded critic: scores plan; may propose a patch (not free-form actions)."""
    nodes = workflow.get("nodes") or []
    scores = {
        "completeness": 0.7 if len(nodes) >= 2 else 0.4,
        "ordering": 0.8 if workflow.get("edges") else 0.5,
        "feasibility": 0.75,
        "domain_fit": 0.8 if workflow.get("domain_pack_id", "").startswith(pack.get("id", "")) else 0.5,
        "source_grounding": 0.6 if not intake.get("quality_warnings") else 0.45,
        "risk": 0.3 if intake.get("sensitive_data_flags") else 0.15,
    }
    patch: list[dict[str, Any]] = []
    has_verify = any(str(n.get("type")) == "verify" for n in nodes if isinstance(n, dict))
    if not has_verify and nodes:
        last = nodes[-1]
        patch.append(
            {
                "op": "add",
                "path": "/nodes/-",
                "value": {
                    "id": str(uuid4()),
                    "type": "verify",
                    "title": "Outcome verifier",
                    "permission_class": "read",
                },
            }
        )
        if isinstance(last, dict) and last.get("id"):
            patch.append(
                {
                    "op": "add",
                    "path": "/edges/-",
                    "value": {
                        "id": str(uuid4()),
                        "from": f"{last['id']}:out",
                        "to": "PENDING_VERIFY:in",
                        "kind": "control",
                    },
                }
            )
    return {
        "stage": "critic",
        "scores": scores,
        "pass": scores["completeness"] >= 0.5 and scores["domain_fit"] >= 0.5,
        "patch": patch[:4],  # bounded
        "notes": "Critic proposes schema-valid patches only; no tool escalation.",
    }


def apply_critic_verify_patch(workflow: dict[str, Any], critic: dict[str, Any]) -> dict[str, Any]:
    """Apply only the safe verify-node addition from critic (deterministic)."""
    nodes = list(workflow.get("nodes") or [])
    edges = list(workflow.get("edges") or [])
    if any(str(n.get("type")) == "verify" for n in nodes if isinstance(n, dict)):
        return workflow
    verify_id = str(uuid4())
    nodes.append(
        {
            "id": verify_id,
            "type": "verify",
            "title": "Outcome verifier",
            "permission_class": "read",
            "idempotency_key": f"verify:{workflow.get('workflow_id')}",
            "cache_key": f"verify:{workflow.get('workflow_id')}",
        }
    )
    if nodes[:-1]:
        prev = nodes[-2]
        edges.append(
            {
                "id": str(uuid4()),
                "from": f"{prev['id']}:out",
                "to": f"{verify_id}:in",
                "kind": "control",
            }
        )
    out = dict(workflow)
    out["nodes"] = nodes
    out["edges"] = edges
    out.setdefault("metadata", {})
    if isinstance(out["metadata"], dict):
        notes = str(out["metadata"].get("notes") or "")
        out["metadata"] = {
            **out["metadata"],
            "notes": (notes + " | critic:added_verify").strip(" |"),
        }
    return out


def run_kernel_pipeline(
    *,
    prompt: str,
    source_text: str,
    compile_fn: Any,
    model: str,
    health: dict[str, Any],
    pack_id: str | None = None,
) -> dict[str, Any]:
    """
    Full bounded stage sequence through policy. Executor is separate (DagExecutor).
    compile_fn(prompt, source_text, model, health, pack) -> workflow dict
    """
    stage_log: list[dict[str, Any]] = []

    intake = intake_analyst(source_text=source_text, prompt=prompt)
    stage_log.append({"stage": "intake_analyst", "at": utc_now(), "result": {k: intake[k] for k in intake if k != "summary"} | {"summary": intake["summary"]}})

    if pack_id:
        pack = get_pack(pack_id)
        if not pack:
            raise RuntimeError(f"unknown domain pack: {pack_id}")
        routed = {
            "pack_ref": pack_ref(pack),
            "confidence": 1.0,
            "needs_user_choice": False,
            "scores": {},
            "inferred_outcomes": pack.get("default_goal_hints", [])[:3],
            "stage": "goal_router",
        }
    else:
        routed = goal_router(prompt=prompt, source_text=source_text)
        pack = get_pack(routed["pack_ref"])
        assert pack is not None
    stage_log.append({"stage": "goal_router", "at": utc_now(), "result": routed})

    plan = domain_planner(prompt=prompt, pack=pack, intake=intake)
    stage_log.append({"stage": "domain_planner", "at": utc_now(), "result": plan})

    # Compiler: LLM via compile_fn — untrusted evidence delimited inside workflow_gen
    _ = build_bounded_user_message(stage="compiler", goal_prompt=prompt, source_text=source_text)
    workflow = compile_fn(
        prompt=prompt,
        source_text=source_text,
        model=model,
        health=health,
        pack=pack,
    )
    stage_log.append(
        {
            "stage": "compiler",
            "at": utc_now(),
            "result": {"workflow_id": workflow.get("workflow_id"), "node_count": len(workflow.get("nodes") or [])},
        }
    )

    schema = validate_workflow_ir(workflow)
    stage_log.append({"stage": "schema_validate", "at": utc_now(), "result": schema})
    if not schema["ok"]:
        return {
            "ok": False,
            "error": "schema_validate_failed",
            "validation": schema,
            "stages": stage_log,
            "system_policy": SYSTEM_POLICY_IMMUTABLE,
        }

    critic = critic_review(workflow=workflow, intake=intake, pack=pack)
    stage_log.append({"stage": "critic", "at": utc_now(), "result": {k: critic[k] for k in critic if k != "patch"} | {"patch_ops": len(critic.get("patch") or [])}})
    if critic.get("patch"):
        workflow = apply_critic_verify_patch(workflow, critic)
        schema2 = validate_workflow_ir(workflow)
        stage_log.append({"stage": "schema_validate", "at": utc_now(), "result": schema2, "pass": "post_critic"})
        if not schema2["ok"]:
            return {
                "ok": False,
                "error": "post_critic_schema_failed",
                "validation": schema2,
                "stages": stage_log,
            }

    policy = validate_workflow_policy(workflow)
    stage_log.append({"stage": "policy", "at": utc_now(), "result": policy})
    if not policy["ok"]:
        return {
            "ok": False,
            "error": "policy_rejected",
            "policy": policy,
            "workflow": workflow,
            "stages": stage_log,
        }

    provenance = new_run_provenance(
        workflow=workflow,
        input_hashes={
            "prompt": content_hash(prompt),
            "source_text": content_hash(source_text),
        },
        stages=stage_log,
    )

    return {
        "ok": True,
        "workflow": workflow,
        "stages": stage_log,
        "intake": intake,
        "routing": routed,
        "plan": plan,
        "critic": critic,
        "policy": policy,
        "provenance": provenance,
        "validation": schema,
        "next_stages": ["executor", "outcome_verifier"],
    }
