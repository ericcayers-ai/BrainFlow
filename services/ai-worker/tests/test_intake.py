"""Golden corpus + resource-limit intake tests."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from brainflow_worker.intake.adapters.image import set_ocr_hook
from brainflow_worker.intake.adapters.media import set_transcribe_hook
from brainflow_worker.intake.evidence import (
    assert_evidence_delimited,
    format_untrusted_evidence_block,
)
from brainflow_worker.intake.limits import IntakeLimits
from brainflow_worker.intake.pipeline import analyze_bytes, analyze_path
from brainflow_worker.rpc import handle_request

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS = REPO_ROOT / "tests" / "corpus"
GOLDEN = CORPUS / "golden"
ADVERSARIAL = CORPUS / "adversarial"


def test_markdown_golden():
    path = GOLDEN / "sample.md"
    pre = path.read_bytes()
    result = analyze_path(path, path_mode="link")
    assert path.read_bytes() == pre  # AC-ING-01
    bundle = result["bundle"]
    assert bundle["evidence_trust"] == "untrusted"
    assert bundle["metadata"]["adapter_id"] == "markdown"
    assert result["validation"]["ok"] is True, result["validation"]
    assert any(s.get("kind") == "heading" for s in bundle["segments"])
    assert assert_evidence_delimited(result["evidence_block"])


def test_html_strips_scripts():
    result = analyze_path(GOLDEN / "sample.html")
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "html"
    assert bundle["security"]["scripts_stripped"] is True
    body = " ".join(s.get("text") or "" for s in bundle["segments"])
    assert "alert(" not in body
    assert "evil" not in body.lower() or "script" not in body.lower()
    assert result["validation"]["ok"] is True


def test_json_yaml_csv():
    for name, adapter in (
        ("sample.json", "json"),
        ("sample.yaml", "yaml"),
        ("sample.csv", "csv"),
    ):
        result = analyze_path(GOLDEN / name)
        assert result["bundle"]["metadata"]["adapter_id"] == adapter
        assert result["validation"]["ok"] is True
        assert result["bundle"]["segments"]


def test_code_not_executed():
    result = analyze_path(GOLDEN / "sample.py")
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "code"
    assert bundle["metadata"]["extra"]["executed"] is False
    assert "source_not_executed" in bundle["security"]["quarantine_actions"]
    assert result["validation"]["ok"] is True


def test_plain_text():
    result = analyze_path(GOLDEN / "sample.txt")
    assert result["bundle"]["metadata"]["adapter_id"] == "plain_text"
    assert result["validation"]["ok"] is True


def test_image_ocr_path():
    """OCR runs when hooked/installed; otherwise clear NeedsAdapter (not stub-as-done)."""
    result = analyze_path(GOLDEN / "sample.png")
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "image"
    assert bundle["images"]
    status = bundle["images"][0]["ocr_status"]
    assert status in {"unavailable", "ok", "failed"}
    if status == "unavailable":
        assert any(e["code"] == "NeedsAdapter" for e in bundle["errors"])
    assert result["validation"]["ok"] is True


def test_image_ocr_hook_runs():
    set_ocr_hook(lambda _data, _mime: "HOOKED_OCR_TEXT")
    try:
        result = analyze_path(GOLDEN / "sample.png")
        bundle = result["bundle"]
        assert bundle["images"][0]["ocr_status"] == "ok"
        assert bundle["images"][0]["ocr_text"] == "HOOKED_OCR_TEXT"
        assert any("HOOKED_OCR_TEXT" in (s.get("text") or "") for s in bundle["segments"])
        assert not any(e["code"] == "NeedsAdapter" for e in bundle["errors"])
    finally:
        set_ocr_hook(None)


def test_pdf_or_needs_adapter():
    result = analyze_path(GOLDEN / "sample.pdf")
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "pdf"
    assert result["validation"]["ok"] is True
    codes = {e["code"] for e in bundle["errors"]}
    if codes:
        assert codes <= {"NeedsAdapter", "Corrupt", "NeedsPassword", "PartialSuccess"}


def test_notebook_golden():
    result = analyze_path(GOLDEN / "sample.ipynb")
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "notebook"
    assert bundle["metadata"]["extra"]["executed"] is False
    assert "notebook_not_executed" in bundle["security"]["quarantine_actions"]
    texts = " ".join(s.get("text") or "" for s in bundle["segments"])
    assert "Hello Notebook" in texts
    assert "brainflow" in texts
    assert result["validation"]["ok"] is True


def test_notebook_code_not_executed():
    result = analyze_path(ADVERSARIAL / "inject.ipynb")
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "notebook"
    assert bundle["metadata"]["extra"]["executed"] is False
    assert "notebook_code_cells_not_executed" in bundle["security"]["active_content_flags"]
    texts = " ".join(s.get("text") or "" for s in bundle["segments"])
    assert "os.system" in texts
    assert result["validation"]["ok"] is True


def test_broken_notebook():
    result = analyze_path(ADVERSARIAL / "broken.ipynb")
    bundle = result["bundle"]
    assert any(e["code"] == "Corrupt" for e in bundle["errors"])
    assert result["validation"]["ok"] is True


def test_opendocument_golden():
    result = analyze_path(GOLDEN / "sample.odt")
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "opendocument"
    texts = " ".join(s.get("text") or "" for s in bundle["segments"])
    assert "OpenDocument" in texts or "BrainFlow ODT" in texts
    assert result["validation"]["ok"] is True


def test_truncated_odt_corrupt():
    result = analyze_path(ADVERSARIAL / "truncated.odt")
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "opendocument"
    codes = {e["code"] for e in bundle["errors"]}
    assert codes & {"Corrupt", "NeedsAdapter"}
    assert result["validation"]["ok"] is True


def test_media_wav_metadata_and_transcription_path():
    """ffprobe metadata when available; Whisper path or clear NeedsAdapter."""
    set_transcribe_hook(None)
    result = analyze_path(GOLDEN / "sample.wav")
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "media"
    assert "media_not_executed" in bundle["security"]["quarantine_actions"]
    assert any(s.get("kind") == "raw_meta" for s in bundle["segments"])
    has_tx = bool(bundle["transcripts"])
    if not has_tx:
        assert any(e["code"] == "NeedsAdapter" for e in bundle["errors"])
    assert result["validation"]["ok"] is True


def test_media_transcribe_hook():
    set_transcribe_hook(
        lambda _path, _mime: [
            {"start_ms": 0, "end_ms": 500, "text": "hello transcript", "confidence": 0.9}
        ]
    )
    try:
        result = analyze_path(GOLDEN / "sample.wav")
        bundle = result["bundle"]
        assert bundle["transcripts"]
        assert bundle["transcripts"][0]["text"] == "hello transcript"
        assert any(s.get("kind") == "media" for s in bundle["segments"])
        assert not any(e["code"] == "NeedsAdapter" for e in bundle["errors"])
    finally:
        set_transcribe_hook(None)


def test_media_duration_resource_limit():
    set_transcribe_hook(lambda _p, _m: [])
    try:
        limits = IntakeLimits(max_media_duration_seconds=0.0)
        result = analyze_bytes(
            (GOLDEN / "sample.wav").read_bytes(),
            filename="sample.wav",
            limits=limits,
        )
        bundle = result["bundle"]
        assert bundle["metadata"]["adapter_id"] == "media"
        assert result["validation"]["ok"] is True
    finally:
        set_transcribe_hook(None)


def test_broken_json_malformed():
    result = analyze_path(ADVERSARIAL / "broken.json")
    bundle = result["bundle"]
    assert any(e["code"] == "Corrupt" for e in bundle["errors"])
    assert result["validation"]["ok"] is True


def test_inject_html_quarantined():
    result = analyze_path(ADVERSARIAL / "inject.html")
    bundle = result["bundle"]
    assert bundle["security"]["scripts_stripped"] is True
    block = format_untrusted_evidence_block(bundle)
    assert "<UNTRUSTED_EVIDENCE" in block
    assert "</UNTRUSTED_EVIDENCE>" in block


def test_zip_bomb_resource_limit():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.txt", b"0" * (2 * 1024 * 1024))
    data = buf.getvalue()
    limits = IntakeLimits(
        max_decompression_ratio=5.0,
        max_decompressed_bytes=512 * 1024,
        max_file_bytes=10 * 1024 * 1024,
    )
    result = analyze_bytes(data, filename="bomb.zip", limits=limits)
    bundle = result["bundle"]
    assert bundle["metadata"]["adapter_id"] == "archive"
    assert any(e["code"] == "ResourceLimit" for e in bundle["errors"])
    assert result["validation"]["ok"] is True


def test_archive_blocks_executable_entry():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "ok")
        zf.writestr("malware.exe", b"MZ\x00\x00fake")
        zf.writestr("run.js", "alert(1)")
    result = analyze_bytes(buf.getvalue(), filename="mixed.zip")
    bundle = result["bundle"]
    flags = bundle["security"]["active_content_flags"]
    assert any("executable" in f or "archive_script" in f for f in flags)
    texts = " ".join(s.get("locator", {}).get("entry_path", "") for s in bundle["segments"])
    assert "malware.exe" not in texts
    assert "run.js" not in texts
    assert "readme.txt" in " ".join(
        str(s.get("locator", {}).get("entry_path", "")) for s in bundle["segments"]
    )


def test_rpc_intake_analyze():
    path = str(GOLDEN / "sample.md")
    resp = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "intake.analyze",
            "params": {"path": path, "path_mode": "link"},
        }
    )
    assert "result" in resp, resp
    assert resp["result"]["bundle"]["evidence_trust"] == "untrusted"
    assert resp["result"]["validation"]["ok"] is True


def test_rpc_intake_adapters():
    resp = handle_request({"jsonrpc": "2.0", "id": 2, "method": "intake.adapters", "params": {}})
    assert "result" in resp
    ids = {a["id"] for a in resp["result"]["adapters"]}
    assert "markdown" in ids
    assert "archive" in ids
    assert "notebook" in ids
    assert "opendocument" in ids
    assert "media" in ids


def test_provenance_derived_from():
    result = analyze_path(GOLDEN / "sample.md")
    prov = result["bundle"]["provenance"]
    assert prov["derived_from"]
    assert prov["derived_from"][0]["content_hash"] == result["bundle"]["source"]["content_hash"]
    assert prov["pipeline_version"]


@pytest.mark.parametrize(
    "filename,mime_hint",
    [
        ("note.md", "text/markdown"),
        ("data.json", "application/json"),
        ("sheet.csv", "text/csv"),
        ("nb.ipynb", "application/x-ipynb+json"),
    ],
)
def test_bytes_routing(filename, mime_hint):
    payloads = {
        "note.md": b"# Title\n\nbody",
        "data.json": b'{"a":1}',
        "sheet.csv": b"a,b\n1,2\n",
        "nb.ipynb": (
            b'{"nbformat":4,"nbformat_minor":5,"metadata":{},'
            b'"cells":[{"cell_type":"markdown","metadata":{},"source":["# X"]}]}'
        ),
    }
    result = analyze_bytes(payloads[filename], filename=filename)
    assert result["bundle"]["source"]["mime_type"]
    assert result["validation"]["ok"] is True
    if filename.endswith(".ipynb"):
        assert result["bundle"]["metadata"]["adapter_id"] == "notebook"
