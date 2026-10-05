#!/usr/bin/env python3
"""Minimal HTTP robot embodiment bridge for local dev and lab tests.

POST /robot          {"action":"say","text":"...","language":"en"}
POST /robot          {"action":"gesture","name":"wave"}
GET  /robot/perceive -> {"frames":[],"audio":null}

Run:
  python3 scripts/robot_bridge_demo.py --port 8765
  export ROBOT_ENDPOINT=http://127.0.0.1:8765/robot
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    log: list[dict] = []

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/perceive"):
            self._json(200, {"frames": [], "audio": None})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        _Handler.log.append(payload)
        self._json(200, {"accepted": True, "payload": payload})

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = HTTPServer((args.host, args.port), _Handler)
    print(f"robot bridge listening on http://{args.host}:{args.port}/robot")
    server.serve_forever()


if __name__ == "__main__":
    main()
