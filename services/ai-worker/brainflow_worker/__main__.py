from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `domain_packs` imports when launched as python -m brainflow_worker
_WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKER_ROOT))

from brainflow_worker.rpc import handle_request  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BrainFlow AI worker (JSON-RPC stdio)")
    parser.add_argument(
        "--http-loopback",
        action="store_true",
        help="Dev-only: bind 127.0.0.1 random port with bearer token (not for production)",
    )
    args = parser.parse_args(argv)

    if args.http_loopback:
        from brainflow_worker.http_loopback import run_loopback

        return run_loopback()

    # Line-delimited JSON-RPC on stdin/stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"parse error: {exc}"},
            }
            print(json.dumps(resp), flush=True)
            continue
        resp = handle_request(req)
        print(json.dumps(resp), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
