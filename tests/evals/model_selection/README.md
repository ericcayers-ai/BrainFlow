# Model selection evals

Hardware-aware scoring and local benchmark stub for BrainFlow ([docs/MODEL_SELECTION.md](../../../docs/MODEL_SELECTION.md)).

## Layout

| Path | Role |
|------|------|
| `harness.py` | Stub shortlist benchmark (planning, citation, graph, latency, memory) |
| `fixtures/hardware_*.json` | Low / mid / high Windows profiles for fit tests |
| `test_*.py` | Contract tests for scoring, pins, registry verify |

## Run

```bash
cd services/ai-worker
pip install -e ".[dev]"
pytest ../../tests/evals/model_selection -q
python ../../tests/evals/model_selection/harness.py
```

Live weight downloads and TTFT measurement are gated; the stub returns deterministic scores so CI stays offline.
