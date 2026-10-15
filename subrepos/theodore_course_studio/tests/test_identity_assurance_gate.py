"""Certification teach sessions need identity assurance; authoring and samples do not."""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def course_id(monkeypatch):
    from theodore_course_studio.main import app

    monkeypatch.setattr(
        "theodore_course_studio.lesson_locale.translate_text",
        lambda text, source, target: (text, False, ""),
    )
    built = TestClient(app).post(
        "/api/studio/courses/certification",
        json={"lesson_id": "alameda-food-hygiene", "language": "en"},
    )
    assert built.status_code == 200
    return built.json()["course_id"]


def _assurance(monkeypatch, allowed: bool) -> list[str]:
    import urllib.request

    calls: list[str] = []
    real_urlopen = urllib.request.urlopen

    def fake_urlopen(request, timeout=0, *args, **kwargs):
        url = getattr(request, "full_url", str(request))
        if "/identity-assurance" not in url:
            return real_urlopen(request, *args, timeout=timeout, **kwargs)
        calls.append(url)
        body = {"allowed": allowed, "missing": [] if allowed else ["government_id"]}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return calls


def _start(course_id: str, **extra):
    from theodore_course_studio.main import app

    payload = {"session_id": f"gate-{extra.get('access', 'author')}", "course_id": course_id}
    payload.update(extra)
    return TestClient(app).post(
        "/api/studio/teach/start",
        json=payload,
        headers={"Authorization": "Bearer test"},
    )


def _paid_learner(course_id: str):
    return _start(
        course_id,
        access="full",
        registered=True,
        enrollment_status="paid",
        learner_id="stu:student-1",
    )


def test_paid_learner_without_assurance_is_blocked(monkeypatch, course_id):
    calls = _assurance(monkeypatch, allowed=False)
    started = _paid_learner(course_id)
    assert started.status_code == 428
    assert started.headers["X-AOEP-Gate"] == "identity_assurance_required"
    assert calls and "/students/student-1/identity-assurance?required=true" in calls[0]


def test_paid_learner_with_assurance_starts(monkeypatch, course_id):
    _assurance(monkeypatch, allowed=True)
    assert _paid_learner(course_id).status_code == 200


def test_authoring_and_sample_skip_identity_check(monkeypatch, course_id):
    calls = _assurance(monkeypatch, allowed=False)
    assert _start(course_id).status_code == 200
    assert _start(course_id, access="sample").status_code == 200
    assert calls == []
