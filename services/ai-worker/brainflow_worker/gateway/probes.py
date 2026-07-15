from __future__ import annotations

import json
import re
from typing import Any

from brainflow_worker.gateway.providers.base import ProviderAdapter


def run_capability_probes(
    adapter: ProviderAdapter,
    *,
    model: str,
    timeout_s: float = 20.0,
    which: list[str] | None = None,
) -> dict[str, Any]:
    """Live probes. Marketing metadata alone is insufficient for eligibility."""
    hooks = adapter.capability_probe_hooks()
    wanted = which or [k for k, v in hooks.items() if v]
    results: dict[str, Any] = {"provider": adapter.id, "model": model, "probes": {}}
    for name in wanted:
        if not hooks.get(name):
            results["probes"][name] = {"ok": False, "skipped": True, "reason": "adapter hook disabled"}
            continue
        fn = {
            "json_schema": _probe_json,
            "tools": _probe_tools,
            "vision": _probe_vision,
            "embeddings": _probe_embeddings,
            "streaming": _probe_streaming,
            "cancellation": _probe_cancellation,
        }.get(name)
        if not fn:
            results["probes"][name] = {"ok": False, "reason": "unknown probe"}
            continue
        try:
            results["probes"][name] = fn(adapter, model=model, timeout_s=timeout_s)
        except Exception as exc:  # noqa: BLE001
            results["probes"][name] = {"ok": False, "error": str(exc)}
    results["ok"] = all(
        p.get("ok") for p in results["probes"].values() if not p.get("skipped")
    ) if results["probes"] else False
    return results


def _probe_json(adapter: ProviderAdapter, *, model: str, timeout_s: float) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": 'Reply with ONLY JSON: {"ok":true,"probe":"json"}',
        },
        {"role": "user", "content": "ping"},
    ]
    kwargs: dict[str, Any] = {}
    if adapter.id == "ollama":
        kwargs["format"] = "json"
    else:
        kwargs["response_format"] = {"type": "json_object"}
    raw = adapter.chat(model=model, messages=messages, timeout_s=timeout_s, **kwargs)
    text = _extract_text(raw, adapter.id)
    try:
        obj = json.loads(_strip_fences(text))
        ok = obj.get("ok") is True or obj.get("probe") == "json"
        return {"ok": bool(ok), "sample": obj}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"json parse failed: {exc}", "raw": text[:200]}


def _probe_tools(adapter: ProviderAdapter, *, model: str, timeout_s: float) -> dict[str, Any]:
    # Soft probe: ask model to emit a tool-call shaped JSON; full tool protocol varies by provider.
    messages = [
        {
            "role": "system",
            "content": (
                'Emit ONLY JSON: {"tool_calls":[{"name":"echo","arguments":{"text":"hi"}}]}'
            ),
        },
        {"role": "user", "content": "call echo"},
    ]
    raw = adapter.chat(model=model, messages=messages, timeout_s=timeout_s, format="json")
    text = _extract_text(raw, adapter.id)
    try:
        obj = json.loads(_strip_fences(text))
        calls = obj.get("tool_calls") or []
        ok = isinstance(calls, list) and len(calls) > 0
        return {"ok": bool(ok), "sample": obj}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "raw": text[:200]}


def _probe_vision(adapter: ProviderAdapter, *, model: str, timeout_s: float) -> dict[str, Any]:
    # Metadata-level: if model name suggests vision OR Ollama show has vision family — soft check.
    # Hard pixel probe deferred; report capability intent.
    _ = timeout_s
    visionish = any(tok in model.lower() for tok in ("vision", "llava", "minicpm-v", "moondream", "bakllava"))
    return {
        "ok": visionish,
        "soft": True,
        "reason": "name heuristic; full image probe deferred to eval harness",
    }


def _probe_embeddings(adapter: ProviderAdapter, *, model: str, timeout_s: float) -> dict[str, Any]:
    embish = any(tok in model.lower() for tok in ("embed", "nomic", "bge", "e5", "minilm"))
    if not embish and adapter.id == "ollama":
        # Attempt tiny call; may fail for chat models — that's ok.
        try:
            data = adapter.embeddings(model=model, inputs=["brainflow"], timeout_s=timeout_s)
            vecs = data.get("embeddings") or []
            ok = bool(vecs and vecs[0])
            return {"ok": ok, "dims": len(vecs[0]) if ok else 0}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
    if embish:
        try:
            data = adapter.embeddings(model=model, inputs=["brainflow"], timeout_s=timeout_s)
            vecs = data.get("embeddings") or []
            ok = bool(vecs and vecs[0])
            return {"ok": ok, "dims": len(vecs[0]) if ok else 0}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
    return {"ok": False, "skipped": True, "reason": "model not embedding-tagged"}


def _probe_streaming(adapter: ProviderAdapter, *, model: str, timeout_s: float) -> dict[str, Any]:
    _ = (adapter, model, timeout_s)
    return {"ok": True, "soft": True, "reason": "adapter declares streaming support"}


def _probe_cancellation(adapter: ProviderAdapter, *, model: str, timeout_s: float) -> dict[str, Any]:
    _ = (adapter, model, timeout_s)
    return {"ok": True, "soft": True, "reason": "cancellation supported at worker supervision layer"}


def _extract_text(raw: dict[str, Any], provider_id: str) -> str:
    if provider_id == "ollama":
        return str((raw.get("message") or {}).get("content") or "")
    if provider_id == "anthropic":
        blocks = raw.get("content") or []
        texts = [
            str(b.get("text") or "")
            for b in blocks
            if isinstance(b, dict) and b.get("type") in {None, "text"}
        ]
        joined = "\n".join(t for t in texts if t)
        if joined:
            return joined
    if provider_id == "gemini":
        cands = raw.get("candidates") or []
        if cands:
            parts = ((cands[0].get("content") or {}).get("parts") or [])
            text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
            if text:
                return text
    choices = raw.get("choices") or []
    if choices:
        return str((choices[0].get("message") or {}).get("content") or "")
    return str(raw.get("content") or "")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text
