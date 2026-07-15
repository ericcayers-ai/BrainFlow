"""Archive adapter with nesting depth and decompression ratio limits."""

from __future__ import annotations

import io
import tarfile
import zipfile
from typing import Any

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, truncate_text, apply_security
from brainflow_worker.intake.quarantine import quarantine_archive_entry, merge_quarantine


class ArchiveAdapter:
    id = "archive"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in {
            "application/zip",
            "application/x-zip-compressed",
            "application/gzip",
            "application/x-tar",
            "application/x-gtar",
        }:
            # Prefer office adapters when filename indicates OOXML
            lower = (filename or "").lower()
            if lower.endswith(
                (
                    ".docx",
                    ".pptx",
                    ".xlsx",
                    ".docm",
                    ".pptm",
                    ".xlsm",
                    ".odt",
                    ".ods",
                    ".odp",
                )
            ):
                return False
            # ODF packages sniffed as zip — defer to OpenDocumentAdapter
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    if "mimetype" in zf.namelist():
                        mt = zf.read("mimetype").decode("utf-8", errors="replace")
                        if mt.startswith("application/vnd.oasis.opendocument."):
                            return False
            except (zipfile.BadZipFile, OSError, KeyError):
                pass
            return True
        lower = (filename or "").lower()
        return lower.endswith((".zip", ".tar", ".tgz", ".tar.gz"))

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type=ctx.mime_type or "application/zip",
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        depth_err = ctx.tracker.check_depth(ctx.depth)
        if depth_err:
            bundle["errors"].append(issue("ResourceLimit", depth_err))
            return _done(bundle, ctx, 0.0)

        if data[:2] == b"PK":
            return _extract_zip(data, ctx, bundle)
        if tarfile.is_tarfile(io.BytesIO(data)):
            return _extract_tar(data, ctx, bundle)

        bundle["errors"].append(issue("Corrupt", "Unrecognized or corrupt archive"))
        return _done(bundle, ctx, 0.0)


def _extract_zip(data: bytes, ctx: AdapterContext, bundle: dict[str, Any]) -> dict[str, Any]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        bundle["errors"].append(issue("Corrupt", f"Bad zip: {exc}"))
        return _done(bundle, ctx, 0.0)

    order = 0
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            entry_err = ctx.tracker.check_entry_count()
            if entry_err:
                bundle["errors"].append(issue("ResourceLimit", entry_err))
                return _done(bundle, ctx, 0.2)

            q = quarantine_archive_entry(info.filename)
            ctx.quarantine = merge_quarantine(ctx.quarantine, q)
            if q.blocked:
                bundle["warnings"].append(
                    issue(
                        "Quarantined",
                        q.block_reason or f"blocked entry {info.filename}",
                        {"entry": info.filename},
                    )
                )
                continue

            # Zip bomb checks using declared sizes before read
            compressed = info.compress_size or 1
            expanded = info.file_size or 0
            ratio_err = ctx.tracker.add_decompressed(compressed, expanded)
            if ratio_err:
                bundle["errors"].append(
                    issue(
                        "ResourceLimit",
                        ratio_err,
                        {"entry": info.filename, "compress_size": compressed, "file_size": expanded},
                    )
                )
                return _done(bundle, ctx, 0.2)

            # Nested archive depth
            nested = info.filename.lower().endswith((".zip", ".tar", ".tgz", ".tar.gz"))
            if nested and ctx.depth + 1 > ctx.limits.max_archive_depth:
                bundle["errors"].append(
                    issue(
                        "ResourceLimit",
                        f"nested archive {info.filename} exceeds max_archive_depth",
                    )
                )
                return _done(bundle, ctx, 0.2)

            try:
                # Cap read to remaining decompressed budget
                remaining = ctx.limits.max_decompressed_bytes - (
                    ctx.tracker.decompressed_bytes - expanded
                )
                raw = zf.read(info)
                if len(raw) > remaining + expanded:
                    bundle["errors"].append(issue("ResourceLimit", "read exceeded decompressed budget"))
                    return _done(bundle, ctx, 0.2)
            except Exception as exc:  # noqa: BLE001
                bundle["warnings"].append(
                    issue("PartialSuccess", f"could not read {info.filename}: {exc}")
                )
                continue

            text_preview = ""
            try:
                text_preview = raw.decode("utf-8")
            except UnicodeDecodeError:
                text_preview = f"<binary {len(raw)} bytes>"
            text_preview, trunc = truncate_text(text_preview, min(8000, ctx.limits.max_segment_chars))
            if trunc:
                bundle["warnings"].append(
                    issue("Truncated", f"archive entry preview truncated: {info.filename}")
                )
            bundle["segments"].append(
                {
                    "id": f"entry-{order}",
                    "kind": "text",
                    "text": text_preview,
                    "order": order,
                    "locator": {"kind": "archive_entry", "entry_path": info.filename},
                    "confidence": 0.7,
                }
            )
            order += 1
            if order >= ctx.limits.max_segments:
                bundle["warnings"].append(issue("ResourceLimit", "archive segment limit"))
                break

    bundle["metadata"]["extra"] = {"entry_count": order, "archive_format": "zip"}
    bundle["confidence"] = 0.8 if bundle["segments"] else 0.3
    if not bundle["segments"] and not bundle["errors"]:
        bundle["warnings"].append(issue("PartialSuccess", "archive yielded no readable entries"))
    return _done(bundle, ctx, bundle["confidence"])


