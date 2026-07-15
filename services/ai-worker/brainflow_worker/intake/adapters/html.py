"""HTML adapter with active-content stripping (never fetches remotes)."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, truncate_text, apply_security
from brainflow_worker.intake.quarantine import strip_html_active_content, merge_quarantine


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.headings: list[tuple[int, str]] = []
        self._skip = False
        self._heading_level: int | None = None
        self._heading_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript"}:
            self._skip = True
            return
        if t in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading_level = int(t[1])
            self._heading_buf = []
        if t in {"p", "div", "br", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript"}:
            self._skip = False
            return
        if t in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading_level:
            text = "".join(self._heading_buf).strip()
            if text:
                self.headings.append((self._heading_level, text))
                self.parts.append(text + "\n")
            self._heading_level = None
            self._heading_buf = []

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._heading_level is not None:
            self._heading_buf.append(data)
        else:
            self.parts.append(data)


class HtmlAdapter:
    id = "html"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in {"text/html", "application/xhtml+xml"}:
            return True
        lower = (filename or "").lower()
        return lower.endswith((".html", ".htm", ".xhtml"))

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type="text/html",
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        raw = data.decode("utf-8", errors="replace")
        cleaned, q = strip_html_active_content(raw)
        ctx.quarantine = merge_quarantine(ctx.quarantine, q)

        title_m = re.search(r"<title[^>]*>(.*?)</title>", cleaned, re.I | re.S)
        if title_m:
            bundle["metadata"]["title"] = re.sub(r"\s+", " ", title_m.group(1)).strip()

        parser = _TextExtractor()
        try:
            parser.feed(cleaned)
            parser.close()
        except Exception as exc:  # noqa: BLE001
            bundle["errors"].append(issue("Corrupt", f"HTML parse failed: {exc}"))
            bundle["confidence"] = 0.0
            apply_security(
                bundle,
                quarantine_actions=ctx.quarantine.actions,
                active_content_flags=ctx.quarantine.active_content_flags,
                scripts_stripped=ctx.quarantine.scripts_stripped,
            )
            return bundle

        text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        text, truncated = truncate_text(text, ctx.limits.max_segment_chars)
        if truncated:
            bundle["warnings"].append(issue("Truncated", "HTML text truncated"))

        headings = []
        path_stack: list[str] = []
        for i, (level, htext) in enumerate(parser.headings):
            path_stack = path_stack[: level - 1]
            path_stack.append(htext)
            sid = f"h-{i}"
            headings.append(
                {"level": level, "text": htext, "path": list(path_stack), "segment_id": sid}
            )
            bundle["segments"].append(
                {
                    "id": sid,
                    "kind": "heading",
                    "text": htext,
                    "order": i,
                    "locator": {"kind": "heading_path", "heading_path": list(path_stack)},
                    "confidence": 0.9,
                }
            )
        bundle["segments"].append(
            {
                "id": "body",
                "kind": "text",
                "text": text,
                "order": len(headings),
                "locator": {"kind": "offset", "offset_start": 0, "offset_end": len(text)},
                "confidence": 0.9,
            }
        )
        bundle["structure"]["headings"] = headings
        bundle["confidence"] = 0.9
        if ctx.quarantine.scripts_stripped:
            bundle["warnings"].append(
                issue("Quarantined", "Active HTML scripts/handlers stripped before extract")
            )
        apply_security(
            bundle,
            quarantine_actions=ctx.quarantine.actions,
            active_content_flags=ctx.quarantine.active_content_flags,
            scripts_stripped=ctx.quarantine.scripts_stripped,
            macros_blocked=ctx.quarantine.macros_blocked,
            limits_applied={"allow_remote_fetch": False},
        )
        return bundle
