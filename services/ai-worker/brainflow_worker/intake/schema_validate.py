"""Validate DocumentBundle against shared JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "schemas"
    / "ingestion"
    / "document-bundle.schema.json"
)


def load_document_bundle_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_document_bundle(doc: dict[str, Any]) -> dict[str, Any]:
    schema = load_document_bundle_schema()
    validator = Draft202012Validator(
        schema,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        return {
            "ok": False,
            "errors": [
                f"{'/'.join(str(p) for p in e.path) or '/'}: {e.message}" for e in errors
            ],
        }
    return {"ok": True, "errors": []}
