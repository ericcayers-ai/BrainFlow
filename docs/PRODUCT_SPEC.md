# Product Specification — BrainFlow

**Status:** Normative for implementers (Phase 0)  
**Audience:** Engineering, design, QA, security  
**Related:** [NON_GOALS.md](NON_GOALS.md) · [AI_SAFETY_AND_AGENCY.md](AI_SAFETY_AND_AGENCY.md) · [ROADMAP.md](../ROADMAP.md)

---

## 1. Product definition

BrainFlow is a **workflow operating environment** for local knowledge work. It is not primarily a file browser.

### 1.1 Primary surface — AI Workflow Suite

The default landing experience includes:

1. **Goal header** — user or inferred goal, constraints, success criteria  
2. **Editable workflow graph** — versioned declarative DAG (see [WORKFLOW_IR.md](WORKFLOW_IR.md))  
3. **Execution state** — per-node status, retries, approvals, budgets  
4. **Artifact outputs** — notes, plans, flashcards, reports, schedules, etc. in the managed overlay  
5. **Evidence / provenance inspector** — source segments, confidence, model digests, run identity  

### 1.2 Secondary surfaces

- Collapsible **vault rail** (files, notes, search)  
- **Peripheral source-reference nodes** linking to immutable originals  
- File viewer / editor for BrainFlow-managed Markdown and “open original externally” for linked sources  

---

## 2. Non-negotiable behavior

### 2.1 Immutable sources

| Rule | Detail |
|------|--------|
| Default import | Link or copy per user choice; **default = link / read-only** |
| Writes | BrainFlow creates derived notes, plans, graphs, flashcards, reports, schedules, etc. under `.brainflow/` and user notes — **not** by mutating linked originals |
| External edit | User may deliberately open a source in an external editor; BrainFlow detects external change and refreshes indexes without rewriting the source |
| Overlay | AI suite orchestration writes versioned, traceable artifacts with provenance |

**Acceptance**

- AC-SRC-01: Given a linked PDF/DOCX/image, completing an AI workflow produces zero byte-level changes to the source path (hash unchanged).  
- AC-SRC-02: Delete/overwrite of a linked source is possible only via explicit user-approved action with parameters shown, never via auto-apply.  
- AC-SRC-03: Derived artifacts record `derived_from` edges to source file identity + content hash + locator.

### 2.2 Automatic execution bounds

Permit automatic execution **only** inside the non-destructive managed workspace.

**Requires explicit approval (exact action + parameters shown):**

- Deletes  
- Source overwrites  
- External messages (email, chat, webhooks)  
- Arbitrary shell / OS commands  
- Publishing / remote side effects  
- Credential use beyond declared provider calls  
- Expanding filesystem or network scopes  

**Acceptance**

- AC-EXE-01: Policy engine rejects unapproved action classes; executor never invokes them.  
- AC-EXE-02: Approval UI lists action type, tool, args, scopes, and rollback/recovery notes before consent.  
- AC-EXE-03: Safe overlay nodes (write under allowed vault paths, index updates) may auto-run when schema-valid and permission class = `safe_overlay`.

### 2.3 LLM required for AI workflows

Workflow **inference, planning, critique, and adaptation** require a **validated** LLM (local or cloud adapter that passed capability probes).

| Situation | Required behavior |
|-----------|-------------------|
| No LLM configured / unhealthy / capability probe failed | Pause AI workflow creation with **actionable setup error** |
| Deterministic helpers (parsing, schema validation, merge, search, sync) | Allowed; these are **not** AI substitutes |
| Editing, reading, search, sync without AI | Remain available |

**Forbidden:** rule-based or template-only “pretend AI” workflows presented as model-generated.

**Acceptance**

- AC-LLM-01: UI cannot proceed past “Generate workflow” without a validated provider+model portfolio for required roles.  
- AC-LLM-02: Setup error names missing component (runtime, model, probe failure) and next step (install Ollama, pull model, add API key, fix health).  
- AC-LLM-03: Eval/CI traps: any path that emits a workflow JSON without an LLM stage fails the contract test.

### 2.4 “Any file” honesty

**Definition:** Any accessible, readable file for which BrainFlow **has or can install** a safe ingestion adapter.

BrainFlow **cannot** invent unavailable semantics from:

- Corrupt or truncated files  
- Encrypted / password-locked content (without password)  
- DRM-protected media  
- Unknown proprietary formats without an adapter  

**Required:** fail explicitly, preserve the source, request password / converter / adapter — never hallucinate structure from the filename alone.

**Acceptance**

