# BrainFlow Roadmap

Phased delivery aligned with the product roadmap. Assumptions: focused team of ~6–8 engineers plus product/design and part-time security/QA for an 18–24 month desktop v1; solo effort should expect longer. Do not market the full vision as an MVP.

User decisions locked for v1 planning: **desktop-first**, **immutable sources by default**, **AI Workflow Suite as primary orchestration**, **file viewer secondary**.

Honest open work vs the 18–24 month GA bar: [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md).

---

## Phase 0 — Product contract and architecture (2–4 weeks)

**Deliverables**

- Product spec, non-goals, AI safety/agency, threat model, data ownership, privacy, workflow IR, graph model, accessibility baseline, UX principles.
- Model selection/registry contracts, file ingestion contract, GitHub sync state machine.
- Obsidian-core parity checklist; initial ADRs (Tauri vs Electron, sidecar transport, graph engines, storage, Git).
- QA, evaluation, and performance budget documents.
- Licensing/contribution model decided without dependencies that force the choice.

**Exit criteria**

- [ ] Every non-negotiable product behavior has a **testable acceptance criterion** (see [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md)).
- [ ] Docs listed in section 14 of the product plan exist and are implementer-ready.
- [ ] ADR set opened for the five foundational decisions.

**Status:** Documentation deliverables in this repository complete product-contract scope. Phase 1 spikes + Phase 2 foundation slice scaffolding are in-tree (see [docs/spikes/SPIKE_RESULTS.md](docs/spikes/SPIKE_RESULTS.md) and monorepo `apps/` / `crates/` / `services/`).

---

## Phase 1 — High-risk technical spikes (4–6 weeks)

**Deliverables**

- Tauri worker supervision/packaging prototypes on Windows, macOS, Linux (Electron only if sidecar/a11y fails measurable criteria).
- Benchmarks: CodeMirror wikilinks/live preview; React Flow + worker ELK; Cytoscape dense graphs; SQLite FTS/vector; safe Office/PDF/media extraction; Ollama structured output; embedded Git conflicts.
- Throwaway E2E spike: PDF → DocumentBundle → validated LLM workflow → graph → derived Markdown → GitHub push.

**Exit criteria**

- [x] ADRs refined with measured evidence in [docs/spikes/SPIKE_RESULTS.md](docs/spikes/SPIKE_RESULTS.md) (multi-OS packaging still open).
- [x] Packaging sizes and startup times recorded. *(Windows 2026-07-16 — NSIS 6.84 MiB, MSI 8.79 MiB, `desktop.exe` 19.54 MiB, `dist` 5.75 MiB; cold-start time-to-window cold-ish **618 ms** / warm **~45–90 ms** via `scripts/measure-cold-start.ps1` — [docs/spikes/tauri-shell.md](docs/spikes/tauri-shell.md). **macOS/Linux packaging still open.**)*
- [x] No unresolved **critical** feasibility risks for Windows Tauri packaging *(prior `rustc` DLL/path flake mitigated with `CARGO_BUILD_JOBS=2`; unsigned MSI/NSIS produced. Multi-OS + signing remain non-blocking for this spike criterion.)*

---

## Phase 2 — Foundation vertical slice (6–8 weeks)

**Deliverables**

- Monorepo, CI, signing/dev release pipeline, schema generation, Rust core, worker IPC, app shell, settings, logging/redaction, migrations.
- Vertical slice: open vault → atomic Markdown edit → index/search → connect LLM → generate validated workflow → render → derived artifact → persist/reopen run.

**Exit criteria**

- [x] Distributable **Windows alpha**. *(Unsigned local NSIS + MSI from `npm run build:desktop` 2026-07-16; sizes in [docs/spikes/tauri-shell.md](docs/spikes/tauri-shell.md). Signing / updater / cold-start are later gates.)*
- [x] Automated tests cover the full vertical slice. *(2026-07-16: `tests/e2e/test_vertical_slice.py` / `npm run test:e2e:vertical-slice` — open vault → save note → optional intake → `workflow.generate` (live Ollama or fail-closed) → `.brainflow` artifact → session reopen. CI `smoke:vertical-slice` remains unit/tsc only; UI graph render not Playwright-automated.)*

