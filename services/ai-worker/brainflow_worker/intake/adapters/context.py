"""Adapter context shared by all intake adapters."""

from __future__ import annotations

from dataclasses import dataclass, field

from brainflow_worker.intake.limits import IntakeLimits, LimitTracker
from brainflow_worker.intake.quarantine import QuarantineResult


@dataclass
class AdapterContext:
    filename: str | None
    path: str | None
    path_mode: str
    file_id: str
    content_hash: str
    mime_type: str
    sniffed_mime: str
    size_bytes: int
    limits: IntakeLimits
    tracker: LimitTracker
    quarantine: QuarantineResult = field(default_factory=QuarantineResult)
    depth: int = 0
