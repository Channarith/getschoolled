"""Slang understanding: endpoint + Tutor integration."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_slang_normalize_endpoint():
    r = client.post(
        "/api/slang/normalize",
        json={"text": "this homework is a piece of cake", "language": "en"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "very easy" in body["plain"]
    assert any(d["phrase"] == "piece of cake" for d in body["detections"])


def test_tutor_understands_idiom_in_question():
    start = client.post(
        "/api/sessions",
        json={"lesson_id": "intro-to-photosynthesis", "class_type": "group"},
    ).json()
    sid = start["session"]["session_id"]
    ans = client.post(
        f"/api/sessions/{sid}/ask",
        json={"text": "is photosynthesis a piece of cake to understand?", "language": "en"},
    )
    assert ans.status_code == 200, ans.text
    body = ans.json()
    # The recognized idiom is surfaced back to the client.
    assert any("piece of cake" in g for g in body["understood"])
