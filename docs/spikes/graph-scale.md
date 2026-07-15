# Spike: Graph scale (500 workflow / 5k knowledge)

**ADR:** [0003-graph-engines.md](../adr/0003-graph-engines.md)  
**Budgets:** [PERFORMANCE_BUDGETS.md](../PERFORMANCE_BUDGETS.md)  
**Machine run:** [graph-scale-results.json](./graph-scale-results.json)

## What we built

- ELK layout off the UI thread via Vite module Web Worker (`apps/desktop/src/graph/elkLayout.worker.ts`).
- LOD / pagination / degree clustering (`apps/desktop/src/graph/lod.ts`) with documented `GRAPH_SCALE_LIMITS`.
- Stress generators: `generateWorkflowFixture(500)`, `generateKnowledgeFixture(5000)`.
- Harness: `npm run stress:graph -w desktop` (main-thread ELK in Node; UI uses worker).

## Documented interactive limits

| Cap | Value | Behavior |
|-----|------:|----------|
| Workflow editable target | 500 | Full ELK layout allowed |
| Workflow visible default (page) | 200 | Paginate when above soft page size without focus |
| Knowledge cluster above | 800 | Degree-cluster to hubs + synthetic clusters |
| Knowledge page size | 400 | Pagination when `forceMode: "page"` |
| Knowledge visible target | 5000 | Explore via LOD; never full-force 5k on canvas |
| Absolute render hard max | 12_000 | Documented refuse budget (elements) |

## Measured results (Windows, Node v24.18.0, 2026-07-15)

| Scenario | Metric | Result |
|----------|--------|--------|
| Workflow 500 | Generate fixture | ~1 ms |
| Workflow 500 | `graphFromWorkflow` | ~9 ms |
| Workflow 500 | ELK layered (main thread) | **~880 ms** |
| Workflow 500 | Shortest path | found, len 9 |
| Knowledge 5000 | Generate | ~5 ms |
| Knowledge 5000 | Default LOD (cluster) | **132** visible nodes in ~24 ms |
| Knowledge 5000 | Page mode | 400 / page, 13 pages in ~2 ms |
| Knowledge 5000 | Shortest path | found, len 3, ~2 ms |

**Interpretation:** 500-node ELK exceeds the 500 ms “show progress” budget on main thread (~880 ms). Production routes layout through the Web Worker so the UI thread stays interactive; progress status is surfaced when layout is large. 5k relationship graphs are only interactively explored after LOD (cluster or page) — full 5k Cytoscape render is intentionally deferred.

## Re-run

```bash
npm run stress:graph -w desktop
npm run smoke:graph-ui -w desktop
npm run test:graph -w desktop
```

**UI data-prep smoke (2026-07-16+):** `smoke:graph-ui` builds 500 React Flow node/edge shapes via the same LOD path as `WorkflowGraph`, times prep, and records ELK — see [graph-ui-smoke-results.json](./graph-ui-smoke-results.json). **Does not** claim NVDA or mid-tier GPU pan/zoom.

## Deferred

- CI gate with mid-tier GPU soak for pan/zoom edit at 500 nodes in real React Flow / Tauri WebView.
- Worker packaging verification inside Tauri WebView (smoke landed in Vite; device matrix open).
- Live NVDA / VoiceOver pass for graph suite exit.
