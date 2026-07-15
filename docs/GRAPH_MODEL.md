# Graph Model

One **typed property graph** with multiple synchronized projections. Edits apply to the canonical model (or schema-valid patches thereof); views never fork divergent truth.

Related: [WORKFLOW_IR.md](WORKFLOW_IR.md) · [DATA_MODEL.md](DATA_MODEL.md) · [ACCESSIBILITY.md](ACCESSIBILITY.md)

---

## 1. Canonical store

- Authoritative portable serialization under `.brainflow/graphs/` (versioned JSON).  
- Query/index acceleration in SQLite (rebuildable).  
- Workflow executable semantics remain in Workflow IR; graph may **reference** workflow nodes via ids.

```text
schema_version, graph_id, nodes[], edges[], views[]
```

---

## 2. Node types

| Type | Role |
|------|------|
| `File` | Vault or linked source identity |
| `Note` | Markdown note |
| `Block` | Block/heading/paragraph region |
| `Entity` | Named entity extracted or asserted |
| `Goal` | User/system goal |
| `Constraint` | Hard/soft constraint |
| `Task` | Actionable task |
| `Decision` | Decision record |
| `Question` | Open question |
| `Evidence` | Cited evidence segment |
| `Artifact` | Generated or approved output |
| `WorkflowStep` | Projection of IR node |
| `Person` | People references |

Each node: stable `id`, `type`, `label`, `properties{}`, optional `locators[]`, `created_at` / `updated_at`, `provenance`.

---

## 3. Edge types

| Type | Semantics |
|------|-----------|
| `links_to` | Wikilink / explicit link |
| `derived_from` | Artifact/evidence ← source |
| `supports` | Claim supported by evidence |
| `contradicts` | Conflict relation |
| `depends_on` | Task/workflow dependency |
| `produces` | Step → artifact |
| `assigned_to` | Task → person |
| `precedes` | Ordering |
| `mentions` | Text mention without strong link |

Edges: `id`, `type`, `from`, `to`, `properties{}`, optional `weight`, provenance.

**Invariants:** no dangling endpoints after commit; type compatibility matrix enforced; deletes cascade or reattach per policy (document in migrations).

---

## 4. Projections (views)

| View | Engine (UI) | Purpose |
|------|-------------|---------|
| Workflow DAG | React Flow + ELK | Executable steps, status, critical path |
| Mind map | React Flow + ELK | Goal-centered ideation |
| Tree / outline | React / list | Keyboard hierarchy, indent/outdent |
| Knowledge graph | Cytoscape | Dense relationships |
| Artifact lineage | Either | Source → steps → outputs |
| Optional later | — | Timeline/Gantt, Kanban, matrix, Bases table |

All projections:

- Share selection/focus via graph ids.  
- Provide synchronized **non-visual** outline/list/table (a11y mandatory).  
- AI mutations = **reviewable schema-valid patches**, not direct free edits to canvas state alone.

---

## 5. View metadata

Saved views store: layout algorithm, camera/viewport, pinned node positions, filters/facets, collapsed groups, LOD thresholds — without mutating semantic edges unless user edits.

Layout presets: layered DAG, radial, force, orthogonal, tree, mind map. Expensive layout runs in Web Workers; preserve manual pins.

---

## 6. Interaction contract

Required capabilities (product):

- Grouping, nested subflows, collapse/expand, portals  
- Filters, facets, saved views, minimap, search  
- Shortest-path tracing, neighborhood focus, clustering, edge labels  
- Diff between workflow/graph versions  
- Drag-connect with type checks; multi-select; copy/paste; undo/redo; history  
- Reusable subgraphs; import/export  
- Peripheral file-reference nodes compact; open evidence drawer + “open original”  

AI commands (`explain cluster`, `suggest missing dependency`, …) emit patches for user approval in Studio; Guided mode may auto-apply only `safe_overlay` semantic updates that do not require elevated permission classes.

---

## 7. Scale and LOD

| Target | Expectation |
|--------|-------------|
| 500 workflow nodes | Smooth editing |
| 5,000 visible relationship nodes | Useful interactive exploration |
| Full vault unbounded | Must cluster/filter — do not attempt to paint everything |

Level-of-detail aggregation required beyond thresholds ([PERFORMANCE_BUDGETS.md](PERFORMANCE_BUDGETS.md)).

---

## 8. Accessibility mirroring

Every node/edge:

- Keyboard reachable  
- Accessible name/role  
- Operable without drag  
- Status changes announced via live regions  

See [ACCESSIBILITY.md](ACCESSIBILITY.md).

---

## 9. Provenance on graph elements

Prefer edges `derived_from` / `supports` with properties:

```text
file_id, content_hash, locator, confidence, claim_kind
```

`claim_kind`: `source_fact` | `inference` | `recommendation` | `uncertainty`

---

## 10. Acceptance criteria

- AC-GR-01: Edit in outline projection appears in DAG projection without divergent edge sets.  
- AC-GR-02: Invalid edge type combo rejected by schema.  
- AC-GR-03: Keyboard-only user can create dependency between two steps.  
- AC-GR-04: AI patch that would add unauthorized tool node fails policy validation.  
- AC-GR-05: Performance targets documented in PERFORMANCE_BUDGETS met for fixture graphs.
