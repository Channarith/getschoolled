"""Lab smoke probe: up, down, version mismatch, and the 18xxx port offset."""

from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "lab_smoke", ROOT / "scripts" / "lab_smoke.py"
)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def _serve(routes: dict[str, tuple[int, dict]]) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            status, payload = routes.get(self.path, (404, {"detail": "no"}))
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, _fmt, *_args):
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_catalog_covers_the_makefile_labs():
    names = [name for name, _port, _kind in smoke.LABS]
    for required in (
        "speech",
        "llm-lab",
        "object3d",
        "course-studio",
        "rag-lab",
        "cosyvoice",
        "webcam",
        "children",
        "drive",
        "homework",
        "music",
        "meeting-agents",
    ):
        assert required in names
    assert smoke.effective_port("rag-lab", 8095, offset=10000, overrides={}) == 18095
    assert smoke.effective_port(
        "rag-lab", 8095, offset=10000, overrides={"rag-lab": 19095}
    ) == 19095


def test_probe_marks_match_mismatch_and_down(tmp_path):
    good = _serve({
        "/health": (200, {"status": "ok"}),
        "/version": (200, {"version": "1.2.3"}),
    })
    bad = _serve({
        "/health": (200, {"ok": True}),
        "/version": (200, {"version": "9.9.9"}),
    })
    bare = _serve({"/health": (200, {"ok": True})})
    labs = (
        ("good", good.server_address[1], "http"),
        ("bad", bad.server_address[1], "http"),
        ("bare", bare.server_address[1], "http"),
        ("closed", 1, "http"),
        ("meeting-agents", None, "offline"),
    )
    try:
        rows = smoke.probe_all(
            host="127.0.0.1",
            offset=0,
            overrides={},
            expected="1.2.3",
            timeout=1.0,
            labs=labs,
        )
    finally:
        good.shutdown()
        bad.shutdown()
        bare.shutdown()
    by_name = {row["name"]: row for row in rows}
    assert by_name["good"]["status"] == "up"
    assert by_name["bad"]["status"] == "mismatch"
    assert by_name["bare"]["status"] == "up"
    assert by_name["bare"]["detail"] == "no /version"
    assert by_name["closed"]["status"] == "down"
    assert by_name["meeting-agents"]["status"] == "offline"
    assert smoke.exit_code(rows, allow_down=True, require_version=False) == 1
    assert smoke.exit_code(
        [by_name["closed"]], allow_down=True, require_version=False
    ) == 0
    assert smoke.exit_code(
        [by_name["closed"]], allow_down=False, require_version=False
    ) == 2
    assert smoke.exit_code(
        [by_name["bare"]], allow_down=True, require_version=True
    ) == 1
