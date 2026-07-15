from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from brainflow_worker.gateway.hardware import profile_hardware
from brainflow_worker.gateway.pins import apply_pins_to_workflow, assert_pins_stable
from brainflow_worker.gateway.probes import run_capability_probes
from brainflow_worker.gateway.providers import aggregate_health, get_adapter
from brainflow_worker.gateway.registry import install_manifest, load_registry, rollback_registry
from brainflow_worker.gateway.secrets import delete_secret, secret_status, set_secret
from brainflow_worker.gateway.select import select_models
from brainflow_worker.validate import validate_workflow_ir
from brainflow_worker.workflow_gen import generate_workflow_ir

SCHEMA_ROOT = Path(__file__).resolve().parents[3] / "packages" / "schemas"


def handle_request(req: dict[str, Any]) -> dict[str, Any]:
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}

    if req.get("jsonrpc") != "2.0":
        return _error(req_id, -32600, "invalid jsonrpc version")

    try:
        if method == "ping":
            return _result(req_id, {"ok": True, "service": "brainflow-ai-worker"})

        if method == "llm.health":
            return _result(req_id, aggregate_health())

        if method == "llm.hardware":
            return _result(req_id, profile_hardware())

        if method in {"llm.select", "llm.recommend"}:
            result = select_models(
                policy=str(params.get("policy") or "auto"),
                requirements=params.get("requirements"),
                pinned=params.get("pinned"),
                run_active=bool(params.get("run_active")),
                allow_auto_reselect=bool(params.get("allow_auto_reselect")),
                single_model_only=bool(params.get("single_model_only")),
                refresh_registry=bool(params.get("refresh_registry")),
            )
            if method == "llm.recommend":
                return _result(
                    req_id,
                    {
                        "ok": result.get("ok"),
                        "recommendation": result.get("recommendation"),
                        "pin_resolution": result.get("pin_resolution"),
                        "error": result.get("error"),
                        "policy": result.get("policy"),
                    },
                )
            return _result(req_id, result)

        if method == "llm.probe":
            provider = str(params.get("provider") or "ollama")
            model = str(params.get("model") or "")
            adapter = get_adapter(provider)
            if adapter is None:
                return _error(req_id, 1003, f"unknown provider: {provider}")
            if not model:
                return _error(req_id, -32602, "model required")
            return _result(
                req_id,
                run_capability_probes(
                    adapter,
                    model=model,
                    which=params.get("probes"),
                    timeout_s=float(params.get("timeout_s") or 20.0),
                ),
            )

        if method == "registry.load":
            return _result(req_id, load_registry(refresh=bool(params.get("refresh"))))

        if method == "registry.install":
            manifest = params.get("manifest")
            if not isinstance(manifest, dict):
                return _error(req_id, -32602, "manifest object required")
            return _result(req_id, install_manifest(manifest, note=str(params.get("note") or "rpc")))

        if method == "registry.rollback":
            return _result(req_id, rollback_registry())

        if method == "secrets.set":
            return _result(
                req_id,
                set_secret(str(params.get("ref") or ""), str(params.get("value") or "")),
            )

        if method == "secrets.delete":
            return _result(req_id, delete_secret(str(params.get("ref") or "")))

        if method == "secrets.status":
            return _result(req_id, secret_status(str(params.get("ref") or "")))

        if method == "pins.assert_stable":
            try:
                assert_pins_stable(
                    pinned=params.get("pinned") or {},
                    requested=params.get("requested"),
                    run_active=bool(params.get("run_active", True)),
                )
                return _result(req_id, {"ok": True})
            except Exception as exc:  # noqa: BLE001
                return _error(req_id, 1004, str(exc))

        # Intake — lazy import so gateway methods stay available if intake deps lag
        if method == "intake.adapters":
            from brainflow_worker.intake.registry import list_adapters

            return _result(req_id, {"adapters": list_adapters()})

        if method == "intake.analyze":
            from brainflow_worker.intake.limits import IntakeLimits
            from brainflow_worker.intake.pipeline import analyze_bytes, analyze_path

            limits = None
            if isinstance(params.get("limits"), dict):
                raw = params["limits"]
                limits = IntakeLimits(
                    **{k: raw[k] for k in IntakeLimits.__dataclass_fields__ if k in raw}
                )
            path_mode = str(params.get("path_mode") or "link")
            file_id = params.get("file_id")
            if params.get("path"):
                return _result(
                    req_id,
                    analyze_path(
                        str(params["path"]),
                        path_mode=path_mode,
                        file_id=file_id,
                        limits=limits,
                    ),
                )
            if params.get("content_base64") is not None:
                data = base64.b64decode(str(params["content_base64"]))
                return _result(
                    req_id,
                    analyze_bytes(
                        data,
                        filename=params.get("filename"),
                        path=params.get("logical_path"),
                        path_mode=path_mode,
                        file_id=file_id,
                        limits=limits,
                    ),
                )
            return _error(req_id, -32602, "path or content_base64 required")

        if method == "workflow.generate":
            health = aggregate_health()
            if not health.get("ok"):
                return _error(
                    req_id,
                    1001,
                    "LLM unavailable (fail-closed): " + str(health.get("error")),
                    data=health,
                )
            prompt = str(params.get("prompt") or "")
            source_text = str(params.get("source_text") or "")
            selection = select_models(
                policy=str(params.get("policy") or "auto"),
                requirements=params.get("requirements"),
                pinned=params.get("pinned"),
                run_active=bool(params.get("run_active")),
                allow_auto_reselect=bool(params.get("allow_auto_reselect")),
            )
            pin_res = selection.get("pin_resolution") or {}
            pins = pin_res.get("pins") or {}
            planner = pins.get("planner") or {}
            model = params.get("model") or planner.get("name") or health.get("preferred_model")
            if params.get("run_active") and params.get("pinned"):
                assert_pins_stable(
                    pinned=params.get("pinned") or {},
                    requested=pins,
                    run_active=True,
                )
            workflow = generate_workflow_ir(
                prompt=prompt,
                source_text=source_text,
                model=str(model),
                health=health,
                pack=params.get("pack") if isinstance(params.get("pack"), dict) else None,
                model_digest=planner.get("digest"),
            )
            if pins:
                workflow = apply_pins_to_workflow(workflow, pins, overwrite=True)
            validation = validate_workflow_ir(workflow)
            if not validation["ok"]:
                return _error(
                    req_id,
                    1002,
                    "Generated workflow failed schema validation",
                    data=validation,
                )
            return _result(
                req_id,
                {
                    "workflow": workflow,
                    "validation": validation,
                    "selection": {
                        "ok": selection.get("ok"),
                        "policy": selection.get("policy"),
                        "recommendation": selection.get("recommendation"),
                        "pin_resolution": pin_res,
                    },
                },
            )

        if method == "schema.root":
            return _result(req_id, {"path": str(SCHEMA_ROOT)})

        return _error(req_id, -32601, f"method not found: {method}")
    except Exception as exc:  # noqa: BLE001 — surface to RPC caller
        return _error(req_id, -32000, str(exc))


def _result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(
    req_id: Any,
    code: int,
    message: str,
    data: Any | None = None,
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}
