# Spike: Storage / FTS

**ADR:** [0004-storage.md](../adr/0004-storage.md)

## What we built

`crates/storage` opens a bundled SQLite DB, creates `notes_meta` + FTS5 `notes_fts`, upserts, and MATCH-queries.

## Results

- Unit test `fts_roundtrip` validates insert + search.
- Catalog path in the desktop app: `%LOCALAPPDATA%\BrainFlow\indexes\catalog.sqlite`.

## Decision

Proceed with rusqlite + FTS5. Vectors deferred. Never place `index.sqlite` inside cloud-synced vault roots.
