from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Canonical keys used when hashing for signature.
_CANON_SKIP = {"signature"}


def schema_root() -> Path:
    return Path(__file__).resolve().parents[4] / "packages" / "schemas"


def bundled_registry_path() -> Path:
    return schema_root() / "model-registry" / "fixtures" / "registry.v1.json"


def app_data_dir() -> Path:
    override = os.environ.get("BRAINFLOW_APP_DATA")
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "BrainFlow"


def registry_cache_dir() -> Path:
    d = app_data_dir() / "model-registry"
    d.mkdir(parents=True, exist_ok=True)
    (d / "previous").mkdir(parents=True, exist_ok=True)
    (d / "keys").mkdir(parents=True, exist_ok=True)
    return d


def canonical_bytes(manifest: dict[str, Any]) -> bytes:
    payload = {k: v for k, v in manifest.items() if k not in _CANON_SKIP}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def content_digest(manifest: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def verify_manifest(
    manifest: dict[str, Any],
    *,
    public_keys: list[dict[str, Any]] | None = None,
    allow_dev: bool = True,
) -> dict[str, Any]:
    """Verify signature. Fail closed on tamper when keys configured."""
    digest = content_digest(manifest)
    sig = manifest.get("signature") or {}
    alg = sig.get("alg")
    keys = public_keys or _load_pinned_keys()

    if alg == "ed25519":
        return _verify_ed25519(manifest, digest, sig, keys)
    if alg == "bf-hmac-v1":
        return _verify_hmac(manifest, digest, sig, keys, allow_dev=allow_dev)
    if alg == "dev-unsigned" and allow_dev:
        return {
            "ok": True,
            "mode": "dev-unsigned",
            "digest": digest,
            "warning": "Development unsigned registry — not for production Auto downloads",
        }
    return {
        "ok": False,
        "digest": digest,
        "error": f"unsupported or missing signature alg: {alg!r}",
    }


def load_registry(*, path: Path | None = None, refresh: bool = False) -> dict[str, Any]:
    """Load current cached registry or bundled snapshot. Offline-safe."""
    cache = registry_cache_dir()
    current = cache / "current.json"
    source = path
    if source is None:
        if refresh or not current.exists():
            bundled = bundled_registry_path()
            if not bundled.exists():
                raise FileNotFoundError(f"No bundled or cached model registry at {bundled}")
            data = json.loads(bundled.read_text(encoding="utf-8"))
            installed = install_manifest(data, note="bundled_bootstrap")
            if installed.get("ok") and current.exists():
                source = current
            else:
                # Fall back to reading bundled without cache write (e.g. verify warn)
                source = bundled
        else:
            source = current
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    verify = verify_manifest(data)
    return {
        "ok": verify.get("ok", False),
        "path": str(source),
        "verify": verify,
        "manifest": data,
        "digest": verify.get("digest") or content_digest(data),
    }


def install_manifest(manifest: dict[str, Any], *, note: str = "install") -> dict[str, Any]:
    """Install after verification; rotate previous snapshot for rollback."""
    verify = verify_manifest(manifest)
    if not verify.get("ok"):
        return {"ok": False, "error": "signature verification failed", "verify": verify}
    cache = registry_cache_dir()
    current = cache / "current.json"
    if current.exists():
        prev_digest = content_digest(json.loads(current.read_text(encoding="utf-8")))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = cache / "previous" / f"{stamp}-{prev_digest.replace(':', '_')}.json"
        dest.write_text(current.read_text(encoding="utf-8"), encoding="utf-8")
    current.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    meta = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
        "digest": content_digest(manifest),
    }
    (cache / "current.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "digest": meta["digest"], "path": str(current)}


def rollback_registry() -> dict[str, Any]:
    cache = registry_cache_dir()
    previous = sorted((cache / "previous").glob("*.json"))
    if not previous:
        return {"ok": False, "error": "no previous registry snapshot"}
    latest = previous[-1]
    data = json.loads(latest.read_text(encoding="utf-8"))
    result = install_manifest(data, note=f"rollback_from:{latest.name}")
    if result.get("ok"):
        latest.unlink(missing_ok=True)
    return result


def sign_manifest_hmac(manifest: dict[str, Any], *, key_id: str, secret: bytes) -> dict[str, Any]:
    import hmac

    dig = content_digest(manifest)
    mac = hmac.new(secret, canonical_bytes(manifest), hashlib.sha256).hexdigest()
    out = dict(manifest)
    out["signature"] = {
        "alg": "bf-hmac-v1",
        "key_id": key_id,
        "value": mac,
        "content_digest": dig,
    }
    return out


def _verify_hmac(
    manifest: dict[str, Any],
    digest: str,
    sig: dict[str, Any],
    keys: list[dict[str, Any]],
    *,
    allow_dev: bool,
) -> dict[str, Any]:
    import hmac

    key_id = sig.get("key_id")
    match = next((k for k in keys if k.get("key_id") == key_id and k.get("alg") == "bf-hmac-v1"), None)
    secret: bytes | None = None
    if match and (match.get("secret_hex") or match.get("secret")):
        secret = (
            bytes.fromhex(match["secret_hex"])
            if match.get("secret_hex")
            else str(match.get("secret")).encode()
        )
    elif allow_dev and key_id == "brainflow-dev":
        secret = os.environ.get("BRAINFLOW_REGISTRY_HMAC", "brainflow-dev-hmac-key").encode()
    else:
        return {"ok": False, "digest": digest, "error": f"unknown hmac key_id: {key_id}"}
    expected = hmac.new(secret, canonical_bytes(manifest), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(sig.get("value") or "")):
        return {"ok": False, "digest": digest, "error": "hmac signature mismatch (tampered?)"}
    if sig.get("content_digest") and sig["content_digest"] != digest:
        return {"ok": False, "digest": digest, "error": "content_digest mismatch"}
    return {"ok": True, "mode": "bf-hmac-v1", "digest": digest, "key_id": key_id}


def _verify_ed25519(
    manifest: dict[str, Any],
    digest: str,
    sig: dict[str, Any],
    keys: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return {
            "ok": False,
            "digest": digest,
            "error": "cryptography package required for ed25519 verification",
        }
    key_id = sig.get("key_id")
    match = next((k for k in keys if k.get("key_id") == key_id and k.get("alg") == "ed25519"), None)
    if not match:
        return {"ok": False, "digest": digest, "error": f"unknown ed25519 key_id: {key_id}"}
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(match["public_key_hex"]))
    try:
        pub.verify(bytes.fromhex(str(sig.get("value"))), canonical_bytes(manifest))
    except InvalidSignature:
        return {"ok": False, "digest": digest, "error": "ed25519 signature invalid"}
    return {"ok": True, "mode": "ed25519", "digest": digest, "key_id": key_id}


def _load_pinned_keys() -> list[dict[str, Any]]:
    keys_path = schema_root() / "model-registry" / "keys" / "pinned-keys.json"
    cache_keys = registry_cache_dir() / "keys" / "pinned-keys.json"
    for path in (cache_keys, keys_path):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")).get("keys") or []
    return [
        {
            "key_id": "brainflow-dev",
            "alg": "bf-hmac-v1",
            "secret_hex": os.environ.get(
                "BRAINFLOW_REGISTRY_HMAC", "brainflow-dev-hmac-key"
            ).encode().hex(),
        }
    ]
