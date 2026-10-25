import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


def _client(monkeypatch):
    for k in ("RATE_LIMIT_DISABLED", "AOEP_OP_THROTTLE_DISABLED"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.setenv("ADMIN_SECRET", "correct-horse-battery-staple-123")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setenv("AOEP_OP_FAIL_LIMIT", "5")
    from aoep_shared.service import create_service

    return TestClient(create_service("locktest"))


def test_wrong_operator_secret_locks_the_caller_out_after_the_limit(monkeypatch):
    c = _client(monkeypatch)
    codes = [c.get("/metrics", headers={"x-admin-secret": f"guess-{i}"}).status_code for i in range(8)]
    assert codes[:5] == [401] * 5
    assert set(codes[5:]) == {429}


def test_lockout_also_blocks_the_right_secret_until_the_window_passes(monkeypatch):
    c = _client(monkeypatch)
    for i in range(5):
        c.get("/metrics", headers={"x-admin-secret": f"guess-{i}"})
    assert c.get("/metrics", headers={"x-admin-secret": "correct-horse-battery-staple-123"}).status_code == 429


def test_the_right_secret_never_counts_against_the_caller(monkeypatch):
    c = _client(monkeypatch)
    ok = [c.get("/metrics", headers={"x-admin-secret": "correct-horse-battery-staple-123"}).status_code for _ in range(20)]
    assert set(ok) == {200}


def test_requests_without_operator_headers_are_unaffected(monkeypatch):
    c = _client(monkeypatch)
    for i in range(5):
        c.get("/metrics", headers={"x-admin-secret": f"guess-{i}"})
    assert c.get("/health").status_code == 200
