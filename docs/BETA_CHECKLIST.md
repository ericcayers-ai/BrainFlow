# Closed beta checklist

Phase 10 hardening gate. Pair with [QA_STRATEGY.md](QA_STRATEGY.md), [ACCESSIBILITY.md](ACCESSIBILITY.md), [THREAT_CONTROLS.md](THREAT_CONTROLS.md), [QA_LAUNCH.md](QA_LAUNCH.md).

---

## 1. Engineering gates (must be green)

- [ ] Feature CI: schemas, Rust crates, Python worker, desktop typecheck/build
- [ ] A11y stub / axe gate on critical routes ([scripts/a11y-check.cjs](../scripts/a11y-check.cjs))
- [ ] Security scan placeholders reviewed; critical audit findings triaged
- [ ] Fuzz entrypoints present; nightly budget scheduled for importers/IR/IPC
- [ ] Prompt-injection suite fixtures run (or recorded) for pinned models
- [ ] Threat control checklist TC-01…TC-16 mapped with owners
- [ ] Migration + backup/restore drill on Windows mid-tier fixture
- [ ] Signed updater dev channel smoke (tamper reject)
- [ ] Crash reporting default **off**; redaction tests green

---

## 2. Multi-device / domain tester matrix

Recruit at least one participant per cell where possible; publish known limitations with the invite.

| Domain persona | Windows | macOS | Linux | A11y focus |
|----------------|---------|-------|-------|------------|
| Student | ☐ | ☐ | ☐ | Keyboard ☐ |
| Researcher | ☐ | ☐ | ☐ | SR (NVDA) ☐ |
| Educator | ☐ | ☐ | ☐ | Zoom 200% ☐ |
| Project / program manager | ☐ | ☐ | ☐ | High contrast ☐ |
| Operations | ☐ | ☐ | ☐ | Reduced motion ☐ |
| Engineer | ☐ | ☐ | ☐ | |
| Analyst | ☐ | ☐ | ☐ | |
| Creative | ☐ | ☐ | ☐ | |
| Screen-reader specialist | ☐ NVDA | ☐ VoiceOver | — | Required |

Hardware classes for model selection: low / mid / high RAM+GPU — at least one Windows machine each.

---

## 3. Scenario scripts (each persona)

1. First-run: Guided path, LLM setup fail-closed then success.  
2. Import/link a source → generate workflow → inspect artifact provenance.  
3. Studio edit (budgets or node) → rerun affected nodes.  
4. Sync or multi-device conflict sample (when sync ships); else mark N/A with date.  
5. Attempt an approval-gated action; confirm exact parameters shown.  
6. Toggle high contrast / reduced motion; confirm usability.

---

## 4. Exit criteria

- No critical data-loss, security, or a11y defects open.  
- Workflow-quality metrics reported **by hardware / model / domain** (not a single blended headline).  
- Known limitations document published to beta cohort.
