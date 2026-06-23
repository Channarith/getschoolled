"""Phases 7-9 - real bridge engine: meeting parsing, Zoom auth, session lifecycle.

These exercise the platform-agnostic bridge implementation end-to-end with an
in-memory FakeTransport (the SDK stand-in), so the join -> bridge -> leave
orchestration, track wiring, chat routing, and disclosures are all verified
without any vendor SDK.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from aoep_shared.bridges import (
    BridgePlatform,
    BridgeSession,
    BridgeState,
    BridgeUnavailable,
    Direction,
    FakeTransport,
    TrackKind,
    get_bridge,
    parse_meeting_ref,
    zoom_sdk_signature,
)


# --- meeting-ref parsing --------------------------------------------------- #
def test_parse_zoom_url_with_passcode():
    ref = parse_meeting_ref(BridgePlatform.ZOOM, "https://us05web.zoom.us/j/87654321012?pwd=AbC123")
    assert ref.meeting_id == "87654321012"
    assert ref.passcode == "AbC123"


def test_parse_zoom_bare_number_with_spaces():
    ref = parse_meeting_ref(BridgePlatform.ZOOM, "876 5432 1012")
    assert ref.meeting_id == "87654321012"


def test_parse_teams_url_extracts_thread_and_tenant():
    ctx = json.dumps({"Tid": "tenant-abc", "Oid": "org-1"})
    from urllib.parse import quote

    url = (
        "https://teams.microsoft.com/l/meetup-join/"
        + quote("19:meeting_NWE4@thread.v2", safe="")
        + "/0?context=" + quote(ctx)
    )
    ref = parse_meeting_ref(BridgePlatform.TEAMS, url)
    assert ref.meeting_id == "19:meeting_NWE4@thread.v2"
    assert ref.tenant_id == "tenant-abc"


def test_parse_meet_code():
    ref = parse_meeting_ref(BridgePlatform.MEET, "https://meet.google.com/abc-defg-hij")
    assert ref.meeting_id == "abc-defg-hij"


def test_parse_bad_ref_raises():
    with pytest.raises(ValueError):
        parse_meeting_ref(BridgePlatform.ZOOM, "not-a-meeting")
    with pytest.raises(ValueError):
        parse_meeting_ref(BridgePlatform.MEET, "https://example.com/foo")


# --- Zoom SDK signature ---------------------------------------------------- #
def test_zoom_signature_is_valid_jwt_with_expected_claims():
    sig = zoom_sdk_signature("KEY", "SECRET", "87654321012", role=1, now=1_000_000, expires_in=7200)
    header_b64, payload_b64, signature_b64 = sig.split(".")

    def _decode(seg: str) -> dict:
        return json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))

    assert _decode(header_b64) == {"alg": "HS256", "typ": "JWT"}
    payload = _decode(payload_b64)
    assert payload["sdkKey"] == "KEY" and payload["appKey"] == "KEY"
    assert payload["mn"] == "87654321012" and payload["role"] == 1
    assert payload["iat"] == 1_000_000 and payload["exp"] == 1_007_200

    expected = hmac.new(b"SECRET", f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64encode(expected).rstrip(b"=").decode() == signature_b64


def test_zoom_signature_requires_credentials():
    with pytest.raises(ValueError):
        zoom_sdk_signature("", "secret", "123")


# --- session lifecycle (FakeTransport) ------------------------------------- #
def test_zoom_bridge_full_lifecycle_with_fake_transport():
    fake = FakeTransport()
    routed = []
    session = get_bridge(BridgePlatform.ZOOM).connect(
        "https://zoom.us/j/87654321012",
        livekit_room="class-1",
        room_url="ws://livekit:7880",
        room_token="tok",
        recording=True,
        retention_days=30,
        tutor_router=routed.append,
        transport=fake,
    )
    assert isinstance(session, BridgeSession)
    assert session.state is BridgeState.BRIDGING
    assert fake.opened is True

    # Audio bridged both directions; video in; screen-share both directions.
    kinds = {(t.kind, t.direction) for t in session.bridged}
    assert (TrackKind.AUDIO, Direction.MEETING_TO_ROOM) in kinds
    assert (TrackKind.AUDIO, Direction.ROOM_TO_MEETING) in kinds
    assert (TrackKind.VIDEO, Direction.MEETING_TO_ROOM) in kinds
    assert (TrackKind.SCREEN, Direction.ROOM_TO_MEETING) in kinds

    # Disclosure was announced (recording + retention surfaced).
    assert session.disclosure is not None and session.disclosure.recording is True
    assert "30 days" in session.disclosure.text
    assert any(c.op == "announce" for c in fake.calls)

    # Chat from the meeting routes to the Tutor; the answer posts back.
    session.route_chat_question("What is a derivative?")
    session.post_to_chat("It's the instantaneous rate of change.")
    assert routed == ["What is a derivative?"]
    assert fake.chat_sent == ["It's the instantaneous rate of change."]

    session.stop()
    assert session.state is BridgeState.CLOSED
    assert fake.closed is True


def test_connect_without_credentials_raises_bridge_unavailable(monkeypatch):
    for var in ("ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(BridgeUnavailable) as exc:
        get_bridge(BridgePlatform.ZOOM).connect("https://zoom.us/j/87654321012", livekit_room="c1")
    assert "credentials" in str(exc.value)


def test_connect_with_credentials_but_no_sdk_raises(monkeypatch):
    monkeypatch.setenv("ZOOM_SDK_KEY", "k")
    monkeypatch.setenv("ZOOM_SDK_SECRET", "s")
    with pytest.raises(BridgeUnavailable) as exc:
        get_bridge(BridgePlatform.ZOOM).connect("https://zoom.us/j/87654321012", livekit_room="c1")
    assert "SDK" in str(exc.value)


def test_connect_bad_meeting_ref_raises_value_error():
    with pytest.raises(ValueError):
        get_bridge(BridgePlatform.ZOOM).connect("garbage", livekit_room="c1", transport=FakeTransport())


def test_teams_sidecar_transport_used_when_configured(monkeypatch):
    # Teams is .NET: with the sidecar URL set, the bridge builds the HTTP control
    # transport (it will only actually reach the sidecar at session.start()).
    monkeypatch.setenv("TEAMS_APP_ID", "a")
    monkeypatch.setenv("TEAMS_APP_SECRET", "b")
    monkeypatch.setenv("TEAMS_TENANT_ID", "t")
    monkeypatch.setenv("TEAMS_BRIDGE_SIDECAR_URL", "http://127.0.0.1:59999")
    with pytest.raises(BridgeUnavailable) as exc:
        get_bridge(BridgePlatform.TEAMS).connect(
            "19:meeting_x@thread.v2", livekit_room="c1"
        )
    # Fails at the sidecar call (no server), not at credential/SDK checks.
    assert "sidecar" in str(exc.value).lower()


def test_meet_chat_capability_routes_questions():
    fake = FakeTransport()
    got = []
    session = get_bridge(BridgePlatform.MEET).connect(
        "https://meet.google.com/abc-defg-hij",
        livekit_room="class-meet",
        tutor_router=got.append,
        transport=fake,
    )
    session.route_chat_question("Explain photosynthesis")
    assert got == ["Explain photosynthesis"]
    session.stop()
