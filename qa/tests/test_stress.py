"""Self-tests for the QA stress harness (runs against a local stub server)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from stress import (
    Scenario,
    evaluate,
    percentile,
    run_scenario,
    service_available,
)


# --------------------------------------------------------------------------- #
# A tiny in-process HTTP server to exercise the harness deterministically.
# --------------------------------------------------------------------------- #
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        elif self.path == "/boom":
            self._send(500, {"error": "boom"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self._send(200, {"echo": True})


@pytest.fixture(scope="module")
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def test_percentile_interpolates():
    data = [10, 20, 30, 40]
    assert percentile(data, 50) == 25.0
    assert percentile(data, 0) == 10
    assert percentile(data, 100) == 40
    assert percentile([], 95) == 0.0


def test_service_available(server):
    assert service_available(server) is True
    assert service_available("http://127.0.0.1:1") is False


def test_run_scenario_success_under_concurrency(server):
    sc = Scenario("health", "GET", "/health", check=lambda j: j.get("status") == "ok")
    res = run_scenario(server, sc, concurrency=8, total=40)
    assert res.requests == 40
    assert res.errors == 0
    assert res.functional_pass_rate == 1.0
    assert res.pct(95) >= 0.0


def test_run_scenario_detects_functional_failure(server):
    # Expect status 200 but assert a key that isn't present -> functional fail.
    sc = Scenario("health", "GET", "/health", check=lambda j: j.get("missing") == 1)
    res = run_scenario(server, sc, concurrency=4, total=12)
    assert res.functional_failures == 12
    assert res.functional_pass_rate == 0.0


def test_run_scenario_counts_5xx_as_errors(server):
    sc = Scenario("boom", "GET", "/boom", expect_status=200)
    res = run_scenario(server, sc, concurrency=4, total=8)
    assert res.errors == 8  # 500s
    assert res.functional_failures == 8


def test_post_scenario_with_body(server):
    sc = Scenario("echo", "POST", "/echo", body={"a": 1}, check=lambda j: j.get("echo") is True)
    res = run_scenario(server, sc, concurrency=4, total=10)
    assert res.functional_pass_rate == 1.0


def test_evaluate_flags_breaches():
    report = {"services": {"svc": {"available": True, "scenarios": {
        "slow": {"error_rate": 0.2, "functional_pass_rate": 0.5, "p95_ms": 5000.0},
    }}}}
    breaches = evaluate(report, max_error_rate=0.01, max_p95_ms=1500, min_functional=0.99)
    assert len(breaches) == 3  # error rate, functional, p95 all breach
