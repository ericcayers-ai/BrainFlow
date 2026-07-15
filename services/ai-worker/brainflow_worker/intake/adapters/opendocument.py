"""OpenDocument (ODT/ODS/ODP) adapters.

Prefer odfpy when installed (intake extras). Fall back to ZIP+content.xml text
extraction so core can still produce evidence without inventing structure.
Macros / scripts inside the package are quarantined, never executed.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, truncate_text, apply_security
from brainflow_worker.intake.quarantine import (
    QuarantineResult,
    quarantine_path_name,
    merge_quarantine,
)

ODT_MIME = "application/vnd.oasis.opendocument.text"
ODS_MIME = "application/vnd.oasis.opendocument.spreadsheet"
ODP_MIME = "application/vnd.oasis.opendocument.presentation"


def _scan_odf_package(data: bytes, ctx: AdapterContext) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                q = quarantine_path_name(name)
                if q.macros_blocked or q.blocked or q.scripts_stripped:
                    ctx.quarantine = merge_quarantine(ctx.quarantine, q)
                lower = name.lower()
                if "basic" in lower or lower.endswith(".bas") or "macros" in lower:
                    ctx.quarantine = merge_quarantine(
                        ctx.quarantine,
                        QuarantineResult(
                            macros_blocked=True,
                            actions=["odf_macros_quarantined"],
                            active_content_flags=["odf_macro_entry"],
                        ),
                    )
    except zipfile.BadZipFile:
        pass


def _is_odf_zip(data: bytes) -> bool:
    if data[:4] != b"PK\x03\x04":
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
            return "mimetype" in names and "content.xml" in names
    except zipfile.BadZipFile:
        return False


def _read_mimetype(data: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return zf.read("mimetype").decode("utf-8", errors="replace").strip()
    except (zipfile.BadZipFile, KeyError, OSError):
        return None


def _odfpy_extract(data: bytes, kind: str, ctx: AdapterContext, bundle: dict[str, Any]) -> bool:
    """Return True if odfpy handled extraction; False if not installed."""
    try:
        from odf.opendocument import load  # type: ignore
        from odf import text as odf_text  # type: ignore
        from odf.table import Table, TableRow, TableCell  # type: ignore
        from odf.draw import Page  # type: ignore
    except ImportError:
        return False

    try:
        doc = load(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        bundle["errors"].append(issue("Corrupt", f"OpenDocument open failed: {exc}"))
        return True

    order = 0
    if kind == "odt":
        for i, para in enumerate(doc.getElementsByType(odf_text.P)):
            t = _odf_node_text(para).strip()
            if not t:
                continue
            t, trunc = truncate_text(t, ctx.limits.max_segment_chars)
            if trunc:
                bundle["warnings"].append(issue("Truncated", f"paragraph {i} truncated"))
            bundle["segments"].append(
                {
                    "id": f"p-{i}",
                    "kind": "text",
                    "text": t,
                    "order": order,
                    "locator": {
                        "kind": "custom",
                        "extra": {"odf": "paragraph", "index": i},
                    },
                    "confidence": 0.95,
                }
            )
            order += 1
            if order >= ctx.limits.max_segments:
                bundle["warnings"].append(issue("ResourceLimit", "ODT segment limit"))
                break
    elif kind == "ods":
        sheets_meta = []
        for ti, table in enumerate(doc.getElementsByType(Table)):
            name = table.getAttribute("name") or f"Sheet{ti + 1}"
            seg_ids: list[str] = []
            rows_preview: list[list[str]] = []
            for ri, row in enumerate(table.getElementsByType(TableRow)):
                if ri >= ctx.limits.max_csv_rows:
                    bundle["warnings"].append(
                        issue("ResourceLimit", f"sheet {name} row limit")
                    )
                    break
                cells = []
                for cell in row.getElementsByType(TableCell):
                    cells.append(_odf_node_text(cell).strip())
                rows_preview.append(cells)
                for ci, val in enumerate(cells):
                    if not val:
                        continue
                    sid = f"{name}-r{ri}c{ci}"
                    bundle["segments"].append(
                        {
                            "id": sid,
                            "kind": "cell",
                            "text": val,
                            "order": order,
                            "locator": {
                                "kind": "custom",
                                "extra": {
                                    "odf": "cell",
                                    "sheet": name,
                                    "row": ri,
                                    "col": ci,
                                },
                            },
                            "confidence": 0.95,
                        }
                    )
                    seg_ids.append(sid)
                    order += 1
                    if order >= ctx.limits.max_segments:
                        break
                if order >= ctx.limits.max_segments:
                    break
            sheets_meta.append({"name": name, "segment_ids": seg_ids[:50]})
            if rows_preview:
                bundle["structure"].setdefault("tables", []).append(
                    {
                        "id": f"sheet-{name}",
                        "caption": name,
                        "rows": rows_preview[:100],
                        "locator": {"kind": "custom", "extra": {"sheet": name}},
                    }
                )
            if order >= ctx.limits.max_segments:
                bundle["warnings"].append(issue("ResourceLimit", "ODS segment limit"))
                break
        bundle["structure"]["sheets"] = sheets_meta
    else:  # odp
        slides_meta = []
        pages = doc.getElementsByType(Page)
        if len(pages) > ctx.limits.max_slides:
            bundle["errors"].append(
                issue(
                    "ResourceLimit",
                    f"ODP has {len(pages)} slides; max={ctx.limits.max_slides}",
                )
            )
            return True
        for si, page in enumerate(pages):
            body = _odf_node_text(page).strip()
            body, trunc = truncate_text(body, ctx.limits.max_segment_chars)
            if trunc:
                bundle["warnings"].append(issue("Truncated", f"slide {si + 1} truncated"))
            seg_id = f"slide-{si + 1}"
            bundle["segments"].append(
                {
                    "id": seg_id,
                    "kind": "text",
                    "text": body,
                    "order": order,
                    "locator": {
                        "kind": "custom",
                        "extra": {"odf": "slide", "slide": si + 1},
                    },
                    "confidence": 0.9,
                }
            )
            slides_meta.append(
                {
                    "slide": si + 1,
                    "title": body.split("\n", 1)[0][:120] if body else "",
                    "segment_ids": [seg_id],
                }
            )
            order += 1
        bundle["structure"]["slides"] = slides_meta

    bundle["metadata"]["extra"] = {"backend": "odfpy", "odf_kind": kind}
    bundle["confidence"] = 0.95 if bundle["segments"] else 0.4
    return True


def _odf_node_text(node: Any) -> str:
    parts: list[str] = []

    def walk(n: Any) -> None:
        if n.nodeType == n.TEXT_NODE:
            parts.append(n.data or "")
            return
        for child in getattr(n, "childNodes", []) or []:
            walk(child)

    walk(node)
    return " ".join("".join(parts).split())


def _xml_fallback_extract(
    data: bytes, kind: str, ctx: AdapterContext, bundle: dict[str, Any]
) -> None:
    """Best-effort text from content.xml without odfpy."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml_bytes = zf.read("content.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        bundle["errors"].append(issue("Corrupt", f"OpenDocument package invalid: {exc}"))
        return

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        bundle["errors"].append(issue("Corrupt", f"content.xml parse failed: {exc}"))
        return

    # Collect text:paragraph and table:table-cell text nodes
    texts: list[str] = []
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]
        if tag in {"p", "h", "span"} and (elem.text or "").strip():
            texts.append((elem.text or "").strip())
        elif tag == "table-cell":
            cell_bits = [
                (t or "").strip()
                for t in elem.itertext()
                if (t or "").strip()
            ]
            if cell_bits:
                texts.append(" ".join(cell_bits))

    # De-dupe consecutive identical lines (ODF nesting often repeats)
    deduped: list[str] = []
    for t in texts:
        if not deduped or deduped[-1] != t:
            deduped.append(t)

    order = 0
    for i, t in enumerate(deduped):
        t, trunc = truncate_text(t, ctx.limits.max_segment_chars)
        if trunc:
            bundle["warnings"].append(issue("Truncated", f"odf text {i} truncated"))
        bundle["segments"].append(
            {
                "id": f"odf-{i}",
                "kind": "text" if kind != "ods" else "cell",
                "text": t,
                "order": order,
                "locator": {
                    "kind": "custom",
                    "extra": {"odf": kind, "index": i, "backend": "content.xml"},
                },
                "confidence": 0.75,
            }
        )
        order += 1
        if order >= ctx.limits.max_segments:
            bundle["warnings"].append(issue("ResourceLimit", "ODF segment limit"))
            break

    bundle["metadata"]["extra"] = {"backend": "content.xml", "odf_kind": kind}
    if not bundle["segments"]:
        bundle["warnings"].append(
            issue(
                "PartialSuccess",
                "OpenDocument opened but no text nodes found; "
                "install intake extras (odfpy) for richer structure",
            )
        )
        bundle["confidence"] = 0.2
    else:
        bundle["confidence"] = 0.75
        bundle["warnings"].append(
            issue(
                "PartialSuccess",
                "odfpy not installed; used content.xml fallback "
                "(install intake extras for structured ODF extract)",
            )
        )


