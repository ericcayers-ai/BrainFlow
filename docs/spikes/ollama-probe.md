# Spike: Ollama health probe

## What we built

`services/ai-worker/brainflow_worker/ollama_probe.py` + RPC method `llm.health`.

## Measurements (2026-07-15, this workstation)

- Tags endpoint: **~33 ms**, HTTP 200.
- Installed models included `llama3.2:3b` and `qwen3.6:35b`.
- Minimal generate latency dominated by model load (**~62 s** for first tiny completion with `llama3.2:3b`).

## Fail-closed behavior

If probe fails or model list is empty, `workflow.generate` returns error code `1001` and does not emit a synthetic plan.
