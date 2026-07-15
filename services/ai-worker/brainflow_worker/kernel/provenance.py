"""Run provenance records — pins, hashes, stage decisions (no hidden CoT)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def definition_hash(workflow: dict[str, Any]) -> str:
    canonical = json.dumps(workflow, sort_keys=True, separators=(",", ":"))
    return content_hash(canonical)


def new_run_provenance(
    *,
    workflow: dict[str, Any],
    input_hashes: dict[str, str],
    stages: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "provenance_id": str(uuid4()),
        "workflow_id": workflow.get("workflow_id"),
        "definition_hash": definition_hash(workflow),
        "created_at": utc_now(),
        "pins": workflow.get("pins"),
        "domain_pack_id": workflow.get("domain_pack_id"),
        "input_hashes": input_hashes,
        "stages": stages,
        "claim_kinds_allowed": ["source_fact", "inference", "recommendation", "uncertainty"],
    }
