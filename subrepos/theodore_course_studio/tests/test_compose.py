"""Compose behavioral segments into a full trial course."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_course_studio.compose import (
    ComposeCourseRequest,
    SegmentKind,
    compose_course_from_segments,
    default_trial_segments,
    resolve_spoken_text,
    trial_demo_plan,
)
from theodore_course_studio.main import app


def test_resolve_spoken_text_never_tags_english_with_foreign_voice():
    text, spoken, source = resolve_spoken_text("Hello world", "km")
    assert spoken == "en"
    assert source == "english"
    assert text == "Hello world"


def test_resolve_spoken_text_curated_spanish_welcome():
    text, spoken, source = resolve_spoken_text("Welcome", "es")
    assert spoken == "es"
    assert source == "curated"
    assert text == "Bienvenido"


def test_compose_trial_course_has_all_segment_kinds():
    course = compose_course_from_segments(
        ComposeCourseRequest(language="en", segments=default_trial_segments())
    )
    kinds = {s.tags[0] for s in course.slides if s.tags}
    assert SegmentKind.LESSON.value in kinds
    assert SegmentKind.GAME.value in kinds
    assert SegmentKind.QUIZ.value in kinds
    assert SegmentKind.PRONUNCIATION.value in kinds
    assert SegmentKind.REMEMBER.value in kinds
    assert len(course.slides) >= 8


def test_trial_slides_carry_spoken_language_matching_text():
    course = compose_course_from_segments(
        ComposeCourseRequest(language="es", segments=default_trial_segments())
    )
    welcome = course.slides[0]
    assert welcome.spoken_language == "es"
    assert welcome.title == "Bienvenido"


def test_trial_demo_plan_reports_soft_limit():
    plan = trial_demo_plan("en")
    assert plan["segment_count"] >= 8
    assert plan["soft_limit_minutes"] == 18


def test_trial_run_api_starts_teaching(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_COURSE_STUDIO_DATA", str(tmp_path / "data"))
    from theodore_course_studio.generate import CourseBuilder
    import theodore_course_studio.main as main_mod

    shared = CourseBuilder(data_dir=tmp_path / "data")
    main_mod._builder = shared
    main_mod._teach._builder = shared

    client = TestClient(app)
    res = client.post(
        "/api/studio/teach/trial-run",
        json={"session_id": "trial-test-1", "language": "en"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("composed") is True
    assert body.get("course_id")
    assert body.get("turn") or body.get("progress")
