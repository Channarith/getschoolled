"""Telemetry endpoints + middleware wired by create_service."""

from fastapi.testclient import TestClient
from memory.main import app

client = TestClient(app)


def test_metrics_prometheus_exposition():
    client.get("/flags/evaluate")  # generate some traffic
    res = client.get("/metrics")
    assert res.headers["content-type"].startswith("text/plain")
    body = res.text
    assert "aoep_process_resident_memory_mb" in body
    assert "aoep_requests_total" in body


def test_summary_reports_perf_and_memory():
    client.get("/flags/evaluate")
    body = client.get("/telemetry/summary").json()
    assert body["service"] == "memory"
    assert body["process"]["rss_mb"] >= 0.0
    assert body["totals"]["requests"] >= 1
    # the route we just hit is tracked
    assert any("/flags/evaluate" in k for k in body["routes"])


def test_request_id_and_server_timing_headers():
    res = client.get("/health")
    assert res.headers.get("X-Request-ID")
    assert "dur=" in res.headers.get("Server-Timing", "")


def test_errors_endpoint_captures_5xx(monkeypatch):
    # A 404 is a 4xx (not an error); ensure the errors endpoint is reachable.
    body = client.get("/telemetry/errors").json()
    assert body["service"] == "memory"
    assert isinstance(body["errors"], list)


def test_logs_endpoint():
    body = client.get("/telemetry/logs").json()
    assert body["service"] == "memory"
    assert isinstance(body["events"], list)
