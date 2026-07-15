# UX Principles

Design guidance for BrainFlow’s progressive disclosure: **Workflow Suite first**, vault and file viewer secondary. Complements [PRODUCT_SPEC.md](PRODUCT_SPEC.md) and [ACCESSIBILITY.md](ACCESSIBILITY.md).

---

## 1. Product posture

1. **Orchestration over browsing** — Default landing: goal, graph, execution, artifacts, evidence. Vault rail collapses; originals are peripheral references.  
2. **Honesty over magic** — Fail closed with actionable errors (LLM missing, adapter missing, conflict). Never fake AI.  
3. **Derived over destructive** — Celebrate overlays and provenance; make “open original” explicit and rare.  
4. **Progressive disclosure** — Guided vs Studio; same engine, different chrome.  
5. **Evidence visible** — Provenance inspector is first-class, not a buried advanced tab.

---

## 2. Guided vs Studio

| | Guided | Studio |
|---|--------|--------|
| Goal | Confidence and clarity | Control and precision |
| Graph | Readable status, limited edit | Full edit, budgets, packs |
| Approvals | Plain-language consequences | Exact args + scopes |
| Explanations | Plain language | Technical detail available |

Personas change **vocabulary, templates, default artifacts, explanation depth** — not capabilities.

---

## 3. Composition rules

- One primary job per major view.  
- Workflow Suite viewport: goal + graph + status + primary CTA; defer secondary marketing clutter.  
- Peripheral file nodes stay visually compact; selection opens evidence drawer.  
- Prefer semantic design tokens for themes (compact/comfortable density, dyslexia-friendly options, zoom).  
- Motion: purposeful status/layout transitions; respect reduced motion.

*(When implementing net-new marketing surfaces, also follow the frontend visual rules in project user preferences. In-app tool UI should prioritize clarity and a11y over ornamental hero layouts.)*

---

## 4. Feedback patterns

| Event | UX |
|-------|-----|
| LLM unavailable | Blocking setup card with steps |
| Adapter failure | Typed error + next action |
| Approval needed | Modal/panel with exact parameters |
| Sync conflict | Side-by-side choices, recovery copies noted |
| Model recommendation | Transparent score card + alternatives |
| Long jobs | Determinate progress when known; cancel always |

---

## 5. Commandability

Global command palette, hotkeys, slash commands, context menus, bulk actions — keyboard parity with pointer. Discoverability: shortcut cheat sheet; no essential action mouse-only.

---

## 6. Empty and first-run states

- First run: link/import → goal → propose workflow (after LLM ready) → watch run.  
- Empty vault: encourage import or template, not a blank editor as hero.  
- Warn if vault path is under OneDrive/Dropbox before heavy sync/index.

---

## 7. Content trust UI

Always label:

- Untrusted evidence  
- Source fact / inference / recommendation / uncertainty  
- Cloud-bound payloads when leaving the device  

---

## 8. Acceptance criteria

- AC-UX-01: Cold start Guided path does not require Studio concepts.  
- AC-UX-02: Source nodes never imply the file is the editable document of record.  
- AC-UX-03: Every destructive/remote action reuse shared approval pattern.  
- AC-UX-04: Persona switch does not hide Workflow Suite or sync.
