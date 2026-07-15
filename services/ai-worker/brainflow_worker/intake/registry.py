"""Capability registry — routes bytes to the right adapter."""

from __future__ import annotations

from typing import Any

from brainflow_worker.intake.adapters.archive import ArchiveAdapter
from brainflow_worker.intake.adapters.code import CodeAdapter
from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.adapters.html import HtmlAdapter
from brainflow_worker.intake.adapters.image import ImageAdapter
from brainflow_worker.intake.adapters.media import MediaAdapter
from brainflow_worker.intake.adapters.notebook import NotebookAdapter
from brainflow_worker.intake.adapters.office import DocxAdapter, PptxAdapter, XlsxAdapter
from brainflow_worker.intake.adapters.opendocument import OpenDocumentAdapter
from brainflow_worker.intake.adapters.pdf import PdfAdapter
from brainflow_worker.intake.adapters.structured import CsvAdapter, JsonAdapter, YamlAdapter
from brainflow_worker.intake.adapters.text import MarkdownAdapter, PlainTextAdapter
from brainflow_worker.intake.bundle import empty_bundle, issue, apply_security


class UnknownBinaryAdapter:
    id = "unknown_binary"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        return True

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type=ctx.mime_type or "application/octet-stream",
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        # Printable strings only
        printable = []
        buf = bytearray()
        for b in data[: min(len(data), 64_000)]:
            if 32 <= b < 127 or b in (9, 10, 13):
                buf.append(b)
            else:
                if len(buf) >= 4:
                    printable.append(buf.decode("ascii", errors="ignore"))
                buf.clear()
        if len(buf) >= 4:
            printable.append(buf.decode("ascii", errors="ignore"))
        strings = "\n".join(printable[:200])
        if strings.strip():
            bundle["segments"].append(
                {
                    "id": "strings-0",
                    "kind": "raw_meta",
                    "text": strings[:8000],
                    "order": 0,
                    "confidence": 0.2,
                }
            )
            bundle["warnings"].append(
                issue(
                    "NeedsAdapter",
                    "Unknown binary: metadata/printable strings only; install adapter pack",
                )
            )
            bundle["confidence"] = 0.2
        else:
            bundle["errors"].append(
                issue(
                    "NeedsAdapter",
                    "No semantic extract available for this file type",
                )
            )
            bundle["confidence"] = 0.0
        apply_security(
            bundle,
            quarantine_actions=[*ctx.quarantine.actions, "binary_not_executed"],
            active_content_flags=ctx.quarantine.active_content_flags,
        )
        return bundle


# Order matters: more specific adapters before catch-alls.
ADAPTERS: list[Any] = [
    MarkdownAdapter(),
    HtmlAdapter(),
    NotebookAdapter(),  # before JsonAdapter (.ipynb is JSON)
    JsonAdapter(),
    YamlAdapter(),
    CsvAdapter(),
    PdfAdapter(),
    DocxAdapter(),
    PptxAdapter(),
    XlsxAdapter(),
    OpenDocumentAdapter(),
    ImageAdapter(),
    MediaAdapter(),
    CodeAdapter(),
    ArchiveAdapter(),
    PlainTextAdapter(),
    UnknownBinaryAdapter(),
]


def resolve_adapter(mime: str, filename: str | None, data: bytes) -> Any:
    for adapter in ADAPTERS:
        if adapter.id == "unknown_binary":
            continue
        if adapter.supports(mime, filename, data):
            return adapter
    return ADAPTERS[-1]


def list_adapters() -> list[dict[str, str]]:
    return [{"id": a.id, "version": "1.0.0"} for a in ADAPTERS if a.id != "unknown_binary"]
