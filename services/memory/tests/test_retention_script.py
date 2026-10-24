"""scripts/retention_purge.py must send the internal token the endpoint requires."""

from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "retention_purge.py"


def _load():
    spec = importlib.util.spec_from_file_location("retention_purge", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_sends_internal_token(monkeypatch):
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["token"] = self.headers.get("X-Internal-Token")
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.dumps({"deleted": 0}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("INTERNAL_TOKEN", "secret-token")
        rc = _load().main(["--memory-url", f"http://127.0.0.1:{server.server_port}"])
    finally:
        server.shutdown()
    assert rc == 0
    assert seen["token"] == "secret-token"
