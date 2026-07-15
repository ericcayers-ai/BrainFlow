# Data Model

Portable vault layout, local-only derived data, and identity rules. Schema versions for workflow/graph live in sibling docs; this file owns **where bytes live** and **what may sync**.

---

## 1. Ownership principle

| Layer | Owner | Syncs via Git? | Rebuildable? |
|-------|-------|----------------|--------------|
| User Markdown, attachments | User | Yes | N/A (source of truth) |
| `.brainflow/workflows`, `artifacts`, `graphs`, `templates`, `vault.json` | User / BrainFlow overlay | Yes (portable) | Partial |
| `index.sqlite`, embeddings, thumbnails, caches | Machine | **No** | **Yes** |
| Secrets, provider keys, device IDs | Machine / OS keychain | **No** | N/A |

**Absolute paths, credentials, device identifiers, private logs, and indexes must never appear in portable vault files.**

---

## 2. Portable vault layout

```text
<vault-root>/
  README.md                    # optional user notes
  notes/ …                     # user Markdown (any folder structure)
  attachments/ …               # optional convention; free-form OK
  .brainflow/
    vault.json                 # portable settings only
    workflows/                 # versioned declarative workflow IR (JSON)
    artifacts/                 # approved/generated portable artifacts
      <workflow-id>/
        <run-id>/
          …
    graphs/                    # user-authored graph state + view metadata
    templates/                 # workflow, note, study, planning, domain templates
  .gitignore                   # BrainFlow-managed exclusions for sync
  .git/                        # when GitHub sync enabled
```

### 2.1 `vault.json` (portable)

Allowed examples:

- Display preferences that are not device-specific (theme id, density)  
- Default domain pack ids  
- Sync remote URL **identifier** (not tokens)  
- Feature toggles for core modules  

Forbidden:

- API keys, OAuth tokens  
- Absolute filesystem paths  
- Machine hardware fingerprints  
- Index paths, embedding model cache paths  
- Private diagnostics logs  

### 2.2 Workflows and artifacts

- Workflows: see [WORKFLOW_IR.md](WORKFLOW_IR.md) — **never executable code**.  
- Artifacts grouped by `workflow-id` / `run-id` for provenance and cleanup.  
- Artifact formats: Markdown, JSON, CSV, PDF export, etc., as declared by node contracts.

### 2.3 Graphs

User view state and projections metadata; canonical typed graph also materialized in local index for query performance, with portable export under `.brainflow/graphs` for sync.

---

## 3. Local-only app data

Typical OS app-data locations (illustrative):

| Platform | Example |
|----------|---------|
| Windows | `%APPDATA%\BrainFlow\` or `%LOCALAPPDATA%\BrainFlow\` |
| macOS | `~/Library/Application Support/BrainFlow/` |
| Linux | `~/.local/share/brainflow/` |

Contents:

- `index.sqlite` (+ WAL)  
- Embeddings / vector tables (per embedding profile)  
- Thumbnails, extraction caches  
- Model-registry snapshots (cached signed manifests)  
- Run-event caches (may also mirror durable events into vault selectively later)  
- Crash reports (redacted, opt-in upload)  
- Secret references (keychain account ids), not raw secrets  

**Deletes of indexes are safe:** next open rebuilds from vault + sources.

---

## 4. File identity

Every tracked file gets:

| Field | Purpose |
|-------|---------|
| `file_id` | Stable UUID |
| `content_hash` | Cryptographic hash of bytes |
| `path` | Current relative (vault) or linked absolute (sources) |
| `path_history` | Prior paths for rename survival |
| `mtime` / size | Change detection |
| `origin` | `vault` \| `linked_source` \| `imported_copy` |

References (wikilinks, graph edges, evidence locators) prefer `file_id` + content hash + structural locator (page, heading path, sheet, timestamp), not raw absolute paths.

---

## 5. Linked sources vs copies

| Mode | Default | Bytes in vault? | Mutation by BrainFlow |
|------|---------|-----------------|------------------------|
| Link | **Yes** | No (pointer + metadata) | Never without approval |
| Copy | Opt-in | Yes under managed import area | Treat as vault-owned copy; still prefer derive-over-mutate |

Linked sources outside the vault root require explicit capability grant and appear in a sources registry (portable metadata without copying bytes when possible).

---

## 6. Cloud sync roots (OneDrive, Dropbox, iCloud)

**Risk:** Git + cloud sync + file watchers → conflict copies, partial writes, duplicate UUIDs.

**Required UX:** On vault open, detect known sync roots; show warning; recommend local disk. Document OS exclusion of `index`/cache dirs. Root `.gitignore` already ignores conflict markers and local caches — keep portable `.gitignore` in vault aligned.

Do not use OneDrive “Files On-Demand” placeholders as authoritative content without hydration checks.

---

## 7. Index rebuild contract

Rebuild must:

1. Walk vault portable files + registered linked sources.  
2. Re-parse frontmatter, links, properties.  
3. Re-ingest when content hash changes.  
4. Re-embed only when embedding profile or content changes (or policy says full rebuild).  
5. Preserve `file_id` via path history / sidecar identity map when possible.

Identity map for linked sources may live in portable `.brainflow/` as non-secret metadata (`sources.json`) — hashes and relative logical ids only.

---

## 8. Migration

- Every persisted schema (`vault.json`, workflow IR, graph files) carries `schema_version`.  
- Migrations are forward functions with tests; rollback via snapshot before migrate.  
- Never write half-migrated IR; use temp + atomic rename.

---

## 9. Acceptance criteria

- AC-DM-01: Committing a vault never includes `index.sqlite`, embeddings, or secrets.  
- AC-DM-02: Opening vault on second machine rebuilds search without portable index files.  
- AC-DM-03: `vault.json` schema validation rejects credential-shaped fields.  
- AC-DM-04: Rename note updates links via identity; graph edges survive.  
- AC-DM-05: Cloud-sync-root warning fires in UX tests for fixtures under simulated OneDrive paths.
