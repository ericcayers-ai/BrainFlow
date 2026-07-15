# Model Selection

Hardware-aware selection of the **best validated** local (or hybrid portfolio) models for BrainFlow tasks. Complements [MODEL_REGISTRY.md](MODEL_REGISTRY.md) and [PRODUCT_SPEC.md](PRODUCT_SPEC.md) §2.5.

---

## 1. Definition

**Best model** = highest-scoring validated candidate or role-based **portfolio** that:

1. Passes **capability gates** for the workflow  
2. **Fits** measured hardware with safety margin (no thrash/excessive spill)  
3. Ranks highest under BrainFlow’s scoring formula  
4. Optionally wins on **local benchmarks** of the shortlist  

Not a fixed brand name. Catalog is signed and refreshed.

---

## 2. Policies

| Policy | Behavior |
|--------|----------|
| Auto | Full pipeline; may reselect only if user authorized automatic LLM reselection on failure |
| Balanced | Quality vs latency/memory tradeoff mid weights |
| Maximum Quality | Prefer top quality; may require download consent |
| Maximum Privacy | Prefer local; cloud only with explicit allow |
| Low Latency | Throughput/TTFT floors prioritized after hard capability gates |
| Pinned | User/workflow-fixed digests; recommendations notify only |

---

## 3. Pipeline

### Step 1 — Hardware profile

Record:

- CPU architecture, core count  
- RAM  
- GPU vendor/model/count, VRAM or unified memory  
- Driver/runtime support (CUDA/ROCm/Metal/Vulkan as applicable)  
- Free disk  
- Thermal/power mode if available  
- Installed Ollama/runtime versions  

### Step 2 — Registry refresh

Pull signed manifest on demand / schedule ([MODEL_REGISTRY.md](MODEL_REGISTRY.md)). Offline: use last good cached snapshot.

### Step 3 — Capability gates

Remove models lacking required modalities (vision, tools, JSON schema, embeddings, context length, languages). Example: multimodal workflow cannot use text-only planner unless a validated vision extraction model is also selected in the portfolio.

### Step 4 — Fit estimation

Estimate: weights + KV cache at target context + runtime overhead + concurrency headroom + **safety margin**. Reject “barely allocates.”

### Step 5 — Rank

Dominant → lesser:

1. Quality (registry + BrainFlow evals)  
2. Required context  
3. Reliability on BrainFlow workflow evals  
4. Local throughput/latency floor  
5. Quantization penalty  
6. License compatibility  
7. Energy / disk constraints  

### Step 6 — Local shortlist benchmark (consent + disk budget)

Representative tasks:

- Structured planning  
- Evidence citation  
- Graph generation  
- Long-document synthesis  
- Tool-call accuracy  
- Time to first token  
- Prompt / generation throughput  
- Peak memory  
- Thermal stability  

### Step 7 — Portfolio vs single

Default: consider portfolio (planner/reasoner, multimodal analyzer, embeddings). Advanced: “single model only” constraint.

### Step 8 — Transparent recommendation card

Show: why winners won, memory/context/speed expectations, download size, license, alternatives, rejected reasons.

### Step 9 — Pin digests

Pins stored on workflow IR / run. New recommendations → notification + optional benchmark; **never** silent change of active/historical runs.

### Step 10 — Failure

Pause on missing/failing model. Auto reselection only if authorized; **never** fall back to deterministic fake AI workflow generation.

---

## 4. Scoring (normative sketch)

```text
score = w_q * quality
      + w_c * context_fit
      + w_r * eval_reliability
      + w_p * performance_floor
      - w_z * quant_penalty
      - w_d * disk_pressure
      + w_l * license_ok
```

Weights differ by policy (`Balanced` vs `Maximum Quality`, etc.). Exact weights versioned in registry + evaluated in `tests/evals/model_selection`.

Quality scores must cite provenance (eval job id, dataset id, date) — no anonymous scrapes.

---

## 5. Provider adapters (gateway)

| Provider | Priority |
|----------|----------|
| Ollama native API | First-class local |
| OpenAI, Anthropic, Gemini, OpenRouter | Cloud |
| OpenAI-compatible | LM Studio, llama.cpp server, vLLM, private |

**Probes required** before eligibility: JSON-schema adherence, tool use, context handling, vision, embeddings, cancellation, streaming. Marketing metadata insufficient.

Secrets: OS keychain. Cloud: request preview. TLS for non-loopback. Endpoint allowlists. Per-provider spend/token limits.

---

## 6. Acceptance criteria

- AC-MS-01: Low-RAM fixture never selects a model that fails fit estimation.  
- AC-MS-02: Vision workflow without vision-capable model → selection error, not text-only silent plan.  
- AC-MS-03: Recommendation UI exposes digest + license + alternatives.  
- AC-MS-04: Pinned run ignores newer registry champion until user opts in.  
- AC-MS-05: Probe failure removes model from eligible set in contract tests.

---

## 7. Implementation map (Phase 5 slice)

| Concern | Location |
|---------|----------|
| Provider adapters | `services/ai-worker/brainflow_worker/gateway/providers/` (Ollama, OpenAI, Anthropic, Gemini, OpenRouter, custom) |
| Request budgets | `gateway/budget.py` (`RequestBudget` on `chat`) |
| Probes | `gateway/probes.py` |
| Hardware profiler | `gateway/hardware.py` |
| Registry verify/cache | `gateway/registry.py` + `packages/schemas/model-registry/` |
| Scoring + policies | `gateway/scoring.py`, `gateway/types.py` |
| Pins / mid-run freeze | `gateway/pins.py` |
| Selection pipeline | `gateway/select.py` → RPC `llm.select` / `llm.recommend` |
| Recommendation UI | `apps/desktop/src/components/ModelIntelligencePanel.tsx` |
| Secrets | `gateway/secrets.py` (+ Tauri `model_set_secret`) |
| Eval stub / live bench | `tests/evals/model_selection/` (`BRAINFLOW_LIVE_BENCH=1` → Ollama) |

**Auto policy:** profile hardware → load signed registry → capability gates → memory fit with margin → weighted score → recommendation card → pin digests on workflow/run. Active runs refuse digest swaps (`pins.assert_stable`).
