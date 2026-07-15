# Architecture Spikes — Results

**Date:** 2026-07-15 (UTC) / local 2026-07-16  
**Environment:** Windows 10/11 · Node 24 · Rust 1.96 · Python 3.12 · Ollama present  
**Scope:** Phase 1 spikes only — focused prototypes, not full product QA.

Related ADRs: [0001](../adr/0001-tauri-vs-electron.md) · [0002](../adr/0002-sidecar-transport.md) · [0003](../adr/0003-graph-engines.md) · [0004](../adr/0004-storage.md) · [0005](../adr/0005-git-strategy.md)

---

## Summary decisions

| Topic | Outcome | Confidence |
|-------|---------|------------|
| Desktop shell | **Proceed with Tauri 2 + React/TS/Vite** | High (scaffold + dialog + crate path deps compile path verified on Windows tooling) |
| Electron fallback | Only if packaging/WebView/a11y blockers appear (criteria below) | — |
| Worker IPC | **Stdio JSON-RPC** as default; loopback HTTP only with random port + bearer for debug | High |
| Schemas | Shared JSON Schema package with `schema_version` | High |
| Graph UI | React Flow + ELK bundled layout OK; Cytoscape smoke import OK | High |
| SQLite/FTS | `rusqlite` bundled + FTS5 works in `crates/storage` | High |
| Ollama | Health ~33 ms; models available; generate fail-closed when down | High |
| Git | Prefer **gitoxide (`gix`)** primary with **git2** escape hatch; avoid UI/worker subprocess | Medium (design spike; lib not wired in slice) |

---

## 1. Tauri 2 + React shell

**Prototype:** `apps/desktop` via `create-tauri-app` (React-TS, Tauri 2), extended with vault/LLM commands and dialog plugin.

**Measured / observed:**

- Scaffold succeeded on Windows with `npm` + `stable-x86_64-pc-windows-msvc`.
- Frontend deps install ~14–20s on this machine.
- Product wiring uses Rust crates (`vault`, `storage`, `policy`) via path deps from `src-tauri`.

**Electron fallback criteria (confirm ADR 0001):**

1. Cannot ship/sign Windows MSI/NSIS with sidecar worker reliably after a packaging spike.  
2. Screen reader / a11y blockers specific to WebView2 that Electron+Chromium does not share.  
3. Sidecar supervision / stdin IPC broken under Tauri capabilities with no workaround.  
4. Critical plugin ecosystem gap that blocks vault FS or keychain for >1 milestone.

**Unresolved risks:** First full `tauri build` failed on this machine (2026-07-16) with rustc `STATUS_DLL_NOT_FOUND` / path errors during release compile — mitigated with `CARGO_BUILD_JOBS=2`; second attempt produced unsigned MSI/NSIS — see [tauri-shell.md](./tauri-shell.md). Installer sizes + time-to-window cold-start **recorded**. Code-signing not spiked. macOS/Linux packaging not run.

---

## 2. Shared JSON schemas

**Prototype:** `packages/schemas` — `workflow-ir.schema.json` + `run-metadata.schema.json`, Ajv validators, Node tests.

**Decision:** Single source of truth under `packages/schemas`; Python loads the same files; TS validates via Ajv. Later: generate bindings rather than hand-duplicating types.

---

## 3. React Flow + ELK / Cytoscape

**Prototype:** `apps/desktop/src/components/WorkflowGraph.tsx` (React Flow + ELK), `apps/desktop/src/spikes/cytoscapeSmoke.ts`.

**Measured / observed:**

- ELK layered layout now runs in a Vite module **Web Worker** (`elkLayout.worker.ts`); Node stress still measures main-thread ELK (~880 ms @ 500 nodes).  
- Cytoscape knowledge view applies LOD/clustering above 800 nodes.  
- A11y twin: `GraphOutline` is mandatory, synchronized, keyboard-first (focus-model tests).

**Scale follow-up:** [graph-scale.md](./graph-scale.md) — 500 workflow / 5k knowledge fixtures + limits.

**Unresolved risks:** Mid-tier React Flow pan/zoom soak at 500; Tauri WebView worker smoke matrix; live AT sign-off.

See also [graph-engines.md](./graph-engines.md).

---

## 4. SQLite / FTS

**Prototype:** `crates/storage` with bundled rusqlite, WAL, FTS5 upsert + MATCH.

**Decision:** Indexes live under `%LOCALAPPDATA%\BrainFlow\indexes\` — never inside OneDrive vault roots (see ADR 0004).

**Deferred:** Vector tables / embedding profiles to model-intelligence phase.

See [storage-fts.md](./storage-fts.md).

---

## 5. Ollama health probe

**Measured on this machine:**

| Probe | Result |
|-------|--------|
| `GET /api/tags` | HTTP 200 in **~33 ms** |
| Models | `llama3.2:3b`, `qwen3.6:35b` (and possibly others) present |
| Tiny `generate` (`llama3.2:3b`, 8 tokens) | **~62 s** wall time (cold/warm model load dominated) |

**Fail-closed:** Worker `llm.health` / `workflow.generate` return RPC errors when Ollama down or no models. No rule-based pretend planner.

See [ollama-probe.md](./ollama-probe.md).

---

## 6. Private worker IPC

**Prototype:** `services/ai-worker` line-delimited JSON-RPC on stdio; optional `--http-loopback` binds `127.0.0.1:0` + bearer token.

**Decision:** Aligns with ADR 0002. Rust core spawns `py -3 -m brainflow_worker` and exchanges one request/response per job in the foundation slice (long-lived supervisor later).

See [worker-ipc.md](./worker-ipc.md).

---

## 7. Git strategy (ADR 0005)

**Decision (spike):**

| Option | Notes |
|--------|-------|
| **gitoxide (`gix`)** | Pure Rust, favored for embedding + async-friendly future; start here for fetch/status |
| **libgit2 (`git2-rs`)** | Mature merge/index APIs; use as escape hatch for hard merge cases |
| **`git` subprocess** | Allowed only behind sync state machine for ops not yet embedded — never from UI/worker/LLM tools |

Conflict UX and semantic Markdown merge remain future work.

**Update (github-sync):** Implemented in `crates/sync` — gitoxide discovery, git2 porcelain escape hatch, semantic Markdown + structural JSON merge, conflict UI, offline queue, OS credential store, interrupted-op recovery. See [docs/GITHUB_SYNC.md](../GITHUB_SYNC.md).

See [git-ops.md](./git-ops.md).

---

## Unresolved risks (carry forward)

1. Structured JSON adherence of small local models — foundation may need prompt tightening or larger planner.  
2. Long-lived worker process + crash restart semantics.  
3. Tauri capability hardening for multi-root vault grants.  
4. OneDrive vault race conditions even when indexes are local.  
5. Full packaging size / cold-start of WebView2 + Python sidecar — **installer sizes + time-to-window recorded** (NSIS 6.84 MiB / MSI 8.79 MiB; cold-ish **618 ms** / warm **~45–90 ms**); **sidecar-ready** latency still open ([tauri-shell.md](./tauri-shell.md)).

---

## Artifacts produced

- `docs/spikes/*` (this file + topic notes)  
- Runnable monorepo scaffolding consumed by Phase 2 foundation slice
