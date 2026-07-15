# ADR 0002: Sidecar / Worker Transport

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** Product roadmap / Phase 0

## Context

Ingestion and AI orchestration run in a supervised **Python** worker. A naive design exposes HTTP on `localhost` with a fixed port, which creates local attack surface (other processes calling the worker) and port conflicts.

## Decision

Use a **private inherited pipe or platform IPC channel** between Rust core and the Python worker. Exchange **schema-validated** JSON-RPC requests and events from shared `packages/schemas`. Do **not** bind an unauthenticated fixed localhost port.

## Consequences

**Positive:** Reduces local confused-deputy/SSRF-adjacent abuse; clearer lifecycle (core owns child process).  
**Negative:** Slightly more complex than HTTP; debugging requires custom tooling.  
**Follow-up:** Phase 1 spike proved stdio JSON-RPC + optional tokenized loopback; see [../spikes/worker-ipc.md](../spikes/worker-ipc.md). CI guardrail against public TCP bind still planned ([SECURITY.md](../SECURITY.md)).
