"""create_service: rate-limit + HTTP cache wired into every service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aoep_shared.service import create_service


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    """Each test in this module sets its own RATE_LIMIT_* env. Make sure
    nothing leaks from a previous test or the suite-level conftest so the
    behaviour we assert is the behaviour we set."""
    monkeypatch.delenv("RATE_LIMIT", raising=False)
    monkeypatch.delenv("RATE_LIMIT_WINDOW", raising=False)
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    monkeypatch.delenv("RATE_LIMIT_DISABLED", raising=False)
    monkeypatch.delenv("HTTP_CACHE_DISABLED", raising=False)


def test_health_is_bypassed_by_rate_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW", "60")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    app = create_service("test-svc")
    client = TestClient(app)
    for _ in range(8):
        assert client.get("/health").status_code == 200


def test_user_routes_are_rate_limited_and_429(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "3")
    monkeypatch.setenv("RATE_LIMIT_WINDOW", "60")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    app = create_service("svc-rl")

    @app.get("/work")
    def work() -> dict:
        return {"ok": True}

    client = TestClient(app)
    statuses = [client.get("/work", headers={"x-user-id": "u1"}).status_code for _ in range(6)]
    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses
    blocked = client.get("/work", headers={"x-user-id": "u1"})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"]
    assert blocked.headers["x-ratelimit-limit"] == "3"
    fresh = client.get("/work", headers={"x-user-id": "u2"})
    assert fresh.status_code == 200


def test_disabled_via_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    app = create_service("svc-rl-off")

    @app.get("/work")
    def work() -> dict:
        return {"ok": True}

    client = TestClient(app)
    for _ in range(50):
        assert client.get("/work").status_code == 200


def test_cache_control_present_on_health_and_meta(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    app = create_service("svc-cache")
    client = TestClient(app)
    r = client.get("/version")
    assert r.status_code == 200
    assert "max-age=" in r.headers.get("cache-control", "")


def test_etag_revalidates_to_304(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    app = create_service("svc-etag")
    client = TestClient(app)
    r1 = client.get("/version")
    etag = r1.headers["etag"]
    r2 = client.get("/version", headers={"If-None-Match": etag})
    assert r2.status_code == 304
