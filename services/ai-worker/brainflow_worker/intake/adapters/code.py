"""Source-code adapter — text extract with line locators; never execute."""

from __future__ import annotations

from typing import Any

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, truncate_text, apply_security

CODE_EXTS = frozenset(
    {
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".kts",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".scala",
        ".r",
        ".sql",
        ".toml",
        ".ini",
        ".cfg",
        ".scss",
        ".css",
        ".less",
        ".vue",
        ".svelte",
        ".dart",
        ".lua",
        ".pl",
        ".pm",
        ".zig",
        ".nim",
    }
)


class CodeAdapter:
    id = "code"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime.startswith("text/x-") or mime in {
            "text/javascript",
            "application/javascript",
            "application/typescript",
            "text/x-python",
            "text/x-rust",
            "text/x-java-source",
        }:
            return True
        lower = (filename or "").lower()
        return any(lower.endswith(ext) for ext in CODE_EXTS)

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        # .js is also in executable quarantine list for archives — code adapter
        # still extracts text when routed for a linked source file.
        ext = ""
        if ctx.filename and "." in ctx.filename:
            ext = "." + ctx.filename.rsplit(".", 1)[-1].lower()
        mime = ctx.mime_type if ctx.mime_type != "application/octet-stream" else "text/x-code"
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type=mime,
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
            bundle["warnings"].append(issue("PartialSuccess", "replaced undecodable bytes"))

        text, truncated = truncate_text(text, ctx.limits.max_segment_chars)
        if truncated:
            bundle["warnings"].append(issue("Truncated", "source truncated to segment limit"))

        lines = text.splitlines()
        bundle["segments"].append(
            {
                "id": "code-0",
                "kind": "code",
                "text": text,
                "order": 0,
                "locator": {
                    "kind": "line",
                    "line_start": 1,
                    "line_end": max(1, len(lines)),
                },
                "confidence": 0.99,
            }
        )
        bundle["metadata"]["extra"] = {
            "language_hint": ext.lstrip(".") if ext else None,
            "line_count": len(lines),
            "executed": False,
        }
        bundle["confidence"] = 0.99
        apply_security(
            bundle,
            quarantine_actions=[*ctx.quarantine.actions, "source_not_executed"],
            active_content_flags=ctx.quarantine.active_content_flags,
            macros_blocked=ctx.quarantine.macros_blocked,
            scripts_stripped=ctx.quarantine.scripts_stripped,
        )
        return bundle
