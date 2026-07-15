# Contributing to BrainFlow

Thanks for your interest in BrainFlow. This project is a **desktop-first, local-first** knowledge and workflow environment (Tauri + React + Rust crates + Python AI worker). It is currently an **unsigned Windows alpha** — not GA. See [ROADMAP.md](ROADMAP.md) and [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md) for honest status.

Please also read the [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

### Prerequisites

- Node.js 20+
- Rust stable (MSVC toolchain on Windows) and [Tauri 2 prerequisites](https://v2.tauri.app/start/prerequisites/)
- Python 3.11+
- [Ollama](https://ollama.com) with at least one model (for live LLM paths), e.g. `ollama pull llama3.2:3b`

### Install

```bash
npm install

cd services/ai-worker
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
pip install -e ".[dev]"
cd ../..
```

Run the desktop app:

```bash
# from repo root
npm run dev:desktop
# or
cd apps/desktop && npm run tauri dev
```

Prefer vault folders on a local disk (not OneDrive/Dropbox) when developing.

## Branch and pull request expectations

1. Open an issue first for non-trivial changes when you can.
2. Branch from `master` (or `main` if that becomes default) with a short, descriptive name.
3. Keep PRs focused; prefer small, reviewable diffs.
4. Fill out the pull request template (summary, test plan, docs, breaking changes).
5. Do not claim CI/signing/GA readiness that is not evidenced in-tree.
6. **Do not edit plan files under `.cursor/plans/`** — those are local agent planning artifacts, not project source of truth.

## Coding norms

- Match existing style in the area you touch (Rust crates, React/TS desktop, Python worker, docs).
- Prefer honest fail-closed behavior for LLM and file adapters; do not add “pretend AI” fallbacks.
- Avoid inventing product claims (signed installers, multi-OS packaging green, GA) that contradict [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md).
- Update or add docs when behavior or contracts change (`docs/`, README links as needed).

## Tests and checks

Run what applies to your change:

```bash
# Vertical-slice smoke (CI-aligned; may not need live Ollama depending on path)
npm run smoke:vertical-slice

# Scripted vertical-slice E2E (Ollama required for live generate; fail-closed otherwise)
npm run test:e2e:vertical-slice

# Desktop TypeScript
npm run typecheck -w desktop

# Schemas
npm run test:schemas

# Rust workspace crates (align with CI)
cargo test -p brainflow-vault -p brainflow-storage -p brainflow-policy -p brainflow-graph -p brainflow-sync -p brainflow-app-core

# Python worker
cd services/ai-worker
pytest
```

CI currently runs schema/web typecheck/build, vertical-slice smoke, soft-fail security placeholders, Rust crate tests, and Python worker tests. Full UI Playwright and signed packaging are **not** claimed.

## License and contributions

By contributing, you agree that your contributions are licensed under the project’s [Apache License 2.0](LICENSE). There is no separate CLA at this time; the Apache-2.0 contribution terms apply (see LICENSE §5).

## Good first issues

Look for issues labeled `good first issue` (when present), or pick small, well-scoped work from [docs/REMAINING_GAPS.md](docs/REMAINING_GAPS.md), for example:

- Docs clarity / typo fixes that match product reality
- Test coverage for an existing fail-closed path
- Narrow accessibility or UX polish called out in docs without inventing new product scope
- CI or script hardening for checks that already exist

If unsure, open a draft issue describing the gap and proposed approach before a large PR.
