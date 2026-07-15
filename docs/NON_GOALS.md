# Non-Goals

Explicit exclusions for BrainFlow v1 and near-term roadmap. If a request conflicts with this list, prefer the product contract in [PRODUCT_SPEC.md](PRODUCT_SPEC.md).

---

## Product positioning

1. **Not a general file manager** — browsing and managing arbitrary filesystem trees is secondary to workflows and vault knowledge work.  
2. **Not a cloud-first SaaS** — desktop local-first is the product; hosted multi-tenant vault hosting is out of scope for v1.  
3. **Not “AI that always works without a model”** — no rule-based fake planner to paper over missing LLMs.  
4. **Not an unbounded autonomous agent** — no open-ended tool loops, unrestricted shell, or unsupervised remote side effects.

---

## Data and files

5. **Not source mutation by default** — AI does not “fix your PDF/DOCX in place.”  
6. **Not a guarantee of semantics for every binary** — DRM, encryption without credentials, unknown proprietary formats, and corrupt files are explicit failures.  
7. **Not a replacement for specialized CAD/GIS/scientific suites** — restricted adapters extract what is safely possible; deep authoring stays in domain tools.  
8. **Not silent cloud sync for vaults** — OneDrive/Dropbox/iCloud as the vault home is discouraged; BrainFlow will warn, not optimize for that race condition.

---

## Sync and collaboration

9. **Not Obsidian Sync** — GitHub (or later equivalent Git remotes) replaces proprietary sync.  
10. **Not real-time CRDT co-editing** in v1 — multi-device via Git with conflict visibility, not Google-Docs-style live cursors.  
11. **Not automatic force-push or history rewrite** — sync state machine never force-pushes without explicit, rare user action.  
12. **Not end-to-end encrypted Git by default** — evaluate optional encrypted vault mode only after ordinary merge/recovery is proven.

---

## Compatibility

13. **Not full Obsidian community plugin API compatibility** in v1 — first-party sandboxed extension points only; optional compatibility investigation after core API stabilizes.  
14. **Not copy of proprietary Obsidian code** — parity is **user outcome**, not implementation cloning.  
15. **Not mobile/web GA in v1** — deferred until desktop portable contracts (schema, sync, plugins) stabilize.

---

## Models and AI

16. **Not “scraped leaderboard = registry”** — signed manifests with provenance and BrainFlow evals, not blind trust of a single public board.  
17. **Not executing model-repo code / unsafe pickles** — weights and signed metadata only under verified checksums.  
18. **Not mid-run model hopping** — digests pinned; recommendations notify, they do not rewrite history.  
19. **Not free-form prose → tool calls** — structured outputs + schema validation only.  
20. **Not storing hidden chain-of-thought as audit** — decision summaries, evidence, and tool parameters only.

---

## Security and plugins

21. **Not arbitrary DOM or native plugin code** at launch — declarative contributions + sandboxed WASM; marketplace/review later.  
22. **Not telemetry on by default** — opt-in crash/telemetry; redact contents/paths/prompts by default.  
23. **Not remote resource loading in Markdown/HTML by default** — sanitize; isolate previews; no active scripts.

---

## Delivery honesty

24. **Not marketing the full roadmap as an MVP** — phased exits; publish known limitations especially in beta.  
25. **Not Electron by default** — Tauri is preferred; Electron only if spikes fail measurable criteria ([adr/0001-tauri-vs-electron.md](adr/0001-tauri-vs-electron.md)).

---

## Revisit policy

Non-goals may move into scope only via an ADR + product-spec amendment with explicit exit criteria. Do not silently expand scope during spikes.
