# Obsidian Core Parity Checklist



Parity is defined by **user outcomes**, not proprietary code or immediate compatibility with every community plugin. Do **not** claim full Obsidian plugin API compatibility in v1.



Status legend: `☐` planned · `☑` done · `◎` partial · `—` deferred with rationale



Track against [ROADMAP.md](../ROADMAP.md) Phases 3 and 9.



**Knowledge-workspace (Phase 3 alpha) status:** vault/editor foundations plus live preview/reading, pinned tabs, split panes, rename-safe wikilinks, heading/block navigation, Bases table UI (filter/sort + formula columns + title/tags cell edit), Canvas board UI, bookmarks/workspaces, footnotes render + view, unique/random notes, word count, slash commands, page-preview hover, and schema suggestions are in-tree. Full infinite canvas chrome, bulk property edit/validation, and advanced Bases remain Phase 9.



---



## 1. Foundation capabilities



| Outcome | Status | Notes |

|---------|--------|-------|

| Local vault open/create | ☑ | Tauri dialogs + `brainflow_vault::{open,create}_vault` |

| File explorer | ☑ | Collapsible vault rail tree |

| Tabs, pinned tabs, split panes | ☑ | Multi-note tabs with pin; split pane (toolbar / double-click tab) |

| Drag-and-drop | ☑ | Drop text/Markdown onto editor panel → `notes/` or `attachments/` |

| Recent files | ◎ | Session restore + quick switcher |

| Safe atomic autosave | ☑ | Debounced atomic writes + pre-save snapshots |

| Undo/redo | ◎ | Editor buffer undo; file-level via snapshots |

| Restore after crash | ◎ | `.brainflow/local/recovery` snapshots |

| External-change detection | ☑ | Hash/mtime poll + reload affordance |

| Native “open source file” (external) | ☐ | Immutable-source model — Phase 9 polish |



### Markdown & editing



| Outcome | Status | Notes |

|---------|--------|-------|

| Source mode | ☑ | CodeMirror 6 |

| Live preview | ☑ | Side-by-side source + sanitized GFM/HTML preview |

| Reading mode | ☑ | Preview-only surface |

| Headings, lists, task lists, tables | ◎ | GFM via marked + CM markdown lang |

| Footnotes | ☑ | `[^id]` / `[^id]:` + `^[inline]` in preview; Footnotes panel in vault rail |

| Code blocks | ◎ | Fenced blocks render; no syntax themes yet |

| Math | ☑ | KaTeX `$…$` / `$$…$$` in preview |

| Callouts | ☑ | `> [!note]` / tip / warning (common Obsidian forms) |

| Comments | ☐ | |

| Embeds | ☑ | `![[note]]` / heading / block embeds in preview |

| Attachments | ◎ | Drag-drop import path; no media gallery |

| Link aliases | ☑ | `[[target\|alias]]` |

| Wikilinks | ☑ | Parse + preview click navigation |

| Heading links | ☑ | `[[Note#Heading]]` scrolls preview (`#h-…` ids) |

| Block references | ☑ | `[[Note#^id]]` / `^id` anchors in preview |

| Rename-safe link updates | ☑ | `rename_note` rewrites `[[…]]` and `![[…]]` vault-wide |



### Properties



| Outcome | Status |

|---------|--------|

| Frontmatter/properties typed fields | ◎ string/list basics |

| Aliases, tags, dates, links, lists | ◎ aliases + tags |

| Schema suggestions | ☑ | Vault-wide key freq + samples in Properties panel; click to set on current note |

| Bulk edit | ☐ |

| Validation | ☐ |



### Search & navigation primitives



| Outcome | Status |

|---------|--------|

| Fast text/property/path/tag search | ☑ FTS5 + `tag:` |

| Saved searches | ☐ |

| Query syntax | ◎ basic FTS + tag: |

| Fuzzy quick switcher | ☑ Ctrl+P |

| Command palette | ☑ Ctrl+K |

| Backlinks | ☑ |

| Outgoing links | ☑ |

| Unlinked mentions | ◎ unresolved wikilinks listed |

| Local graph | ☑ hooks via `knowledge_graph` |

| Global graph | ☑ hooks via `knowledge_graph` |

| Tags view | ◎ tags in links panel + FTS |

| Relationship filters | ☐ graph-suite |



---



## 2. Navigation and organization (core-feature coverage)



| Feature | Status | Phase |

|---------|--------|-------|

