# BrainFlow AI Worker

Supervised Python sidecar for LLM gateway, ingestion hooks, and workflow IR generation.

## Transport

**Default:** JSON-RPC 2.0 over **stdio** (one JSON object per line).  
Do **not** bind an unauthenticated fixed localhost port (ADR 0002).

Optional `--http-loopback` exists only for local debugging and binds `127.0.0.1` with a random port + required bearer token. Production path remains stdio via Rust supervision.

## Run

```bash
# From repo root
cd services/ai-worker
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -e ".[dev]"

# Stdio RPC (normal)
python -m brainflow_worker

# Health-only probe
python -m brainflow_worker.ollama_probe
```

## Fail-closed LLM

If Ollama (or configured cloud API) is unreachable / has no models, `llm.health` and `workflow.generate` return structured errors. The worker **never** invents a pretend-AI workflow.

## Model intelligence (gateway)

Additive RPC methods under `brainflow_worker.gateway`:

| Method | Purpose |
|--------|---------|
| `llm.health` | Aggregate provider health (Ollama + OpenAI/Anthropic/Gemini/OpenRouter/custom) |
| `llm.hardware` | CPU/RAM/GPU/VRAM profile |
| `llm.select` / `llm.recommend` | Scoring + recommendation card + pin resolution |
| `llm.probe` | Capability probes for a provider/model |
| `registry.load` / `install` / `rollback` | Signed registry cache |
| `secrets.set` / `delete` / `status` | OS keyring / env / memory (never vault) |
| `pins.assert_stable` | Mid-run digest swap guard |

Cloud adapters implement real HTTP request paths (Anthropic Messages, Gemini generateContent, OpenAI-compatible). Without API keys they fail closed with setup guidance. Unit tests inject `httpx.MockTransport` — no live keys required.

Local shortlist benchmarks: stub by default; set `BRAINFLOW_LIVE_BENCH=1` to run against Ollama when available.

Policies: `auto`, `balanced`, `maximum_quality`, `maximum_privacy`, `low_latency`, `pinned`.

Token/spend limits: pass a `budget` (`RequestBudget`) into adapter `chat(...)` — clamps `max_tokens` and fail-closes on exhaustion.

## Intake (DocumentBundle)

Additive RPC methods:

| Method | Params | Result |
|--------|--------|--------|
| `intake.analyze` | `path` **or** `content_base64` (+ optional `filename`, `path_mode`, `limits`, `file_id`) | `bundle`, `validation`, `evidence_block`, `adapters` |
| `intake.adapters` | — | registered adapter ids |

Example:

```json
{"jsonrpc":"2.0","id":1,"method":"intake.analyze","params":{"path":"C:/vault/note.md","path_mode":"link"}}
```

Install optional document libs:

```bash
pip install -e ".[dev,intake]"
```

Apache Tika is **not** bundled — see [docs/FILE_INGESTION.md](../../docs/FILE_INGESTION.md) §9 for the future extension pack.
