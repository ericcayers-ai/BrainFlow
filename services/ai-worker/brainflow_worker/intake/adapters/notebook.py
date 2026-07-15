"""Jupyter notebook (.ipynb) adapter — parse cells as text; never execute code."""

from __future__ import annotations

import json
from typing import Any

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, truncate_text, apply_security


class NotebookAdapter:
    id = "notebook"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in {
            "application/x-ipynb+json",
            "application/vnd.jupyter",
            "application/json",
        } and (filename or "").lower().endswith(".ipynb"):
            return True
        if (filename or "").lower().endswith(".ipynb"):
            return True
        # Sniff: JSON with nbformat + cells
        if data[:1] in (b"{", b"\xef") and b'"cells"' in data[:4096] and b'"nbformat"' in data[:8192]:
            return True
        return False

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        bundle = empty_bundle(
            file_id=ctx.file_id,
            content_hash=ctx.content_hash,
            mime_type="application/x-ipynb+json",
            size_bytes=ctx.size_bytes,
            path=ctx.path,
            path_mode=ctx.path_mode,
            adapter_id=self.id,
            sniffed_mime=ctx.sniffed_mime,
        )
        try:
            text = data.decode("utf-8")
            nb = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            bundle["errors"].append(issue("Corrupt", f"invalid notebook JSON: {exc}"))
            return _done(bundle, ctx, 0.0)

        if not isinstance(nb, dict) or "cells" not in nb:
            bundle["errors"].append(
                issue("Corrupt", "JSON is not a Jupyter notebook (missing cells)")
            )
            return _done(bundle, ctx, 0.0)

        cells = nb.get("cells")
        if not isinstance(cells, list):
            bundle["errors"].append(issue("Corrupt", "notebook cells must be a list"))
            return _done(bundle, ctx, 0.0)

        # Flag executable code cells but never run them
        code_cells = sum(1 for c in cells if isinstance(c, dict) and c.get("cell_type") == "code")
        if code_cells:
            bundle["security"]["active_content_flags"] = list(
                dict.fromkeys(
                    [
                        *bundle["security"].get("active_content_flags", []),
                        "notebook_code_cells_not_executed",
                    ]
                )
            )

        meta = nb.get("metadata") if isinstance(nb.get("metadata"), dict) else {}
        kernelspec = meta.get("kernelspec") if isinstance(meta.get("kernelspec"), dict) else {}
        title = None
        if isinstance(meta.get("title"), str):
            title = meta["title"]
        if title:
            bundle["metadata"]["title"] = title

        bundle["metadata"]["extra"] = {
            "nbformat": nb.get("nbformat"),
            "nbformat_minor": nb.get("nbformat_minor"),
            "kernel": kernelspec.get("name") or kernelspec.get("display_name"),
            "cell_count": len(cells),
            "code_cell_count": code_cells,
            "executed": False,
        }

        order = 0
        for i, cell in enumerate(cells):
            if not isinstance(cell, dict):
                continue
            cell_type = str(cell.get("cell_type") or "raw")
            source = cell.get("source", "")
            if isinstance(source, list):
                source_text = "".join(str(s) for s in source)
            else:
                source_text = str(source or "")
            source_text = source_text.strip()
            if not source_text:
                continue
            source_text, truncated = truncate_text(source_text, ctx.limits.max_segment_chars)
            if truncated:
                bundle["warnings"].append(issue("Truncated", f"cell {i} truncated"))

            kind = "code" if cell_type == "code" else "text"
            if cell_type == "markdown" and source_text.lstrip().startswith("#"):
                kind = "heading"

            bundle["segments"].append(
                {
                    "id": f"cell-{i}",
                    "kind": kind,
                    "text": source_text,
                    "order": order,
                    "locator": {
                        "kind": "custom",
                        "extra": {
                            "notebook_cell": i,
                            "cell_type": cell_type,
                        },
                    },
                    "confidence": 0.95,
                }
            )
            order += 1

            # Capture printed text outputs only (never re-run)
            outputs = cell.get("outputs") if isinstance(cell.get("outputs"), list) else []
            for oi, out in enumerate(outputs[:20]):
                if not isinstance(out, dict):
                    continue
                out_text = _output_text(out)
                if not out_text:
                    continue
                out_text, trunc = truncate_text(out_text, ctx.limits.max_segment_chars)
                if trunc:
                    bundle["warnings"].append(
                        issue("Truncated", f"cell {i} output {oi} truncated")
                    )
                bundle["segments"].append(
                    {
                        "id": f"cell-{i}-out-{oi}",
                        "kind": "text",
                        "text": out_text,
                        "order": order,
                        "locator": {
                            "kind": "custom",
                            "extra": {
                                "notebook_cell": i,
                                "cell_type": "output",
                                "output_index": oi,
                            },
                        },
                        "confidence": 0.8,
                    }
                )
                order += 1

            if order >= ctx.limits.max_segments:
                bundle["warnings"].append(issue("ResourceLimit", "notebook segment limit"))
                break

        bundle["confidence"] = 0.95 if bundle["segments"] else 0.3
        return _done(bundle, ctx, bundle["confidence"])


def _output_text(out: dict[str, Any]) -> str:
    if out.get("output_type") == "stream":
        text = out.get("text", "")
        if isinstance(text, list):
            return "".join(str(t) for t in text).strip()
        return str(text or "").strip()
    data = out.get("data")
    if isinstance(data, dict):
        plain = data.get("text/plain")
        if isinstance(plain, list):
            return "".join(str(t) for t in plain).strip()
        if isinstance(plain, str):
            return plain.strip()
    return ""


def _done(bundle: dict[str, Any], ctx: AdapterContext, confidence: float) -> dict[str, Any]:
    bundle["confidence"] = confidence
    apply_security(
        bundle,
        quarantine_actions=[*ctx.quarantine.actions, "notebook_not_executed"],
        active_content_flags=ctx.quarantine.active_content_flags,
        macros_blocked=False,
        scripts_stripped=False,
    )
    return bundle
