"""JSON, YAML, and CSV/TSV adapters."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, truncate_text, apply_security


class JsonAdapter:
    id = "json"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        lower = (filename or "").lower()
        if lower.endswith(".ipynb"):
            return False
        if mime in {"application/json", "text/json", "application/ld+json"}:
            return True
        return lower.endswith(".json")

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type="application/json",
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        try:
            obj = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            bundle["errors"].append(issue("Corrupt", f"JSON parse failed: {exc}"))
            return _finalize(bundle, ctx, 0.0)

        pretty = json.dumps(obj, indent=2, ensure_ascii=False)
        pretty, truncated = truncate_text(pretty, ctx.limits.max_segment_chars)
        if truncated:
            bundle["warnings"].append(issue("Truncated", "JSON text truncated"))
        bundle["segments"].append(
            {
                "id": "json-0",
                "kind": "code",
                "text": pretty,
                "order": 0,
                "locator": {"kind": "offset", "offset_start": 0, "offset_end": len(pretty)},
                "confidence": 1.0,
            }
        )
        bundle["metadata"]["extra"] = {
            "json_root_type": type(obj).__name__,
            "top_level_keys": list(obj.keys())[:50] if isinstance(obj, dict) else None,
        }
        return _finalize(bundle, ctx, 1.0)


class YamlAdapter:
    id = "yaml"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in {"application/yaml", "text/yaml", "application/x-yaml"}:
            return True
        lower = (filename or "").lower()
        return lower.endswith((".yaml", ".yml"))

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type="application/yaml",
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        text = data.decode("utf-8-sig", errors="replace")
        try:
            import yaml  # type: ignore
        except ImportError:
            bundle["warnings"].append(
                issue("PartialSuccess", "PyYAML not installed; returning raw text only")
            )
            text, truncated = truncate_text(text, ctx.limits.max_segment_chars)
            if truncated:
                bundle["warnings"].append(issue("Truncated", "YAML truncated"))
            bundle["segments"].append(
                {
                    "id": "yaml-raw",
                    "kind": "text",
                    "text": text,
                    "order": 0,
                    "confidence": 0.5,
                }
            )
            return _finalize(bundle, ctx, 0.5)

        try:
            obj = yaml.safe_load(text)
        except Exception as exc:  # noqa: BLE001
            bundle["errors"].append(issue("Corrupt", f"YAML parse failed: {exc}"))
            return _finalize(bundle, ctx, 0.0)

        pretty = yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)
        pretty, truncated = truncate_text(pretty, ctx.limits.max_segment_chars)
        if truncated:
            bundle["warnings"].append(issue("Truncated", "YAML truncated"))
        bundle["segments"].append(
            {
                "id": "yaml-0",
                "kind": "code",
                "text": pretty,
                "order": 0,
                "locator": {"kind": "offset", "offset_start": 0, "offset_end": len(pretty)},
                "confidence": 0.95,
            }
        )
        return _finalize(bundle, ctx, 0.95)


class CsvAdapter:
    id = "csv"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in {"text/csv", "text/tab-separated-values", "application/csv"}:
            return True
        lower = (filename or "").lower()
        return lower.endswith((".csv", ".tsv"))

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        is_tsv = (ctx.filename or "").lower().endswith(".tsv") or ctx.mime_type.endswith(
            "tab-separated-values"
        )
        mime = "text/tab-separated-values" if is_tsv else "text/csv"
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
        text = data.decode("utf-8-sig", errors="replace")
        dialect = "excel-tab" if is_tsv else "excel"
        reader = csv.reader(io.StringIO(text), dialect=dialect)
        rows: list[list[str]] = []
        for i, row in enumerate(reader):
            if i >= ctx.limits.max_csv_rows:
                bundle["warnings"].append(
                    issue(
                        "ResourceLimit",
                        f"CSV rows truncated at max_csv_rows={ctx.limits.max_csv_rows}",
                    )
                )
                break
            rows.append([str(c) for c in row])

        table_id = "table-0"
        bundle["structure"]["tables"] = [{"id": table_id, "rows": rows}]
        # Flatten for segments (cells + preview text)
        preview_lines = [",".join(r) for r in rows[:100]]
        preview = "\n".join(preview_lines)
        preview, truncated = truncate_text(preview, ctx.limits.max_segment_chars)
        if truncated:
            bundle["warnings"].append(issue("Truncated", "CSV preview truncated"))
        bundle["segments"].append(
            {
                "id": "csv-preview",
                "kind": "table",
                "text": preview,
                "order": 0,
                "locator": {"kind": "custom", "extra": {"table_id": table_id}},
                "confidence": 0.95,
            }
        )
        for ri, row in enumerate(rows[: min(500, len(rows))]):
            for ci, cell in enumerate(row):
                if not cell:
                    continue
                col = _col_letter(ci)
                bundle["segments"].append(
                    {
                        "id": f"c-{ri}-{ci}",
                        "kind": "cell",
                        "text": cell,
                        "order": 1 + ri * 1000 + ci,
                        "locator": {
                            "kind": "xlsx_cell",
                            "sheet": "csv",
                            "cell": f"{col}{ri + 1}",
                        },
                        "confidence": 0.95,
                    }
                )
                if len(bundle["segments"]) >= ctx.limits.max_segments:
                    bundle["warnings"].append(
                        issue("ResourceLimit", "segment limit reached while expanding CSV cells")
                    )
                    return _finalize(bundle, ctx, 0.9)
        return _finalize(bundle, ctx, 0.95)


def _col_letter(index: int) -> str:
    n = index + 1
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def _finalize(bundle: dict[str, Any], ctx: AdapterContext, confidence: float) -> dict[str, Any]:
    bundle["confidence"] = confidence
    apply_security(
        bundle,
        quarantine_actions=ctx.quarantine.actions,
        active_content_flags=ctx.quarantine.active_content_flags,
        macros_blocked=ctx.quarantine.macros_blocked,
        scripts_stripped=ctx.quarantine.scripts_stripped,
    )
    return bundle
