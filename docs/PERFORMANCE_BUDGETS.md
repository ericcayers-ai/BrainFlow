# Performance Budgets

Initial quantitative targets. Revisit after Phase 1 spikes with measured baselines; budgets become CI gates once harness exists.

---

## 1. Interaction responsiveness

| Interaction | Budget | Measured (catalog, 2026-07-16 re-run) |
|-------------|--------|--------------------------------------|
| Keystroke in Markdown editor (warm) | ≤ 50 ms p95 input latency perceived; no multi-frame stalls on mid-tier | **UI not measured** — catalog open+save+search **proxy** below |
| Catalog open+save+search cycle (proxy) | ≤ 50 ms p95 on 10k vault (storage path) | **30.1 ms** p95 ([spikes/soak-10k.md](spikes/soak-10k.md)) |
| Command palette open | ≤ 100 ms p95 | Not measured (UI) |
| Quick switcher query | ≤ 100 ms p95 on 10k-note vault | **0.090 ms** p95 FTS proxy |
| Search (text, warm, 10k notes) | **p95 &lt; 100 ms** | **0.454 ms** p95 |
| Tab switch / split | ≤ 100 ms p95 | Not measured (UI) |
| Workflow node select | ≤ 50 ms p95 | Not measured (UI) |

Background indexing and model execution **must not** block typing/navigation (async jobs + priority). Catalog FTS + edit-cycle proxy budgets **met** at N=10k; WebView keystroke budget remains open.

---

## 2. Graph scale

| Scenario | Target |
|----------|--------|
| 500-node editable workflow DAG | Smooth pan/zoom/edit on mid-tier Windows |
| 5,000 visible relationship nodes | Useful interactive explore with LOD/clustering |
| Layout (ELK) 500 nodes | Worker off main thread; UI remains interactive; show progress if &gt; 500 ms |

### Measured baseline (Phase 7 harness, 2026-07-15)

See [spikes/graph-scale.md](spikes/graph-scale.md) and [spikes/graph-scale-results.json](spikes/graph-scale-results.json).

| Scenario | Measurement |
|----------|-------------|
| 500-node ELK layered (Node main thread) | **~880 ms** (over 500 ms → UI shows worker progress; production uses worker) |
| 5,000 relationship nodes default LOD | Cluster → **132** visible nodes in ~24 ms |
| 5,000 page mode | **400**/page, 13 pages, ~2 ms |

Limits source of truth: `apps/desktop/src/graph/lod.ts` (`GRAPH_SCALE_LIMITS`).

---

## 3. Startup and packaging (record in Phase 1)

| Metric | Initial aspiration (refine after spike) | Measured (2026-07-16, Windows) |
|--------|----------------------------------------|--------------------------------|
| Cold start to interactive shell | Measure & optimize; track regression | **Time-to-visible window:** cold-ish **618 ms** (1st after idle); warm **~45–90 ms** (`scripts/measure-cold-start.ps1`). Not sidecar-ready. See [spikes/tauri-shell.md](spikes/tauri-shell.md). |
| Installer size | Track; prefer Tauri lean footprint vs Electron baseline if compared | NSIS **6.84 MiB**; MSI **8.79 MiB**; `desktop.exe` **19.54 MiB**; web `dist` **5.75 MiB** ([spikes/tauri-shell.md](spikes/tauri-shell.md)) |
| Idle RSS | Track by OS | **Not measured** |

---

## 4. Ingestion

| Metric | Budget |
|--------|--------|
| Small PDF (&lt;20 pages) normalize | Interactive progress; complete within seconds on mid-tier |
| Large job | Streaming progress; cancel &lt; 2 s to acknowledge |
| Zip bomb | Fail within resource limit without OOM kill of whole app |

---

## 5. LLM UX

| Metric | Budget |
|--------|--------|
| Time to first structured token | Display streaming; cancel always |
| Mid-run UI | Run events &lt; 100 ms to reflect in graph status after durable write |

Throughput itself is hardware-bound; budgets focus on **UI responsiveness** and **cancellation**.

---

## 6. Sync

| Metric | Budget |
|--------|--------|
| Debounce window | Configurable; default hundreds of ms–seconds to coalesce |
| Status update after commit | Near-immediate local |
| Large push | Progress; non-blocking UI |

---

## 7. Soak

- Multi-hour session: editor + periodic workflows + sync — no unbounded memory growth.  
- Index rebuild of 10k vault: completes; UI stays usable at reduced priority.  
- **Catalog FTS + edit-cycle (2026-07-16):** N=10,000 indexed in ~182 s; warm FTS p95 **0.45 ms**; QS p95 **0.09 ms**; open+save+search cycle p95 **30.1 ms** (≤50 ms budget); no data loss — [spikes/soak-10k.md](spikes/soak-10k.md). WebView keystroke soak still open.

---

## 8. Hardware classes

Define fixture profiles (RAM/GPU) used in CI manual racks or cloud runners. Model selection budgets: selection decision itself &lt; a few seconds excluding downloads/benchmarks; benchmarks are explicit user-consented jobs.

---

## 9. Acceptance criteria

- AC-PERF-01: Search p95 gate on reference vault in CI or nightly.  
- AC-PERF-02: Graph 500-node edit scenario has automated smoke timing — **data-prep smoke** via `npm run smoke:graph-ui -w desktop` ([spikes/graph-ui-smoke-results.json](spikes/graph-ui-smoke-results.json)); mid-tier GPU pan/zoom still open.  
- AC-PERF-03: Typing jitter under background embed job within regression band.  
- AC-PERF-04: Phase 1 spike report publishes measured startup/size numbers into this doc.
