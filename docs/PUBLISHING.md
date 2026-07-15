# Publishing and export

Local export and static-site publish stubs for Phase 9+. Remote publishing is a **side effect** and always requires explicit user approval ([AI_SAFETY_AND_AGENCY.md](AI_SAFETY_AND_AGENCY.md)).

---

## 1. Local export (planned)

| Format | Scope | Status |
|--------|-------|--------|
| Markdown bundle | Selected notes + linked attachments | Planned |
| PDF | Rendered note / artifact set | Planned |
| HTML single-file | Reading view snapshot | Planned |
| Workflow IR JSON | `.brainflow/workflows` | Exists as portable vault files |
| Graph export | Canonical graph JSON | Planned |

Sources linked as immutable imports are **not** rewritten during export; exporters copy or reference them according to user choice.

---

## 2. Static site publish (stub)

**UI:** Studio mode → “Export / publish (stub)” or command palette `export.publishStub` (`Ctrl+Shift+E`).

**Intended pipeline (not yet executed):**

1. User selects notes / artifacts / graph views to include.
2. BrainFlow generates a static site tree under a user-chosen output folder (or `.brainflow/publish/preview/`).
3. Preview opens in the **sandboxed web viewer** (no remote load by default).
4. Optional remote upload (GitHub Pages, S3, custom) shows an approval card with exact destination, files, and size.

Current behavior: in-app status message pointing here; no files written.

---

## 3. Security gates

- Disable active scripts and remote resource loading in published previews by default ([SECURITY.md](SECURITY.md)).
- Credentialed remotes use OS keychain; never store tokens in vault JSON.
- Plugin exporters may produce local packages; `publish.remote` capability is denied in v1 ([PLUGIN_SDK.md](PLUGIN_SDK.md)).

---

## 4. Acceptance criteria

- AC-PUB-01: Remote publish blocked without explicit approval UI.  
- AC-PUB-02: Static preview does not execute vault-origin scripts.  
- AC-PUB-03: Stub command remains discoverable via palette until pipeline ships.
