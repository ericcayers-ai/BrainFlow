"""Pin model digests per workflow/run — never silently swap mid-run."""

from __future__ import annotations

from typing import Any


class PinViolation(RuntimeError):
    pass


def pins_from_workflow(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pins = (workflow.get("pins") or {}).get("models") or {}
    return {str(role): dict(ref) for role, ref in pins.items() if isinstance(ref, dict)}


def assert_pins_stable(
    *,
    pinned: dict[str, dict[str, Any]],
    requested: dict[str, dict[str, Any]] | None,
    run_active: bool,
) -> None:
    """Reject mid-run model swaps. New recommendations must notify, not mutate."""
    if not run_active:
        return
    if not requested:
        return
    for role, pin in pinned.items():
        nxt = requested.get(role)
        if not nxt:
            continue
        if pin.get("digest") and nxt.get("digest") and pin["digest"] != nxt["digest"]:
            raise PinViolation(
                f"Refuse mid-run swap for role '{role}': "
                f"pinned digest {pin['digest']} != requested {nxt['digest']}"
            )
        if pin.get("name") and nxt.get("name") and pin["name"] != nxt["name"]:
            raise PinViolation(
                f"Refuse mid-run swap for role '{role}': "
                f"pinned name {pin['name']} != requested {nxt['name']}"
            )


def apply_pins_to_workflow(
    workflow: dict[str, Any],
    pins: dict[str, dict[str, Any]],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Attach digests to workflow IR pins. Existing pins win unless overwrite."""
    out = dict(workflow)
    pins_block = dict(out.get("pins") or {})
    models = dict(pins_block.get("models") or {})
    for role, ref in pins.items():
        if role in models and not overwrite:
            # Keep historical/active pin frozen.
            continue
        models[role] = {
            "provider": ref["provider"],
            "name": ref["name"],
            "digest": ref.get("digest") or "unknown",
        }
    pins_block["models"] = models
    if "prompt_pack_version" not in pins_block:
        pins_block["prompt_pack_version"] = "0.1.0"
    out["pins"] = pins_block
    return out


def resolve_for_run(
    *,
    policy: str,
    pinned: dict[str, dict[str, Any]] | None,
    recommended: dict[str, dict[str, Any]],
    allow_auto_reselect: bool = False,
    run_active: bool = False,
) -> dict[str, Any]:
    """
    Choose pins for a run.
    - Pinned policy / existing pins: keep
    - Active run: never swap
    - Auto + failure reselect: only if allow_auto_reselect
    """
    pinned = pinned or {}
    if run_active and pinned:
        # Active runs never swap — freeze pins. Callers that attempt an explicit
        # digest change must use assert_pins_stable (raises PinViolation).
        return {"pins": pinned, "changed": False, "reason": "run_active_frozen"}

    if policy == "pinned" and pinned:
        return {
            "pins": pinned,
            "changed": False,
            "reason": "pinned_policy",
            "notification": "Newer registry recommendations available but pinned policy holds",
        }

    if pinned and not allow_auto_reselect:
        return {
            "pins": pinned,
            "changed": False,
            "reason": "existing_pins_hold",
            "notification": "Recommendation differs; pin holds until user opts in",
        }

    return {"pins": recommended, "changed": True, "reason": "auto_selected"}
