# ADR 0001: Tauri vs Electron

- **Status:** Accepted (provisional; revisit if Phase 1 spikes fail criteria)
- **Date:** 2026-07-15
- **Deciders:** Product roadmap / Phase 0

## Context

BrainFlow needs a desktop shell with strong filesystem/Git/OS security integration, smaller distribution footprint where possible, and a React UI. Electron is the common alternative with mature tooling but typically larger installs and a different privilege model.

## Decision

Use **Tauri 2** as the default desktop shell with React/TypeScript frontend and Rust core. Continuously build on Windows, macOS, and Linux. Consider Electron **only** if Phase 1 spikes show Tauri fails measurable criteria for:

- Worker/sidecar supervision and packaging reliability  
- Accessibility / assistive technology parity  
- Critical native integration blockers  

## Consequences

**Positive:** Least-privilege capabilities, CSP fits, Rust core for vault/sync/policy, smaller relative footprint.  
**Negative:** Smaller ecosystem than Electron; WebView differences across OS; packaging/signing learning curve.  
**Follow-up:** Phase 1 packaging/startup benchmarks; measured Windows spike results in [../spikes/SPIKE_RESULTS.md](../spikes/SPIKE_RESULTS.md) and [../spikes/tauri-shell.md](../spikes/tauri-shell.md).
