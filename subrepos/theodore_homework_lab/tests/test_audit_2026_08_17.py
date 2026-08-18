"""Regression test for the 2026-08-17 audit (homework lab).

POST /api/homework/grade with "answers": null used to 500 (TypeError inside
grade_assignment) — now a clean 422.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_homework_lab.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_grade_rejects_null_answers():
    r = client.post("/api/homework/generate", json={
        "topic": "photosynthesis", "subject": "biology", "item_count": 2,
    })
    assert r.status_code == 200, r.text
    assignment = r.json()["assignment"]
    out = client.post("/api/homework/grade", json={
        "assignment": assignment, "answers": None,
    })
    assert out.status_code == 422
