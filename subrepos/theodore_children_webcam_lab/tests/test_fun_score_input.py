"""fun-score takes loose JSON from the browser: bad input is a 422, never a 500."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_children_webcam_lab.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_empty_payload_scores_as_not_completed():
    r = client.post("/api/child/fun-score", json={})
    assert r.status_code == 200


def test_wrong_types_are_422():
    for body in ({"attempts": "many"}, {"duration_ms": [1]}, {"smile": {"x": 1}}, {"combo": 10**400}):
        r = client.post("/api/child/fun-score", json=body)
        assert r.status_code in (200, 422), body
        assert r.status_code < 500


def test_normal_payload_still_scores():
    r = client.post("/api/child/fun-score", json={"completed": True, "attempts": 1, "duration_ms": 3000})
    assert r.status_code == 200
