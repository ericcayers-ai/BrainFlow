# Spike: Graph engines (React Flow + ELK, Cytoscape)

**ADR:** [0003-graph-engines.md](../adr/0003-graph-engines.md)

## What we built

- Editable workflow DAG stub: `@xyflow/react` + `elkjs` layered layout.
- Cytoscape headless import stub confirming package load.
- ELK moved to a dedicated Web Worker (`apps/desktop/src/graph/elkLayout.worker.ts`).
- Scale / LOD follow-up: [graph-scale.md](./graph-scale.md).

## Results

- Both libraries install cleanly under Vite 7 / React 19 on Windows.
- ELK sync layout is acceptable for foundation-sized graphs (<50 nodes).
- Worker packaging via Vite `new Worker(new URL(..., import.meta.url), { type: "module" })` with main-thread fallback.
- ~500-node ELK ~880 ms on Node main thread → progress UI + worker in app.

## Decision

Keep dual-engine approach. Workflow Suite uses React Flow + worker ELK; knowledge exploration uses Cytoscape with clustering/pagination.
