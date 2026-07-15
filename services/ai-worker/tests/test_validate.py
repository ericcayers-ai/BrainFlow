from brainflow_worker.validate import validate_workflow_ir
from brainflow_worker.kernel.policy_gate import may_auto_apply, validate_workflow_policy


def test_rejects_missing_version():
    result = validate_workflow_ir({"title": "x"})
    assert result["ok"] is False


def test_policy_safe_overlay():
    assert may_auto_apply("safe_overlay")
    assert not may_auto_apply("publish")


def test_policy_rejects_bad_budget():
    doc = {
        "schema_version": 1,
        "nodes": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "type": "summarize",
                "title": "t",
                "permission_class": "safe_overlay",
            }
        ],
        "edges": [],
        "budgets": {"max_steps": 9999, "max_parallel_jobs": 1},
    }
    report = validate_workflow_policy(doc)
    assert report["ok"] is False
