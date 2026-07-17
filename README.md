# BrainFlow

BrainFlow is a **desktop-first, local-first** knowledge and workflow environment. It combines Obsidian-class Markdown vault capabilities, GitHub repository sync, mandatory LLM-driven workflow generation, hardware-aware local-model selection, and multiple graph projections over one shared data model.

**Primary surface:** the AI Workflow Suite (goal, editable workflow graph, execution state, artifacts, evidence/provenance).  
**Secondary:** vault rail, source-reference nodes, and a file viewer for originals — sources stay immutable by default.

> Status: **Unsigned Windows alpha** (`v0.1.2`) — foundation vertical slice + knowledge-workspace scaffolding + workflow-first shell UX revamp. Phase 1 sizes/startup recorded; scripted vertical-slice E2E and CI green. See [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md). **Not GA.** Installers are not code-signed; macOS/Linux packaging is not verified. Repository / releases: [github.com/ericcayers-ai/BrainFlow](https://github.com/ericcayers-ai/BrainFlow/releases/tag/v0.1.2).

## Product contract (summary)

| Principle | Behavior |
|-----------|----------|
| Workflow-first | Default landing is the Workflow Suite, not a file browser |
| Immutable sources | Linked imports are read-only; BrainFlow writes versioned derived artifacts |
| LLM-required for AI | No validated LLM → AI workflow creation pauses; no rule-based “pretend AI” |
| Honest “any file” | Only files with a safe adapter; fail closed on DRM/corrupt/unknown semantics |
| Best local model | Highest-scoring validated fit for task + measured hardware — not a fixed model name |
| Reproducibility | Pin model digest, prompt-pack, input hashes, schema version, settings per run |

Full contract: [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) · Non-goals: [docs/NON_GOALS.md](docs/NON_GOALS.md) · Agency: [docs/AI_SAFETY_AND_AGENCY.md](docs/AI_SAFETY_AND_AGENCY.md)

## Architecture

```
apps/desktop          React + TypeScript + Vite + Tauri 2 shell
crates/*              Rust core: vault, storage, graph, sync, policy, app-core
services/ai-worker    Supervised Python worker (JSON-RPC stdio, Ollama gateway)
packages/schemas      Versioned JSON Schemas (Workflow IR + run metadata)
packages/plugin-sdk   Capability-based plugin manifest stub
docs/                 Product, architecture, spikes, security, QA
```

Spike outcomes: [docs/spikes/SPIKE_RESULTS.md](docs/spikes/SPIKE_RESULTS.md)

## Run the foundation vertical slice (local)

### Prerequisites

- Node.js 20+
- Rust stable (MSVC on Windows) + [Tauri 2 prerequisites](https://v2.tauri.app/start/prerequisites/)
- Python 3.11+
- [Ollama](https://ollama.com) running with at least one model (e.g. `ollama pull llama3.2:3b`)

### 1. Install JS workspaces

```bash
cd BrainFlow
npm install
```

### 2. Install Python worker

```bash
cd services/ai-worker
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
pip install -e ".[dev]"
cd ../..
```

The Tauri shell prefers `services/ai-worker/.venv/Scripts/python.exe` automatically (or set `BRAINFLOW_PYTHON`).

### 3. Run Rust crate tests (optional)

```bash
cargo test -p brainflow-vault -p brainflow-storage
```

### 4. Start the desktop slice

```bash
# from repo root
npm run dev:desktop
# or
cd apps/desktop && npm run tauri dev
```

Release-style local build (unsigned):

```bash
npm run build:desktop
```

### Slice checklist in the UI

1. **Open vault** — pick a folder (prefer non-OneDrive). Layout `.brainflow/` + `notes/` is created.
2. **Edit / save** a Markdown note (`notes/welcome.md`) — atomic write.
3. Confirm **LLM health** (fail-closed if Ollama is down).
4. **Generate workflow** — Ollama produces schema-validated Workflow IR.
5. **Graph** — React Flow + ELK renders the DAG.
6. **Artifact** — Markdown under `.brainflow/artifacts/<workflow>/<run>/summary.md`.
7. **Reopen** — restart the app; session restores vault, note, workflow, and run metadata from `%LOCALAPPDATA%\BrainFlow\session.json`.

Indexes live under `%LOCALAPPDATA%\BrainFlow\indexes\` (not inside the vault).

### Automated vertical-slice E2E

```bash
npm run test:e2e:vertical-slice
# or: services/ai-worker/.venv/Scripts/python.exe -m pytest tests/e2e/test_vertical_slice.py -v
```

Requires Ollama up for the live generate path (otherwise the test fail-closes as designed). Cold-start of the release binary: `npm run measure:cold-start`.

### Frontend-only (no Tauri window)

```bash
cd apps/desktop
npm run dev
```

Vite UI loads, but vault/LLM commands require the Tauri shell.

## OneDrive / cloud sync warning

Vaults under OneDrive/Dropbox/iCloud can race with Git and watchers. Prefer a local disk path. Machine indexes stay in OS app data — see [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

## Documentation map

| Document | Purpose |
|----------|---------|
| [ROADMAP.md](ROADMAP.md) | Phases and exit criteria |
| [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md) | Prioritized open work vs GA bar |
| [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) | Product contract |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [docs/spikes/SPIKE_RESULTS.md](docs/spikes/SPIKE_RESULTS.md) | Phase 1 spike measurements |
| [docs/WORKFLOW_IR.md](docs/WORKFLOW_IR.md) | Declarative DAG semantics |
| [docs/OBSIDIAN_PARITY.md](docs/OBSIDIAN_PARITY.md) | Core parity checklist |
| [docs/PLUGIN_SDK.md](docs/PLUGIN_SDK.md) | Plugin capability allowlist |
| [docs/RELEASE.md](docs/RELEASE.md) | GA order, updater, deferred mobile/web |
| [docs/VERSIONING.md](docs/VERSIONING.md) | Compatibility and deprecation |
| [docs/BETA_CHECKLIST.md](docs/BETA_CHECKLIST.md) | Closed beta matrix |
| [docs/adr/](docs/adr/) | Architecture decisions |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Setup, PR norms, tests |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug/feature templates live under `.github/ISSUE_TEMPLATE/`.

## License

Licensed under the [Apache License 2.0](LICENSE). Copyright 2026 BrainFlow contributors.
