# QA Strategy

Layered testing and release gates. Metrics thresholds also in [EVALUATION_STRATEGY.md](EVALUATION_STRATEGY.md) and [PERFORMANCE_BUDGETS.md](PERFORMANCE_BUDGETS.md).

---

## 1. Test layers

| Layer | Covers |
|-------|--------|
| Unit / property | Parsers, links, graph invariants, compiler, policy, merge, model scoring, migrations |
| Contract | Shared schemas across Rust/TS/Python; every LLM/provider adapter |
| Golden extraction | Each supported format + source-location mapping |
| Recorded provider | Deterministic fixtures for gateway |
| Live smoke/eval | Ollama + cloud models (separate CI job, secrets) |
| E2E desktop | First run, vault lifecycle, import→workflow, graph edit, interrupt/resume, Git sync/conflicts, updates, recovery |
| Fuzz | Importers, archives, Markdown/render, workflow JSON, Git conflict payloads, IPC messages |
| Performance / soak | Low/mid/high Windows hardware; macOS/Linux parity |
| Adversarial LLM | Injection, hidden text, malicious docs, spoofing, exfil, invalid tools, runaway loops, poisoned metadata |
| Accessibility | axe CI + manual AT checklist |

---

## 2. Initial quality targets

| Gate | Target |
|------|--------|
| Data loss | Zero known data-loss paths; restore succeeds in crash/interrupted-sync matrix |
| Workflow validity | 100% schema-valid after compiler/validator acceptance |
| Provenance | ≥95% coverage for factual claims in curated corpus; unsupported high-severity claims block release |
| Domain eval | ≥85% actionable/ordered/complete by rubric; **tracked by model**, not blended headline only |
| Search | p95 &lt; 100 ms warm on 10k-note vault; UI responsive during index/model |
| A11y | No critical/serious automated violations; manual checklist done |
| Crash-free / sync-success | Establish in beta; promote to GA only with honest statistics |

---

## 3. Environments

- OS: Windows (primary), macOS, Linux  
- Hardware fixtures: low / mid / high RAM+GPU classes for model selection  
- Cloud sync roots: include warning tests; avoid OneDrive as primary CI vault home  

---

## 4. Release process

1. Feature CI green (unit/contract/golden/a11y automated).  
2. Nightly: fuzz + recorded providers + performance subset.  
3. Pre-beta/pre-GA: live evals, LLM red team, sync interruption matrix, security review checklist ([THREAT_CONTROLS.md](THREAT_CONTROLS.md), [BETA_CHECKLIST.md](BETA_CHECKLIST.md)).  
4. Sign + SBOM ([RELEASE_SECURITY.md](RELEASE_SECURITY.md)).  
5. Publish known limitations with beta.  
6. Platform order and channels: [RELEASE.md](RELEASE.md).

---

## 5. Ownership

| Area | Owner (role) |
|------|----------------|
| Schema/contracts | Platform |
| Ingestion corpus | Ingestion |
| Eval rubrics | AI / applied science |
| Sync matrix | Sync |
| A11y | Frontend + QA |
| Security | Security part-time + eng |

---

## 6. Acceptance for QA harness itself

- AC-QA-01: Vertical slice (Phase 2) has automated E2E covering import→artifact.  
- AC-QA-02: Policy tests prove approval gates.  
- AC-QA-03: Flaky live model jobs do not gate unit CI; they gate release trains.  
- AC-QA-04: Corpus licenses documented; no copyright-risk fixtures.
