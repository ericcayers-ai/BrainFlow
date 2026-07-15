"""Bundle builders and types shared by adapters."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


PIPELINE_VERSION = "1.0.0"
ADAPTER_VERSION = "1.0.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def new_id() -> str:
    return str(uuid.uuid4())


def issue(code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": code, "message": message}
    if detail:
        out["detail"] = detail
    return out


def empty_bundle(
    *,
    file_id: str,
    content_hash: str,
    mime_type: str,
    size_bytes: int,
    path: str | None,
    path_mode: str,
    adapter_id: str,
    sniffed_mime: str | None = None,
    modified_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "bundle_id": new_id(),
        "evidence_trust": "untrusted",
        "source": {
            "file_id": file_id,
            "path_mode": path_mode,
            "content_hash": content_hash,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            **({"path": path} if path else {}),
            **({"sniffed_mime": sniffed_mime} if sniffed_mime else {}),
            **({"modified_at": modified_at} if modified_at else {}),
        },
        "metadata": {
            "adapter_id": adapter_id,
            "adapter_version": ADAPTER_VERSION,
        },
        "segments": [],
        "structure": {},
        "images": [],
        "transcripts": [],
        "confidence": 0.0,
        "warnings": [],
        "errors": [],
        "security": {
            "quarantine_actions": [],
            "macros_blocked": False,
            "scripts_stripped": False,
            "active_content_flags": [],
            "limits_applied": {},
        },
        "provenance": {
            "derived_from": [
                {
                    "file_id": file_id,
                    "content_hash": content_hash,
                    "role": "source",
                }
            ],
            "analyzed_at": utc_now_iso(),
            "pipeline_version": PIPELINE_VERSION,
        },
    }


def apply_security(bundle: dict[str, Any], **kwargs: Any) -> None:
    sec = bundle["security"]
    for key, val in kwargs.items():
        if key == "quarantine_actions" and isinstance(val, list):
            sec["quarantine_actions"] = list(
                dict.fromkeys([*sec.get("quarantine_actions", []), *val])
            )
        elif key == "active_content_flags" and isinstance(val, list):
            sec["active_content_flags"] = list(
                dict.fromkeys([*sec.get("active_content_flags", []), *val])
            )
        elif key == "limits_applied" and isinstance(val, dict):
            sec.setdefault("limits_applied", {}).update(val)
        else:
            sec[key] = val


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True
