"""POST /api/studio/voice/ask: every voice engine gets the same grounded text answers, behind server-issued sessions and layered caps."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from theodore_course_studio import voice_ask_guard as vg
from theodore_course_studio import voice_ask_routes as ask
from theodore_course_studio.main import app
from theodore_course_studio.voice_agent import VoiceTurn

SAME = {"origin": "https://salareen.com", "host": "salareen.com", "x-forwarded-for": "203.0.113.7"}
LESSON = "The Roman Empire. Augustus became the first emperor in 27 BC. Roads connected the provinces and carried trade and soldiers."
START = 1_700_000_000.0


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.message = "Augustus was the first emperor."

    def respond(self, **kw):
        self.calls.append(kw)
        return VoiceTurn(provider="fake", message=self.message, language_code=kw["language_code"],
                         language_name="English", fallback_used=False)


def no_redis():
    raise RuntimeError("no redis in tests")


@pytest.fixture()
def client(monkeypatch):
    agent = FakeAgent()
    now = [START]
    monkeypatch.setattr(ask, "_agent", lambda: agent)
    monkeypatch.setattr(ask, "_limiter", ask.AskLimiter(per_minute=3, per_session=5, per_ip_hour=50, clock=lambda: now[0]))
    ask.set_guard(vg.Guard(clock=lambda: now[0], wall=lambda: now[0], daily_budget=100, redis_factory=no_redis))
    monkeypatch.setattr(ask, "verified_caller", lambda auth, **kw: None)
    monkeypatch.delenv("VOICE_ASK_APP_KEY", raising=False)
    c = TestClient(app, headers=SAME)
    c.agent, c.now = agent, now
    yield c
    ask.set_guard(vg.Guard(redis_factory=no_redis))


def session(c, headers=None):
    r = c.post("/api/studio/voice/session", headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()["session"]


def body(token, **over):
    base = {"session_id": token, "question": "Who was the first emperor?", "lesson_context": LESSON, "language": "en",
            "course_title": "The Roman Empire"}
    base.update(over)
    return base


def test_answers_from_the_lesson_text(client):
    token = session(client)
    r = client.post("/api/studio/voice/ask", json=body(token))
    assert r.status_code == 200
    out = r.json()
    assert out["answer"] == "Augustus was the first emperor."
    assert out["provider"] == "fake" and out["language"] == "en"
    call = client.agent.calls[0]
    sid = vg.verify_token(token, now=lambda: START)[0].session_id
    assert call["session_id"] == f"ask:{sid}" and call["scope_to_course"] is True
    assert "Augustus became the first emperor" in call["lesson_context"] and call["lesson_context"].startswith("The Roman Empire")


def test_no_lesson_text_does_not_scope_to_a_course(client):
    client.post("/api/studio/voice/ask", json=body(session(client), lesson_context="", course_title=""))
    assert client.agent.calls[0]["scope_to_course"] is False


@pytest.mark.parametrize("over,code", [({"question": "   "}, 422), ({"question": "x" * 501}, 422)])
def test_validation(client, over, code):
    assert client.post("/api/studio/voice/ask", json=body(session(client), **over)).status_code == code
    assert client.agent.calls == []


def test_context_is_bounded_and_cleaned():
    text = ask.clean_context("T" * 500, "a\x00b\n\n\n\nc" + "z" * 20000)
    assert len(text) <= ask.MAX_CONTEXT_CHARS + ask.MAX_TITLE_CHARS + 2
    assert "\x00" not in text and "\n\n\n" not in text


def test_the_answer_is_length_bounded(client):
    client.agent.message = "word " * 2000
    out = client.post("/api/studio/voice/ask", json=body(session(client))).json()
    assert len(out["answer"]) <= ask.MAX_ANSWER_CHARS


# ---- the hole that was found: a client-made session id used to be enough -------------------------------------------------------

@pytest.mark.parametrize("fake", ["probe-12345678", "s" + "0" * 24, "short", "bad id with spaces!!", "", "va1.AAAA.BBBB"])
def test_a_client_made_session_id_is_refused(client, fake):
    r = client.post("/api/studio/voice/ask", json=body(fake))
    assert r.status_code in (401, 422) and client.agent.calls == []


def test_a_tampered_token_is_refused(client):
    token = session(client)
    prefix, payload, sig = token.split(".")
    flipped = f"{prefix}.{payload}.{'0' * 64 if sig != '0' * 64 else '1' * 64}"
    assert client.post("/api/studio/voice/ask", json=body(flipped)).status_code == 401
    # a payload edit (e.g. claiming an account or a later expiry) breaks the signature
    import base64, json
    doc = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    doc["a"] = "acct-admin"
    forged = base64.urlsafe_b64encode(json.dumps(doc, separators=(",", ":")).encode()).decode().rstrip("=")
    assert client.post("/api/studio/voice/ask", json=body(f"{prefix}.{forged}.{sig}")).status_code == 401
    assert client.agent.calls == []


def test_a_token_signed_with_another_key_is_refused(client, monkeypatch):
    token = session(client)
    monkeypatch.setenv("VOICE_ASK_SIGNING_KEY", "a-different-secret")
    r = client.post("/api/studio/voice/ask", json=body(token))
    assert r.status_code == 401 and r.json()["detail"]["reason"] == "forged"


def test_an_anonymous_session_expires_with_the_sample_window(client):
    token = session(client)
    assert client.post("/api/studio/voice/ask", json=body(token)).status_code == 200
    client.now[0] += (vg.sample_minutes() + 2) * 60 + 1
    r = client.post("/api/studio/voice/ask", json=body(token))
    assert r.status_code == 401 and r.json()["detail"]["reason"] == "expired"
    assert client.post("/api/studio/voice/ask", json=body(session(client))).status_code == 200   # a fresh session works again


# ---- who may call --------------------------------------------------------------------------------------------------------------

def test_another_sites_page_is_refused_on_both_routes(client):
    other = {"origin": "https://evil.example", "host": "salareen.com"}
    assert client.post("/api/studio/voice/session", headers=other).status_code == 403
    token = session(client)
    assert client.post("/api/studio/voice/ask", json=body(token), headers=other).status_code == 403
    assert client.agent.calls == []


def test_a_script_without_origin_is_refused_but_a_browser_fetch_metadata_is_ok(client):
    bare = {"origin": "", "host": "salareen.com"}
    assert client.post("/api/studio/voice/session", headers=bare).status_code == 403
    token = session(client)
    assert client.post("/api/studio/voice/ask", json=body(token), headers=bare).status_code == 403
    fetchy = {"origin": "", "host": "salareen.com", "sec-fetch-site": "same-origin"}
    assert client.post("/api/studio/voice/ask", json=body(token), headers=fetchy).status_code == 200


def test_the_native_app_header_stands_in_for_the_origin_only_when_configured(client, monkeypatch):
    bare = {"origin": "", "host": "salareen.com", "x-salareen-app": "app-key-1"}
    assert client.post("/api/studio/voice/session", headers=bare).status_code == 403          # no key configured: no exception
    monkeypatch.setenv("VOICE_ASK_APP_KEY", "app-key-1")
    assert client.post("/api/studio/voice/session", headers=bare).status_code == 200
    assert client.post("/api/studio/voice/session", headers={**bare, "x-salareen-app": "wrong"}).status_code == 403


# ---- the caps that do not depend on any client-chosen value --------------------------------------------------------------------

def test_rotating_to_new_sessions_cannot_bypass_the_address_cap(client, monkeypatch):
    monkeypatch.setattr(ask, "_limiter", ask.AskLimiter(per_minute=100, per_session=100, per_ip_hour=4, clock=lambda: client.now[0]))
    codes = [client.post("/api/studio/voice/ask", json=body(session(client))).status_code for _ in range(6)]
    assert codes == [200, 200, 200, 200, 429, 429]
    assert len(client.agent.calls) == 4


def test_session_issuance_is_limited_per_address(client):
    client.app_guard = ask.guard()
    ask.guard().issue_per_ip_hour = 3
    ask.guard().anon_per_ip_day = 100
    codes = [client.post("/api/studio/voice/session").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    r = client.post("/api/studio/voice/session")
    assert r.json()["detail"]["reason"] == "issue" and int(r.headers["Retry-After"]) >= 1
    # another address is unaffected
    assert client.post("/api/studio/voice/session", headers={"x-forwarded-for": "198.51.100.9"}).status_code == 200


def test_anonymous_issuance_has_a_daily_ceiling_per_address(client):
    ask.guard().issue_per_ip_hour = 100
    ask.guard().anon_per_ip_day = 2
    assert [client.post("/api/studio/voice/session").status_code for _ in range(3)] == [200, 200, 429]
    client.now[0] += 86401
    assert client.post("/api/studio/voice/session").status_code == 200


def test_rate_cap_per_minute_then_retry_after(client):
    token = session(client)
    for _ in range(3):
        assert client.post("/api/studio/voice/ask", json=body(token)).status_code == 200
    r = client.post("/api/studio/voice/ask", json=body(token))
    assert r.status_code == 429
    assert r.json()["detail"]["reason"] == "rate" and int(r.headers["Retry-After"]) >= 1
    assert len(client.agent.calls) == 3


def test_global_daily_budget_stops_every_caller_then_resets(client):
    ask.set_guard(vg.Guard(clock=lambda: client.now[0], wall=lambda: client.now[0], daily_budget=2, redis_factory=no_redis))
    codes = [client.post("/api/studio/voice/ask", json=body(session(client, {"x-forwarded-for": f"198.51.100.{i}"})),
                         headers={"x-forwarded-for": f"198.51.100.{i}"}).status_code for i in range(4)]
    assert codes == [200, 200, 429, 429]
    r = client.post("/api/studio/voice/ask", json=body(session(client)))
    assert r.status_code == 429 and r.json()["detail"]["reason"] == "budget" and int(r.headers["Retry-After"]) >= 60
    client.now[0] += 86400
    assert client.post("/api/studio/voice/ask", json=body(session(client))).status_code == 200


def test_a_denied_ask_does_not_spend_the_budget(client):
    ask.set_guard(vg.Guard(clock=lambda: client.now[0], wall=lambda: client.now[0], daily_budget=3, redis_factory=no_redis))
    token = session(client)
    for _ in range(3):
        client.post("/api/studio/voice/ask", json=body(token))          # the per-minute cap (3) is reached by the third
    for _ in range(5):
        assert client.post("/api/studio/voice/ask", json=body(token)).status_code == 429
    assert len(client.agent.calls) == 3
    assert ask.guard().budget._mem[next(iter(ask.guard().budget._mem))] == 3   # only the three answered asks were counted


def test_signed_in_session_is_bound_to_the_verified_account(client, monkeypatch):
    monkeypatch.setattr(ask, "verified_caller", lambda auth, **kw: {"id": "acct-77"} if auth == "Bearer good" else None)
    r = client.post("/api/studio/voice/session", headers={"authorization": "Bearer good"})
    out = r.json()
    assert r.status_code == 200 and out["signed_in"] is True and out["expires_in"] > (vg.sample_minutes() + 2) * 60
    assert vg.verify_token(out["session"], now=lambda: START)[0].account == "acct-77"
    bad = client.post("/api/studio/voice/session", headers={"authorization": "Bearer nope"}).json()
    assert bad["signed_in"] is False   # an unverifiable login is just an anonymous session, never an error or a free upgrade


def test_per_account_cap_holds_across_sessions(client, monkeypatch):
    monkeypatch.setattr(ask, "verified_caller", lambda auth, **kw: {"id": "acct-77"})
    monkeypatch.setattr(ask, "_limiter", ask.AskLimiter(per_minute=100, per_session=100, per_ip_hour=1000, clock=lambda: client.now[0]))
    ask.guard().per_account_hour = 3
    auth = {"authorization": "Bearer good"}
    codes = [client.post("/api/studio/voice/ask", json=body(session(client, auth))).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    r = client.post("/api/studio/voice/ask", json=body(session(client, auth)))
    assert r.json()["detail"]["reason"] == "account"


# ---- the pieces ----------------------------------------------------------------------------------------------------------------

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


def test_limiter_memory_is_bounded():
    lim = ask.AskLimiter(max_keys=50)
    for i in range(500):
        lim.check(f"sess-{i:08d}", f"10.0.{i % 200}.{i % 250}")
    assert len(lim._sessions) <= 50 and len(lim._ips) <= 50
    counter = vg.SlidingCounter(max_keys=20)
    for i in range(300):
        counter.allow(f"k{i}", 5, 60)
    assert len(counter._data) <= 20


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, int] = {}
        self.expires: dict[str, int] = {}

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def decr(self, key):
        self.data[key] -= 1

    def expire(self, key, seconds):
        self.expires[key] = seconds


def test_daily_budget_uses_redis_when_present_and_sets_an_expiry():
    fake = FakeRedis()
    budget = vg.DailyBudget(2, redis_factory=lambda: fake, clock=lambda: START)
    assert [budget.take()[0] for _ in range(4)] == [True, True, False, False]
    key = next(iter(fake.data))
    assert key.startswith("voice-ask:budget:") and fake.expires[key] == 2 * 86400 and fake.data[key] == 2


def test_daily_budget_falls_back_to_memory_when_redis_fails():
    class Broken(FakeRedis):
        def incr(self, key):
            raise ConnectionError("down")

    budget = vg.DailyBudget(2, redis_factory=lambda: Broken(), clock=lambda: START)
    assert [budget.take()[0] for _ in range(3)] == [True, True, False]   # never an open door


def test_token_round_trip_and_the_log_label_hides_the_address():
    token, sess = vg.issue_token("acct-1", now=lambda: START)
    got, why = vg.verify_token(token, now=lambda: START + 10)
    assert why == "" and got == sess and got.account == "acct-1"
    assert vg.verify_token(token, now=lambda: START + 10_000_000)[1] == "expired"
    assert "203.0.113.7" not in vg.ip_label("203.0.113.7") and len(vg.ip_label("203.0.113.7")) == 8
