# Remaining gaps vs 18–24 month GA bar

Honest backlog after P0 packaging / E2E pass and P1 automation closes (2026-07-16). Exit criteria below are **unchecked** in [ROADMAP.md](../ROADMAP.md) unless noted. Do not treat in-tree scaffolding as GA.

**Priority legend:** P0 blocker for alpha/distributable · P1 required before beta claim · P2 GA / parity · P3 polish / follow-ons

---

## P0 — Packaging & foundation gates

| Gap | Phase | Notes |
|-----|-------|-------|
| Cold-start / WebView2 + sidecar timing | 1 | **Sizes + time-to-window recorded** — cold-ish **618 ms**, warm **~45–90 ms** (`scripts/measure-cold-start.ps1`); sidecar-ready still unmeasured — [spikes/tauri-shell.md](spikes/tauri-shell.md). Phase 1 compound sizes+startup **checked**. |
| Multi-OS packaging spikes (macOS/Linux) | 1, 11 | Windows unsigned alpha OK; **macOS/Linux not run** (no local/CI Mac or Linux packaging verification) — prerequisites unchecked. |
| Full vertical-slice E2E automation | 2 | **Scripted E2E landed** — `tests/e2e/test_vertical_slice.py` / `npm run test:e2e:vertical-slice` (vault→note→intake→LLM fail-closed/live→`.brainflow`→reopen). CI smoke job still unit/tsc only; UI Playwright not present. |
| Code signing / updater channels | 10–11 | Alpha installers remain **unsigned**; steps documented in [RELEASE.md](RELEASE.md) §7 — no fake signatures. |

---

## P1 — Product exits still open

| Gap | Phase | Notes |
|-----|-------|-------|
| Phase 0 acceptance completeness | 0 | Product docs exist; every non-negotiable behavior still needs implementer-ready ACs across §14 docs set. |
| ADR follow-through | 0–1 | Foundational ADRs opened; macOS/Linux packaging evidence incomplete. |
| 10k-note soak (no data loss, input latency) | 3 | **Catalog budgets met** at N=10k: FTS p95 **0.45 ms**, QS **0.09 ms**, open+save+search cycle p95 **30.1 ms** ≤50 ([spikes/soak-10k.md](spikes/soak-10k.md)). **Daily-team use** and **WebView keystroke** still human-only → Phase 3 compound exit **unchecked**. |
| Live LLM domain-rubric ≥85% + red-team bands | 6 | Deterministic fail-closed red-team runner (10 fixtures) + stub rubric CI; live Ollama rubric smoke + optional `BRAINFLOW_LIVE_EVAL` multi-run variance — **PARTIAL** until release-train thresholds with evidence. |
| Graph AT sign-off (NVDA/VoiceOver) | 7 | §6.1 focus/announce/path/patch **automated** in unit tests; live AT **unsigned**. |
| Graph scale CI/soak | 7 | **500-node React Flow data-prep smoke** automated (`npm run smoke:graph-ui`); 5k via LOD only; mid-tier GPU pan/zoom **not** claimed; NVDA **not** claimed. |
| Live multi-device sync soak | 8 | Fixture matrix + **dry-run simulation** (`multi_device_dry_run`); manual live matrix documented — live soak **unchecked**. |
| No critical data-loss / security / a11y defects | 10 | Soft-gates in CI ≠ exit. |
| Workflow-quality metrics by hardware/model/domain | 10 | Reporting harness incomplete for beta exit. |
| GA release gates green | 11 | QA / release-security / perf budgets not green for a target platform yet. |

---

## P2 — Feature depth still short of plan

### Intake (Phase 4) — deepened, not finished

In-tree: notebook, OCR path, media, OpenDocument adapters + golden/malformed coverage (~27 intake tests). OCR/whisper remain **optional extras** (`.[ocr]`, `.[media]` / Tesseract / FFmpeg).

Still open:

- Live golden corpus run with optional deps installed (Tesseract + Whisper + Office extras)
- Apache Tika extension pack
- Broader Office/PDF hardening (DRM, huge corpora, fuzz beyond entrypoints)
- End-to-end provenance UX in desktop for every adapter family

### Editor / knowledge workspace (Phase 3 → 9)

**Landed (parity checklist ☑ / ◎):** footnotes render + panel; bookmarks / workspaces; Bases filter/sort + formula columns + title/tags cell edit; Canvas board UI; live/reading modes; pins/split; rename-safe links — see [OBSIDIAN_PARITY.md](OBSIDIAN_PARITY.md).