**Status:** Foundation slice + **unsigned Windows alpha installers** + scripted vertical-slice E2E green (Ollama live on this host). Signing / updater / multi-OS still open. See [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md).

---

## Phase 3 — Knowledge workspace alpha (10–14 weeks)

**Deliverables**

- Editor modes, wikilinks/embeds, properties, links/backlinks, tags, quick switcher, command palette, search, tabs/splits, templates/daily notes, recovery, local/global graph.
- Import from Markdown/Obsidian-style vault; Bases and Canvas foundations with portable serialization.

**Exit criteria**

- [ ] Daily team use on a **10,000-note** test vault with no data loss and acceptable input latency. *(Human daily-team + WebView keystroke still required. **Catalog** measurable budgets — warm FTS/QS p95 ≪ 100 ms; open+save+search edit-cycle proxy p95 budget 50 ms — harness in `soak_bench` / [docs/spikes/soak-10k.md](docs/spikes/soak-10k.md).)*

**Status:** Knowledge-workspace alpha **implemented** in-tree — vault rail (open/create, explorer, CodeMirror source + live preview + reading modes, multi-note tabs with pin, split panes, atomic autosave, external-change awareness, drag-drop import), wikilinks/embeds/math/callouts/backlinks/tags/frontmatter basics, rename-safe link updates, heading/block navigation, FTS search + quick switcher + command palette, recovery snapshots, templates/daily stubs, Bases filterable/sortable table UI + formula columns + title/tags cell edit, Canvas board UI, bookmarks/workspaces, footnotes render + panel, local/global graph hooks via `crates/graph`. **FTS + edit-cycle catalog soak at N=10,000** recorded ([docs/spikes/soak-10k.md](docs/spikes/soak-10k.md): warm FTS p95 **0.45 ms**, QS proxy p95 **0.09 ms**, open+save+search cycle p95 **30.1 ms** ≤50 ms, no data loss). **Phase 3 exit still unchecked** (daily-team use + WebView input-latency not signed). Still open for Phase 9: full infinite canvas chrome, bulk property edit/validation, advanced Bases. See [docs/OBSIDIAN_PARITY.md](docs/OBSIDIAN_PARITY.md), [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md).

---

## Phase 4 — Universal intake and evidence index (8–12 weeks)

**Deliverables**

- Core text, PDF, Office/OpenDocument, image/OCR, tabular, code, audio/video, archive, notebook adapters.
- Normalized provenance, security/resource limits; adapter SDK; optional extended-format pack.

**Exit criteria**

- [x] Golden corpus meets extraction, location, malformed-input, and resource-bound criteria ([docs/FILE_INGESTION.md](docs/FILE_INGESTION.md)).

**Status:** Deepened — notebook, OCR path, media, OpenDocument adapters in-tree with **27** intake tests (`services/ai-worker/tests/test_intake.py`). OCR (Tesseract / `.[ocr]`) and transcription (Whisper / `.[media]`) are **optional deps**; fail closed with `NeedsAdapter` when absent. Apache Tika pack and live optional-dep matrix still open. See [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md).

---

## Phase 5 — LLM gateway and model intelligence (8–12 weeks, overlaps 4)

**Status:** mostly complete (local + cloud HTTP adapters; live cloud smoke still opt-in). Provider/pin/budget paths covered in worker tests; deterministic evals under `tests/evals` (**34** passed this consolidate run). See [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md).

**Deliverables**

- Provider adapters, health/capability probes, hardware detection, signed registry, scoring, model manager, local benchmarks, Auto/Pinned policies, budgets, provenance.

**Exit criteria**

- [x] Low/mid/high hardware fixtures select only fitting, probed models that meet benchmarks (stub harness + scoring tests; live Ollama via `BRAINFLOW_LIVE_BENCH=1`).
- [x] Registry rollback and offline cached operation verified.
- [x] Anthropic / Gemini / OpenRouter / custom have real HTTP request paths + mockable capability probes (fail-closed without keys).
- [x] `pins.assert_stable` blocks mid-run digest/name swaps (unit + eval coverage).
- [x] Token/spend `RequestBudget` wired into provider `chat` request path.

