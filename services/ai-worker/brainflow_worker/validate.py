from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from brainflow_worker.kernel.policy_gate import validate_workflow_policy

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "schemas"
    / "workflow"
    / "workflow-ir.schema.json"
)


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_workflow_ir(doc: dict[str, Any]) -> dict[str, Any]:
    schema = load_schema()
    validator = Draft202012Validator(
        schema,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        return {
            "ok": False,
            "errors": [
                f"{'/'.join(str(p) for p in e.path) or '/'}: {e.message}" for e in errors
            ],
        }
    policy = validate_workflow_policy(doc)
    if not policy["ok"]:
        return {
            "ok": False,
            "errors": policy["errors"],
            "approvals_needed": policy.get("approvals_needed", []),
            "policy": True,
        }
    return {
        "ok": True,
        "errors": [],
        "approvals_needed": policy.get("approvals_needed", []),
    }
