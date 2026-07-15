"""Resumable DAG executor with budgets, retries, cancel, and idempotent cache keys."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable

from brainflow_worker.kernel.policy_gate import evaluate_node_action, may_auto_apply
from brainflow_worker.kernel.provenance import content_hash, utc_now


NodeHandler = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


@dataclass
class RunState:
    run_id: str
    workflow_id: str
    status: str = "queued"
    node_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    cache: dict[str, Any] = field(default_factory=dict)
    budgets_used: dict[str, int | float] = field(
        default_factory=lambda: {"steps": 0, "tokens": 0, "generated_files": 0}
    )
    artifact_paths: list[str] = field(default_factory=list)
    error: str | None = None
    cancel_requested: bool = False

    def emit(self, kind: str, **payload: Any) -> None:
        self.events.append({"at": utc_now(), "kind": kind, **payload})

    def request_cancel(self) -> None:
        self.cancel_requested = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "node_states": self.node_states,
            "events": self.events,
            "approvals": self.approvals,
            "budgets_used": self.budgets_used,
            "artifact_paths": self.artifact_paths,
            "error": self.error,
            "cancel_requested": self.cancel_requested,
            "updated_at": utc_now(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RunState:
        state = cls(
            run_id=str(raw["run_id"]),
            workflow_id=str(raw["workflow_id"]),
            status=str(raw.get("status") or "queued"),
        )
        state.node_states = dict(raw.get("node_states") or {})
        state.events = list(raw.get("events") or [])
        state.approvals = list(raw.get("approvals") or [])
        state.cache = dict(raw.get("cache") or {})
        state.budgets_used = dict(raw.get("budgets_used") or {"steps": 0, "tokens": 0, "generated_files": 0})
        state.artifact_paths = list(raw.get("artifact_paths") or [])
        state.error = raw.get("error")
        state.cancel_requested = bool(raw.get("cancel_requested"))
        return state


def cache_key_for_node(node: dict[str, Any], pins: dict[str, Any], input_hash: str) -> str:
    if node.get("cache_key"):
        base = str(node["cache_key"])
    elif node.get("idempotency_key"):
        base = str(node["idempotency_key"])
    else:
        base = json.dumps(
            {"id": node.get("id"), "type": node.get("type"), "title": node.get("title")},
            sort_keys=True,
        )
    material = f"{base}|{json.dumps(pins, sort_keys=True)}|{input_hash}"
    return "cache:" + hashlib.sha256(material.encode()).hexdigest()[:24]


def _topo_layers(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[str]]:
    ids = [str(n["id"]) for n in nodes]
    indeg = {i: 0 for i in ids}
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        frm = str(e.get("from") or "").split(":")[0]
        to = str(e.get("to") or "").split(":")[0]
        if frm in indeg and to in indeg:
            adj[frm].append(to)
            indeg[to] += 1
    q = deque([i for i, d in indeg.items() if d == 0])
    order: list[str] = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(order) != len(ids):
        # fall back to declaration order if cycle (should be rejected upstream)
        return [[i] for i in ids]
    return [[i] for i in order]


class DagExecutor:
    """Executes schema-valid workflows; auto-applies only safe_overlay/.brainflow writes."""

    def __init__(
        self,
        *,
        handlers: dict[str, NodeHandler] | None = None,
        approval_callback: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self.handlers = handlers or {}
        self.approval_callback = approval_callback

    def cancel(self, run_state: RunState) -> RunState:
        """Cooperative cancel: marks the run cancelled and stops further spend."""
        run_state.request_cancel()
        if run_state.status in {"succeeded", "failed", "cancelled"}:
            return run_state
        run_state.status = "cancelled"
        run_state.error = run_state.error or "cancelled by user"
        run_state.emit("run_cancelled")
        return run_state

    def execute(
        self,
        workflow: dict[str, Any],
        *,
        run_state: RunState,
        input_hash: str,
        resume: bool = True,
    ) -> RunState:
        budgets = workflow.get("budgets") or {}
        max_steps = int(budgets.get("max_steps") or 80)
        max_tokens = budgets.get("max_tokens")
        max_tokens_i = int(max_tokens) if max_tokens is not None else None
        max_files = budgets.get("max_generated_files")
        max_files_i = int(max_files) if max_files is not None else None
        nodes = {str(n["id"]): n for n in workflow.get("nodes") or []}
        edges = list(workflow.get("edges") or [])
        pins = workflow.get("pins") or {}

        if run_state.cancel_requested or run_state.status == "cancelled":
            return self.cancel(run_state)

        run_state.status = "running"
        run_state.emit("run_started", resume=resume)

        for layer in _topo_layers(list(nodes.values()), edges):
            for nid in layer:
                if run_state.cancel_requested:
                    return self.cancel(run_state)

                if resume:
                    prev = run_state.node_states.get(nid)
                    if prev and prev.get("status") == "succeeded":
                        run_state.emit("node_skipped_resume", node_id=nid)
                        continue

                node = nodes[nid]
                run_state.node_states[nid] = {
                    "status": "running",
                    "attempts": int((run_state.node_states.get(nid) or {}).get("attempts") or 0),
                }
                if int(run_state.budgets_used.get("steps") or 0) >= max_steps:
                    run_state.status = "failed"
                    run_state.error = "max_steps budget exceeded"
                    run_state.emit("budget_exceeded", budget="max_steps")
                    return run_state
                if max_tokens_i is not None and int(run_state.budgets_used.get("tokens") or 0) >= max_tokens_i:
                    run_state.status = "failed"
                    run_state.error = "max_tokens budget exceeded"
                    run_state.emit("budget_exceeded", budget="max_tokens")
                    return run_state
                if max_files_i is not None and int(run_state.budgets_used.get("generated_files") or 0) >= max_files_i:
                    run_state.status = "failed"
                    run_state.error = "max_generated_files budget exceeded"
                    run_state.emit("budget_exceeded", budget="max_generated_files")
                    return run_state

                policy = evaluate_node_action(node)
                if policy.get("approval_required"):
                    approved = False
                    if self.approval_callback:
                        approved = bool(self.approval_callback(node))
                    run_state.approvals.append(
                        {
                            "node_id": nid,
                            "permission_class": policy.get("permission_class"),
                            "decision": "approved" if approved else "denied",
                            "at": utc_now(),
                        }
                    )
                    if not approved:
                        run_state.node_states[nid] = {
                            "status": "needs_approval",
                            "attempts": run_state.node_states[nid]["attempts"],
                        }
                        run_state.status = "needs_review"
                        run_state.emit("approval_required", node_id=nid)
                        return run_state

                ck = cache_key_for_node(node, pins, input_hash)
                if ck in run_state.cache:
                    run_state.node_states[nid] = {
                        "status": "succeeded",
                        "attempts": run_state.node_states[nid]["attempts"],
                        "cache_hit": True,
                        "cache_key": ck,
                    }
                    run_state.emit("cache_hit", node_id=nid, cache_key=ck)
                    continue

                retry_cfg = node.get("retry") or {}
                max_retry = int(retry_cfg.get("max") or 0)
                attempt = 0
                last_err: str | None = None
                while attempt <= max_retry:
                    if run_state.cancel_requested:
                        return self.cancel(run_state)
                    attempt += 1
                    run_state.node_states[nid]["attempts"] = attempt
                    run_state.budgets_used["steps"] = int(run_state.budgets_used.get("steps") or 0) + 1
                    try:
                        result = self._invoke(node, {"input_hash": input_hash, "run_id": run_state.run_id})
                        tokens = int(result.get("tokens_used") or result.get("tokens") or 0)
                        if tokens:
                            run_state.budgets_used["tokens"] = (
                                int(run_state.budgets_used.get("tokens") or 0) + tokens
                            )
                            if max_tokens_i is not None and int(run_state.budgets_used["tokens"]) > max_tokens_i:
                                run_state.status = "failed"
                                run_state.error = "max_tokens budget exceeded"
                                run_state.emit("budget_exceeded", budget="max_tokens")
                                return run_state
                        if result.get("artifact_path"):
                            path = str(result["artifact_path"])
                            if may_auto_apply(str(node.get("permission_class") or "safe_overlay")):
                                path_policy = evaluate_node_action(node, write_path=path)
                                if not path_policy.get("ok"):
                                    raise RuntimeError(path_policy.get("error") or "unsafe write path")
                            run_state.artifact_paths.append(path)
                            run_state.budgets_used["generated_files"] = (
                                int(run_state.budgets_used.get("generated_files") or 0) + 1
                            )
                        run_state.cache[ck] = {"result": result, "at": utc_now()}
                        run_state.node_states[nid] = {
                            "status": "succeeded",
                            "attempts": attempt,
                            "cache_hit": False,
                            "cache_key": ck,
                            "output": result,
                        }
                        run_state.emit("node_succeeded", node_id=nid)
                        last_err = None
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_err = str(exc)
                        run_state.emit("node_retry", node_id=nid, attempt=attempt, error=last_err)
                if last_err:
                    run_state.node_states[nid] = {
                        "status": "failed",
                        "attempts": attempt,
                        "error": last_err,
                    }
                    run_state.status = "failed"
                    run_state.error = last_err
                    run_state.emit("node_failed", node_id=nid, error=last_err)
                    return run_state

        # Outcome verifier: check completion criteria presence (stub acceptance)
        criteria = (workflow.get("completion") or {}).get("criteria") or []
        if criteria and not run_state.artifact_paths:
            run_state.status = "needs_review"
            run_state.error = "outcome verifier: criteria unmet (no artifacts)"
            run_state.emit("verify_failed", reason=run_state.error)
            return run_state

        run_state.status = "succeeded"
        run_state.emit("run_succeeded")
        return run_state

    def _invoke(self, node: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        ntype = str(node.get("type") or "summarize")
        handler = self.handlers.get(ntype) or self.handlers.get("*")
        if handler:
            return handler(node, ctx)
        # Default no-op safe overlay marker
        return {
            "ok": True,
            "node_type": ntype,
            "message": "noop",
            "input_hash": ctx.get("input_hash"),
            "content_hash": content_hash(str(node.get("title") or "")),
        }
