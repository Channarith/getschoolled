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
    assert "trial" in stopped["sample"]["message"].lower()
    assert "pay for the course" in stopped["sample"]["message"].lower()
    assert session.path_pos == before
    assert engine.continue_past_checkpoint("sample-1")["sample"]["complete"] is True
    assert session.soft_limit_minutes == 10


def test_starting_over_does_not_reset_a_finished_trial(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path)
    engine = TeachEngine(builder)
    course = _mini(builder, "sticky-mini")
    engine.start(
        session_id="sticky-1",
        course_id=course.course_id,
        learner_id="learner-a",
        access="sample",
        use_voice_agent=False,
    )
    session = engine._sessions["sticky-1"]
    session.started_at_ms = int(time.time() * 1000) - 11 * 60_000
    engine._persist_live(session, status="in_progress")
    again = engine.start(
        session_id="sticky-2",
        course_id=course.course_id,
        learner_id="learner-a",
        access="sample",
        resume=False,
        use_voice_agent=False,
    )
    assert again["sample"]["complete"] is True
    assert again["session"]["started_at_ms"] == session.started_at_ms


def test_audio_trial_is_a_separate_ten_minutes(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path)
    engine = TeachEngine(builder)
    course = _mini(builder, "split-mini")
    engine.start(
        session_id="class-1",
        course_id=course.course_id,
        learner_id="learner-a",
        access="sample",
        use_voice_agent=False,
    )
    class_session = engine._sessions["class-1"]
    class_session.started_at_ms = int(time.time() * 1000) - 11 * 60_000
    engine._persist_live(class_session, status="in_progress")
    audio = engine.start(
        session_id="audio-1",
        course_id=course.course_id,
        learner_id="learner-a:audio",
        access="sample",
        use_voice_agent=False,
    )
    assert audio["sample"]["complete"] is False
    assert audio["sample"]["minutes"] == 10


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


