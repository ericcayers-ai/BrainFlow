"""Planner-facing evidence formatting — untrusted by contract."""

from __future__ import annotations

from typing import Any

from brainflow_worker.kernel.delimit import UNTRUSTED_CLOSE, delimit_untrusted

EVIDENCE_CLOSE = UNTRUSTED_CLOSE


def format_untrusted_evidence_block(
    bundle: dict[str, Any],
    *,
    max_chars: int = 12_000,
) -> str:
    """Serialize bundle segments into a delimited untrusted evidence block.

    Callers must never concatenate this text into system prompts without delimiters.
    """
    if bundle.get("evidence_trust") != "untrusted":
        raise ValueError("bundle evidence_trust must be 'untrusted'")

    lines: list[str] = [
        f"bundle_id={bundle.get('bundle_id')}",
        f"adapter={bundle.get('metadata', {}).get('adapter_id')}",
        f"content_hash={bundle.get('source', {}).get('content_hash')}",
        "--- segments ---",
    ]
    used = 0
    for seg in bundle.get("segments") or []:
        text = seg.get("text") or ""
        chunk = f"[{seg.get('id')}|{seg.get('kind')}] {text}"
        if used + len(chunk) > max_chars:
            lines.append("...[truncated]...")
            break
        lines.append(chunk)
        used += len(chunk)
    return delimit_untrusted("\n".join(lines), source="document_bundle")


def assert_evidence_delimited(prompt: str) -> bool:
    """Return True if untrusted evidence appears only inside delimiters (basic check)."""
    open_tag = '<UNTRUSTED_EVIDENCE'
    if open_tag not in prompt:
        return True
    start = prompt.find(open_tag)
    end = prompt.find(EVIDENCE_CLOSE, start)
    return end != -1
