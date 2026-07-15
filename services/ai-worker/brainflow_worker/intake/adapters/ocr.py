"""Optional Tesseract OCR path used by image (and future PDF-scan) adapters.

When pytesseract + a Tesseract binary are available, OCR actually runs.
Otherwise callers surface a clear NeedsAdapter (not a silent stub-as-done).
"""

from __future__ import annotations

import io
import shutil
from dataclasses import dataclass
from typing import Callable


# Host/tests may override: (image_bytes, mime) -> str | None
_OCR_HOOK: Callable[[bytes, str], str | None] | None = None


@dataclass(frozen=True)
class OcrResult:
    text: str | None
    status: str  # ok | failed | unavailable | stub (only if hook-forced empty)
    detail: str | None = None


def set_ocr_hook(hook: Callable[[bytes, str], str | None] | None) -> None:
    """Register a custom OCR implementation (or None to clear)."""
    global _OCR_HOOK
    _OCR_HOOK = hook


def tesseract_available() -> bool:
    """True when pytesseract imports and a tesseract binary is on PATH."""
    try:
        import pytesseract  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def run_ocr(data: bytes, mime: str) -> OcrResult:
    """Run OCR via hook → Tesseract → Unavailable (NeedsAdapter)."""
    if _OCR_HOOK is not None:
        try:
            text = _OCR_HOOK(data, mime)
            if text and text.strip():
                return OcrResult(text=text.strip(), status="ok", detail="hook")
            return OcrResult(text=None, status="failed", detail="hook returned empty")
        except Exception as exc:  # noqa: BLE001
            return OcrResult(text=None, status="failed", detail=f"OCR hook failed: {exc}")

    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError as exc:
        missing = getattr(exc, "name", None) or str(exc)
        return OcrResult(
            text=None,
            status="unavailable",
            detail=(
                f"OCR extras missing ({missing}); "
                "install intake[ocr] / pytesseract+Pillow and the Tesseract binary"
            ),
        )

    if shutil.which("tesseract") is None:
        return OcrResult(
            text=None,
            status="unavailable",
            detail=(
                "Tesseract binary not found on PATH; "
                "install Tesseract OCR to enable image text extraction"
            ),
        )

    try:
        with Image.open(io.BytesIO(data)) as im:
            # RGB avoids some palette/mode errors on 1-bit / P images
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            text = pytesseract.image_to_string(im) or ""
        text = text.strip()
        if text:
            return OcrResult(text=text, status="ok", detail="tesseract")
        return OcrResult(text=None, status="failed", detail="tesseract returned empty text")
    except Exception as exc:  # noqa: BLE001
        return OcrResult(text=None, status="failed", detail=f"tesseract failed: {exc}")
