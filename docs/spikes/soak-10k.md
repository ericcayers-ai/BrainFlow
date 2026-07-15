# 10k-note vault soak (FTS / search / open / edit-cycle)

Automated index + latency probe for Phase 3 exit readiness. **Does not** claim daily-team soak or WebView/CodeMirror keystroke sign-off.

## How to run

```bash
python scripts/soak_10k_notes.py              # aim N=10000
python scripts/soak_10k_notes.py --n 2000     # resource-bound smaller N
cargo run -p brainflow-storage --example soak_bench --release -- 10000
```

Env: `BRAINFLOW_SOAK_N`, `BRAINFLOW_SOAK_VAULT`, `BRAINFLOW_SOAK_CATALOG`, `BRAINFLOW_SOAK_KEEP=1`.

## Latest run

| Metric | Value |
|--------|-------|
| Recorded | 2026-07-15T14:03:29.513461+00:00 |
| N notes indexed | **10000** |
| Index build | 182436.6 ms |
| FTS warm MATCH p50 / p95 | 0.391 / **0.454** ms |
| Tag search p50 / p95 | 0.119 / 0.237 ms |
| Quick-switcher proxy FTS p50 / p95 | 0.044 / **0.09** ms |
| Note open (read body) p50 / p95 | 0.082 / 0.157 ms |
| Note save upsert p50 / p95 | 15.594 / **28.106** ms |
| Open+save+search cycle p50 / p95 | 16.074 / **30.079** ms |
| Data loss during generate/index/edit | False |
| Budget search/QS p95 &lt; 100.0 ms | FTS=pass · QS=pass |
| Budget edit-cycle p95 &lt; 50.0 ms | save=pass · cycle=pass |

Raw: [soak-10k-results.json](./soak-10k-results.json).

## Honest status

- Catalog FTS + **open+save+search edit-cycle proxy** are measured here (storage path that backs autosave/search).
- **Desktop UI keystroke / WebView** path is **not** measured — do not equate cycle_p95 with perceived typing latency.
- Phase 3 exit remains **unchecked** until daily-team use on a 10k vault is recorded by humans.
- Measurable catalog budgets (search/QS &lt; 100 ms; edit-cycle &lt; 50 ms) may be recorded as met when this harness passes at N=10k.
- If host is resource-bound, run smaller `N` and record the honest max in this file / JSON.
