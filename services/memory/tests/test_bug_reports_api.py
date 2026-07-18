"""Bug report HTTP endpoints."""

from __future__ import annotations

import base64

from aoep_shared.bug_reports import BugReportStore
from fastapi.testclient import TestClient

from memory.main import app

ADMIN = {"X-Admin-Secret": "dev-admin-secret"}


def _tiny_png_b64() -> str:
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(data).decode("ascii")


def test_submit_and_admin_list(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_BUG_REPORT_DIR", str(tmp_path / "bugs"))
    app.state.bug_reports = BugReportStore.open(tmp_path / "bugs")
    client = TestClient(app)

    r = client.post(
        "/bugs",
        json={
            "description": "Mic does not open on languages screen",
            "platform": "web",
            "app_version": "0.19.92",
            "screen": "/languages",
            "snapshot": {"route": "/languages"},
            "logs": ["TypeError: mic denied"],
            "screenshots": [
                {
                    "filename": "page.png",
                    "content_type": "image/png",
                    "data_base64": _tiny_png_b64(),
                }
            ],
        },
    )
    assert r.status_code == 200, r.text
    rid = r.json()["id"]

    listed = client.get("/admin/bugs", headers=ADMIN)
    assert listed.status_code == 200, listed.text
    assert listed.json()["count"] >= 1
    assert any(row["id"] == rid for row in listed.json()["reports"])

    detail = client.get(f"/admin/bugs/{rid}", headers=ADMIN)
    assert detail.status_code == 200
    assert detail.json()["attachments"]

    att = client.get(
        f"/admin/bugs/{rid}/attachments/{detail.json()['attachments'][0]}",
        headers=ADMIN,
    )
    assert att.status_code == 200
    assert att.headers["content-type"].startswith("image/")


def test_admin_requires_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_BUG_REPORT_DIR", str(tmp_path / "bugs2"))
    app.state.bug_reports = BugReportStore.open(tmp_path / "bugs2")
    client = TestClient(app)
    assert client.get("/admin/bugs").status_code == 401
