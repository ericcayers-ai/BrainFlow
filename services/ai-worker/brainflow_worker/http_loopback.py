"""Dev-only loopback HTTP with random port + bearer token (never a fixed unauthenticated port)."""

from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from brainflow_worker.rpc import handle_request


def run_loopback() -> int:
    token = secrets.token_urlsafe(24)
    state = {"token": token}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            return

        def do_POST(self) -> None:  # noqa: N802
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {state['token']}":
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error":"unauthorized"}')
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            try:
                req = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                req = {}
            resp = handle_request(req)
            raw = json.dumps(resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    host, port = server.server_address
    print(json.dumps({"host": host, "port": port, "token": token, "path": "/rpc"}), flush=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()
    return 0
