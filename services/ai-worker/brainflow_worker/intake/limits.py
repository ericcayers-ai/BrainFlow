"""Resource limits for sandboxed ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntakeLimits:
    """Tunable defaults — see docs/FILE_INGESTION.md §5."""

    max_file_bytes: int = 50 * 1024 * 1024  # 50 MiB
    max_archive_depth: int = 3
    max_archive_entries: int = 500
    max_decompressed_bytes: int = 100 * 1024 * 1024  # 100 MiB
    max_decompression_ratio: float = 100.0
    max_pages: int = 500
    max_sheets: int = 100
    max_slides: int = 200
    max_media_duration_seconds: float = 3600.0
    max_segments: int = 10_000
    max_segment_chars: int = 500_000
    max_csv_rows: int = 50_000
    max_memory_hint_bytes: int = 256 * 1024 * 1024
    allow_remote_fetch: bool = False


DEFAULT_LIMITS = IntakeLimits()


@dataclass
class LimitTracker:
    limits: IntakeLimits = field(default_factory=lambda: DEFAULT_LIMITS)
    decompressed_bytes: int = 0
    archive_depth: int = 0
    pages_seen: int = 0
    entries_seen: int = 0

    def check_file_size(self, size: int) -> str | None:
        if size > self.limits.max_file_bytes:
            return (
                f"file size {size} exceeds max_file_bytes "
                f"{self.limits.max_file_bytes}"
            )
        return None

    def add_decompressed(self, compressed: int, expanded: int) -> str | None:
        self.decompressed_bytes += expanded
        if self.decompressed_bytes > self.limits.max_decompressed_bytes:
            return (
                f"decompressed bytes {self.decompressed_bytes} exceed "
                f"max_decompressed_bytes {self.limits.max_decompressed_bytes}"
            )
        if compressed > 0:
            ratio = expanded / compressed
            if ratio > self.limits.max_decompression_ratio:
                return (
                    f"decompression ratio {ratio:.1f} exceeds "
                    f"max_decompression_ratio {self.limits.max_decompression_ratio}"
                )
        return None

    def check_depth(self, depth: int) -> str | None:
        if depth > self.limits.max_archive_depth:
            return (
                f"archive nesting depth {depth} exceeds "
                f"max_archive_depth {self.limits.max_archive_depth}"
            )
        return None

    def check_entry_count(self) -> str | None:
        self.entries_seen += 1
        if self.entries_seen > self.limits.max_archive_entries:
            return (
                f"archive entries exceed max_archive_entries "
                f"{self.limits.max_archive_entries}"
            )
        return None
