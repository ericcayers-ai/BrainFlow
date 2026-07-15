# ADR 0005: Git Strategy

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** Product roadmap / Phase 0

## Context

Multi-device sync is required without Obsidian Sync. Exposing raw Git CLI to users or to AI tools is error-prone (force pushes, half-finished ops, credential leaks). AI-driven Git is unsafe.

## Decision

- Implement sync as an **embedded Git state machine** in Rust (`crates/sync`), not shelling out to ad-hoc commands from the UI or worker.  
- **GitHub** OAuth/App auth with minimal scopes; tokens in OS keychain.  
- Non-destructive fetch/integrate/validate/push; **never automatic force-push**.  
- Semantic Markdown merge + structural JSON merge by stable IDs; conflict UI mandatory.  
- Git is **not** an AI tool ([GITHUB_SYNC.md](../GITHUB_SYNC.md)).  
- Default vault `.gitignore` excludes local indexes/caches/secrets.

## Consequences

**Positive:** Predictable recovery; testable state machine; safer multi-device.  
**Negative:** Must implement/own merge UX and edge cases (SSO, LFS opt-in, rename races).  
**Follow-up:** Spike chose gitoxide-primary / git2 escape hatch ([../spikes/git-ops.md](../spikes/git-ops.md)); Phase 8 conflict matrix including interruptions remains.