- AC-FILE-01: Unsupported/locked adapters return typed errors (`NeedsPassword`, `NeedsAdapter`, `Corrupt`, `ResourceLimit`) and leave source untouched.  
- AC-FILE-02: Planner receives only normalized `DocumentBundle` content labeled **untrusted evidence**.  
- AC-FILE-03: Golden corpus includes negative cases that assert “no workflow from filename-only.”

### 2.5 “Best local model” definition

**Best local model** = highest-scoring **validated** model or **role-based portfolio** that satisfies:

1. Current task **capability gates** (vision, tools, JSON schema, context, embeddings, …)  
2. Machine’s **measured** hardware constraints (fit with safety margin — not “barely allocates”)  
3. Ranking: quality dominant, then context, BrainFlow eval reliability, local throughput/latency floor, quantization penalty, license, energy/disk  

It is **not** a timeless model name. Absolute best = signed, refreshed catalog + local fit + workload benchmarks.

Policies: Auto · Balanced · Maximum Quality · Maximum Privacy · Low Latency · Pinned.

**Acceptance**

- AC-MOD-01: Selection output includes digests, scores, memory estimate, download size, license, and rejected alternatives with reasons.  
- AC-MOD-02: Active and historical runs never silently change model digests mid-run.  
- AC-MOD-03: If selected model disappears/fails → pause; Auto reselection only if user authorized automatic LLM reselection; never drop to deterministic workflow generation.

### 2.6 Reproducibility

Every workflow run must pin and retain:

| Field | Purpose |
|-------|---------|
| Model identity + content digest | Exact weights/runtime binding |
| Prompt-pack / domain-pack version | Pack reproducibility |
| Input content hashes | Sources and prompts boundary |
| Workflow IR schema version | Graph interpretability |
| Settings snapshot (privacy redacted where needed) | Policy/budgets |
| Generated output hashes / artifact IDs | Outcome integrity |
| Validator and policy versions | Authority chain |

**Acceptance**

- AC-REP-01: Reopening a completed run shows pinned digests and identical IR version.  
- AC-REP-02: Executor refuses mid-run model swap.  
- AC-REP-03: Export bundle includes enough metadata to re-validate schema and provenance offline.

---

## 3. Personas and progressive disclosure

| Mode | Intent |
|------|--------|
| **Guided** | Import → goal → review proposal → watch execution with plain-language explanations |
| **Studio** | Edit nodes, constrained templates, providers, policies, budgets, schemas, packs |

Persona presets (student, researcher, educator, PM, ops, engineer, analyst, creative) change terminology, starters, default artifacts, and explanation depth — **not** core capabilities.

---

## 4. Platform scope (v1)

| In scope | Deferred |
|----------|----------|
| Desktop: Windows first, continuous macOS/Linux builds | Mobile/web clients until portable contracts stable |
| Local vaults + GitHub sync | Proprietary Obsidian Sync |
| Sandboxed first-party plugins | Full Obsidian community plugin API compatibility |

---

## 5. Data ownership

- User owns portable Markdown, attachments, `.brainflow/workflows`, artifacts, graphs, templates, `vault.json`.  
- Credentials, absolute paths, device IDs, indexes, embeddings, private logs → **local app data only**.  
- Private GitHub remotes are access-controlled, **not** end-to-end encrypted (communicate honestly — [PRIVACY.md](PRIVACY.md)).

---

## 6. Release acceptance (product-level)

A release candidate claiming Phase N exit must satisfy the phase exit criteria in [ROADMAP.md](../ROADMAP.md) plus the cross-cutting ACs in §2. GA additionally requires security, a11y, QA, and performance gates documented in sibling docs.

**Phase 0 exit (this document set):** every item in §2 has an AC with an owner doc / future test id.

| Contract | ACs | Primary doc |
|----------|-----|-------------|
| Immutable sources | AC-SRC-* | This file · AI_SAFETY |
| Execution bounds | AC-EXE-* | AI_SAFETY · SECURITY |
| LLM-required | AC-LLM-* | This file · MODEL_* |
| File honesty | AC-FILE-* | FILE_INGESTION |
| Best model | AC-MOD-* | MODEL_SELECTION |
| Reproducibility | AC-REP-* | WORKFLOW_IR · EVALUATION |

---

## 7. Glossary

| Term | Meaning |
|------|---------|
| Overlay | Derived, BrainFlow-managed workspace content linked to immutable sources |
| DocumentBundle | Normalized ingestion output with provenance and locators |
| Portfolio | Role-split models (planner, multimodal, embeddings) selected together |
| Safe overlay | Permission class auto-applicable inside allowed vault paths |
| Validated LLM | Provider+model that passed health and capability probes for required roles |
