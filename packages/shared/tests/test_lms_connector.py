"""LMS/SIS connector building blocks (Phase 18)."""

import pytest

from aoep_shared.connectors.lms import (
    MockLMS,
    build_ags_score,
    build_xapi_statement,
    parse_lti_launch,
    parse_oneroster,
)

_LTI = "https://purl.imsglobal.org/spec/lti/claim"


def _launch_claims():
    return {
        f"{_LTI}/message_type": "LtiResourceLinkRequest",
        f"{_LTI}/version": "1.3.0",
        "sub": "user-123",
        "name": "Jordan",
        f"{_LTI}/roles": ["Learner"],
        f"{_LTI}/context": {"id": "course-9"},
    }


def test_parse_lti_launch():
    ctx = parse_lti_launch(_launch_claims())
    assert ctx.user_id == "user-123"
    assert ctx.context_id == "course-9"
    assert "Learner" in ctx.roles


def test_parse_lti_launch_rejects_bad_version():
    claims = _launch_claims()
    claims[f"{_LTI}/version"] = "1.1"
    with pytest.raises(ValueError):
        parse_lti_launch(claims)


def test_parse_oneroster():
    payload = {"users": [
        {"sourcedId": "u1", "role": "student", "givenName": "Sam", "familyName": "Lee"},
        {"sourcedId": "u2", "role": "teacher", "givenName": "Pat"},
        {"role": "student"},  # no id -> dropped
    ]}
    members = parse_oneroster(payload)
    assert len(members) == 2
    assert members[0].user_id == "u1" and members[0].name == "Sam Lee"


def test_ags_score_payload():
    p = build_ags_score("u1", 8.0, 10.0, line_item="quiz-1")
    assert p["userId"] == "u1" and p["scoreGiven"] == 8.0 and p["scoreMaximum"] == 10.0
    assert p["gradingProgress"] == "FullyGraded"


def test_xapi_statement():
    s = build_xapi_statement("u1", "completed", "course-9", scaled=0.8)
    assert s["actor"]["name"] == "u1"
    assert s["result"]["score"]["scaled"] == 0.8


def test_mock_lms_push_grade():
    lms = MockLMS()
    lms.push_grade(build_ags_score("u1", 1.0, 1.0))
    assert len(lms.pushed) == 1 and lms.pushed[0]["userId"] == "u1"
