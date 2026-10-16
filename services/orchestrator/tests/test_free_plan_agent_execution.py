"""Free plans cannot execute tutor, training, cognitive, or meeting agents.

Anonymous callers may still open a non-AI sample lesson. A presented Bearer
token is never treated as that guest: identity rejection is 401 and an
unreadable identity service is 503.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from orchestrator.curriculum import Lesson, Slide
from orchestrator.main import app, get_sessions

client = TestClient(app)

_EXECUTION = (
    ("post", "/api/sessions/{sid}/ask", {"text": "What is a fraction?"}),
    ("post", "/api/sessions/{sid}/ask/stream", {"text": "What is a fraction?"}),
    ("post", "/api/training/sessions", {"scenario_id": "medical_triage_quick"}),
    ("get", "/api/training/sessions/not-a-session", None),
    ("post", "/api/training/sessions/not-a-session/tick", None),
    ("post", "/api/training/sessions/not-a-session/respond", {"text": "I would triage first."}),
    ("post", "/api/cognitive/check-in", {"learner_id": "ada", "stress_level": 3, "focus_level": 8}),
    ("get", "/api/cognitive/recommend/ada", None),
    ("get", "/api/cognitive/summary/ada", None),
    ("post", "/api/cognitive/critical-thinking/question", {
        "learner_id": "ada", "term": "fraction", "passage": "A fraction is a part of a whole.",
    }),
    ("post", "/api/cognitive/critical-thinking/evaluate", {
        "learner_id": "ada",
        "question_id": "q1",
        "question_text": "Why?",
        "bloom_level": "understand",
        "learner_answer": "because it is a part",
    }),
    ("post", "/api/cognitive/situational/ooda-prompt", {"learner_id": "ada", "scenario_id": "missing"}),
    ("post", "/api/cognitive/rapid-decision/evaluate", {
        "learner_id": "ada",
        "drill_id": "missing",
        "chosen_label": "stop",
        "time_taken_s": 1.0,
    }),
    ("post", "/api/cognitive/emergency/start", {"learner_id": "ada", "scenario_id": "missing"}),
    ("post", "/api/cognitive/emergency/action", {
        "learner_id": "ada",
        "scenario_id": "missing",
        "phase_id": "p1",
        "action_id": "a1",
    }),
    ("post", "/api/cognitive/mental-readiness/pre-mortem", {
        "learner_id": "ada",
        "plan_description": "Cross the street.",
        "failure_modes": ["traffic"],
    }),
    ("post", "/api/cognitive/mental-readiness/rehearsal", {
        "learner_id": "ada",
        "rehearsal_key": "breath",
    }),
    ("post", "/api/cognitive/mental-readiness/tem", {
        "learner_id": "ada",
        "scenario_description": "A busy crossing.",
        "learner_threats": ["speed"],
    }),
    ("post", "/classes", {"title": "Meeting bypass", "class_type": "group"}),
    ("get", "/classes/room-1/join?identity=stu-1", None),
)


def _profiles(authorization="", **kwargs):
    auth = str(authorization or "")
    if "outage" in auth:
        raise RuntimeError("identity down")
    if "nameless" in auth:
        return {"tier": "premium"}
    if "free-active" in auth:
        return {"id": "free-active", "tier": "free", "free_plan": {"active": True}}
    if "free-expired" in auth:
        return {"id": "free-expired", "tier": "free", "free_plan": {"active": False}}
    if "paid" in auth:
        return {"id": "paid-user", "tier": "premium", "free_plan": {"active": False}}
    return None


def _auth(kind: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {kind}"}


def _lesson() -> str:
    return client.get("/api/lessons").json()[0]["lesson_id"]


def _install(monkeypatch) -> None:
    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.profile_from_authorization",
        _profiles,
    )


def _register(lesson_id: str, language: str) -> str:
    sessions = get_sessions()
    if sessions.curriculum.get(lesson_id) is None:
        sessions.curriculum.register_lesson(
            lesson_id,
            Lesson(
                lesson_id=lesson_id,
                title=lesson_id,
                language=language,
                slides=[Slide(index=0, title="Page", body="Body text", narration="Narration")],
            ),
            ["Page: body text"],
        )
    return lesson_id


def _start(lesson_id: str, headers: dict | None = None, **extra):
    body = {"lesson_id": lesson_id, "class_type": "solo", **extra}
    return client.post("/api/sessions", json=body, headers=headers or {})


def _watch_start(monkeypatch):
    sessions = get_sessions()
    calls = {"n": 0}
    original = sessions.start_session

    def wrapped(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(sessions, "start_session", wrapped)
    return calls


def test_session_start_fails_closed_and_keeps_english_self_study(monkeypatch):
    _install(monkeypatch)
    calls = _watch_start(monkeypatch)
    english = _lesson()
    spanish = _register("free-plan-es", "es")
    variety = _register("free-plan-en-us", "en-US")
    blank = _register("free-plan-blank-lang", "")

    guest = _start(english)
    assert guest.status_code == 200, guest.text
    guest_sid = guest.json()["session"]["session_id"]
    assert client.post(f"/api/sessions/{guest_sid}/advance").status_code == 200

    missing_spanish = _start(spanish)
    assert missing_spanish.status_code == 200, missing_spanish.text

    active = _start(english, _auth("free-active"))
    assert active.status_code == 200, active.text
    active_sid = active.json()["session"]["session_id"]
    assert client.post(f"/api/sessions/{active_sid}/advance").status_code == 200
    grouped = client.post(
        "/api/sessions",
        json={"lesson_id": english, "class_type": "group"},
        headers=_auth("free-active"),
    )
    assert grouped.status_code == 200, grouped.text
    assert _start(variety, _auth("free-active")).status_code == 200

    before = calls["n"]
    denied = _start(spanish, _auth("free-active"))
    assert denied.status_code == 403, denied.text
    assert "English" in denied.json()["detail"]
    assert calls["n"] == before
    spoofed = client.post(
        "/api/sessions?language=en",
        json={"lesson_id": spanish, "class_type": "solo"},
        headers=_auth("free-active"),
    )
    assert spoofed.status_code == 403, spoofed.text
    assert calls["n"] == before
    extra = client.post(
        "/api/sessions",
        json={"lesson_id": spanish, "class_type": "solo", "language": "en"},
        headers=_auth("free-active"),
    )
    assert extra.status_code == 422, extra.text
    assert _start(blank, _auth("free-active")).status_code == 403

    expired = _start(english, _auth("free-expired"))
    assert expired.status_code == 403, expired.text
    assert "14-day" in expired.json()["detail"]
    assert calls["n"] == before

    invalid = _start(english, _auth("invalid"))
    assert invalid.status_code == 401, invalid.text
    assert calls["n"] == before
    nameless = _start(english, _auth("nameless"))
    assert nameless.status_code == 401, nameless.text

    outage = _start(english, _auth("outage"))
    assert outage.status_code == 503, outage.text
    assert outage.json()["detail"] == "identity service unavailable"
    assert calls["n"] == before

    paid = _start(spanish, _auth("paid"))
    assert paid.status_code == 200, paid.text


def test_tutor_ask_and_stream_block_free_and_anonymous_callers(monkeypatch):
    _install(monkeypatch)
    sessions = get_sessions()
    asked = {"n": 0, "stream": 0}
    original = sessions.ask
    original_stream = sessions.ask_stream

    def wrapped(*args, **kwargs):
        asked["n"] += 1
        return original(*args, **kwargs)

    def wrapped_stream(*args, **kwargs):
        asked["stream"] += 1
        return original_stream(*args, **kwargs)

    monkeypatch.setattr(sessions, "ask", wrapped)
    monkeypatch.setattr(sessions, "ask_stream", wrapped_stream)

    started = _start(_lesson(), _auth("free-active"))
    assert started.status_code == 200, started.text
    sid = started.json()["session"]["session_id"]
    ask = client.post(
        f"/api/sessions/{sid}/ask",
        json={"text": "What is a fraction?", "language": "en"},
        headers=_auth("free-active"),
    )
    assert ask.status_code == 403, ask.text
    assert "AI agents" in ask.json()["detail"]
    streamed = client.post(
        f"/api/sessions/{sid}/ask/stream",
        json={"text": "What is a fraction?"},
        headers=_auth("free-active"),
    )
    assert streamed.status_code == 403, streamed.text
    assert asked == {"n": 0, "stream": 0}

    expired = client.post(
        f"/api/sessions/{sid}/ask",
        json={"text": "What is a fraction?"},
        headers=_auth("free-expired"),
    )
    assert expired.status_code == 403, expired.text
    for kind, status in (("invalid", 401), ("nameless", 401), ("outage", 503)):
        response = client.post(
            f"/api/sessions/{sid}/ask",
            json={"text": "What is a fraction?"},
            headers=_auth(kind),
        )
        assert response.status_code == status, f"{kind}: {response.text}"
        streamed = client.post(
            f"/api/sessions/{sid}/ask/stream",
            json={"text": "What is a fraction?"},
            headers=_auth(kind),
        )
        assert streamed.status_code == status, f"stream {kind}: {streamed.text}"
    omitted = client.post(f"/api/sessions/{sid}/ask", json={"text": "What is a fraction?"})
    assert omitted.status_code == 401, omitted.text
    omitted_stream = client.post(
        f"/api/sessions/{sid}/ask/stream",
        json={"text": "What is a fraction?"},
    )
    assert omitted_stream.status_code == 401, omitted_stream.text
    assert asked == {"n": 0, "stream": 0}

    # Related AI start path: the solo live room is the tutor, not self-study.
    solo = client.post(
        "/api/live-rooms/solo",
        json={"lesson_id": _lesson()},
        headers=_auth("free-active"),
    )
    assert solo.status_code == 403, solo.text
    solo_outage = client.post(
        "/api/live-rooms/solo",
        json={"lesson_id": _lesson()},
        headers=_auth("outage"),
    )
    assert solo_outage.status_code == 503, solo_outage.text

    paid = client.post(
        f"/api/sessions/{sid}/ask",
        json={"text": "What is a fraction?"},
        headers=_auth("paid"),
    )
    assert paid.status_code == 200, paid.text
    assert asked["n"] == 1
    paid_stream = client.post(
        f"/api/sessions/{sid}/ask/stream",
        json={"text": "explain this slide"},
        headers=_auth("paid"),
    )
    assert paid_stream.status_code == 200, paid_stream.text
    assert paid_stream.headers["content-type"].startswith("text/event-stream")
    assert asked["stream"] == 1


def test_agent_execution_endpoints_require_a_paid_profile(monkeypatch):
    _install(monkeypatch)
    import orchestrator.main as main

    created = {"training": 0, "cognitive": 0}
    original_training = main.create_training_session
    original_check = main._cognitive_trainer.check_in

    def training_session(*args, **kwargs):
        created["training"] += 1
        return original_training(*args, **kwargs)

    def check_in(*args, **kwargs):
        created["cognitive"] += 1
        return original_check(*args, **kwargs)

    monkeypatch.setattr(main, "create_training_session", training_session)
    monkeypatch.setattr(main._cognitive_trainer, "check_in", check_in)
    guest = _start(_lesson())
    assert guest.status_code == 200, guest.text
    sid = guest.json()["session"]["session_id"]

    def hit(method: str, path: str, body, headers: dict | None):
        url = path.format(sid=sid)
        if method == "get":
            return client.get(url, headers=headers or {})
        return client.post(url, json=body, headers=headers or {})

    cases = (
        ("free-active", 403, _auth("free-active")),
        ("free-expired", 403, _auth("free-expired")),
        ("invalid", 401, _auth("invalid")),
        ("outage", 503, _auth("outage")),
        ("omitted", 401, None),
    )
    for kind, status, headers in cases:
        for method, path, body in _EXECUTION:
            response = hit(method, path, body, headers)
            assert response.status_code == status, f"{kind} {method} {path}: {response.text}"
    assert created == {"training": 0, "cognitive": 0}

    # Read-only roster, training, and cognitive catalogs stay public.
    for path in (
        "/api/agents/roster",
        "/api/training/catalog",
        "/api/training/capabilities",
        "/api/training/scenarios?limit=1",
        "/api/cognitive/situational/scenarios",
        "/api/cognitive/rapid-decision/drills",
        "/api/cognitive/emergency/scenarios",
    ):
        opened = client.get(path, headers=_auth("free-active"))
        assert opened.status_code == 200, f"{path}: {opened.text}"
        anonymous = client.get(path)
        assert anonymous.status_code == 200, f"anon {path}: {anonymous.text}"

    paid_training = client.post(
        "/api/training/sessions",
        json={"scenario_id": "medical_triage_quick"},
        headers=_auth("paid"),
    )
    assert paid_training.status_code == 200, paid_training.text
    assert created["training"] == 1
    paid_cognitive = client.post(
        "/api/cognitive/check-in",
        json={"learner_id": "ada", "stress_level": 3, "focus_level": 8},
        headers=_auth("paid"),
    )
    assert paid_cognitive.status_code == 200, paid_cognitive.text
    assert created["cognitive"] == 1
    paid_class = client.post(
        "/classes",
        json={"title": "Paid meeting", "class_type": "group"},
        headers=_auth("paid"),
    )
    assert paid_class.status_code == 200, paid_class.text
    room = paid_class.json()["room"]
    joined = client.get(
        f"/classes/{room}/join",
        params={"identity": "stu-paid"},
        headers=_auth("paid"),
    )
    assert joined.status_code == 200, joined.text


def test_meeting_requests_do_not_open_for_free_or_during_outage(monkeypatch):
    _install(monkeypatch)
    from orchestrator.main import _group_store

    before = len(_group_store().list(upcoming_only=False))
    body = {
        "title": "Free host",
        "lesson_id": _lesson(),
        "start_time": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        "credentials_summary": "A certificate",
    }
    requested = client.post(
        "/api/group-classes/teach-request",
        json=body,
        headers=_auth("free-active"),
    )
    assert requested.status_code == 403, requested.text
    assert "group classes" in requested.json()["detail"]
    outage = client.post(
        "/api/group-classes/teach-request",
        json=body,
        headers=_auth("outage"),
    )
    assert outage.status_code == 503, outage.text
    missing = client.post("/api/group-classes/teach-request", json=body)
    assert missing.status_code == 401, missing.text
    assert len(_group_store().list(upcoming_only=False)) == before

    uploaded = client.post(
        "/api/group-classes/upload-presentation",
        files={"file": ("deck.pdf", b"%PDF-not-really", "application/pdf")},
        data={"title": "Labeled English", "language": "en"},
        headers=_auth("free-active"),
    )
    assert uploaded.status_code == 403, uploaded.text
    upload_outage = client.post(
        "/api/group-classes/upload-presentation",
        files={"file": ("deck.pdf", b"%PDF-not-really", "application/pdf")},
        data={"language": "en"},
        headers=_auth("outage"),
    )
    assert upload_outage.status_code == 503, upload_outage.text
