# Domain rubric evals (Phase 6)

| Mode | Gate | Purpose |
|------|------|---------|
| Stub (default) | Always in CI | Deterministic actionability scoring ≥85% on fixture cases |
| Live | `BRAINFLOW_LIVE_EVAL=1` | Ollama structured JSON artifacts scored by the same rubric |

```bash
pytest tests/evals/domain_rubric -q
BRAINFLOW_LIVE_EVAL=1 pytest tests/evals/domain_rubric -q
```

Phase 6 exit remains **PARTIAL** until live runs meet ≥85% with red-team variance bands recorded — see [docs/EVALUATION_STRATEGY.md](../../../docs/EVALUATION_STRATEGY.md).
