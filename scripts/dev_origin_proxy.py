#!/usr/bin/env python3
"""Dev-only single-origin reverse proxy mirroring infra/compose/edge.conf.

Routes same-origin /<svc>/<path> to the matching backend (prefix stripped) and
everything else to the Next.js web app. Used to validate the deployed-mode
same-origin path-prefix routing locally; NOT part of the shipped stack.
"""

from __future__ import annotations

import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEB = "127.0.0.1:3000"
PREFIXES = {
    "/orchestrator": "127.0.0.1:8000",
    "/identity": "127.0.0.1:8008",
    "/curriculum": "127.0.0.1:8005",
    "/integrations": "127.0.0.1:8007",
    "/memory": "127.0.0.1:8004",
    "/speech": "127.0.0.1:8002",
    "/billing": "127.0.0.1:8006",
    "/perception": "127.0.0.1:8003",
}


def resolve(path: str):
    for prefix, host in PREFIXES.items():
        if path == prefix or path.startswith(prefix + "/"):
            stripped = path[len(prefix):] or "/"
            return host, stripped
    return WEB, path


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self):
        host, upstream_path = resolve(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None
        url = f"http://{host}{upstream_path}"
        req = urllib.request.Request(url, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() in ("host", "content-length", "connection"):
                continue
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding", "connection", "content-length"):
                        continue
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:  # noqa: BLE001
            msg = f"proxy error: {e}".encode()
            self.send_response(502)
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    do_GET = _proxy
    do_POST = _proxy
    do_PUT = _proxy
    do_DELETE = _proxy
    do_PATCH = _proxy

    def log_message(self, fmt, *args):  # quieter
        sys.stderr.write("%s -> %s\n" % (self.path, resolve(self.path)[0]))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