| File Explorer | ☑ | 3 |

| Quick Switcher | ☑ | 3 |

| Command Palette | ☑ | 3 |

| Bookmarks | ☑ | 9 — `.brainflow/bookmarks.json` + rail panel / command |

| Search | ☑ | 3 |

| Tags | ◎ | 3 |

| Random Note | ☑ | 9 — command + tab bar |

| Workspaces | ☑ | 9 — save/restore tabs, split, editor mode, surface under `.brainflow/workspaces/` |

| Page preview | ☑ | 9 — hover tooltip on preview wikilinks |



---



## 3. Note workflows



| Feature | Status | Phase |

|---------|--------|-------|

| Daily Notes | ☑ | 3 |

| Templates | ☑ stubs under `.brainflow/templates` | 3 |

| Unique Note Creator | ☑ | 9 — timestamped `notes/YYYYMMDDHHmmss.md` |

| Note Composer | ☐ | 9 |

| Outline | ◎ via graph suite outline | 3–9 |

| Word Count | ☑ | 9 — status line + Footnotes panel + command |

| Slash Commands | ☑ | 9 — `/` menu in source/live (headings, lists, callout, footnote, …) |

| Footnotes View | ☑ | 9 — rail panel lists defs + refs |

| Format Converter | ☐ | 9 |



---



## 4. Structured and visual work



| Feature | Status | Phase |

|---------|--------|-------|

| Properties View | ◎ links/tags panel + schema suggestions | 3 |

| Bases-style editable/filterable/sortable/formula views | ◎ | Filter/sort + portable `.base.json`; formula DSL (`len(tags)`, `word_count`, `contains`, …) + double-click title/tags cell edit |

| Infinite Canvas | ◎ | Board UI: pan/grid, drag nodes, add cards, read/write portable JSON under `.brainflow/graphs/canvas`; not full infinite zoom/minimap |

| Graph view | ◎ local/global projection hooks + suite knowledge view | 3 local/global; 7 suite |

| Slides / presentation export | ☐ | 9 |



---



## 5. Capture and resilience



| Feature | Status | Phase |

|---------|--------|-------|

| Audio Recorder + local transcription option | ☐ | 9 |

| File recovery snapshots | ☑ | 3 |

| Importers (Markdown/Obsidian-style vault) | ◎ open existing Markdown vault + drag-drop files | 3 |

| Restore history | ◎ latest snapshot restore | 3–8 |



---



## 6. Web / output



| Feature | Status | Phase |

|---------|--------|-------|

| Sandboxed web viewer | ☐ | 9 |

| PDF/HTML/Markdown export | ☐ | 9 |

| Publish pipeline → static site | ◎ command stub | 9 |

| Remote publishing approval gate | ☐ | 9 — required |



---



## 7. Sync



| Feature | Status | Notes |

|---------|--------|-------|

| GitHub repository sync | ◎ owned by sync agent / SyncPanel | Replaces Obsidian Sync |

| Offline editing | ☑ | |

| History | ◎ | Git history via sync |

| Conflict visibility | ◎ | SyncPanel |

| Multi-device | ☐ | |



---



## 8. Tailoring



| Feature | Status | Phase |

|---------|--------|-------|

| Themes | ◎ tokens / contrast / density | 9 |

| CSS tokens / snippets | ◎ | 9 |

| Hotkeys | ◎ | 9 |

| Plugin manager (sandboxed) | ☐ | 9 |

| Core feature toggles | ☐ | 9 |

| Workspace layouts | ☑ | 9 — same as Workspaces (named layouts) |

| Import/export of settings | ☐ | 9 |



---



## 9. Canvas interoperability



| Feature | Status | Notes |

|---------|--------|-------|

| JSON Canvas import/export where practical | ◎ | BrainFlow portable canvas JSON read/write + board UI; full `.canvas` interop not claimed |



---



## 10. Explicit non-parity (v1)



| Item | Status |

|------|--------|

| Full Obsidian community plugin API | — Deferred; optional investigation after core API stabilizes |

| Obsidian Sync proprietary protocol | — Out of scope ([NON_GOALS.md](NON_GOALS.md)) |

| Mobile apps | — Deferred to post-desktop contract stability |



---



## 11. Exit mapping



- **Phase 3 exit:** Foundation capabilities + daily team use on 10k-note vault.  
- **Phase 9 exit:** Checklist items for v1 marked done or explicitly deferred with rationale; usability studies complete.

