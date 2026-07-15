"""
Full vertical-slice integration (scripted, no Tauri UI):

  open/create vault → save note → optional intake → workflow.generate
  (Ollama if up, else fail-closed) → artifact under .brainflow → reopen session

Run from repo root (worker venv on PYTHONPATH / installed editable)::

  services/ai-worker/.venv/Scripts/python.exe -m pytest tests/e2e/test_vertical_slice.py -v

Or::

  npm run test:e2e:vertical-slice
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_ROOT = REPO_ROOT / "services" / "ai-worker"
GOLDEN_MD = REPO_ROOT / "tests" / "corpus" / "golden" / "sample.md"


def _ensure_worker_importable() -> None:
    import sys

    root = str(WORKER_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


_ensure_worker_importable()

from brainflow_worker.rpc import handle_request  # noqa: E402
from brainflow_worker.validate import validate_workflow_ir  # noqa: E402


def _rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }
    )


def _ensure_vault_layout(root: Path) -> None:
    for rel in (
        ".brainflow",
        ".brainflow/workflows",
        ".brainflow/artifacts",
        ".brainflow/graphs",
        ".brainflow/graphs/canvas",
        ".brainflow/bases",
        ".brainflow/templates",
        ".brainflow/runs",
        ".brainflow/local",
        ".brainflow/local/recovery",
        "notes",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)
    vault_json = root / ".brainflow" / "vault.json"
    if not vault_json.exists():
        vault_json.write_text(
            json.dumps({"schema_version": 1, "display_name": "E2E Vault"}, indent=2),
            encoding="utf-8",
        )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_json(path: Path, value: object) -> None:
    _atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _session_path(tmp_home: Path) -> Path:
    """Mirror Tauri load_session / generate_workflow_slice session location."""
    return tmp_home / "BrainFlow" / "session.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.fixture()
def e2e_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate session.json from the real %LOCALAPPDATA%\\BrainFlow."""
    home = tmp_path / "localappdata"
    home.mkdir()
    # dirs::data_local_dir on Windows uses LOCALAPPDATA; Python e2e mirrors that path.
    monkeypatch.setenv("LOCALAPPDATA", str(home))
    # Also set for Unix-like runners if/when used.
    monkeypatch.setenv("XDG_DATA_HOME", str(home))
    return home