def test_teach_start_downgrades_an_unpaid_full_request(tmp_path, monkeypatch):
    import theodore_course_studio.caller_claims as claims
    import theodore_course_studio.main as main_mod

    # An explicit "full" request is verified against the identity service, flag or no flag: the request's own
    # registered / is_admin / enrollment_status fields are never the proof.
    users = {"Bearer user": {"id": "u1", "is_admin": False}, "Bearer admin": {"id": "u9", "is_admin": True}}
    monkeypatch.setattr(claims, "_fetch_me", lambda auth: users.get(auth))
    monkeypatch.delenv("STUDIO_VERIFY_CLAIMS", raising=False)
    claims._CACHE.clear()
    old_builder = main_mod._builder
    old_teach_builder = main_mod._teach._builder
    shared = CourseBuilder(data_dir=tmp_path / "data")
    main_mod._builder = shared
    main_mod._teach._builder = shared
    try:
        course = _mini(shared, "api-sample")
        client = TestClient(main_mod.app)
        base = {"course_id": course.course_id, "access": "full", "use_voice_agent": False}
        unpaid = client.post("/api/studio/teach/start", json={**base, "session_id": "api-sample-1", "registered": True,
                                                              "enrollment_status": "enrolled"}, headers={"authorization": "Bearer user"})
        assert unpaid.status_code == 200, unpaid.text
        assert unpaid.json()["access_mode"] == "sample"
        assert unpaid.json()["sample"]["minutes"] == 10

        anonymous = client.post("/api/studio/teach/start", json={**base, "session_id": "api-anon-1", "registered": True,
                                                                 "enrollment_status": "paid", "is_admin": True})
        assert anonymous.status_code == 200, anonymous.text
        assert anonymous.json()["access_mode"] == "sample"

        admin = client.post("/api/studio/teach/start", json={**base, "session_id": "api-admin-1"},
                            headers={"authorization": "Bearer admin"})
        assert admin.status_code == 200, admin.text
        assert admin.json()["access_mode"] == "full"

        authoring = client.post("/api/studio/teach/start", json={
            "session_id": "api-author-1", "course_id": course.course_id, "use_voice_agent": False})
        assert authoring.status_code == 200, authoring.text
        assert authoring.json()["access_mode"] == "full"  # the authoring studio (no access mode, not a public course) is unchanged
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
    assert "armSampleClock" in STUDIO_JS
    assert "formatSampleClock" in STUDIO_JS
    assert 'id="sample-clock"' in page
    assert "$19.99" in page
    assert 'id="pay-card"' in page
    assert 'id="pay-paypal"' in page
    assert "/api/studio/pay/checkout" in STUDIO_JS
    assert "presentation" in STUDIO_JS
    assert "if (audioOnly) return;" not in STUDIO_JS
    assert 'id="audio-stage"' in page
    assert 'id="lesson-caption"' in page
    assert "audio-only" in page
    assert "body.audio-only #teach-title" in page
    assert "body.audio-only #quiz-box" in page
    assert "body.audio-only #theodore-live-audio" in page
    assert "body.audio-only #sample-clock" in page
    assert "drive-chrome-hidden" in page
    assert "revealDriveChrome" in STUDIO_JS
    assert "FS_CHROME_HIDE_MS = 2000" in STUDIO_JS
    assert 'id="fs-chrome-edge"' in page
    assert "body.presenting.drive-chrome-hidden #course-price" in page
    assert "body.presenting.drive-chrome-hidden .lesson-window-controls" in page
    # Chrome hide must not swallow the 10-minute free-trial clock.
    assert "body.presenting.drive-chrome-hidden #sample-clock:not([hidden])" in page
    assert "body.audio-only.drive-chrome-hidden #sample-clock:not([hidden])" in page
    assert "parkSampleClock()" in STUDIO_JS
    assert "controls.appendChild(clock)" not in STUDIO_JS
    assert "body.audio-only .lesson-toolbar" in page
    assert "position:fixed !important; inset:0 !important;" in page
    assert 'class="audio-avatar"' not in page
    assert "onDriveWaveTap" in STUDIO_JS
    # Sample demos and full courses share this page. Leaving the camera pauses both.
    assert 'id="presence-hold"' in page
    assert "We detected that you left the camera." in STUDIO_JS
    assert "pauseLessonForAbsence" in STUDIO_JS
    assert "studentStillAway" in STUDIO_JS
    assert "function pauseLessonForAbsence" in STUDIO_JS
    assert "ABSENCE_HOLD_MS = 600" in STUDIO_JS
    assert "PRESENCE_RESUME_MS" in STUDIO_JS
    assert "learnerLocallyBack" in STUDIO_JS
    assert "resumeLessonAfterPresence" in STUDIO_JS
    # Returning face/contours must resume locally — not only when the server clears hold.
    assert "holdGroup(learningHoldReason) === 'away'" in STUDIO_JS
    assert "learnerLocallyBack() && learningHold" in STUDIO_JS
    assert "watchStudentPresence" in STUDIO_JS
    assert "setInterval(watchStudentPresence, 200)" in STUDIO_JS
    assert "fullDriversProgram()" not in STUDIO_JS.split("function pauseLessonForAbsence")[0][-400:]
    assert "/api/studio/courses/certification-program" in STUDIO_JS
    assert "program_percent" in STUDIO_JS
    assert "Next gap" in page
    assert 'id="drive-look"' in page
    assert 'data-look="bars"' in page
    assert "Frequency line" in page
    assert "Talking mouth" in page
    assert "face-amina" in page
    assert "applyAudioLook" in STUDIO_JS
    assert "TheodoreLiveAudio.start()" in STUDIO_JS
    assert "kind !== 'backup'" in STUDIO_JS
    assert 'id="course-map"' in page
    assert "syncVoiceToSlide" in STUDIO_JS
    assert "/api/studio/teach/goto" in STUDIO_JS
    assert "library-panel" in page
    assert 'id="library-picker"' in page
    assert "setLibraryCollapsed" in STUDIO_JS
    assert "public-course .layout" in page
    assert "grid-template-columns:minmax(260px, 0.9fr)" not in page
    assert "public-course .library-panel { display:none" not in page
    assert "library.filter((row) => row.id === pinnedCourse)" not in STUDIO_JS
