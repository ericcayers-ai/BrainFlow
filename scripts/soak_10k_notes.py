#!/usr/bin/env python3
"""Generate + time a large-vault FTS soak via crates/storage soak_bench.

Examples:
  python scripts/soak_10k_notes.py
  python scripts/soak_10k_notes.py --n 1000
  BRAINFLOW_SOAK_N=5000 python scripts/soak_10k_notes.py --keep

Writes docs/spikes/soak-10k-results.json and refreshes docs/spikes/soak-10k.md metrics.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_JSON = ROOT / "docs" / "spikes" / "soak-10k-results.json"
RESULTS_MD = ROOT / "docs" / "spikes" / "soak-10k.md"


def run_bench(n: int, keep: bool, vault: Path | None) -> dict:
    env = os.environ.copy()
    env["BRAINFLOW_SOAK_N"] = str(n)
    if keep:
        env["BRAINFLOW_SOAK_KEEP"] = "1"
    if vault is not None:
        env["BRAINFLOW_SOAK_VAULT"] = str(vault)
        vault.mkdir(parents=True, exist_ok=True)

    cmd = [
        "cargo",
        "run",
        "-p",
        "brainflow-storage",
        "--example",
        "soak_bench",
        "--release",
        "--",
        str(n),
    ]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    if proc.returncode != 0:
        raise SystemExit(f"soak_bench failed with exit {proc.returncode}")

    m = re.search(r"RESULT_JSON\s+(\{.*\})", out)
    if not m:
        raise SystemExit("soak_bench did not emit RESULT_JSON line")
    payload = json.loads(m.group(1))
    payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
    payload["command"] = " ".join(cmd)
    payload["release"] = True
    return payload


def write_docs(payload: dict) -> None:
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    n = payload["n"]
    budget = 100.0
    cycle_budget = 50.0
    fts_ok = payload.get("fts_budget_ok")
    qs_ok = payload.get("qs_budget_ok")
    cycle_ok = payload.get("cycle_budget_ok")
    save_ok = payload.get("save_budget_ok")
    md = f"""# 10k-note vault soak (FTS / search / open / edit-cycle)

Automated index + latency probe for Phase 3 exit readiness. **Does not** claim daily-team soak or WebView/CodeMirror keystroke sign-off.

## How to run

```bash
python scripts/soak_10k_notes.py              # aim N=10000
python scripts/soak_10k_notes.py --n 2000     # resource-bound smaller N
cargo run -p brainflow-storage --example soak_bench --release -- 10000
```

Env: `BRAINFLOW_SOAK_N`, `BRAINFLOW_SOAK_VAULT`, `BRAINFLOW_SOAK_CATALOG`, `BRAINFLOW_SOAK_KEEP=1`.

## Latest run

| Metric | Value |
|--------|-------|
| Recorded | {payload.get("recorded_at", "—")} |
| N notes indexed | **{n}** |
| Index build | {payload.get("index_build_ms", "—")} ms |
| FTS warm MATCH p50 / p95 | {payload.get("fts_p50_ms")} / **{payload.get("fts_p95_ms")}** ms |
| Tag search p50 / p95 | {payload.get("tag_p50_ms")} / {payload.get("tag_p95_ms")} ms |
| Quick-switcher proxy FTS p50 / p95 | {payload.get("qs_p50_ms")} / **{payload.get("qs_p95_ms")}** ms |
| Note open (read body) p50 / p95 | {payload.get("open_p50_ms")} / {payload.get("open_p95_ms")} ms |
| Note save upsert p50 / p95 | {payload.get("save_p50_ms", "—")} / **{payload.get("save_p95_ms", "—")}** ms |
| Open+save+search cycle p50 / p95 | {payload.get("cycle_p50_ms", "—")} / **{payload.get("cycle_p95_ms", "—")}** ms |
| Data loss during generate/index/edit | {payload.get("data_loss")} |
| Budget search/QS p95 &lt; {budget} ms | FTS={"pass" if fts_ok else "FAIL"} · QS={"pass" if qs_ok else "FAIL"} |
| Budget edit-cycle p95 &lt; {cycle_budget} ms | save={"pass" if save_ok else "FAIL/n/a"} · cycle={"pass" if cycle_ok else "FAIL/n/a"} |

Raw: [soak-10k-results.json](./soak-10k-results.json).

## Honest status

- Catalog FTS + **open+save+search edit-cycle proxy** are measured here (storage path that backs autosave/search).
- **Desktop UI keystroke / WebView** path is **not** measured — do not equate cycle_p95 with perceived typing latency.
- Phase 3 exit remains **unchecked** until daily-team use on a 10k vault is recorded by humans.
- Measurable catalog budgets (search/QS &lt; 100 ms; edit-cycle &lt; 50 ms) may be recorded as met when this harness passes at N=10k.
- If host is resource-bound, run smaller `N` and record the honest max in this file / JSON.
"""
    RESULTS_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {RESULTS_JSON.relative_to(ROOT)} and {RESULTS_MD.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="BrainFlow large-vault FTS soak")
    ap.add_argument("--n", type=int, default=int(os.environ.get("BRAINFLOW_SOAK_N", "10000")))
    ap.add_argument("--keep", action="store_true", help="Keep generated vault on disk")
    ap.add_argument("--vault", type=Path, default=None)
    ap.add_argument("--skip-run", action="store_true", help="Only rewrite docs from existing JSON")
    args = ap.parse_args()

    if args.skip_run and RESULTS_JSON.exists():
        payload = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
        write_docs(payload)
        return

    payload = run_bench(args.n, keep=args.keep, vault=args.vault)
    write_docs(payload)


if __name__ == "__main__":
    main()