---

## Phase 6 — AI workflow kernel (12–16 weeks)

**Deliverables**

- Goal routing, domain packs, hierarchical retrieval, planner/compiler/critic/verifier, deterministic policy validation, resumable DAG execution, bounded retries, caching, provenance, safe auto-apply, approval gates.
- Domain packs: study, research, project planning first; others via same contracts.

**Exit criteria**

- [x] Deterministic CI evals for schema validity after compile, provenance fields, injection delimit resistance, cancel/resume, budget enforcement, approval gates (`tests/evals/workflow_kernel`, `tests/evals/prompt_injection`).
- [ ] Live LLM actionability / domain-rubric ≥85% **and** full red-team variance bands ([docs/EVALUATION_STRATEGY.md](docs/EVALUATION_STRATEGY.md) §9–10) — harness + one local Ollama smoke (3/3 @ 1.0 on `llama3.2:3b`) **≠** exit; deterministic fail-closed red-team runner expanded (`tests/evals/prompt_injection/runner.py`, 10 fixtures); live multi-run optional behind `BRAINFLOW_LIVE_EVAL` — still **PARTIAL**.

**Status:** Kernel + deterministic CI evals landed; live domain-rubric runner gated by `BRAINFLOW_LIVE_EVAL=1` (`tests/evals/domain_rubric`); fail-closed prompt-injection / red-team runner executes fixtures and asserts policy. Phase 6 exit remains **PARTIAL**. Backlog: [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md).

---

## Phase 7 — Graph suite (10–14 weeks, overlaps 6)

**Deliverables**

- Workflow DAG, mind map, tree/outline, knowledge graph, lineage, conversion, filters, layouts, groups/subflows, diff, path tracing, AI patch proposals, accessible semantic alternatives.

**Exit criteria**

- [ ] Keyboard/screen-reader testing passed. *(Automated §6.1 ≠ NVDA.)*
- [ ] Scale: **500** editable workflow nodes; **5,000** visible relationship nodes. *(500-node **React Flow data-prep smoke** automated — `npm run smoke:graph-ui`; mid-tier GPU pan/zoom + live canvas soak not claimed; 5k via LOD.)*

**Status:** Suite advanced — ELK Web Worker, LOD/pagination/clustering with documented limits, path tracing, group collapse, schema-valid AI patch review, GraphOutline as mandatory alternate. **Automated §6.1 focus/announce/path/patch model tests** in CI (`graphAtChecklist.test.ts`); **500-node UI data-prep smoke** (`graph-ui-smoke.ts`). **Exit NOT claimed:** live NVDA/VoiceOver unsigned; 5k relationships require LOD (not full canvas); mid-tier GPU pan/zoom not CI-gated. See [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md) §6.1, [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md).

---

## Phase 8 — GitHub sync and recovery (8–10 weeks)

**Deliverables**

- OAuth, clone/create, background commit/fetch/integrate/push, offline queue, semantic conflict UI, structural merge, secret/large-file checks, history, restore, multi-device tests.

**Exit criteria**

- [x] Forced interruption + simultaneous-edit matrices: no silent loss, no automatic force-push, understandable conflict recovery (**unit + fixture + dry-run simulation**; see [docs/GITHUB_SYNC.md](docs/GITHUB_SYNC.md) §9). Live multi-device soak remains a beta gate (manual matrix documented; leave unchecked).

**Status:** `github-sync` in-tree and deepened (LCS Markdown merge, edges-by-id JSON, rename/delete, **three-device / clock-skew / token-expiry / default-branch** fixtures, **`multi_device_dry_run` simulation**, offline queue drain, secret/large-file preflight tests, SyncPanel conflict UX). Live multi-device soak still open. See [docs/GITHUB_SYNC.md](docs/GITHUB_SYNC.md) §9, [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md).

---

## Phase 9 — Full core parity, extensibility, polish (10–14 weeks)

**Deliverables**

