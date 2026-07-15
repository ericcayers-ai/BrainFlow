"""PDF text adapter (optional pypdf). Never executes embedded content."""

from __future__ import annotations

from typing import Any

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, truncate_text, apply_security


class PdfAdapter:
    id = "pdf"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime == "application/pdf" or data.startswith(b"%PDF"):
            return True
        return (filename or "").lower().endswith(".pdf")

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type="application/pdf",
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        # Heuristic encrypted PDF markers
        if b"/Encrypt" in data[: min(len(data), 200_000)]:
            bundle["errors"].append(
                issue("NeedsPassword", "PDF appears encrypted; password required")
            )
            apply_security(bundle, quarantine_actions=["noted_encrypted_pdf"])
            return bundle

        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            bundle["errors"].append(
                issue(
                    "NeedsAdapter",
                    "pypdf not installed; install intake extras for PDF text extraction",
                )
            )
            return _sec(bundle, ctx, 0.0)

        import io

        try:
            reader = PdfReader(io.BytesIO(data), strict=False)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "password" in msg or "encrypted" in msg:
                bundle["errors"].append(issue("NeedsPassword", f"PDF encrypted: {exc}"))
            else:
                bundle["errors"].append(issue("Corrupt", f"PDF open failed: {exc}"))
            return _sec(bundle, ctx, 0.0)

        if getattr(reader, "is_encrypted", False):
            bundle["errors"].append(issue("NeedsPassword", "PDF is encrypted"))
            return _sec(bundle, ctx, 0.0)

        n_pages = len(reader.pages)
        if n_pages > ctx.limits.max_pages:
            bundle["errors"].append(
                issue(
                    "ResourceLimit",
                    f"PDF has {n_pages} pages; max_pages={ctx.limits.max_pages}",
                )
            )
            return _sec(bundle, ctx, 0.0)

        pages_meta = []
        order = 0
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                bundle["warnings"].append(
                    issue("PartialSuccess", f"page {i + 1} extract failed: {exc}")
                )
                text = ""
            text, truncated = truncate_text(text, ctx.limits.max_segment_chars)
            if truncated:
                bundle["warnings"].append(issue("Truncated", f"page {i + 1} truncated"))
            seg_id = f"page-{i + 1}"
            bundle["segments"].append(
                {
                    "id": seg_id,
                    "kind": "text",
                    "text": text,
                    "order": order,
                    "locator": {"kind": "pdf_page", "page": i + 1},
                    "confidence": 0.85 if text.strip() else 0.3,
                }
            )
            pages_meta.append({"page": i + 1, "segment_ids": [seg_id]})
            order += 1
            if order >= ctx.limits.max_segments:
                bundle["warnings"].append(issue("ResourceLimit", "segment limit on PDF pages"))
                break

        if reader.metadata:
            title = getattr(reader.metadata, "title", None) or reader.metadata.get("/Title")
            if title:
                bundle["metadata"]["title"] = str(title)

        bundle["structure"]["pages"] = pages_meta
        if not any((s.get("text") or "").strip() for s in bundle["segments"]):
            bundle["warnings"].append(
                issue(
                    "PartialSuccess",
                    "No extractable text (possible scan); OCR not run in core adapter",
                )
            )
            bundle["confidence"] = 0.2
        else:
            bundle["confidence"] = 0.85
        apply_security(
            bundle,
            quarantine_actions=[*ctx.quarantine.actions, "pdf_js_not_executed"],
            active_content_flags=ctx.quarantine.active_content_flags,
            limits_applied={"max_pages": ctx.limits.max_pages},
        )
        return bundle


def _sec(bundle: dict[str, Any], ctx: AdapterContext, confidence: float) -> dict[str, Any]:
    bundle["confidence"] = confidence
    apply_security(
        bundle,
        quarantine_actions=ctx.quarantine.actions,
        active_content_flags=ctx.quarantine.active_content_flags,
    )
    return bundle
