"""Worker-side deterministic policy gate (mirrors crates/policy)."""

from __future__ import annotations

from typing import Any

AUTO_APPLY = frozenset({"read", "safe_overlay"})
APPROVAL_REQUIRED = frozenset(
    {
        "vault_mutate",
        "source_mutate",
        "network_egress",
        "network",  # legacy
        "publish",
        "shell",
        "credentials",
        "approval_required",  # legacy
    }
)
KNOWN_CLASSES = AUTO_APPLY | APPROVAL_REQUIRED


def normalize_permission_class(raw: str) -> str:
    mapping = {
        "network": "network_egress",
        "approval_required": "vault_mutate",
    }
    return mapping.get(raw, raw)


def may_auto_apply(permission_class: str) -> bool:
    return normalize_permission_class(permission_class) in AUTO_APPLY


def assert_path_safe_overlay(path: str) -> dict[str, Any]:
    """Safe auto-apply paths must stay under .brainflow overlays."""
    p = path.replace("\\", "/").lstrip("/")
    if ".." in p.split("/"):
        return {"ok": False, "error": "path traversal rejected"}
    allowed = (
        p.startswith(".brainflow/artifacts/")
        or p.startswith(".brainflow/workflows/")
        or p.startswith(".brainflow/graphs/")
        or p.startswith(".brainflow/templates/")
        or p.startswith("artifacts/")  # executor-relative shorthand
    )
    if not allowed:
        return {"ok": False, "error": f"path not under .brainflow overlay: {path}"}
    return {"ok": True}


def evaluate_node_action(node: dict[str, Any], *, write_path: str | None = None) -> dict[str, Any]:
    cls = normalize_permission_class(str(node.get("permission_class") or "safe_overlay"))
    if cls not in KNOWN_CLASSES and cls not in {"read", "safe_overlay"}:
        return {"ok": False, "approval_required": True, "error": f"unknown permission class: {cls}"}
    if not may_auto_apply(cls):
        return {
            "ok": False,
            "approval_required": True,
            "permission_class": cls,
            "error": f"permission class requires approval: {cls}",
        }
    if write_path:
        path_check = assert_path_safe_overlay(write_path)
        if not path_check["ok"]:
            return {**path_check, "approval_required": True}
    return {"ok": True, "permission_class": cls, "approval_required": False}


def validate_workflow_policy(doc: dict[str, Any]) -> dict[str, Any]:
    """Structural + policy checks beyond JSON Schema."""
    errors: list[str] = []
    nodes = doc.get("nodes") or []
    if not isinstance(nodes, list) or not nodes:
        return {"ok": False, "errors": ["nodes required"], "approvals_needed": []}

    node_ids = {str(n.get("id")) for n in nodes if isinstance(n, dict)}
    approvals_needed: list[dict[str, Any]] = []

    for n in nodes:
        if not isinstance(n, dict):
            errors.append("non-object node")
            continue
        cls = normalize_permission_class(str(n.get("permission_class") or ""))
        if cls not in KNOWN_CLASSES:
            errors.append(f"node {n.get('id')}: unknown permission_class {cls}")
        elif not may_auto_apply(cls):
            approvals_needed.append({"node_id": n.get("id"), "permission_class": cls})
        loop = n.get("review_loop")
        if isinstance(loop, dict):
            mi = loop.get("max_iterations")
            if not isinstance(mi, int) or mi < 1 or mi > 10:
                errors.append(f"node {n.get('id')}: review_loop.max_iterations must be 1..10")

    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for e in doc.get("edges") or []:
        if not isinstance(e, dict):
            continue
        frm = str(e.get("from") or "").split(":")[0]
        to = str(e.get("to") or "").split(":")[0]
        if frm in adj and to in node_ids:
            adj[frm].append(to)

    visiting: set[str] = set()
    visited: set[str] = set()
    loop_nodes = {
        str(n.get("id"))
        for n in nodes
        if isinstance(n, dict) and isinstance(n.get("review_loop"), dict)
    }

    def dfs(u: str, stack: list[str]) -> None:
        if u in visiting:
            cycle = stack[stack.index(u) :]
            if not all(c in loop_nodes for c in cycle):
                errors.append(f"unbounded cycle involving {cycle}")
            return
        if u in visited:
            return
        visiting.add(u)
        stack.append(u)
        for v in adj.get(u, []):
            dfs(v, stack)
        stack.pop()
        visiting.remove(u)
        visited.add(u)

    for nid in node_ids:
        dfs(nid, [])

    budgets = doc.get("budgets") or {}
    if isinstance(budgets, dict):
        if int(budgets.get("max_steps") or 0) > 500:
            errors.append("budgets.max_steps exceeds hard cap 500")
        if int(budgets.get("max_parallel_jobs") or 0) > 32:
            errors.append("budgets.max_parallel_jobs exceeds hard cap 32")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "approvals_needed": approvals_needed,
    }
