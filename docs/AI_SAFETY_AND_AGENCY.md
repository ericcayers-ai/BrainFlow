# AI Safety and Agency

Normative controls for LLM-driven features. Complements [PRODUCT_SPEC.md](PRODUCT_SPEC.md), [SECURITY.md](SECURITY.md), and [THREAT_MODEL.md](THREAT_MODEL.md).

---

## 1. Fail-closed LLM posture

| Condition | System behavior |
|-----------|-----------------|
| No provider configured | Block AI workflow create/adapt; show setup path |
| Provider unhealthy | Block; surface health check failure |
| Capability probe failed for required role | Block that role; do not silently substitute weaker unprobed model |
| Structured output invalid | Reject plan; bounded critic revision only — no prose-to-action parse |
| Policy/schema validation failed | Reject; never execute |
| Model missing mid-run | Pause; optional authorized reselection only |

**Hard rule:** Never generate or present a deterministic/template workflow as if it were LLM-inferred.

**Acceptance:** AC-LLM-01..03 in PRODUCT_SPEC; red-team suite asserts no bypass ([EVALUATION_STRATEGY.md](EVALUATION_STRATEGY.md)).

---

## 2. Overlays vs originals

```text
Immutable source (user file / linked path)
        │  derived_from + content hash + locator
        ▼
DocumentBundle (untrusted evidence)
        │
        ▼
Workflow IR + run events (overlay)
        │
        ▼
Artifacts under .brainflow/artifacts/...
```

- Planning models have **no** direct filesystem write to source paths.  
- Executor writes only under policy-scoped vault / `.brainflow` paths for `safe_overlay`.  
- “Open original” is an explicit user action opening externally or in a read-only viewer.  
- Graph peripheral nodes are references, not editable source blobs.

**Acceptance:** AC-SRC-01..03.

---

## 3. Approval gates

### 3.1 Permission classes

| Class | Auto-apply? | Examples |
|-------|-------------|----------|
| `safe_overlay` | Yes, if schema-valid | Write derived Markdown under allowed dirs; update indexes; emit artifacts |
| `vault_mutate` | Approval | Rename/delete BrainFlow-managed notes (not linked sources) |
| `source_mutate` | Approval | Overwrite/delete linked original |
| `network_egress` | Approval (except allowlisted LLM providers already consented) | Arbitrary HTTP, webhooks |
| `publish` | Approval | Static site publish, remote share |
| `shell` | Approval | OS commands |
| `credentials` | Approval | Use secrets beyond declared provider |

### 3.2 Approval UX requirements

- Exact tool name, arguments, path scopes, network destinations.  
- Diff or summary of filesystem effects when applicable.  
- Persistence: one-shot vs session vs remember-for-workflow (never remember `shell` / `source_mutate` silently across vaults).  
- Immutable audit event: who/what/when/decision.

**Acceptance:** AC-EXE-01..03.

---

## 4. Planning vs execution separation

1. **Intake Analyst** — summarize bundle, warnings, sensitive flags (LLM).  
2. **Goal Router** — infer outcomes; present choice when confidence low (LLM).  
3. **Domain Planner** — draft goals/tasks/artifacts via domain pack (LLM).  
4. **Workflow Compiler** — emit schema-valid IR (LLM constrained to schema).  
5. **Deterministic validator** — cycles, budgets, tools, paths, capabilities.  
6. **Critic** — separate context; bounded revision proposal.  
7. **Second deterministic pass** — references, integrity, policy.  
8. **Executor** — resumable DAG; safe auto-apply only.  
9. **Outcome Verifier** — acceptance criteria + citations; bounded retries.  
10. **UI** — review artifacts, assumptions, evidence, history.

Planning models must **not** receive tools for: FS write outside sandbox APIs, Git, shell, network (except through gateway for model inference), credentials, publish, delete.

---

## 5. Anti-derailment controls

| Threat | Control |
|--------|---------|
| Prompt injection (direct/indirect) | Delimit untrusted evidence; label segments; system policy immutable |
| Tool escalation | Schema-defined tools only; policy engine scopes + rate limits |
| Confused deputy | Capability tokens per job; no ambient authority |
| Poisoned retrieval | Treat retrieval as untrusted; cite; verifier |
| Free-form action parsing | Structured output + JSON Schema only |
| Unbounded loops | Max steps, retries, tokens, time, cost, files, nodes, archives, parallelism |
| Hidden CoT as authority | Store summaries/evidence/params only |
| Source spoofing | Hash + locator provenance; warn on mismatch |
| Data exfiltration via model | Redaction policy; cloud request previews; path/secret scrubbing |

Imported text, document metadata, web content, retrieval, and plugin output = **hostile data**.

---

## 6. Evidence and claim discipline

Artifacts and graphs must distinguish:

- **Source fact** (cited locator)  
- **Inference**  
- **Recommendation**  
- **Unresolved uncertainty**  

Factual claims require evidence references. High-severity unsupported claims fail Outcome Verifier and block GA metrics thresholds ([EVALUATION_STRATEGY.md](EVALUATION_STRATEGY.md)).

---

## 7. Audit trail

Immutable local audit of:

- Plan versions  
- Validator decisions  
- Approvals / denials  
- Tool invocations (args redacted per policy)  
- Model digests  
- Outputs / failures  

Retention user-controlled; default excludes raw prompts of sensitive content where privacy policy requires ([PRIVACY.md](PRIVACY.md)).

---

## 8. Domain packs

Domain packs supply schemas, rubrics, templates, vocabulary, samples, and eval cases — **not** unrestricted prompts. Initial packs: study prep, research synthesis, industry/project planning, ops/SOP, software/product, teaching/course, meeting→actions, creative, PKM, dataset/report analysis.

---

## 9. Test obligations

Every release: prompt-injection, indirect injection, data exfiltration, confused deputy, poisoned retrieval, excessive agency suites ([QA_STRATEGY.md](QA_STRATEGY.md)).

**Release blocker:** any path that auto-applies `source_mutate`, `shell`, or `publish` without approval.