- Remaining Obsidian-class features per [docs/OBSIDIAN_PARITY.md](docs/OBSIDIAN_PARITY.md).
- Guided/Studio modes, personas, templates, onboarding, QOL, localization seam, settings import/export, sandboxed plugin SDK.

**Cross-cutting polish (tailoring-parity) — in-tree**

- [x] Guided / Studio experience toggle in desktop shell  
- [x] Persona presets (student, researcher, educator, PM, ops, engineer, analyst, creative)  
- [x] Theme tokens, reduced motion, high contrast hooks; `locales/en.json` seam  
- [x] Command palette + hotkeys for main actions  
- [x] Plugin SDK allowlist docs + example manifests ([docs/PLUGIN_SDK.md](docs/PLUGIN_SDK.md))  
- [x] Publish/export stub documented ([docs/PUBLISHING.md](docs/PUBLISHING.md)); parity checklist updated  

Deep vault/editor/Bases/Canvas/sync features remain Phase 3–8 owners.

**Exit criteria**

- [ ] Parity checklist items for v1 marked done or explicitly deferred with rationale.
- [ ] Novice and power-user usability studies completed.

---

## Phase 10 — Security hardening and closed beta (8–12 weeks)

**Deliverables**

- Threat-model controls, SBOM/license, LLM red team, importer fuzz, a11y audit, performance/soak, migration drills, signing/updater, backup/restore.
- Closed beta across student, researcher, educator, planner, operator, engineer, and a11y users; published known limitations.

**Hardening scaffolding (hardening-beta) — in-tree**

- [x] CI: a11y structural + best-effort axe on dist HTML; security soft-gates (`npm audit` critical + `cargo audit`); fuzz entrypoint check; **vertical-slice smoke** job  
- [x] [docs/THREAT_CONTROLS.md](docs/THREAT_CONTROLS.md) mapping  
- [x] Prompt-injection fixtures under `tests/evals/prompt_injection`  
- [x] [docs/BETA_CHECKLIST.md](docs/BETA_CHECKLIST.md) + [docs/QA_LAUNCH.md](docs/QA_LAUNCH.md)  
- [x] Crash reporting opt-in docs + log redaction module (**wired into Tauri sync/worker error logging**)  

Full live red-team / soak / signing validation still required before beta exit. A11y/security soft-gates are **not** exit criteria.

**Exit criteria**

- [ ] No critical data-loss / security / accessibility defects.
- [ ] Workflow-quality metrics reported by hardware / model / domain.

---

## Phase 11 — GA and continuous model governance

**Deliverables**

- Windows GA first; macOS/Linux when packaging and AT parity pass.
- Signed app + model-registry channels, rollback, deprecation, plugin review/revocation, recurring benchmarks.
- Mobile/web discovery only after portable contracts stabilize.

**Governance docs (ga-governance) — in-tree**

- [x] [docs/RELEASE.md](docs/RELEASE.md) — Windows-first; signed Tauri updater; deferred mobile/web  
- [x] Model registry channel/rollback docs ([MODEL_REGISTRY.md](docs/MODEL_REGISTRY.md), [RELEASE.md](docs/RELEASE.md))  
- [x] [docs/VERSIONING.md](docs/VERSIONING.md) — compatibility + deprecation  

**Exit criteria**

- [ ] Release gates in [docs/QA_STRATEGY.md](docs/QA_STRATEGY.md), [docs/RELEASE_SECURITY.md](docs/RELEASE_SECURITY.md), and [docs/PERFORMANCE_BUDGETS.md](docs/PERFORMANCE_BUDGETS.md) green for the target platform.
- [x] Documented deferral of mobile/web until shared schemas are stable.

---

## Cross-cutting constraints (all phases)

1. **Sources immutable** unless user deliberately opens externally; overlays write derived artifacts only.
2. **Fail-closed LLM** for AI workflow creation — never substitute deterministic “fake AI.”
3. **Non-destructive automation** only; destructive/remote side effects need explicit approval.
4. **Portable vault files** are user-owned truth; indexes are rebuildable and local-only.
5. **WCAG 2.2 AA** and keyboard/graph alternatives are release gates, not cleanup.
6. Avoid vaults under concurrent cloud sync roots during development and QA.
