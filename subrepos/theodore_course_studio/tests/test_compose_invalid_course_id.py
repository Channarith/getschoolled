"""A client-supplied course_id that cannot be stored is a 422, not a 500."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_course_studio.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_compose_with_unstorable_course_id_is_422():
    for bad in ("x\x00y", "../escape", "a/b"):
        r = client.post("/api/studio/courses/compose", json={"title": "t", "course_id": bad})
        assert r.status_code == 422, bad
        assert "invalid course_id" in r.json()["detail"]


def test_compose_without_course_id_still_works():
    r = client.post("/api/studio/courses/compose", json={"title": "t"})
    assert r.status_code == 200
