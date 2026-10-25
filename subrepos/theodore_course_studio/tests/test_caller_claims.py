"""STUDIO_VERIFY_CLAIMS: the teach endpoints must not trust is_admin / registered / paid / empty access from the body."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from theodore_course_studio import caller_claims as cc


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    cc._CACHE.clear()
    monkeypatch.delenv("STUDIO_VERIFY_CLAIMS", raising=False)
    yield
    cc._CACHE.clear()


def _eff(monkeypatch, who, **kw):
    monkeypatch.setenv("STUDIO_VERIFY_CLAIMS", "1")
    args = dict(authorization="Bearer t", access="", registered=False, is_admin=False, enrollment_status="")
    args.update(kw)
    return cc.effective_access(**args, fetch=lambda _h: who)


def test_flag_off_passes_the_request_through_unchanged():
    out = cc.effective_access(authorization="", access="", registered=True, is_admin=True, enrollment_status="paid")
    assert (out["access"], out["registered"], out["is_admin"], out["verified"]) == ("", True, True, None)


def test_flag_on_ignores_a_claimed_admin(monkeypatch):
    out = _eff(monkeypatch, None, is_admin=True, registered=True, enrollment_status="paid", access="full")
    assert out["is_admin"] is False and out["registered"] is False and out["enrollment_status"] == ""
    assert out["access"] == "full"  # the request still asks; resolve_teach_access then downgrades it to sample


def test_flag_on_empty_access_is_the_sample_not_the_authoring_default(monkeypatch):
    assert _eff(monkeypatch, None, access="")["access"] == "sample"
    assert _eff(monkeypatch, {"id": "a1", "is_admin": False}, access="")["access"] == "sample"


def test_flag_on_a_verified_admin_keeps_the_authoring_default(monkeypatch):
    out = _eff(monkeypatch, {"id": "a1", "is_admin": True}, access="")
    assert out["is_admin"] is True and out["access"] == "" and out["verified"] is True


def test_flag_on_a_verified_learner_is_registered_and_keeps_the_claimed_enrollment(monkeypatch):
    out = _eff(monkeypatch, {"id": "a2", "is_admin": False}, enrollment_status="paid", access="full")
    assert out["registered"] is True and out["is_admin"] is False and out["enrollment_status"] == "paid"


def test_identity_outage_fails_closed(monkeypatch):
    out = _eff(monkeypatch, None, is_admin=True, access="")
    assert out["is_admin"] is False and out["access"] == "sample"


def test_lookups_are_cached_and_misses_expire_sooner(monkeypatch):
    calls = []
    clock = [1000.0]

    def fetch(h):
        calls.append(h)
        return {"id": "a1"} if h == "Bearer good" else None

    now = lambda: clock[0]  # noqa: E731
    assert cc.verified_caller("Bearer good", fetch=fetch, now=now)["id"] == "a1"
    assert cc.verified_caller("Bearer good", fetch=fetch, now=now)["id"] == "a1"
    assert cc.verified_caller("Bearer bad", fetch=fetch, now=now) is None
    assert cc.verified_caller("Bearer bad", fetch=fetch, now=now) is None
    assert len(calls) == 2
    clock[0] += 11
    assert cc.verified_caller("Bearer bad", fetch=fetch, now=now) is None  # miss expired after 10 s
    assert len(calls) == 3
    assert cc.verified_caller("Bearer good", fetch=fetch, now=now)["id"] == "a1"  # hit lasts 60 s
    assert len(calls) == 3


def test_no_token_is_anonymous_without_a_lookup():
    assert cc.verified_caller("", fetch=lambda h: pytest.fail("must not call identity")) is None


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("COURSE_STUDIO_DATA_DIR", str(tmp_path))
    import importlib

    from theodore_course_studio import main as m
    importlib.reload(m)
    return m, TestClient(m.app)


def _seed(m):
    from theodore_course_studio.types import CourseSlide, StudioCourse

    m._builder.save_course(StudioCourse(course_id="trial-c", title="T", category="other", slides=[
        CourseSlide(index=0, title="One", body="First."), CourseSlide(index=1, title="Two", body="Second.")]))


def _start(client, **extra):
    body = {"session_id": "s1", "course_id": "trial-c", "learner_id": "browser-x", "use_voice_agent": False}
    body.update(extra)
    return client.post("/api/studio/teach/start", json=body)


def test_endpoint_flag_off_documents_the_gap_an_anonymous_admin_claim_gets_full(tmp_path, monkeypatch):
    m, client = _client(tmp_path, monkeypatch)
    _seed(m)
    r = _start(client, access="full", is_admin=True)
    assert r.status_code == 200
    assert m._teach._sessions["s1"].sample_only is False  # the exposure STUDIO_VERIFY_CLAIMS=1 closes


def test_endpoint_flag_on_anonymous_admin_claim_and_empty_access_get_only_the_sample(tmp_path, monkeypatch):
    m, client = _client(tmp_path, monkeypatch)
    _seed(m)
    monkeypatch.setenv("STUDIO_VERIFY_CLAIMS", "1")
    monkeypatch.setattr(cc, "_fetch_me", lambda _h: None)
    for i, extra in enumerate(({"access": "full", "is_admin": True}, {"is_admin": True}, {}, {"access": "full", "registered": True, "enrollment_status": "paid"})):
        r = _start(client, session_id=f"s{i}", **extra)
        assert r.status_code == 200, r.text
        sess = m._teach._sessions[f"s{i}"]
        assert sess.sample_only is True and sess.soft_limit_minutes == 10, extra


def test_endpoint_flag_on_verified_admin_still_gets_full(tmp_path, monkeypatch):
    m, client = _client(tmp_path, monkeypatch)
    _seed(m)
    monkeypatch.setenv("STUDIO_VERIFY_CLAIMS", "1")
    monkeypatch.setattr(cc, "_fetch_me", lambda _h: {"id": "adm", "is_admin": True})
    r = client.post("/api/studio/teach/start", headers={"Authorization": "Bearer ok"}, json={
        "session_id": "adm1", "course_id": "trial-c", "learner_id": "browser-y", "access": "full", "is_admin": False, "use_voice_agent": False})
    assert r.status_code == 200, r.text
    assert m._teach._sessions["adm1"].sample_only is False