Still open:

- Full infinite-canvas chrome / JSON Canvas interop depth
- Bulk property edit / validation
- WebView keystroke + daily-team 10k sign-off (catalog budgets may be met — Phase 3 exit still compound)
- Remaining `☐` items in [OBSIDIAN_PARITY.md](OBSIDIAN_PARITY.md)

### Models + kernel (Phases 5–6)

Deeper: real HTTP providers, budgets, pins, executable evals (providers + kernel suites); expanded prompt-injection / red-team fail-closed runner.

Still open:

- Live cloud smoke (opt-in keys) as CI optional job, not just mocks
- Live Ollama structured-output reliability on small models
- Live rubric + red-team **release-train** variance (Phase 6 exit still PARTIAL)
- Hardware fixture matrix on real mid/low machines (not only stub harness)

### Graph suite (Phase 7)

Deeper: ELK worker, LOD, stress fixtures, **500-node UI data-prep smoke**.

Still open:

- Exit criteria (live AT + mid-tier GPU scale soak) — **do not claim**
- Conversion / mind-map / tree polish depth vs product plan
- AI patch proposal UX beyond schema-valid review stub
- Worker packaging verification inside real Tauri WebView matrix

### Sync (Phase 8)

Deeper: merge harden (LCS Markdown, edges-by-id), CI vertical-slice touch, SyncPanel conflict UX, dry-run multi-device simulation + documented manual matrix.

Still open:

- OAuth/prod token UX polish
- Live multi-device + forced-interruption soak (human)
- History/restore product surfaces at GA depth

---

## P3 — Hardening, polish, governance

| Gap | Phase | Notes |
|-----|-------|-------|
| Usability studies (novice + power user) | 9 | Exit unchecked. |
| Localization beyond `en` seam | 9 | Seam only. |
| Plugin SDK beyond allowlist stubs | 9 | Sandbox/review/revocation for GA. |
| Publish/export beyond stubs | 9 | [PUBLISHING.md](PUBLISHING.md) stub. |
| SBOM, signing, updater end-to-end | 10–11 | Signing **steps** in RELEASE.md; proof on real channels open. |
| Importer fuzz campaign depth | 10 | Entrypoint check ≠ campaign. |
| Closed beta cohort + known-limitations publish | 10 | Checklist scaffolding only. |
| Model registry channels in production | 11 | Docs; live channels deferred. |
| Mobile/web | 11 | Explicitly deferred until portable contracts stabilize. |

---

## Explicitly **not** exit-complete (do not check off)

| Claim | Reality |
|-------|---------|
| Phase 1 packaging sizes **and** startup times | **Checked** on Windows (sizes + time-to-window). macOS/Linux still open. Sidecar-ready latency still open. |
| Phase 2 full vertical-slice E2E | **Checked** for scripted vault→LLM→artifact→reopen; UI graph render / CI job wiring still softer than GA. |
| Phase 3 10k exit | Catalog FTS + edit-cycle proxy measurable; **daily-team** + **WebView keystroke** open → exit unchecked |
| Phase 6 full exit | Deterministic red-team OK; live harness + smoke OK; live variance bands → **PARTIAL** |
| Phase 7 exits | §6.1 automated ≠ NVDA; 500 node **data-prep smoke** ≠ GPU pan/zoom / AT |
| Phase 8 live multi-device | Dry-run + fixtures OK; live soak open |
| Phase 9–11 GA gates | Scaffolding ≠ green release; alpha installers unsigned |

---

## Suggested next sequence (engineering)

1. ~~Measure cold-start~~ / optionally measure sidecar-ready + wire `measure:cold-start` into a periodic CI smoke on Windows.  
2. ~~Scripted vault→LLM→artifact reopen~~ — optionally add Playwright UI + promote E2E into CI (opt-in Ollama job).  
3. ~~10k FTS + edit-cycle catalog soak~~ — **human:** daily-team use + WebView keystroke on same vault.  
4. Schedule live evals (`BRAINFLOW_LIVE_EVAL=1`) with variance bands across release trains (deterministic red-team runner landed ≠ exit).  
5. Live sync interruption matrix on two devices (manual §9); **NVDA** graph AT recording.  
6. Authenticode + updater path per [RELEASE.md](RELEASE.md) §7; only then treat Phase 10 closed-beta exits as in reach.

---

*Last updated: 2026-07-16 (P1 edit-cycle / red-team runner / graph UI smoke / sync dry-run).*