class OpenDocumentAdapter:
    """Routes ODT / ODS / ODP by mimetype or extension."""

    id = "opendocument"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in {ODT_MIME, ODS_MIME, ODP_MIME}:
            return True
        lower = (filename or "").lower()
        if lower.endswith((".odt", ".ods", ".odp")):
            return True
        if _is_odf_zip(data):
            mt = _read_mimetype(data) or ""
            return mt.startswith("application/vnd.oasis.opendocument.")
        return False

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        mt = _read_mimetype(data) if data[:4] == b"PK\x03\x04" else None
        lower = (ctx.filename or "").lower()
        if lower.endswith(".ods") or (mt and "spreadsheet" in mt) or mt == ODS_MIME:
            kind, mime = "ods", ODS_MIME
        elif lower.endswith(".odp") or (mt and "presentation" in mt) or mt == ODP_MIME:
            kind, mime = "odp", ODP_MIME
        else:
            kind, mime = "odt", ODT_MIME

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

        if data[:4] != b"PK\x03\x04":
            bundle["errors"].append(issue("Corrupt", "OpenDocument must be a ZIP package"))
            return _done(bundle, ctx, 0.0)

        _scan_odf_package(data, ctx)
        if ctx.quarantine.macros_blocked:
            bundle["warnings"].append(
                issue("Quarantined", "ODF macro/basic payload detected; not executed")
            )

        handled = _odfpy_extract(data, kind, ctx, bundle)
        if not handled:
            # No odfpy — still extract via XML rather than NeedsAdapter-only,
            # but document the optional richer path.
            if not _is_odf_zip(data):
                bundle["errors"].append(
                    issue(
                        "NeedsAdapter",
                        "OpenDocument package unreadable and odfpy not installed; "
                        "install intake extras (odfpy)",
                    )
                )
            else:
                _xml_fallback_extract(data, kind, ctx, bundle)

        return _done(bundle, ctx, bundle.get("confidence", 0.0))


def _done(bundle: dict[str, Any], ctx: AdapterContext, confidence: float) -> dict[str, Any]:
    bundle["confidence"] = confidence
    apply_security(
        bundle,
        quarantine_actions=[*ctx.quarantine.actions, "odf_not_executed"],
        active_content_flags=ctx.quarantine.active_content_flags,
        macros_blocked=ctx.quarantine.macros_blocked,
        scripts_stripped=ctx.quarantine.scripts_stripped,
    )
    return bundle
