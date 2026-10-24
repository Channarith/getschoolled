from fastapi.testclient import TestClient

from theodore_webcam_lab import main


def test_shutdown_is_refused_for_non_local_callers(monkeypatch):
    killed = []
    monkeypatch.setattr(main.os, "kill", lambda *a: killed.append(a))
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    client = TestClient(main.app)  # the client host is "testclient", not loopback
    assert client.post("/admin/shutdown").status_code == 403
    assert client.post("/admin/shutdown", headers={"x-admin-secret": "guess"}).status_code == 403
    assert killed == []


def test_shutdown_allows_the_admin_secret(monkeypatch):
    killed = []
    monkeypatch.setattr(main.os, "kill", lambda *a: killed.append(a))
    monkeypatch.setenv("ADMIN_SECRET", "s3cret-value")
    client = TestClient(main.app)
    assert client.post("/admin/shutdown", headers={"x-admin-secret": "s3cret-value"}).status_code == 200
