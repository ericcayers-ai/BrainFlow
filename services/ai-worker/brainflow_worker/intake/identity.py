"""File identity: content hash and MIME sniffing from bytes (no trust of extension alone)."""

from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass


@dataclass(frozen=True)
class FileIdentity:
    content_hash: str  # sha256:<hex>
    size_bytes: int
    sniffed_mime: str
    extension_guess: str | None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_hash(data: bytes) -> str:
    return f"sha256:{sha256_hex(data)}"


def sniff_mime(data: bytes, filename: str | None = None) -> str:
    """Sniff MIME from magic bytes; fall back to extension then octet-stream."""
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"OggS":
        lower = (filename or "").lower()
        if lower.endswith((".ogv", ".ogm")):
            return "video/ogg"
        return "audio/ogg"
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        lower = (filename or "").lower()
        if lower.endswith((".mp3", ".mp2")):
            return "audio/mpeg"
    if data[:4] == b"ftyp" or (len(data) >= 8 and data[4:8] == b"ftyp"):
        lower = (filename or "").lower()
        if lower.endswith((".mp4", ".m4v", ".mov", ".m4a")):
            return "video/mp4" if not lower.endswith(".m4a") else "audio/mp4"
    if data[:4] == b"PK\x03\x04":
        # Could be zip / docx / pptx / xlsx / odt — inspect later
        lower = (filename or "").lower()
        if lower.endswith(".docx"):
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if lower.endswith(".pptx"):
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if lower.endswith(".xlsx"):
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if lower.endswith(".odt"):
            return "application/vnd.oasis.opendocument.text"
        if lower.endswith(".ods"):
            return "application/vnd.oasis.opendocument.spreadsheet"
        if lower.endswith(".odp"):
            return "application/vnd.oasis.opendocument.presentation"
        # Peek mimetype for ODF
        try:
            import io
            import zipfile

            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if "mimetype" in zf.namelist():
                    mt = zf.read("mimetype").decode("utf-8", errors="replace").strip()
                    if mt.startswith("application/vnd.oasis.opendocument."):
                        return mt
        except Exception:  # noqa: BLE001
            pass
        return "application/zip"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:2] == b"BM":
        return "image/bmp"
    if data.startswith(b"<!DOCTYPE html") or data.startswith(b"<html") or data.startswith(
        b"<HTML"
    ):
        return "text/html"
    # UTF-8 BOM
    sample = data[:2048]
    if sample.startswith(b"\xef\xbb\xbf"):
        sample = sample[3:]
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError:
        if filename:
            guessed, _ = mimetypes.guess_type(filename)
            if guessed:
                return guessed
        return "application/octet-stream"

    stripped = text.lstrip()
    lower_name = (filename or "").lower()
    if lower_name.endswith(".ipynb") or (
        '"cells"' in text[:4096] and '"nbformat"' in text[:8192]
    ):
        return "application/x-ipynb+json"
    if stripped.startswith("{") or stripped.startswith("["):
        return "application/json"
    if filename and filename.lower().endswith((".yaml", ".yml")):
        return "application/yaml"
    if filename and filename.lower().endswith((".csv", ".tsv")):
        return "text/csv" if filename.lower().endswith(".csv") else "text/tab-separated-values"
    if filename and filename.lower().endswith((".md", ".markdown")):
        return "text/markdown"
    if "<html" in stripped.lower() or "<!doctype html" in stripped.lower():
        return "text/html"
    if filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed
    return "text/plain"


def identify(data: bytes, filename: str | None = None) -> FileIdentity:
    mime = sniff_mime(data, filename)
    ext = None
    if filename and "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    return FileIdentity(
        content_hash=content_hash(data),
        size_bytes=len(data),
        sniffed_mime=mime,
        extension_guess=ext,
    )
