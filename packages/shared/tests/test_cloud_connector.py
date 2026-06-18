"""Cloud/collab connectors (Phase 19)."""

import time

import pytest

from aoep_shared.connectors.cloud import (
    MockCalendar,
    MockNotifier,
    build_slack_message,
    parse_saml_attributes,
    schedule_event,
    verify_oidc_claims,
)


def test_slack_message_payload():
    m = build_slack_message("Class starts soon", channel="#class")
    assert m["channel"] == "#class"
    assert m["blocks"][0]["text"]["text"] == "Class starts soon"


def test_mock_notifier_records():
    n = MockNotifier()
    n.send("#general", "hello")
    assert len(n.sent) == 1


def test_schedule_event_computes_end():
    ev = schedule_event("Algebra", "2026-07-01T15:00:00+00:00", 90, ["a@x.com"])
    assert ev["start"].startswith("2026-07-01T15:00")
    assert ev["end"].startswith("2026-07-01T16:30")
    assert ev["attendees"] == ["a@x.com"]


def test_mock_calendar_create():
    cal = MockCalendar()
    out = cal.create_event(schedule_event("X", "2026-07-01T10:00:00Z", 30))
    assert out["id"] == "evt-1"


def test_oidc_valid_and_invalid():
    base = {"iss": "https://idp.test", "aud": "aoep", "sub": "u1", "email": "u@x.com",
            "exp": time.time() + 3600}
    ident = verify_oidc_claims(base, audience="aoep")
    assert ident.subject == "u1" and ident.email == "u@x.com"

    with pytest.raises(ValueError):
        verify_oidc_claims({**base, "aud": "other"}, audience="aoep")
    with pytest.raises(ValueError):
        verify_oidc_claims({**base, "exp": time.time() - 10}, audience="aoep")


def test_saml_attributes():
    ident = parse_saml_attributes({"NameID": "u9", "email": "u9@x.com", "displayName": "Nine"})
    assert ident.subject == "u9" and ident.provider == "saml"
