"""Secret storage for provider API keys.

Never writes secrets into the portable vault. Prefer:
1. Ephemeral injection from Tauri/Rust core (env BRAINFLOW_SECRET_<REF>)
2. OS keychain via optional `keyring` package
3. Explicit denial (fail-closed) — no plaintext fallback files with live keys

Tauri commands may set keys into the OS store; the worker only reads by ref.
"""

from __future__ import annotations

import os
import re
from typing import Any

_SERVICE = "BrainFlow"
_MEMORY: dict[str, str] = {}
_REF_RE = re.compile(r"^[a-zA-Z0-9_.:@-]{1,128}$")


def _env_key(ref: str) -> str:
    safe = re.sub(r"[^A-Z0-9_]", "_", ref.upper())
    return f"BRAINFLOW_SECRET_{safe}"


def validate_ref(ref: str) -> str:
    if not _REF_RE.match(ref):
        raise ValueError(f"invalid secret ref: {ref!r}")
    return ref


def get_secret(ref: str) -> str | None:
    ref = validate_ref(ref)
    if ref in _MEMORY:
        return _MEMORY[ref]
    env = os.environ.get(_env_key(ref))
    if env:
        return env
    try:
        import keyring  # type: ignore

        val = keyring.get_password(_SERVICE, ref)
        return val or None
    except Exception:  # noqa: BLE001
        return None


def set_secret(ref: str, value: str, *, prefer_keyring: bool = True) -> dict[str, Any]:
    """Store secret. Never persists under vault paths."""
    ref = validate_ref(ref)
    if not value:
        raise ValueError("empty secret rejected")
    if prefer_keyring:
        try:
            import keyring  # type: ignore

            keyring.set_password(_SERVICE, ref, value)
            _MEMORY.pop(ref, None)
            return {"ok": True, "ref": ref, "backend": "os_keyring"}
        except Exception as exc:  # noqa: BLE001
            # Session memory only — caller (Tauri) should own durable store.
            _MEMORY[ref] = value
            return {
                "ok": True,
                "ref": ref,
                "backend": "process_memory",
                "warning": f"OS keyring unavailable ({exc}); secret held in worker memory only",
            }
    _MEMORY[ref] = value
    return {"ok": True, "ref": ref, "backend": "process_memory"}


def delete_secret(ref: str) -> dict[str, Any]:
    ref = validate_ref(ref)
    _MEMORY.pop(ref, None)
    try:
        import keyring  # type: ignore

        keyring.delete_password(_SERVICE, ref)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "ref": ref}


def secret_status(ref: str) -> dict[str, Any]:
    ref = validate_ref(ref)
    present = get_secret(ref) is not None
    backend = "missing"
    if ref in _MEMORY:
        backend = "process_memory"
    elif os.environ.get(_env_key(ref)):
        backend = "env"
    elif present:
        backend = "os_keyring_or_unknown"
    return {"ref": ref, "present": present, "backend": backend}
