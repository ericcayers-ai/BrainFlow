"""Image metadata adapter with real Tesseract OCR when optional extras are installed."""

from __future__ import annotations

from typing import Any

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.adapters.ocr import run_ocr, set_ocr_hook as _set_ocr_hook
from brainflow_worker.intake.bundle import empty_bundle, issue, apply_security

# Re-export for host/tests (brainflow_worker.intake.adapters.image.set_ocr_hook)
set_ocr_hook = _set_ocr_hook


IMAGE_MIMES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
    }
)


class ImageAdapter:
    id = "image"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in IMAGE_MIMES:
            return True
        lower = (filename or "").lower()
        return lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"))

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        mime = ctx.mime_type if ctx.mime_type in IMAGE_MIMES else ctx.sniffed_mime
        if mime not in IMAGE_MIMES:
            mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
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

        width = height = 0
        exif: dict[str, Any] = {}
        try:
            from PIL import Image  # type: ignore
            import io

            with Image.open(io.BytesIO(data)) as im:
                width, height = im.size
                mime = Image.MIME.get(im.format or "", mime)
                exif_raw = getattr(im, "getexif", lambda: {})()
                if exif_raw:
                    for k, v in list(exif_raw.items())[:40]:
                        if isinstance(v, (int, float, str)):
                            exif[str(k)] = v
        except ImportError:
            bundle["warnings"].append(
                issue("PartialSuccess", "Pillow not installed; dimensions/EXIF unavailable")
            )
            width, height = _png_size(data) if mime == "image/png" else (0, 0)
        except Exception as exc:  # noqa: BLE001
            bundle["warnings"].append(issue("PartialSuccess", f"image open failed: {exc}"))

        ocr = run_ocr(data, mime)
        ocr_text = ocr.text
        ocr_status = ocr.status
        if ocr_status == "unavailable":
            bundle["errors"].append(
                issue(
                    "NeedsAdapter",
                    ocr.detail
                    or "OCR unavailable; install intake[ocr] and the Tesseract binary",
                )
            )
        elif ocr_status == "failed":
            bundle["warnings"].append(
                issue("PartialSuccess", ocr.detail or "OCR failed")
            )

        img_id = "img-0"
        bundle["images"].append(
            {
                "id": img_id,
                "mime_type": mime,
                "width": width,
                "height": height,
                "exif": exif,
                "ocr_text": ocr_text,
                "ocr_status": ocr_status,
                "locator": {"kind": "image"},
            }
        )
        meta_bits = [f"mime={mime}", f"{width}x{height}"]
        order = 0
        if ocr_text:
            meta_bits.append(f"ocr_chars={len(ocr_text)}")
            bundle["segments"].append(
                {
                    "id": "ocr-0",
                    "kind": "text",
                    "text": ocr_text,
                    "order": order,
                    "locator": {"kind": "image"},
                    "confidence": 0.6,
                }
            )
            order += 1
        bundle["segments"].append(
            {
                "id": "img-meta",
                "kind": "raw_meta",
                "text": "; ".join(meta_bits),
                "order": order,
                "locator": {"kind": "image"},
                "confidence": 0.9,
            }
        )
        bundle["confidence"] = 0.7 if ocr_text else 0.5
        bundle["metadata"]["extra"] = {
            "ocr_backend": ocr.detail,
            "ocr_status": ocr_status,
        }
        apply_security(
            bundle,
            quarantine_actions=[*ctx.quarantine.actions, "image_not_executed"],
            active_content_flags=ctx.quarantine.active_content_flags,
        )
        return bundle


def _png_size(data: bytes) -> tuple[int, int]:
    if len(data) >= 24 and data.startswith(b"\x89PNG"):
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        return w, h
    return 0, 0
