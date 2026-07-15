"""Audio/video adapter: ffprobe metadata + optional Whisper transcription.

Transcription never invents speech when deps are missing — clear NeedsAdapter.
Media bytes are never executed; only metadata / speech-to-text when available.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from brainflow_worker.intake.adapters.context import AdapterContext
from brainflow_worker.intake.bundle import empty_bundle, issue, truncate_text, apply_security

# Optional host/test hook: (path, mime) -> list[{start_ms,end_ms,text,confidence?}]
_TRANSCRIBE_HOOK: Callable[[str, str], list[dict[str, Any]]] | None = None


def set_transcribe_hook(
    hook: Callable[[str, str], list[dict[str, Any]]] | None,
) -> None:
    global _TRANSCRIBE_HOOK
    _TRANSCRIBE_HOOK = hook


AUDIO_MIMES = frozenset(
    {
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/ogg",
        "audio/flac",
        "audio/aac",
        "audio/mp4",
        "audio/webm",
    }
)
VIDEO_MIMES = frozenset(
    {
        "video/mp4",
        "video/webm",
        "video/ogg",
        "video/quicktime",
        "video/x-msvideo",
        "video/x-matroska",
    }
)
AUDIO_EXTS = (".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a", ".wma")
VIDEO_EXTS = (".mp4", ".webm", ".ogv", ".mov", ".avi", ".mkv", ".m4v")


class MediaAdapter:
    id = "media"

    def supports(self, mime: str, filename: str | None, data: bytes) -> bool:
        if mime in AUDIO_MIMES or mime in VIDEO_MIMES:
            return True
        if mime.startswith("audio/") or mime.startswith("video/"):
            return True
        lower = (filename or "").lower()
        return lower.endswith(AUDIO_EXTS + VIDEO_EXTS)

    def extract(self, data: bytes, ctx: AdapterContext) -> dict[str, Any]:
        mime = ctx.mime_type or ctx.sniffed_mime or "application/octet-stream"
        if mime not in AUDIO_MIMES and mime not in VIDEO_MIMES:
            lower = (ctx.filename or "").lower()
            if lower.endswith(VIDEO_EXTS):
                mime = "video/mp4"
            elif lower.endswith(AUDIO_EXTS):
                mime = "audio/wav" if lower.endswith(".wav") else "audio/mpeg"
            elif data[:4] == b"RIFF" and data[8:12] == b"WAVE":
                mime = "audio/wav"
            else:
                mime = "application/octet-stream"

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

        suffix = Path(ctx.filename or "media.bin").suffix or (
            ".wav" if mime.startswith("audio/") else ".mp4"
        )
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            meta = _ffprobe_metadata(tmp_path)
            if meta is None:
                bundle["warnings"].append(
                    issue(
                        "PartialSuccess",
                        "ffprobe not available; install FFmpeg for A/V metadata",
                    )
                )
                meta = {"ffprobe": False}
            else:
                meta["ffprobe"] = True

            duration_s = float(meta.get("duration_seconds") or 0)
            max_dur = getattr(ctx.limits, "max_media_duration_seconds", 3600)
            if duration_s > max_dur:
                bundle["errors"].append(
                    issue(
                        "ResourceLimit",
                        f"media duration {duration_s:.1f}s exceeds "
                        f"max_media_duration_seconds={max_dur}",
                    )
                )
                return _done(bundle, ctx, 0.0, meta)

            meta_bits = [
                f"mime={mime}",
                f"bytes={ctx.size_bytes}",
            ]
            if meta.get("format_name"):
                meta_bits.append(f"format={meta['format_name']}")
            if duration_s:
                meta_bits.append(f"duration_s={duration_s:.3f}")
            if meta.get("codec_name"):
                meta_bits.append(f"codec={meta['codec_name']}")
            if meta.get("sample_rate"):
                meta_bits.append(f"sample_rate={meta['sample_rate']}")
            if meta.get("width") and meta.get("height"):
                meta_bits.append(f"{meta['width']}x{meta['height']}")

            bundle["segments"].append(
                {
                    "id": "media-meta",
                    "kind": "raw_meta",
                    "text": "; ".join(meta_bits),
                    "order": 0,
                    "locator": {
                        "kind": "custom",
                        "extra": {"media": True, "start_ms": 0},
                    },
                    "confidence": 0.9 if meta.get("ffprobe") else 0.4,
                }
            )
            bundle["metadata"]["extra"] = meta

            spans = _transcribe(tmp_path, mime, ctx, bundle)
            if spans:
                order = 1
                for i, span in enumerate(spans):
                    text = (span.get("text") or "").strip()
                    if not text:
                        continue
                    text, truncated = truncate_text(text, ctx.limits.max_segment_chars)
                    if truncated:
                        bundle["warnings"].append(
                            issue("Truncated", f"transcript span {i} truncated")
                        )
                    start_ms = int(span.get("start_ms") or 0)
                    end_ms = int(span.get("end_ms") or start_ms)
                    tid = f"tr-{i}"
                    conf = float(span.get("confidence") or 0.7)
                    bundle["transcripts"].append(
                        {
                            "id": tid,
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                            "text": text,
                            "confidence": conf,
                        }
                    )
                    bundle["segments"].append(
                        {
                            "id": f"tx-{i}",
                            "kind": "media",
                            "text": text,
                            "order": order,
                            "locator": {
                                "kind": "custom",
                                "extra": {
                                    "start_ms": start_ms,
                                    "end_ms": end_ms,
                                    "transcript_id": tid,
                                },
                            },
                            "confidence": conf,
                        }
                    )
                    order += 1
                    if order >= ctx.limits.max_segments:
                        bundle["warnings"].append(
                            issue("ResourceLimit", "media transcript segment limit")
                        )
                        break
                bundle["confidence"] = 0.85
            else:
                # Metadata-only is PartialSuccess when ffprobe worked;
                # missing transcription deps → NeedsAdapter (not pretend success).
                if not any(e["code"] == "NeedsAdapter" for e in bundle["errors"]):
                    # _transcribe already appended NeedsAdapter when deps missing
                    pass
                bundle["confidence"] = 0.55 if meta.get("ffprobe") else 0.3

            return _done(bundle, ctx, bundle["confidence"], meta)
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass


def _ffprobe_metadata(path: str) -> dict[str, Any] | None:
    if shutil.which("ffprobe") is None:
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None

    fmt = payload.get("format") or {}
    streams = payload.get("streams") or []
    out: dict[str, Any] = {
        "format_name": fmt.get("format_name"),
        "duration_seconds": _safe_float(fmt.get("duration")),
        "bit_rate": fmt.get("bit_rate"),
    }
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    prefer = video or audio
    if prefer:
        out["codec_name"] = prefer.get("codec_name")
        out["sample_rate"] = prefer.get("sample_rate")
        out["channels"] = prefer.get("channels")
        out["width"] = prefer.get("width")
        out["height"] = prefer.get("height")
        if not out["duration_seconds"]:
            out["duration_seconds"] = _safe_float(prefer.get("duration"))
    return out


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _transcribe(
    path: str,
    mime: str,
    ctx: AdapterContext,
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    if _TRANSCRIBE_HOOK is not None:
        try:
            return list(_TRANSCRIBE_HOOK(path, mime) or [])
        except Exception as exc:  # noqa: BLE001
            bundle["warnings"].append(
                issue("PartialSuccess", f"transcription hook failed: {exc}")
            )
            return []

    # Prefer faster-whisper, then openai-whisper
    try:
        from faster_whisper import WhisperModel  # type: ignore

        model_size = "tiny"
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _info = model.transcribe(path, beam_size=1)
        spans: list[dict[str, Any]] = []
        for seg in segments:
            spans.append(
                {
                    "start_ms": int(float(seg.start) * 1000),
                    "end_ms": int(float(seg.end) * 1000),
                    "text": (seg.text or "").strip(),
                    "confidence": float(getattr(seg, "avg_logprob", -1.0) + 1.0)
                    if hasattr(seg, "avg_logprob")
                    else 0.7,
                }
            )
        bundle["metadata"].setdefault("extra", {})["transcription_backend"] = (
            "faster-whisper"
        )
        return spans
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        bundle["warnings"].append(
            issue("PartialSuccess", f"faster-whisper failed: {exc}")
        )
        return []

    try:
        import whisper  # type: ignore

        model = whisper.load_model("tiny")
        result = model.transcribe(path)
        spans = []
        for seg in result.get("segments") or []:
            spans.append(
                {
                    "start_ms": int(float(seg.get("start", 0)) * 1000),
                    "end_ms": int(float(seg.get("end", 0)) * 1000),
                    "text": (seg.get("text") or "").strip(),
                    "confidence": 0.7,
                }
            )
        if not spans and result.get("text"):
            spans.append(
                {
                    "start_ms": 0,
                    "end_ms": int(float(result.get("segments", [{}])[-1].get("end", 0)) * 1000)
                    if result.get("segments")
                    else 0,
                    "text": str(result["text"]).strip(),
                    "confidence": 0.6,
                }
            )
        bundle["metadata"].setdefault("extra", {})["transcription_backend"] = "whisper"
        return spans
    except ImportError:
        bundle["errors"].append(
            issue(
                "NeedsAdapter",
                "transcription unavailable; install intake[media] "
                "(faster-whisper or openai-whisper) for speech-to-text",
            )
        )
        return []
    except Exception as exc:  # noqa: BLE001
        bundle["warnings"].append(issue("PartialSuccess", f"whisper failed: {exc}"))
        return []


def _done(
    bundle: dict[str, Any],
    ctx: AdapterContext,
    confidence: float,
    meta: dict[str, Any],
) -> dict[str, Any]:
    bundle["confidence"] = confidence
    bundle["metadata"].setdefault("extra", {}).update(meta)
    apply_security(
        bundle,
        quarantine_actions=[*ctx.quarantine.actions, "media_not_executed"],
        active_content_flags=ctx.quarantine.active_content_flags,
        limits_applied={
            "max_media_duration_seconds": getattr(
                ctx.limits, "max_media_duration_seconds", 3600
            ),
        },
    )
    return bundle
