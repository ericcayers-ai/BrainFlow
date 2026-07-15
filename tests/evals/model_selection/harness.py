"""Local model-selection eval harness.

Representative BrainFlow tasks for shortlist benchmarking.
- Default path: deterministic stub scores (CI-safe).
- Live path: set BRAINFLOW_LIVE_BENCH=1 and use Ollama when available.
See docs/MODEL_SELECTION.md §3 step 6.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@dataclass
class BenchmarkTask:
    id: str
    name: str
    kind: str  # planning | citation | graph | synthesis | tools | latency | memory
    weight: float = 1.0
    requires: list[str] = field(default_factory=list)


DEFAULT_TASKS: list[BenchmarkTask] = [
    BenchmarkTask("plan_struct", "Structured planning", "planning", 1.2, ["json_schema"]),
    BenchmarkTask("cite_ev", "Evidence citation", "citation", 1.0, ["json_schema"]),
    BenchmarkTask("graph_gen", "Graph generation", "graph", 1.0, ["json_schema"]),
    BenchmarkTask("long_synth", "Long-document synthesis", "synthesis", 0.8, []),
    BenchmarkTask("tool_acc", "Tool-call accuracy", "tools", 1.1, ["tools"]),
    BenchmarkTask("ttft", "Time to first token", "latency", 0.9, []),
    BenchmarkTask("throughput", "Prompt/gen throughput", "latency", 0.7, []),
    BenchmarkTask("peak_mem", "Peak memory", "memory", 1.0, []),
    BenchmarkTask("thermal", "Thermal stability", "memory", 0.5, []),
]


LIVE_PROMPTS: dict[str, str] = {
    "plan_struct": 'Reply with ONLY JSON: {"ok":true,"tasks":["a","b"]}',
    "cite_ev": 'Reply with ONLY JSON: {"claims":[{"text":"x","evidence_id":"e1"}]}',
    "graph_gen": 'Reply with ONLY JSON: {"nodes":[{"id":"n1"}],"edges":[]}',
    "long_synth": "Summarize in one short paragraph: BrainFlow preserves immutable sources.",
    "tool_acc": 'Emit ONLY JSON: {"tool_calls":[{"name":"echo","arguments":{"text":"hi"}}]}',
    "ttft": "Say OK.",
    "throughput": "Count from 1 to 5.",
    "peak_mem": "Say OK.",
    "thermal": "Say OK.",
}


def list_tasks() -> list[dict[str, Any]]:
    return [asdict(t) for t in DEFAULT_TASKS]


def load_hardware_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES / f"hardware_{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def live_bench_enabled() -> bool:
    return os.environ.get("BRAINFLOW_LIVE_BENCH", "").strip() == "1"


def _stub_task_result(
    model_id: str, hardware_class: str, t: BenchmarkTask, hw: dict[str, Any]
) -> dict[str, Any]:
    seed = sum(ord(c) for c in f"{model_id}:{t.id}:{hardware_class}") % 100
    score = 0.45 + (seed / 200.0)
    return {
        "task_id": t.id,
        "score": round(score, 4),
        "latency_ms": 100 + seed * 3,
        "peak_memory_mb": hw.get("ram", {}).get("total_gb", 16) * 64 + seed,
        "stub": True,
    }


def run_stub_benchmark(
    *,
    model_id: str,
    hardware_class: str = "mid",
    tasks: list[str] | None = None,
) -> dict[str, Any]:
    """Deterministic synthetic scores for CI without downloading weights."""
    hw = load_hardware_fixture(hardware_class)
    selected = [t for t in DEFAULT_TASKS if tasks is None or t.id in tasks]
    results = [_stub_task_result(model_id, hardware_class, t, hw) for t in selected]
    overall = sum(
        r["score"] * next(t.weight for t in selected if t.id == r["task_id"]) for r in results
    )
    overall /= max(sum(t.weight for t in selected), 1e-9)
    return {
        "ok": True,
        "stub": True,
        "live": False,
        "model_id": model_id,
        "hardware_class": hardware_class,
        "hardware": hw,
        "tasks": results,
        "overall": round(overall, 4),
        "note": "Stub harness. Set BRAINFLOW_LIVE_BENCH=1 for Ollama live path.",
    }


def run_live_ollama_benchmark(
    *,
    model_id: str,
    hardware_class: str = "mid",
    tasks: list[str] | None = None,
    timeout_s: float = 60.0,
) -> dict[str, Any]:
    """Live shortlist bench against local Ollama. Gated by BRAINFLOW_LIVE_BENCH=1."""
    if not live_bench_enabled():
        return {
            "ok": False,
            "stub": False,
            "live": False,
            "error": "BRAINFLOW_LIVE_BENCH!=1 — refusing live network bench",
        }

    import sys

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "services" / "ai-worker"))
    from brainflow_worker.gateway.budget import RequestBudget
    from brainflow_worker.gateway.providers.ollama import OllamaAdapter

    adapter = OllamaAdapter()
    health = adapter.health(timeout_s=min(5.0, timeout_s))
    if not health.get("ok"):
        return {
            "ok": False,
            "stub": False,
            "live": True,
            "error": health.get("error") or "Ollama unavailable",
            "health": health,
        }

    model = model_id if model_id in (health.get("models") or []) else health.get("preferred_model")
    if not model:
        return {"ok": False, "stub": False, "live": True, "error": "No Ollama model available"}

    hw = load_hardware_fixture(hardware_class)
    selected = [t for t in DEFAULT_TASKS if tasks is None or t.id in tasks]
    if tasks is None:
        selected = [t for t in selected if t.id in {"plan_struct", "ttft", "tool_acc"}]

    budget = RequestBudget(max_tokens=2048, max_requests=len(selected) + 2, label="live_bench")
    results: list[dict[str, Any]] = []
    for t in selected:
        prompt = LIVE_PROMPTS.get(t.id, "Say OK.")
        messages = [
            {"role": "system", "content": prompt if t.kind != "latency" else "Be brief."},
            {"role": "user", "content": prompt if t.kind == "latency" else "Execute the task."},
        ]
        kwargs: dict[str, Any] = {"budget": budget, "max_tokens": 128}
        if "json_schema" in t.requires or t.kind in {"planning", "citation", "graph", "tools"}:
            kwargs["format"] = "json"
        t0 = time.perf_counter()
        try:
            raw = adapter.chat(model=str(model), messages=messages, timeout_s=timeout_s, **kwargs)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            text = str((raw.get("message") or {}).get("content") or "")
            ok = bool(text.strip())
            if t.kind == "tools":
                ok = "tool_calls" in text or "echo" in text
            elif "json_schema" in t.requires:
                cleaned = (
                    text.strip()
                    .removeprefix("```json")
                    .removeprefix("```")
                    .removesuffix("```")
                    .strip()
                )
                try:
                    json.loads(cleaned)
                    ok = True
                except Exception:  # noqa: BLE001
                    ok = False
            latency_score = max(0.0, min(1.0, 1.0 - (elapsed_ms / 30_000.0)))
            score = (0.7 if ok else 0.1) + 0.3 * latency_score
            results.append(
                {
                    "task_id": t.id,
                    "score": round(score, 4),
                    "latency_ms": round(elapsed_ms, 1),
                    "ok": ok,
                    "stub": False,
                    "sample": text[:240],
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "task_id": t.id,
                    "score": 0.0,
                    "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
                    "ok": False,
                    "stub": False,
                    "error": str(exc),
                }
            )

    overall = sum(
        r["score"] * next(t.weight for t in selected if t.id == r["task_id"]) for r in results
    )
    overall /= max(sum(t.weight for t in selected), 1e-9)
    return {
        "ok": any(r.get("ok") for r in results),
        "stub": False,
        "live": True,
        "model_id": model,
        "hardware_class": hardware_class,
        "hardware": hw,
        "tasks": results,
        "overall": round(overall, 4),
        "budget": budget.to_dict(),
        "note": "Live Ollama bench (BRAINFLOW_LIVE_BENCH=1)",
    }


def run_benchmark(
    *,
    model_id: str,
    hardware_class: str = "mid",
    tasks: list[str] | None = None,
) -> dict[str, Any]:
    """Dispatch stub vs live based on BRAINFLOW_LIVE_BENCH."""
    if live_bench_enabled():
        return run_live_ollama_benchmark(
            model_id=model_id, hardware_class=hardware_class, tasks=tasks
        )
    return run_stub_benchmark(model_id=model_id, hardware_class=hardware_class, tasks=tasks)


def main() -> None:
    print(json.dumps(run_benchmark(model_id="llama3.2:3b"), indent=2))


if __name__ == "__main__":
    main()
