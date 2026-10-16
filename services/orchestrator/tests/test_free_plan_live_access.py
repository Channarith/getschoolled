"""Direct live-room routes must enforce the free-plan group and AI gates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from orchestrator.main import _group_store, _live_rooms, app

client = TestClient(app)


def _iso(delta_minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).isoformat()


def _lesson() -> str:
    return client.get("/api/lessons").json()[0]["lesson_id"]


def _schedule() -> str:
    return client.post(
        "/api/group-classes",
        json={
            "title": "Free plan bypass",
            "lesson_id": _lesson(),
            "start_time": _iso(30),
            "platform": "salareen",
            "room_size": 6,
            "capacity": 5,
        },
    ).json()["id"]


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


def test_free_users_cannot_join_or_materialize_a_group_room(monkeypatch):
    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.profile_from_authorization",
        _profiles,
    )
    class_id = _schedule()
    room_id = f"class-{class_id}"

    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ada", "identity": "ada-free"},
        headers=_auth("free-active"),
    )
    assert joined.status_code == 403, joined.text
    assert "group classes" in joined.json()["detail"]
    assert _live_rooms().get(room_id) is None

    viewed = client.get(f"/api/live-rooms/{room_id}", headers=_auth("free-expired"))
    assert viewed.status_code == 403, viewed.text
    assert _live_rooms().get(room_id) is None

    ticked = client.post(f"/api/live-rooms/{room_id}/tick", headers=_auth("free-active"))
    assert ticked.status_code == 403, ticked.text
    assert _live_rooms().get(room_id) is None

    started = client.post(f"/api/group-classes/{class_id}/start", headers=_auth("free-active"))
    assert started.status_code == 403, started.text
    assert _group_store().get(class_id).status != "live"
    assert _live_rooms().get(room_id) is None

    registered = client.post(
        f"/api/group-classes/{class_id}/register",
        json={"name": "Ada", "email": "ada@example.com"},
        headers=_auth("free-expired"),
    )
    assert registered.status_code == 403, registered.text

    omitted = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Guest", "identity": "guest-1"},
    )
    assert omitted.status_code == 401, omitted.text
    assert _live_rooms().get(room_id) is None

    paid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Paid", "identity": "paid-1"},
        headers=_auth("paid"),
    )
    assert paid.status_code == 200, paid.text


def test_free_users_cannot_open_instant_or_paid_group_entry_points(monkeypatch):
    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.profile_from_authorization",
        _profiles,
    )
    created = client.post(
        "/api/live-rooms",
        json={"title": "Free instant", "creator_name": "Ada"},
        headers=_auth("free-active"),
    )
    assert created.status_code == 403, created.text

    guest_room = client.post(
        "/api/live-rooms",
        json={"title": "Guest instant", "creator_name": "Guest"},
    )
    assert guest_room.status_code == 401, guest_room.text
    paid_room = client.post(
        "/api/live-rooms",
        json={"title": "Paid instant", "creator_name": "Paid"},
        headers=_auth("paid"),
    )
    assert paid_room.status_code == 200, paid_room.text
    room_id = paid_room.json()["room"]["room_id"]
    blocked = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ada", "identity": "ada-instant"},
        headers=_auth("free-active"),
    )
    assert blocked.status_code == 403, blocked.text

    class_id = client.post(
        "/api/group-classes",
        json={
            "title": "Paid seat",
            "lesson_id": _lesson(),
            "start_time": _iso(40),
            "platform": "salareen",
            "price_per_user_usd": 12,
            "payment_required": True,
        },
    ).json()["id"]
    checkout = client.post(
        f"/api/group-classes/{class_id}/checkout",
        json={"name": "Ada", "email": "ada@example.com"},
        headers=_auth("free-expired"),
    )
    assert checkout.status_code == 403, checkout.text
    confirm = client.post(
        f"/api/group-classes/{class_id}/confirm-payment",
        json={"checkout_session_id": "cs_test"},
        headers=_auth("free-active"),
    )
    assert confirm.status_code == 403, confirm.text


def test_solo_room_blocks_expired_trials_and_active_free_ai_access(monkeypatch):
    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.profile_from_authorization",
        _profiles,
    )
    lesson_id = _lesson()
    expired = client.post(
        "/api/live-rooms/solo",
        json={"lesson_id": lesson_id},
        headers=_auth("free-expired"),
    )
    assert expired.status_code == 403, expired.text
    assert "14-day" in expired.json()["detail"]

    active = client.post(
        "/api/live-rooms/solo",
        json={"lesson_id": lesson_id},
        headers=_auth("free-active"),
    )
    assert active.status_code == 403, active.text
    assert "AI agents" in active.json()["detail"]

    guest = client.post("/api/live-rooms/solo", json={"lesson_id": lesson_id})
    assert guest.status_code == 401, guest.text
    paid_first = client.post(
        "/api/live-rooms/solo",
        json={"lesson_id": lesson_id},
        headers=_auth("paid"),
    )
    assert paid_first.status_code == 200, paid_first.text
    room_id = paid_first.json()["room_id"]
    rejoined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ada", "identity": "ada-solo"},
        headers=_auth("free-active"),
    )
    assert rejoined.status_code == 403, rejoined.text
    assert "AI agents" in rejoined.json()["detail"]

    paid = client.post(
        "/api/live-rooms/solo",
        json={"lesson_id": lesson_id},
        headers=_auth("paid"),
    )
    assert paid.status_code == 200, paid.text


_CLOSED_CASES = (
    ("omitted auth", None, 401),
    ("invalid auth", "invalid", 401),
    ("identity outage", "outage", 503),
    ("free user omits token", None, 401),
    ("nameless profile", "nameless", 401),
)


def _headers(kind: str | None) -> dict[str, str]:
    if not kind:
        return {}
    return _auth(kind)


def test_direct_paths_fail_closed_without_a_verified_paid_account(monkeypatch):
    """Omitted, invalid, unreadable, and dropped free-user tokens must not act."""
    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.profile_from_authorization",
        _profiles,
    )
    calls = {"session": 0, "checkout": 0, "status": 0, "token": 0}
    sessions = __import__("orchestrator.main", fromlist=["get_sessions"]).get_sessions()
    original_start = sessions.start_session

    def start_session(*args, **kwargs):
        calls["session"] += 1
        return original_start(*args, **kwargs)

    monkeypatch.setattr(sessions, "start_session", start_session)
    payment = client.app.state.factory.payment()
    media = client.app.state.factory.media()
    original_checkout = payment.create_checkout
    original_status = payment.get_checkout_status
    original_token = media.issue_token

    def create_checkout(**kwargs):
        calls["checkout"] += 1
        return original_checkout(**kwargs)

    def get_checkout_status(*args, **kwargs):
        calls["status"] += 1
        return original_status(*args, **kwargs)

    def issue_token(**kwargs):
        calls["token"] += 1
        return original_token(**kwargs)

    monkeypatch.setattr(payment, "create_checkout", create_checkout)
    monkeypatch.setattr(payment, "get_checkout_status", get_checkout_status)
    monkeypatch.setattr(media, "issue_token", issue_token)

    class_id = _schedule()
    room_id = f"class-{class_id}"
    lesson_id = _lesson()
    priced = client.post(
        "/api/group-classes",
        json={
            "title": "Closed checkout",
            "lesson_id": lesson_id,
            "start_time": _iso(50),
            "platform": "salareen",
            "price_per_user_usd": 12,
            "payment_required": True,
        },
    ).json()["id"]

    def assert_untouched(response, status: int, label: str) -> None:
        assert response.status_code == status, f"{label}: {response.text}"
        assert _live_rooms().get(room_id) is None
        assert _group_store().get(class_id).status != "live"
        assert _group_store().get(priced).registrations == [] or (
            len(_group_store().get(priced).registrations) == 0
        )
        assert calls == {"session": 0, "checkout": 0, "status": 0, "token": 0}

    for label, kind, status in _CLOSED_CASES:
        headers = _headers(kind)
        assert_untouched(
            client.post(
                f"/api/live-rooms/{room_id}/join",
                json={"name": "Ada", "identity": "ada"},
                headers=headers,
            ),
            status,
            f"join {label}",
        )
        assert_untouched(
            client.get(f"/api/live-rooms/{room_id}", headers=headers),
            status,
            f"materialize {label}",
        )
        assert_untouched(
            client.post(f"/api/live-rooms/{room_id}/tick", headers=headers),
            status,
            f"tick {label}",
        )
        assert_untouched(
            client.post(f"/api/group-classes/{class_id}/start", headers=headers),
            status,
            f"start {label}",
        )
        assert_untouched(
            client.post(
                "/api/live-rooms",
                json={"title": "Closed instant", "creator_name": "Ada"},
                headers=headers,
            ),
            status,
            f"create {label}",
        )
        assert_untouched(
            client.post(
                "/api/live-rooms/solo",
                json={"lesson_id": lesson_id},
                headers=headers,
            ),
            status,
            f"solo {label}",
        )
        assert_untouched(
            client.post(
                f"/api/group-classes/{priced}/checkout",
                json={"name": "Ada", "email": "ada@example.com"},
                headers=headers,
            ),
            status,
            f"checkout {label}",
        )
        assert_untouched(
            client.post(
                f"/api/group-classes/{priced}/confirm-payment",
                json={"checkout_session_id": "cs_closed"},
                headers=headers,
            ),
            status,
            f"payment {label}",
        )
        assert_untouched(
            client.post(
                f"/api/group-classes/{class_id}/register",
                json={"name": "Ada", "email": "ada@example.com"},
                headers=headers,
            ),
            status,
            f"register {label}",
        )

    paid_headers = _auth("paid")
    started = client.post(f"/api/group-classes/{class_id}/start", headers=paid_headers)
    assert started.status_code == 200, started.text
    assert calls["session"] == 1
    assert calls["token"] >= 1
    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Paid", "identity": "paid-1"},
        headers=paid_headers,
    )
    assert joined.status_code == 200, joined.text
    solo = client.post(
        "/api/live-rooms/solo",
        json={"lesson_id": lesson_id},
        headers=paid_headers,
    )
    assert solo.status_code == 200, solo.text
    checkout = client.post(
        f"/api/group-classes/{priced}/checkout",
        json={"name": "Paid", "email": "paid@example.com"},
        headers=paid_headers,
    )
    assert checkout.status_code == 200, checkout.text
    assert calls["checkout"] == 1
    confirm = client.post(
        f"/api/group-classes/{priced}/confirm-payment",
        json={"checkout_session_id": checkout.json()["checkout"]["session_id"]},
        headers=paid_headers,
    )
    assert confirm.status_code == 200, confirm.text
    assert calls["status"] == 1


def test_require_verified_profile_classifies_transport_failures(monkeypatch):
    import io
    import json
    from email.message import EmailMessage

    import urllib.error
    import urllib.request

    from aoep_shared.live_room_rewards import VerifiedIdentityError, require_verified_profile

    try:
        require_verified_profile("")
    except VerifiedIdentityError as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("missing token must be 401")

    def down(*_args, **_kwargs):
        raise urllib.error.URLError("identity down")

    monkeypatch.setattr(urllib.request, "urlopen", down)
    try:
        require_verified_profile("Bearer live-token")
    except VerifiedIdentityError as exc:
        assert exc.status_code == 503
        assert exc.detail == "identity service unavailable"
    else:
        raise AssertionError("identity outage must be 503")

    def rejected(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "http://identity/auth/me",
            401,
            "unauthorized",
            EmailMessage(),
            io.BytesIO(b""),
        )

    monkeypatch.setattr(urllib.request, "urlopen", rejected)
    try:
        require_verified_profile("Bearer live-token")
    except VerifiedIdentityError as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("rejected token must be 401")

    class _Body:
        def read(self):
            return json.dumps({"id": "paid-user", "tier": "premium"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: _Body())
    assert require_verified_profile("Bearer live-token")["id"] == "paid-user"
