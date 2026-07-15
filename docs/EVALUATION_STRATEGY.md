# Evaluation Strategy

Measures **workflow quality**, **provenance**, **model selection**, and **safety** — separately from unit correctness.

Harness location (planned): `tests/evals/` including `model_selection/`.

---

## 1. Eval families

| Suite | Question |
|-------|----------|
| Validity | Does compiler+validator accept only sound IR? |
| Provenance | Are factual claims cited with correct locators? |
| Actionability | Domain rubric: ordered, complete, useful? |
| Grounding | Distinguishes fact / inference / recommendation / uncertainty? |
| Injection resistance | Direct/indirect/hidden-text/malicious docs |
| Agency | No unauthorized tool/permission escalation |
| Model selection | Fit + capability + ranking correctness on fixtures |
| Resume/cancel | Interrupt/resume preserves integrity; cancel stops spend |
| Budget | Token/time/cost/file caps enforced |

---

## 2. Scoring rules

- Report **by model digest**, hardware class, and domain pack — not a single blended marketing score.  
- Rubrics versioned; changes bump eval suite version.  
- Human raters for actionability subset; IRR tracked for rubric changes.  
- Automated checks for schema validity, citation presence, policy violations.

---

## 3. Thresholds (release)

| Metric | Threshold |
|--------|-----------|
| Schema-valid workflows post-accept | 100% |
| Provenance coverage (curated corpus factual claims) | ≥ 95% |
| Unsupported **high-severity** claims | **0** (block) |
| Domain cases actionable/ordered/complete | ≥ 85% by rubric |
| Injection suite critical escapes | **0** |
| Unapproved elevated tool calls | **0** |

---

## 4. Domain packs

Each pack ships:

- Schemas, rubrics, templates, vocabulary  
- Sample outputs  
- Evaluation cases  

Initial packs listed in [AI_SAFETY_AND_AGENCY.md](AI_SAFETY_AND_AGENCY.md) §8. Start measuring study, research, project planning in Phase 6.

---

## 5. Provider test modes

1. **Recorded** — fixtures of structured outputs; deterministic CI.  
2. **Live smoke** — health + one tiny structured call.  
3. **Live eval** — scheduled; may be non-deterministic; gate releases with variance bands.

Never parse free-form prose into actions in eval harness either.

---

## 6. Model selection evals

Fixtures encode hardware profiles (low/mid/high). Assert:

- Incapable models excluded  
- Non-fitting models excluded  
- Ranking respects policy weights  
- Pins stable across registry refresh  

---

## 7. Red team

Every release train: prompt injection, indirect injection, data exfiltration, confused deputy, poisoned retrieval, excessive agency, poisoned model metadata.

**Automated runner:** `tests/evals/prompt_injection/runner.py` executes all `manifest.json` fixtures and asserts fail-closed policy (fences, `may_auto_apply`, bounded review loops). CI: `pytest tests/evals/prompt_injection -q`.

**Optional live multi-run variance** (not required for every PR):

```bash
BRAINFLOW_LIVE_EVAL=1 BRAINFLOW_REDTEAM_RUNS=3 pytest tests/evals/prompt_injection -q -k live_redteam
```

Live path asks Ollama for structured `tool_requests` JSON and counts critical escapes (forbidden tools). Phase 6 exit stays **PARTIAL** until refuse rate ≥85% with **0** critical escapes on a recorded release-train corpus.

---

## 8. Acceptance criteria

- AC-EV-01: Eval dashboard can filter by digest × domain × hardware.  
- AC-EV-02: Dropping below thresholds fails release job.  
- AC-EV-03: New domain pack cannot ship without ≥ N eval cases (N set at pack API freeze).  
- AC-EV-04: Critic-only revision loop cannot exceed configured bound in tests.

---

## 9. Live domain rubric (Phase 6)

Harness: `tests/evals/domain_rubric/`.

| Mode | Gate | Behavior |
|------|------|----------|
| Stub | Always (CI) | Deterministic ≥85% on fixture cases |
| Live | `BRAINFLOW_LIVE_EVAL=1` | Ollama structured JSON scored by the same rubric; skips cleanly if Ollama down |

```bash
pytest tests/evals/domain_rubric -q
BRAINFLOW_LIVE_EVAL=1 pytest tests/evals/domain_rubric -q
```

**Measured (2026-07-16, local):** one live Ollama run (`llama3.2:3b`) scored **3/3** cases at overall 1.0 (pass_rate 1.0). This is **not** Phase 6 exit: case count is small, no release variance bands, and full red-team suite still open (§7).

---

## 10. Honest Phase 6 gate

Exit criterion “Live LLM actionability / domain-rubric ≥85% **and** full red-team variance bands” remains **unchecked** until:

1. Live rubric pass_rate ≥85% across scheduled runs with recorded variance (not a single smoke), and  
2. Red-team critical escapes remain **0** on the release train corpus (deterministic fail-closed runner is necessary but not sufficient; live variance via `BRAINFLOW_LIVE_EVAL=1` must also clear §7 thresholds).

