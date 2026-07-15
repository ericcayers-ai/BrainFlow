"""Sandboxed intake pipeline entry points."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, apply_security
from brainflow_worker.intake.evidence import format_untrusted_evidence_block
from brainflow_worker.intake.identity import identify
from brainflow_worker.intake.limits import DEFAULT_LIMITS, IntakeLimits, LimitTracker
from brainflow_worker.intake.quarantine import quarantine_path_name
from brainflow_worker.intake.registry import list_adapters, resolve_adapter
from brainflow_worker.intake.schema_validate import validate_document_bundle


def analyze_path(
    path: str | Path,
    *,
    path_mode: str = "link",
    file_id: str | None = None,
    limits: IntakeLimits | None = None,
    include_evidence_block: bool = True,
) -> dict[str, Any]:
    """Read a file, run intake, return DocumentBundle (+ optional evidence block)."""
    p = Path(path)
    data = p.read_bytes()
    pre_hash = identify(data, p.name).content_hash
    result = analyze_bytes(
        data,
        filename=p.name,
        path=str(p.resolve()),
        path_mode=path_mode,
        file_id=file_id,
        limits=limits,
        include_evidence_block=include_evidence_block,
        modified_at=_mtime_iso(p),
    )
    # AC-ING-01: linked source hash unchanged after full intake
    post = identify(p.read_bytes(), p.name)
    if post.content_hash != pre_hash:
        raise RuntimeError("source file mutated during intake (forbidden)")
    if result["bundle"]["source"]["content_hash"] != pre_hash:
        raise RuntimeError("bundle content_hash mismatch vs source")
    return result


def analyze_bytes(
    data: bytes,
    *,
    filename: str | None = None,
    path: str | None = None,
    path_mode: str = "link",
    file_id: str | None = None,
    limits: IntakeLimits | None = None,
    include_evidence_block: bool = True,
    modified_at: str | None = None,
    depth: int = 0,
) -> dict[str, Any]:
    limits = limits or DEFAULT_LIMITS
    tracker = LimitTracker(limits=limits)
    file_id = file_id or str(uuid.uuid4())

    size_err = tracker.check_file_size(len(data))
    identity = identify(data, filename)

    if size_err:
        bundle = empty_bundle(
            file_id=file_id,
            content_hash=identity.content_hash,
            mime_type=identity.sniffed_mime,
            size_bytes=identity.size_bytes,
            path=path,
            path_mode=path_mode,
            adapter_id="limits",
            sniffed_mime=identity.sniffed_mime,
            modified_at=modified_at,
        )
        bundle["errors"].append(issue("ResourceLimit", size_err))
        apply_security(bundle, limits_applied={"max_file_bytes": limits.max_file_bytes})
        return _wrap(bundle, include_evidence_block)

    q = quarantine_path_name(filename or path or "unknown")
    if q.blocked and identity.extension_guess in {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".msi",
        ".scr",
        ".com",
    }:
        bundle = empty_bundle(
            file_id=file_id,
            content_hash=identity.content_hash,
            mime_type=identity.sniffed_mime,
            size_bytes=identity.size_bytes,
            path=path,
            path_mode=path_mode,
            adapter_id="quarantine",
            sniffed_mime=identity.sniffed_mime,
            modified_at=modified_at,
        )
        bundle["errors"].append(
            issue("Quarantined", q.block_reason or "executable content blocked")
        )
        apply_security(
            bundle,
            quarantine_actions=q.actions,
            active_content_flags=q.active_content_flags,
            macros_blocked=q.macros_blocked,
        )
        return _wrap(bundle, include_evidence_block)

    ctx = AdapterContext(
        filename=filename,
        path=path,
        path_mode=path_mode,
        file_id=file_id,
        content_hash=identity.content_hash,
        mime_type=identity.sniffed_mime,
        sniffed_mime=identity.sniffed_mime,
        size_bytes=identity.size_bytes,
        limits=limits,
        tracker=tracker,
        quarantine=q,
        depth=depth,
    )
    adapter = resolve_adapter(identity.sniffed_mime, filename, data)
    bundle = adapter.extract(data, ctx)
    if modified_at and "modified_at" not in bundle["source"]:
        bundle["source"]["modified_at"] = modified_at

    validation = validate_document_bundle(bundle)
    return _wrap(bundle, include_evidence_block, validation=validation)


def _wrap(
    bundle: dict[str, Any],
    include_evidence_block: bool,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if validation is None:
        validation = validate_document_bundle(bundle)
    out: dict[str, Any] = {
        "bundle": bundle,
        "validation": validation,
        "adapters": list_adapters(),
    }
    if include_evidence_block:
        out["evidence_block"] = format_untrusted_evidence_block(bundle)
    return out


def _mtime_iso(path: Path) -> str | None:
    try:
        ts = path.stat().st_mtime
        return (
            datetime.fromtimestamp(ts, tz=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z"
        )
    except OSError:
        return None
