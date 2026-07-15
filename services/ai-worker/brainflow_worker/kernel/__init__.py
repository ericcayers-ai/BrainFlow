"""Workflow kernel: bounded planner → validator → policy → executor → verifier."""

from brainflow_worker.kernel.delimit import SYSTEM_POLICY_IMMUTABLE, delimit_untrusted
from brainflow_worker.kernel.executor import DagExecutor, RunState, cache_key_for_node
from brainflow_worker.kernel.policy_gate import may_auto_apply, validate_workflow_policy

__all__ = [
    "SYSTEM_POLICY_IMMUTABLE",
    "DagExecutor",
    "RunState",
    "cache_key_for_node",
    "delimit_untrusted",
    "may_auto_apply",
    "validate_workflow_policy",
]


def __getattr__(name: str):
    if name == "STAGES":
        from brainflow_worker.kernel.stages import STAGES

        return STAGES
    if name == "run_kernel_pipeline":
        from brainflow_worker.kernel.stages import run_kernel_pipeline

        return run_kernel_pipeline
    raise AttributeError(name)