def test_vertical_slice_open_save_intake_llm_artifact_reopen(e2e_home: Path) -> None:
    vault = Path(tempfile.mkdtemp(prefix="brainflow-e2e-vault-"))
    try:
        # 1) Open/create vault
        _ensure_vault_layout(vault)
        assert (vault / ".brainflow" / "vault.json").is_file()
        assert (vault / "notes").is_dir()

        # 2) Save note (atomic write into vault notes/)
        note_rel = "notes/welcome.md"
        note_body = (
            "# Welcome\n\n"
            "E2E vertical-slice note for BrainFlow.\n\n"
            "Goal: produce a short study workflow from this text.\n"
        )
        _atomic_write_text(vault / note_rel, note_body)
        assert (vault / note_rel).read_text(encoding="utf-8") == note_body

        # 3) Intake (optional): golden markdown when present
        intake_ok = False
        if GOLDEN_MD.is_file():
            intake = _rpc(
                "intake.analyze",
                {
                    "path": str(GOLDEN_MD),
                    "path_mode": "link",
                },
                req_id=10,
            )
            assert "error" not in intake, intake
            bundle = intake["result"]["bundle"]
            assert bundle["metadata"]["adapter_id"] == "markdown"
            assert intake["result"]["validation"]["ok"] is True
            intake_ok = True

        # 4) LLM health — fail closed if unavailable
        health = _rpc("llm.health", {}, req_id=20)
        if "error" in health or not (health.get("result") or {}).get("ok"):
            err = health.get("error") or (health.get("result") or {}).get("error")
            pytest.fail(
                "LLM unavailable (fail-closed assert): vertical slice must not invent AI. "
                f"detail={err!r}"
            )

        # 5) workflow.generate (live Ollama)
        gen = _rpc(
            "workflow.generate",
            {
                "prompt": "Create a short study workflow that extracts key points and writes a summary artifact.",
                "source_text": note_body,
                "model": "llama3.2:3b",
            },
            req_id=30,
        )
        if "error" in gen:
            pytest.fail(
                "workflow.generate failed (fail-closed; no pretend AI): "
                f"{gen['error']}"
            )
        workflow = gen["result"]["workflow"]
        validation = validate_workflow_ir(workflow)
        assert validation["ok"] is True, validation
        workflow_id = workflow.get("workflow_id") or str(uuid.uuid4())
        workflow["workflow_id"] = workflow_id

        # Persist workflow + graph stub + artifact + run (same layout as Tauri slice)
        wf_rel = f".brainflow/workflows/{workflow_id}.json"
        _atomic_write_json(vault / wf_rel, workflow)

        run_id = str(uuid.uuid4())
        artifact_rel = f".brainflow/artifacts/{workflow_id}/{run_id}/summary.md"
        title = workflow.get("title") or "Workflow"
        goal = ((workflow.get("goal") or {}).get("statement")) or ""
        artifact = (
            f"# {title}\n\nGenerated by BrainFlow workflow kernel.\n\n"
            f"## Goal\n\n{goal}\n\n## Source\n\n`{note_rel}`\n\n"
            f"## Workflow ID\n\n`{workflow_id}`\n\n## Run ID\n\n`{run_id}`\n"
        )
        _atomic_write_text(vault / artifact_rel, artifact)
        assert (vault / artifact_rel).is_file()

        run = {
            "schema_version": 1,
            "run_id": run_id,
            "workflow_id": workflow_id,
            "status": "succeeded",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "vault_relative_workflow_path": wf_rel,
            "artifact_paths": [artifact_rel],
            "error": None,
            "intake_ran": intake_ok,
        }
        run_rel = f".brainflow/runs/{run_id}.json"
        _atomic_write_json(vault / run_rel, run)

        # Session pointer for reopen (LOCALAPPDATA/BrainFlow/session.json)
        session = {
            "schema_version": 1,
            "last_vault": str(vault),
            "last_note": note_rel,
            "last_run_id": run_id,
            "last_workflow_id": workflow_id,
        }
        sess_path = _session_path(e2e_home)
        sess_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(sess_path, session)

        # 6) Reopen session: read session → vault → note / workflow / run / artifact
        loaded = json.loads(sess_path.read_text(encoding="utf-8"))
        assert loaded["last_vault"] == str(vault)
        reopen_root = Path(loaded["last_vault"])
        assert reopen_root.is_dir()
        _ensure_vault_layout(reopen_root)  # open_vault ensure_layout equivalent

        note_again = (reopen_root / loaded["last_note"]).read_text(encoding="utf-8")
        assert note_again == note_body

        wf_again = json.loads(
            (reopen_root / f".brainflow/workflows/{loaded['last_workflow_id']}.json").read_text(
                encoding="utf-8"
            )
        )
        assert wf_again["workflow_id"] == workflow_id
        assert isinstance(wf_again.get("nodes"), list) and wf_again["nodes"]

        run_again = json.loads(
            (reopen_root / f".brainflow/runs/{loaded['last_run_id']}.json").read_text(
                encoding="utf-8"
            )
        )
        assert run_again["status"] == "succeeded"
        art_rel = run_again["artifact_paths"][0]
        assert (reopen_root / art_rel).is_file()
        assert "Generated by BrainFlow" in (reopen_root / art_rel).read_text(encoding="utf-8")

    finally:
        shutil.rmtree(vault, ignore_errors=True)


def test_vertical_slice_fail_closed_when_llm_unhealthy(
    e2e_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a healthy LLM, workflow.generate must error — never invent IR."""
    from brainflow_worker import rpc as rpc_mod

    def _dead_health(*_a, **_k):
        return {
            "ok": False,
            "error": "LLM unavailable (forced for e2e fail-closed test)",
            "provider": "ollama",
            "models": [],
        }

    # rpc.handle_request calls the name bound in rpc module at import time.
    monkeypatch.setattr(rpc_mod, "aggregate_health", _dead_health)

    gen = _rpc(
        "workflow.generate",
        {"prompt": "should not run", "source_text": "x"},
        req_id=41,
    )
    assert "error" in gen, "expected fail-closed RPC error, got success"
    assert gen["error"]["code"] == 1001
    msg = gen["error"]["message"].lower()
    assert "fail-closed" in msg or "unavailable" in msg
    _ = e2e_home  # session isolation still applied
