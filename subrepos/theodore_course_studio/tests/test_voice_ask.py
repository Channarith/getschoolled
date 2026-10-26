"""POST /api/studio/voice/ask: every voice engine gets the same grounded text answers, capped and origin-checked."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from theodore_course_studio import voice_ask_routes as ask
from theodore_course_studio.main import app
from theodore_course_studio.voice_agent import VoiceTurn

SID = "otg-abcdef123456"
LESSON = "The Roman Empire. Augustus became the first emperor in 27 BC. Roads connected the provinces and carried trade and soldiers."


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def respond(self, **kw):
        self.calls.append(kw)
        return VoiceTurn(provider="fake", message="Augustus was the first emperor.", language_code=kw["language_code"],
                         language_name="English", fallback_used=False)


@pytest.fixture()
def client(monkeypatch):
    agent = FakeAgent()
    monkeypatch.setattr(ask, "_agent", lambda: agent)
    monkeypatch.setattr(ask, "_limiter", ask.AskLimiter(per_minute=3, per_session=5, per_ip_hour=50))
    c = TestClient(app)
    c.agent = agent
    return c


def body(**over):
    base = {"session_id": SID, "question": "Who was the first emperor?", "lesson_context": LESSON, "language": "en",
            "course_title": "The Roman Empire"}
    base.update(over)
    return base


def test_answers_from_the_lesson_text(client):
    r = client.post("/api/studio/voice/ask", json=body())
    assert r.status_code == 200
    out = r.json()
    assert out["answer"] == "Augustus was the first emperor."
    assert out["provider"] == "fake" and out["language"] == "en"
    call = client.agent.calls[0]
    assert call["session_id"] == f"ask:{SID}" and call["scope_to_course"] is True
    assert "Augustus became the first emperor" in call["lesson_context"] and call["lesson_context"].startswith("The Roman Empire")


def test_no_lesson_text_does_not_scope_to_a_course(client):
    client.post("/api/studio/voice/ask", json=body(lesson_context="", course_title=""))
    assert client.agent.calls[0]["scope_to_course"] is False


@pytest.mark.parametrize("over,code", [
    ({"session_id": "short"}, 422),
    ({"session_id": "bad id with spaces!!"}, 422),
    ({"question": "   "}, 422),
    ({"question": "x" * 501}, 422),
])
def test_validation(client, over, code):
    assert client.post("/api/studio/voice/ask", json=body(**over)).status_code == code
    assert client.agent.calls == []


def test_context_is_bounded_and_cleaned():
    text = ask.clean_context("T" * 500, "a\x00b\n\n\n\nc" + "z" * 20000)
    assert len(text) <= ask.MAX_CONTEXT_CHARS + ask.MAX_TITLE_CHARS + 2
    assert "\x00" not in text and "\n\n\n" not in text


def test_another_sites_page_is_refused(client):
    r = client.post("/api/studio/voice/ask", json=body(), headers={"origin": "https://evil.example", "host": "salareen.com"})
    assert r.status_code == 403 and client.agent.calls == []


def test_same_site_origin_is_allowed(client):
    r = client.post("/api/studio/voice/ask", json=body(), headers={"origin": "https://salareen.com", "host": "salareen.com"})
    assert r.status_code == 200


def test_rate_cap_per_minute_then_retry_after(client):
    for _ in range(3):
        assert client.post("/api/studio/voice/ask", json=body()).status_code == 200
    r = client.post("/api/studio/voice/ask", json=body())
    assert r.status_code == 429
    assert r.json()["detail"]["reason"] == "rate" and int(r.headers["Retry-After"]) >= 1
    assert len(client.agent.calls) == 3


def test_session_cap_and_other_sessions_unaffected():
    now = [0.0]
    lim = ask.AskLimiter(per_minute=100, per_session=3, per_ip_hour=1000, clock=lambda: now[0])
    for _ in range(3):
        assert lim.check("sess-aaaaaaaa", "1.1.1.1")[0]
    ok, reason, retry = lim.check("sess-aaaaaaaa", "1.1.1.1")
    assert (ok, reason) == (False, "session") and retry > 0
    assert lim.check("sess-bbbbbbbb", "1.1.1.1")[0]
    now[0] = 3601.0
    assert lim.check("sess-aaaaaaaa", "1.1.1.1")[0]


def test_address_cap_stops_a_flood_of_made_up_sessions():
    lim = ask.AskLimiter(per_minute=100, per_session=100, per_ip_hour=4)
    results = [lim.check(f"sess-{i:08d}", "9.9.9.9")[0] for i in range(6)]
    assert results == [True, True, True, True, False, False]


def test_limiter_memory_is_bounded():
    lim = ask.AskLimiter(max_keys=50)
    for i in range(500):
        lim.check(f"sess-{i:08d}", f"10.0.{i % 200}.{i % 250}")
    assert len(lim._sessions) <= 50 and len(lim._ips) <= 50
