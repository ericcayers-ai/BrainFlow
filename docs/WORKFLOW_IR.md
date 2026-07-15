# Workflow Intermediate Representation (IR)

Versioned, **declarative** DAG describing AI and safe-overlay work. Models propose JSON; **deterministic** code validates and executes. Never embed executable code in IR.

Related: [PRODUCT_SPEC.md](PRODUCT_SPEC.md) · [AI_SAFETY_AND_AGENCY.md](AI_SAFETY_AND_AGENCY.md) · [GRAPH_MODEL.md](GRAPH_MODEL.md)

---

## 1. Design goals

1. Portable across machines (JSON under `.brainflow/workflows/`).  
2. Schema-validatable in Rust, TypeScript, and Python from one source.  
3. Bounded: no unbounded autonomous loops.  
4. Reproducible: pins models, packs, input hashes per run.  
5. Migratable: every `schema_version` has a migration function.

---

## 2. Document envelope

```json
{
  "schema_version": 1,
  "workflow_id": "uuid",
  "title": "string",
  "domain_pack_id": "study_preparation@1.2.0",
  "goal": { "statement": "…", "constraints": [], "success_metrics": [] },
  "pins": {
    "models": {
      "planner": { "provider": "ollama", "name": "…", "digest": "sha256:…" },
      "embeddings": { "provider": "ollama", "name": "…", "digest": "sha256:…" }
    },
    "prompt_pack_version": "1.2.0",
    "settings_digest": "sha256:…"
  },
  "nodes": [],
  "edges": [],
  "budgets": {
    "max_steps": 80,
    "max_wall_time_ms": 3600000,
    "max_tokens": 500000,
    "max_cost_usd": 5.0,
    "max_generated_files": 200,
    "max_parallel_jobs": 4
  },
  "completion": {
    "criteria": [],
    "terminal_statuses": ["succeeded", "failed", "cancelled", "needs_review"]
  },
  "metadata": {
    "created_at": "ISO-8601",
    "created_by": "user|system",
    "notes": ""
  }
}
```

Exact field names will be locked in `packages/schemas`; this doc is the semantic contract.

---

## 3. Nodes

Each node:

| Field | Requirement |
|-------|-------------|
| `id` | Stable UUID |
| `type` | Registry type (e.g. `extract`, `retrieve`, `llm_plan`, `write_artifact`, `verify`, `human_approve`) |
| `title` | Human label |
| `inputs` | Typed ports + binding refs |
| `outputs` | Typed ports + artifact contracts |
| `preconditions` | Expressions / evidence checks |
| `postconditions` | Acceptance checks |
| `timeout_ms` | Hard timeout |
| `retry` | `{ max, backoff_ms, retry_on: [] }` |
| `token_budget` / `cost_budget` | Optional per-node caps |
| `idempotency_key` | Stable for cache reuse |
| `cache_key` | Optional explicit cache identity |
| `evidence_requirements` | Min citations / locator rules |
| `source_refs` | File ids + locators |
| `allowed_tools` | Tool ids |
| `permission_class` | See AI_SAFETY |
| `branch` | Optional bounded conditional |
| `review_loop` | Optional `{ max_iterations }` — **required** if looping |

### 3.1 Artifact contracts

Outputs declare MIME/schema, path template under `.brainflow/artifacts/{workflow_id}/{run_id}/…`, and whether auto-apply is `safe_overlay`.

### 3.2 Bounded control flow

Allowed:

- Fan-out / fan-in DAG edges  
- Conditional branch with finite arm set  
- Review loop with explicit `max_iterations`  

Forbidden:

- Unbounded `while`  
- Dynamic node injection at runtime without re-validation creating a new plan version  
- Cycles except those encoded as bounded review loops  

---

## 4. Edges

```json
{
  "id": "uuid",
  "from": "node_id:port",
  "to": "node_id:port",
  "kind": "data|control|approval"
}
```

Type compatibility enforced at validation (port types).

---

## 5. Run instance

Separate from definition:

| Field | Meaning |
|-------|---------|
| `run_id` | UUID |
| `workflow_id` + definition hash | Immutable plan snapshot |
| `status` | queued → running → … terminal |
| `events` | Append-only structured progress |
| `node_states` | per-node status, attempts, cache hits |
| `approvals` | Decisions recorded |
| `input_hashes` | Sources + params |
| `output_index` | Artifact ids |

Mid-run model digest must match pin; mismatch → fail closed.

---

## 6. Validation (deterministic)

Reject when:

- Unknown node/tool types  
- Cycles outside bounded loops  
- Missing inputs / unreachable required outputs  
- Capability not satisfied by pinned models  
- Budgets exceeded vs app maximums  
- Unsafe paths (escape vault, source overwrite without class)  
- Unauthorized permission class for auto-apply  
- Schema version unsupported  

Compiler emission **must** pass validation before UI marks plan runnable.

**Acceptance:** AC-IR-01: 100% of executable workflows after acceptance are schema-valid (QA gate).

---

## 7. Execution semantics

1. Topological schedule with parallelism ≤ `max_parallel_jobs`.  
2. Idempotent nodes: reuse cache when `cache_key` + pins match.  
3. On crash: resume from last durable event; do not re-apply non-idempotent side effects without approval.  
4. Outcome Verifier node type checks artifact criteria; failed criteria → configured retries → `needs_review`.  
5. User edit of goal/node → new plan version; invalidate only downstream of dirty nodes.

---

## 8. Migrations

| Version | Notes |
|---------|-------|
| 1 | Initial envelope as above |

For every `N → N+1`: pure migration function, golden fixtures, reject unknown future versions with clear upgrade prompt.

---

## 9. AI emission rules

- LLM emits JSON only via structured output matching schema.  
- Critic proposes **patch** (JSON Patch / IR patch schema), not free prose actions.  
- Free-form chat never becomes toolchain input.

---

## 10. Acceptance criteria

- AC-IR-02: Round-trip serialize/validate/serialize is byte-stable for canonicalization rules.  
- AC-IR-03: Unbounded loop IR fails validation.  
- AC-IR-04: Run export includes pins + input hashes + schema_version.  
- AC-IR-05: Permission class `shell` without approval cannot reach executor invoke.
