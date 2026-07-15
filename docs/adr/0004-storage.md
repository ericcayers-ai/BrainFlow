# ADR 0004: Storage

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** Product roadmap / Phase 0

## Context

BrainFlow needs fast search and embeddings locally while keeping portable user ownership of notes and workflows. A pure file-only index is too slow for 10k+ note vaults; a proprietary DB as source of truth fights portability and sync.

## Decision

- **Portable source of truth:** Markdown, attachments, versioned workflow JSON, graph exports under the vault (`.brainflow/…`).  
- **Local rebuildable catalog:** **SQLite** with **FTS5** and per-embedding-profile vector indexes in OS app data.  
- Indexes must be deletable and deterministically rebuilt.  
- Never store credentials, absolute secret material, or device-private logs in portable vault files ([DATA_MODEL.md](../DATA_MODEL.md)).

## Consequences

**Positive:** Sync-friendly vaults; machine-specific speed; clear rebuild story.  
**Negative:** Must handle index invalidation and embedding profile migrations carefully.  
**Follow-up:** FTS5 rusqlite sketch passed ([../spikes/storage-fts.md](../spikes/storage-fts.md)); vector profile + rebuild drills in later phases.
