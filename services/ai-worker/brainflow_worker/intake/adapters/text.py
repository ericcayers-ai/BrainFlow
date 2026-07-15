"""Markdown and plain-text adapters."""

from __future__ import annotations

import re
from typing import Any

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, truncate_text, apply_security

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class PlainTextAdapter:
    id = "plain_text"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in {"text/plain", "text/log", "application/octet-stream"}:
            # Only claim octet-stream if clearly textual
            if mime == "application/octet-stream":
                return _looks_like_text(data) and not _looks_like_code(filename)
            return True
        lower = (filename or "").lower()
        return lower.endswith((".txt", ".log", ".text"))

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type=ctx.mime_type or "text/plain",
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        text, enc_warn = _decode(data)
        text, truncated = truncate_text(text, ctx.limits.max_segment_chars)
        if enc_warn:
            bundle["warnings"].append(issue("PartialSuccess", enc_warn))
        if truncated:
            bundle["warnings"].append(issue("Truncated", "text truncated to segment limit"))
        bundle["segments"].append(
            {
                "id": "seg-0",
                "kind": "text",
                "text": text,
                "order": 0,
                "locator": {"kind": "offset", "offset_start": 0, "offset_end": len(text)},
                "confidence": 0.95 if not enc_warn else 0.7,
            }
        )
        bundle["confidence"] = 0.95 if not enc_warn else 0.7
        apply_security(
            bundle,
            quarantine_actions=ctx.quarantine.actions,
            active_content_flags=ctx.quarantine.active_content_flags,
            macros_blocked=ctx.quarantine.macros_blocked,
            scripts_stripped=ctx.quarantine.scripts_stripped,
        )
        return bundle


class MarkdownAdapter:
    id = "markdown"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in {"text/markdown", "text/x-markdown"}:
            return True
        lower = (filename or "").lower()
        return lower.endswith((".md", ".markdown", ".mdx"))

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type="text/markdown",
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        text, enc_warn = _decode(data)
        text, truncated = truncate_text(text, ctx.limits.max_segment_chars)
        if enc_warn:
            bundle["warnings"].append(issue("PartialSuccess", enc_warn))
        if truncated:
            bundle["warnings"].append(issue("Truncated", "markdown truncated to segment limit"))

        headings: list[dict[str, Any]] = []
        path_stack: list[str] = []
        order = 0
        for match in _HEADING_RE.finditer(text):
            level = len(match.group(1))
            title = match.group(2).strip()
            path_stack = path_stack[: level - 1]
            path_stack.append(title)
            seg_id = f"h-{order}"
            headings.append(
                {
                    "level": level,
                    "text": title,
                    "path": list(path_stack),
                    "segment_id": seg_id,
                }
            )
            bundle["segments"].append(
                {
                    "id": seg_id,
                    "kind": "heading",
                    "text": title,
                    "order": order,
                    "locator": {
                        "kind": "heading_path",
                        "heading_path": list(path_stack),
                        "offset_start": match.start(),
                        "offset_end": match.end(),
                    },
                    "confidence": 1.0,
                }
            )
            order += 1

        bundle["segments"].append(
            {
                "id": "body",
                "kind": "text",
                "text": text,
                "order": order,
                "locator": {"kind": "offset", "offset_start": 0, "offset_end": len(text)},
                "confidence": 0.98,
            }
        )
        bundle["structure"]["headings"] = headings
        if path_stack or headings:
            bundle["metadata"]["title"] = headings[0]["text"] if headings else None
            if bundle["metadata"]["title"] is None:
                del bundle["metadata"]["title"]
        bundle["confidence"] = 0.98
        apply_security(
            bundle,
            quarantine_actions=ctx.quarantine.actions,
            active_content_flags=ctx.quarantine.active_content_flags,
            macros_blocked=ctx.quarantine.macros_blocked,
            scripts_stripped=ctx.quarantine.scripts_stripped,
        )
        return bundle


def _decode(data: bytes) -> tuple[str, str | None]:
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(enc), None if enc.startswith("utf") else f"decoded as {enc}"
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "replaced undecodable bytes"


def _looks_like_text(data: bytes) -> bool:
    if not data:
        return True
    sample = data[:4096]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _looks_like_code(filename: str | None) -> bool:
    if not filename:
        return False
    lower = filename.lower()
    return any(
        lower.endswith(ext)
        for ext in (
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".rs",
            ".go",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".cs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".scala",
            ".r",
            ".sql",
            ".sh",
        )
    )
