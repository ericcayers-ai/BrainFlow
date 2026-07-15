# Graph UI scale smoke (500 React Flow nodes)

Node harness — mirrors `WorkflowGraph` conversion + LOD + React Flow node/edge shapes.

**Not claimed:** mid-tier GPU pan/zoom, Tauri WebView render soak, NVDA/AT.

## Run

```bash
npm run smoke:graph-ui -w desktop
npm run test:graph -w desktop   # includes graphUiScaleSmoke.test.ts
```

## Latest run

See [graph-ui-smoke-results.json](./graph-ui-smoke-results.json).

| Metric | Value |
|--------|------:|
| Target nodes | 500 (full LOD) |
| React Flow nodes / edges | 500 / 499 |
| Prep p50 / p95 | 1.37 / **4.02** ms (budget ≤100 ms) |
| ELK main-thread | ~1114 ms (progress UI expected; production uses worker) |
| NVDA claimed | **false** |

Related: [graph-scale.md](./graph-scale.md), [PERFORMANCE_BUDGETS.md](../PERFORMANCE_BUDGETS.md) AC-PERF-02.