def _extract_tar(data: bytes, ctx: AdapterContext, bundle: dict[str, Any]) -> dict[str, Any]:
    try:
        tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
    except tarfile.TarError as exc:
        bundle["errors"].append(issue("Corrupt", f"Bad tar: {exc}"))
        return _done(bundle, ctx, 0.0)

    order = 0
    with tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            entry_err = ctx.tracker.check_entry_count()
            if entry_err:
                bundle["errors"].append(issue("ResourceLimit", entry_err))
                return _done(bundle, ctx, 0.2)
            q = quarantine_archive_entry(member.name)
            ctx.quarantine = merge_quarantine(ctx.quarantine, q)
            if q.blocked:
                bundle["warnings"].append(
                    issue("Quarantined", q.block_reason or member.name, {"entry": member.name})
                )
                continue
            size = int(member.size or 0)
            ratio_err = ctx.tracker.add_decompressed(max(1, size // 10), size)
            if ratio_err:
                bundle["errors"].append(issue("ResourceLimit", ratio_err))
                return _done(bundle, ctx, 0.2)
            try:
                f = tf.extractfile(member)
                raw = f.read() if f else b""
            except Exception as exc:  # noqa: BLE001
                bundle["warnings"].append(
                    issue("PartialSuccess", f"could not read {member.name}: {exc}")
                )
                continue
            try:
                preview = raw.decode("utf-8")
            except UnicodeDecodeError:
                preview = f"<binary {len(raw)} bytes>"
            preview, _ = truncate_text(preview, 8000)
            bundle["segments"].append(
                {
                    "id": f"entry-{order}",
                    "kind": "text",
                    "text": preview,
                    "order": order,
                    "locator": {"kind": "archive_entry", "entry_path": member.name},
                    "confidence": 0.7,
                }
            )
            order += 1
    bundle["metadata"]["extra"] = {"entry_count": order, "archive_format": "tar"}
    bundle["confidence"] = 0.8 if bundle["segments"] else 0.3
    return _done(bundle, ctx, bundle["confidence"])


def _done(bundle: dict[str, Any], ctx: AdapterContext, confidence: float) -> dict[str, Any]:
    bundle["confidence"] = confidence
    apply_security(
        bundle,
        quarantine_actions=ctx.quarantine.actions,
        active_content_flags=ctx.quarantine.active_content_flags,
        macros_blocked=ctx.quarantine.macros_blocked,
        scripts_stripped=ctx.quarantine.scripts_stripped,
        limits_applied={
            "max_archive_depth": ctx.limits.max_archive_depth,
            "max_decompression_ratio": ctx.limits.max_decompression_ratio,
            "max_decompressed_bytes": ctx.limits.max_decompressed_bytes,
        },
    )
    return bundle
