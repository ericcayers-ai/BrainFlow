# Accessibility

Accessibility is a **release gate**, not a cleanup phase. Target **WCAG 2.2 AA**.

Related: [UX_PRINCIPLES.md](UX_PRINCIPLES.md) · [GRAPH_MODEL.md](GRAPH_MODEL.md) · [QA_STRATEGY.md](QA_STRATEGY.md)

---

## 1. Scope

Applies to: Workflow Suite, vault editor, search/command palette, settings, sync/conflict UI, model recommendation cards, onboarding, plugins’ declarative UI contributions.

---

## 2. Requirements

### 2.1 Perception

- Contrast meeting WCAG 2.2 AA for text and essential graphics  
- Color not sole channel (status icons + text; color-blind-safe palettes)  
- High-contrast / forced-colors themes supported  
- Zoom/reflow to 200% without loss of essential function  
- Reduced motion: honor OS preference; no essential info in motion alone  

### 2.2 Operability

- **Keyboard-only** complete paths for all primary tasks  
- Visible focus; logical focus order  
- No keyboard traps  
- Target sizes meet WCAG 2.2 where applicable  
- Graph: every node/edge operable without drag; command palette actions for connect/move/validate  

### 2.3 Understandability

- Consistent labels; accessible names for controls  
- Error identification and suggestions (LLM setup errors actionable)  
- Language of page/parts programmatic  

### 2.4 Robustness

- Valid roles/states/properties for custom widgets  
- Live regions for connection, movement, validation, run-status changes  

---

## 3. Graph-specific gate

| Requirement | Detail |
|-------------|--------|
| Semantic twin | Synchronized outline/list/table for every graph view |
| Naming | Nodes/edges expose accessible name + type + status |
| Announcements | Assertive/polite live regions per event class |
| Alternatives | Shortcut help documenting graph operations |

**Release blocker:** graph feature shipping without keyboard+SR path.

---

## 4. Assistive technology matrix

| Platform | AT | Required before GA |
|----------|----|--------------------|
| Windows | NVDA (baseline) | Yes |
| macOS | VoiceOver | Yes (macOS GA) |
| Optional | JAWS smoke | Beta desirable |

Also: keyboard-only users, zoom/reflow, forced-colors, color-vision simulation.

---

## 5. Automated CI gates

- axe (or equivalent) on critical routes — **zero critical/serious**  
- Focus-order tests on shell + workflow suite  
- Contrast checks for semantic tokens  
- Accessible-name snapshots for icon-only controls  

**Current stub:** [scripts/a11y-check.cjs](../scripts/a11y-check.cjs) runs in CI after the desktop web build (token/focus-visible/mode hooks). Replace with full axe crawls before GA.

---

## 6. Manual release checklist

- [ ] First-run/onboarding completable by keyboard  
- [ ] Create/run/review workflow without mouse  
- [ ] Resolve sync conflict via keyboard  
- [ ] NVDA: announce node select, edge create, run status  
- [ ] 200% zoom: Workflow Suite usable  
- [ ] Reduced motion: layouts still understandable  
- [ ] High contrast: status still distinguishable  

### 6.1 Graph suite keyboard / AT steps (Phase 7)

**Automated (CI — do not claim NVDA sign-off):** `npm run test:graph -w desktop`

| §6.1 step | Coverage |
|-----------|----------|
| 2 Roving tabindex (one tab stop) | `graphAtChecklist.test.ts` + `assertSingleTabStop` |
| 3 Arrow/Home/End + announce text | focus model + `announceOutlineSelection` |
| 4 Enter activate announce | `announceOutlineActivate` (assertive) |
| 5 Path status live region text | `announcePathStatus` + `shortestPath` |
| 6 Outline twin across views | `GRAPH_AT_VIEWS` projection smoke |
| 7 Escape/Tab leave canvas (model) | `isCanvasLeaveKey` — **not** live NVDA |
| 8 Invalid AI patch → error | `parseGraphPatch` rejects unknown ops |
| Focus primitives | `focusModel.test.ts` (Arrow/Home/End, roving tabindex) |

**Manual steps (required before checking Phase 7 keyboard/SR exit):**

1. Open Workflow Suite with a multi-node workflow.  
2. Tab to **Outline**; confirm only one outline item is in tab order (roving tabindex).  
3. Use **ArrowDown / ArrowUp / Home / End**; confirm focus + live region announce the selected node, and the canvas selection highlight matches.  
4. Press **Enter** on an outline item; confirm `aria-selected` / live region update.  
5. Use **Path: set anchor** then select another node; confirm path status in live region and path highlight (or “No path…”).  
6. Switch views (DAG / mind / tree / knowledge / lineage); confirm Outline remains visible and stays in sync.  
7. **NVDA (Windows):** navigate outline with arrows; hear node type + label; confirm canvas `role="application"` does not trap keyboard (Escape / Tab reaches chrome).  
8. Propose AI patch → invalid ops must surface alert; only schema-valid patches show Apply.

**Sign-off:** leave Phase 7 exit criteria unchecked until steps 1–7 pass on a GA candidate build (**NVDA recorded**). Tree/React Flow full canvas drag paths remain mouse-assisted; Outline is the mandatory keyboard twin. Automated unit coverage ≠ assistive-technology sign-off.

---

## 7. User testing cohorts

Must include: non-technical participants, screen-reader users, keyboard-only users, students, industry planners (Phase 9–10).

---

## 8. Acceptance criteria

- AC-A11Y-01: CI fails on critical/serious axe violations for gated pages.  
- AC-A11Y-02: Manual checklist signed for each GA candidate.  
- AC-A11Y-03: Graph semantic twin stays in sync under property tests.  
- AC-A11Y-04: Model/LLM setup errors meet accessible name + description patterns.
