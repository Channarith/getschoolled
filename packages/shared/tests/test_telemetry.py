"""Telemetry store: perf, process metrics, errors, Prometheus exposition."""

from aoep_shared.telemetry import TelemetryStore, _percentile, process_metrics


def test_percentile():
    assert _percentile([], 95) == 0.0
    assert _percentile([10], 95) == 10
    assert _percentile([10, 20, 30, 40], 50) == 25.0


def test_process_metrics_has_memory_and_runtime():
    m = process_metrics()
    assert m["rss_mb"] >= 0.0
    assert m["threads"] >= 1
    assert "gc_objects" in m and "cpu_user_s" in m


def test_route_perf_and_totals():
    t = TelemetryStore("svc")
    for ms in (5, 10, 15, 20):
        t.observe_request("/x", "GET", 200, ms)
    t.observe_request("/x", "GET", 500, 99)
    perf = t.routes_perf()["GET /x"]
    assert perf["count"] == 5
    assert perf["errors"] == 1
    assert perf["p95_ms"] >= perf["p50_ms"]
    totals = t.totals()
    assert totals["requests"] == 5 and totals["errors"] == 1
    assert totals["error_rate"] == round(1 / 5, 4)


def test_inflight_gauge():
    t = TelemetryStore("svc")
    t.inc_inflight(); t.inc_inflight()
    assert t.totals()["inflight"] == 2
    t.dec_inflight()
    assert t.totals()["inflight"] == 1


def test_error_ring_captures_traceback_and_context():
    t = TelemetryStore("svc")
    try:
        raise ValueError("boom")
    except ValueError as exc:
        t.record_error(route="/a", method="POST", exc=exc, request_id="abc123")
    errs = t.recent_errors()
    assert errs[0]["type"] == "ValueError"
    assert errs[0]["message"] == "boom"
    assert "ValueError" in errs[0]["traceback"]
    assert errs[0]["request_id"] == "abc123"


def test_events_filterable_by_level():
    t = TelemetryStore("svc")
    t.event("info", "started")
    t.event("warning", "slow query", ms=1200)
    assert len(t.recent_events()) == 2
    warns = t.recent_events(level="warning")
    assert len(warns) == 1 and warns[0]["ms"] == 1200


def test_prometheus_exposition_format():
    t = TelemetryStore("memory")
    t.observe_request("/flags/{key}", "GET", 200, 12.0)
    text = t.prometheus_text()
    assert "# TYPE aoep_requests_total counter" in text
    assert 'aoep_requests_total{service="memory"' in text
    assert "aoep_process_resident_memory_mb" in text
    assert 'quantile="0.95"' in text


def test_summary_shape():
    t = TelemetryStore("svc")
    t.observe_request("/x", "GET", 200, 3.0)
    s = t.summary()
    assert s["service"] == "svc"
    assert "process" in s and "routes" in s and "totals" in s and "exporters" in s
