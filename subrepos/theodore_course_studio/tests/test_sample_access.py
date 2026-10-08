"""A sales-demo session stops at 10 minutes and cannot be extended."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.teach import TeachEngine
from theodore_course_studio.types import CourseSlide, StudioCourse


def _mini(builder: CourseBuilder, course_id: str = "sample-mini") -> StudioCourse:
    course = StudioCourse(
        course_id=course_id,
        title="Sample Mini",
        category="other",
        slides=[
            CourseSlide(index=0, title="One", body="First body."),
            CourseSlide(index=1, title="Two", body="Second body."),
        ],
    )
    builder.save_course(course)
    return course


def test_sample_stops_at_ten_minutes_and_does_not_extend(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path)
    engine = TeachEngine(builder)
    course = _mini(builder)
    payload = engine.start(
        session_id="sample-1",
        course_id=course.course_id,
        access="sample",
        use_voice_agent=False,
    )
    session = engine._sessions["sample-1"]
    assert session.sample_only is True
    assert session.soft_limit_minutes == 10
    assert payload["access_mode"] == "sample"
    assert payload["sample"]["complete"] is False

    session.started_at_ms = int(time.time() * 1000) - 11 * 60_000
    before = session.path_pos
    stopped = engine.advance("sample-1")
    assert stopped["sample"]["complete"] is True
    assert "pay for the course" in stopped["sample"]["message"].lower()
    assert session.path_pos == before
    assert engine.continue_past_checkpoint("sample-1")["sample"]["complete"] is True
    assert session.soft_limit_minutes == 10


def test_paid_session_still_advances_after_ten_minutes(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path)
    engine = TeachEngine(builder)
    course = _mini(builder, "full-mini")
    engine.start(
        session_id="full-1",
        course_id=course.course_id,
        access="full",
        use_voice_agent=False,
    )
    session = engine._sessions["full-1"]
    session.started_at_ms = int(time.time() * 1000) - 11 * 60_000
    moved = engine.advance("full-1")
    assert moved["access_mode"] == "full"
    assert moved["sample"]["complete"] is False
    assert session.path_pos == 1


def test_teach_start_downgrades_an_unpaid_full_request(tmp_path):
    import theodore_course_studio.main as main_mod

    old_builder = main_mod._builder
    old_teach_builder = main_mod._teach._builder
    shared = CourseBuilder(data_dir=tmp_path / "data")
    main_mod._builder = shared
    main_mod._teach._builder = shared
    try:
        course = _mini(shared, "api-sample")
        client = TestClient(main_mod.app)
        unpaid = client.post("/api/studio/teach/start", json={
            "session_id": "api-sample-1",
            "course_id": course.course_id,
            "access": "full",
            "registered": True,
            "enrollment_status": "enrolled",
            "use_voice_agent": False,
        })
        assert unpaid.status_code == 200, unpaid.text
        assert unpaid.json()["access_mode"] == "sample"
        assert unpaid.json()["sample"]["minutes"] == 10

        paid = client.post("/api/studio/teach/start", json={
            "session_id": "api-full-1",
            "course_id": course.course_id,
            "access": "full",
            "registered": True,
            "enrollment_status": "paid",
            "use_voice_agent": False,
        })
        assert paid.status_code == 200, paid.text
        assert paid.json()["access_mode"] == "full"

        admin = client.post("/api/studio/teach/start", json={
            "session_id": "api-admin-1",
            "course_id": course.course_id,
            "access": "full",
            "is_admin": True,
            "use_voice_agent": False,
        })
        assert admin.status_code == 200, admin.text
        assert admin.json()["access_mode"] == "full"

        authoring = client.post("/api/studio/teach/start", json={
            "session_id": "api-author-1",
            "course_id": course.course_id,
            "use_voice_agent": False,
        })
        assert authoring.status_code == 200, authoring.text
        assert authoring.json()["access_mode"] == "full"
    finally:
        main_mod._builder = old_builder
        main_mod._teach._builder = old_teach_builder


def test_studio_page_offers_the_sample_banner():
    from theodore_course_studio.studio_page import STUDIO_JS, render_studio_page

    page = render_studio_page()
    assert 'id="sample-banner"' in page
    assert "enrollment_status" in STUDIO_JS
    assert "get('course')" in STUDIO_JS
    assert "is_admin" in STUDIO_JS
    assert "sampleIsComplete" in STUDIO_JS
    assert "library-panel" in page
    assert "public-course .library-panel { display:none" not in page
    assert "library.filter((row) => row.id === pinnedCourse)" not in STUDIO_JS
