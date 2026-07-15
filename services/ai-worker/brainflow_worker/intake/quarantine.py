"""Quarantine / execute-prevention for imported content.

Never execute macros, scripts, or active content from ingested files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Hard binaries — blocked at top-level and inside archives.
HARD_EXECUTABLE_EXTENSIONS = frozenset(
    {
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bat",
        ".cmd",
        ".com",
        ".msi",
        ".scr",
        ".vbs",
        ".vbe",
        ".jse",
        ".wsf",
        ".wsh",
        ".jar",
        ".apk",
        ".app",
        ".bin",
        ".run",
        ".gadget",
        ".hta",
        ".cpl",
        ".msc",
        ".reg",
        ".inf",
        ".lnk",
        ".url",
        ".scf",
        ".pif",
    }
)

# Scripts blocked only when encountered as archive members (never executed).
ARCHIVE_SCRIPT_EXTENSIONS = frozenset(
    {
        ".ps1",
        ".js",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
    }
)

EXECUTABLE_EXTENSIONS = HARD_EXECUTABLE_EXTENSIONS | ARCHIVE_SCRIPT_EXTENSIONS

MACRO_CONTAINER_EXTENSIONS = frozenset(
    {
        ".docm",
        ".xlsm",
        ".pptm",
        ".dotm",
        ".xltm",
        ".potm",
        ".docb",
    }
)

# Office Open XML parts that carry VBA / macros.
OOXML_MACRO_PARTS = (
    "vbaProject.bin",
    "vbaData.xml",
    "vbaproject.bin",
)


@dataclass
class QuarantineResult:
    actions: list[str] = field(default_factory=list)
    active_content_flags: list[str] = field(default_factory=list)
    macros_blocked: bool = False
    scripts_stripped: bool = False
    blocked: bool = False
    block_reason: str | None = None


_SCRIPT_TAG_RE = re.compile(
    r"<script\b[^>]*>.*?</script>",
    re.IGNORECASE | re.DOTALL,
)
_EVENT_HANDLER_RE = re.compile(
    r"\son[a-z]+\s*=\s*(['\"]).*?\1",
    re.IGNORECASE | re.DOTALL,
)
_JS_URL_RE = re.compile(r"\bjavascript\s*:", re.IGNORECASE)
_REMOTE_REF_RE = re.compile(
    r"""(?i)(?:src|href|data)\s*=\s*["']\s*https?://""",
)


def quarantine_path_name(name: str) -> QuarantineResult:
    """Inspect a top-level filename for hard-exec / macro risk (code sources OK)."""
    result = QuarantineResult()
    lower = name.lower().replace("\\", "/")
    base = lower.rsplit("/", 1)[-1]
    ext = ""
    if "." in base:
        ext = "." + base.rsplit(".", 1)[-1]

    if ext in HARD_EXECUTABLE_EXTENSIONS:
        result.blocked = True
        result.block_reason = f"executable extension blocked: {ext}"
        result.active_content_flags.append(f"executable:{ext}")
        result.actions.append("blocked_executable_entry")
        return result

    if ext in MACRO_CONTAINER_EXTENSIONS:
        result.macros_blocked = True
        result.active_content_flags.append(f"macro_container:{ext}")
        result.actions.append("macro_container_flagged")

    for part in OOXML_MACRO_PARTS:
        if part.lower() in lower:
            result.macros_blocked = True
            result.active_content_flags.append("ooxml_macro_part")
            result.actions.append("blocked_macro_part")
            result.blocked = True
            result.block_reason = "Office macro payload part quarantined"
            return result

    return result


def quarantine_archive_entry(name: str) -> QuarantineResult:
    """Stricter checks for members inside archives — scripts never extracted for exec."""
    result = quarantine_path_name(name)
    if result.blocked:
        return result
    lower = name.lower().replace("\\", "/")
    base = lower.rsplit("/", 1)[-1]
    ext = ""
    if "." in base:
        ext = "." + base.rsplit(".", 1)[-1]
    if ext in ARCHIVE_SCRIPT_EXTENSIONS:
        result.blocked = True
        result.block_reason = f"archive script entry blocked: {ext}"
        result.active_content_flags.append(f"archive_script:{ext}")
        result.actions.append("blocked_archive_script")
    return result


def strip_html_active_content(html: str) -> tuple[str, QuarantineResult]:
    """Remove script tags, event handlers, and javascript: URLs. Never fetch remotes."""
    result = QuarantineResult()
    out = html
    if _SCRIPT_TAG_RE.search(out):
        result.scripts_stripped = True
        result.active_content_flags.append("html_script")
        result.actions.append("stripped_script_tags")
        out = _SCRIPT_TAG_RE.sub("", out)
    if _EVENT_HANDLER_RE.search(out):
        result.scripts_stripped = True
        result.active_content_flags.append("html_event_handler")
        result.actions.append("stripped_event_handlers")
        out = _EVENT_HANDLER_RE.sub("", out)
    if _JS_URL_RE.search(out):
        result.scripts_stripped = True
        result.active_content_flags.append("javascript_url")
        result.actions.append("stripped_javascript_urls")
        out = _JS_URL_RE.sub("blocked:", out)
    if _REMOTE_REF_RE.search(out):
        result.active_content_flags.append("remote_reference")
        result.actions.append("noted_remote_reference_not_fetched")
    return out, result


def merge_quarantine(*parts: QuarantineResult) -> QuarantineResult:
    merged = QuarantineResult()
    for p in parts:
        merged.actions.extend(p.actions)
        merged.active_content_flags.extend(p.active_content_flags)
        merged.macros_blocked = merged.macros_blocked or p.macros_blocked
        merged.scripts_stripped = merged.scripts_stripped or p.scripts_stripped
        if p.blocked and not merged.blocked:
            merged.blocked = True
            merged.block_reason = p.block_reason
    merged.actions = list(dict.fromkeys(merged.actions))
    merged.active_content_flags = list(dict.fromkeys(merged.active_content_flags))
    return merged
