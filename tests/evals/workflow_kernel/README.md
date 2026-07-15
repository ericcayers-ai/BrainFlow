# Workflow kernel eval stubs

Deterministic harness stubs for Phase 6 exit criteria. Full live LLM evals are deferred to the E2E/hardening agent.

## Cases (executable)

| ID | Intent |
|----|--------|
| `test_schema_valid_after_compile_pipeline` | Domain pack + deterministic compiler → schema-valid IR |
| `test_provenance_fields_present` | Provenance contract fields |
| `test_injection_delimit_resistance` | UNTRUSTED_EVIDENCE fencing + no auto-apply escalation |
| `test_cancel_and_resume_executor` | Cancel stops spend; resume skips succeeded nodes |
| `test_budget_max_steps_and_tokens_enforced` | Executor stops at max_steps / max_tokens |
| `test_approval_gate_for_non_safe_actions` | `shell` requires approval; not auto-applied |

Run: `pytest tests/evals/workflow_kernel -q` from repo root (PYTHONPATH includes `services/ai-worker`).

Live LLM actionability/domain rubrics remain a hardening-beta gate — these tests cover the deterministic Phase 6 exit criteria that can fail in CI without keys.