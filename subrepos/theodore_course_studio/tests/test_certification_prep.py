from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_course_studio.certification_prep import (
    CERT_SESSION_MAX_MINUTES,
    CertTrackId,
    build_cert_course,
    list_cert_courses,
)
from theodore_course_studio.checkpoints import soft_checkpoint_due
from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.main import app
from theodore_course_studio.teach import TeachEngine
from theodore_course_studio.types import CategoryId


def test_cert_tracks_cover_dmv_and_food():
    tracks = {row.track for row in list_cert_courses()}
    assert tracks == {CertTrackId.CA_DMV_PERMIT, CertTrackId.ALAMEDA_FOOD_HANDLER}
    assert all(row.prep_only for row in list_cert_courses())
    assert all(10 <= row.slides <= 20 for row in list_cert_courses())
    assert all(row.estimated_minutes <= CERT_SESSION_MAX_MINUTES for row in list_cert_courses())
    food = [row for row in list_cert_courses() if row.track is CertTrackId.ALAMEDA_FOOD_HANDLER]
    assert len(food) == 6
    assert sum(row.slides for row in food) >= 120
    assert all(row.slides == 20 for row in food)


def test_build_ca_dmv_course_has_jurisdiction_metadata():
    course = build_cert_course(lesson_id="ca-dmv-basics")
    assert course.category is CategoryId.DRIVER_EDUCATION
    assert course.audience == "adult_cert_prep"
    assert course.estimated_minutes <= 20
    assert course.profile_adaptations["jurisdiction"] == "us-ca"
    assert course.profile_adaptations["prep_only"] is True
    assert course.profile_adaptations["picture_led"] is True
    assert course.profile_adaptations["motion_clip"] is True
    assert "not a dmv-approved" in course.profile_adaptations["disclaimer"].lower()
    assert any("us-ca" in slide.tags for slide in course.slides)
    assert all(slide.avatar_script for slide in course.slides)
    assert all(slide.avatar_script.source == "curated" for slide in course.slides)


def test_all_cert_lessons_have_picture_and_motion():
    from urllib.parse import unquote

    for row in list_cert_courses():
        course = build_cert_course(lesson_id=row.lesson_id)
        assert course.slides, row.lesson_id
        for slide in course.slides:
            assert slide.picture_url.startswith("data:image/svg+xml"), slide.title
            assert slide.video_url.startswith("data:image/svg+xml"), slide.title
            assert slide.activity_prompt, slide.title
            motion_svg = unquote(slide.video_url.split(",", 1)[1])
            still_svg = unquote(slide.picture_url.split(",", 1)[1])
            assert (
                "animateTransform" in motion_svg
                or "@keyframes" in motion_svg
                or "keyframes" in motion_svg
            ), slide.title
            if "animateTransform" in motion_svg:
                assert "animateTransform" not in still_svg


def test_build_alameda_food_course():
    course = build_cert_course(
        track=CertTrackId.ALAMEDA_FOOD_HANDLER,
        lesson_id="alameda-food-temps",
    )
    assert course.category is CategoryId.FOOD_SAFETY
    assert course.profile_adaptations["jurisdiction"] == "us-ca-alameda"
    assert "alameda" in course.profile_adaptations["disclaimer"].lower()
    assert course.slides[0].picture_url.startswith("data:image/svg+xml")
    assert course.slides[0].video_url.startswith("data:image/svg+xml")
    assert len(course.slides) == 20


def test_certification_api_builds_and_teaches(monkeypatch, tmp_path):
    import theodore_course_studio.main as main_module

    builder = CourseBuilder(data_dir=tmp_path / "data")
    monkeypatch.setattr(main_module, "_builder", builder)
    monkeypatch.setattr(main_module, "_teach", TeachEngine(builder))
    client = TestClient(app)

    options = client.get("/api/studio/certification/options")
    assert options.status_code == 200
    body = options.json()
    assert body["default_track"] == "ca_dmv_permit"
    assert len(body["tracks"]) == 2
    assert len(body["courses"]) >= 6

    made = client.post(
        "/api/studio/courses/certification",
        json={"track": "ca_dmv_permit", "lesson_id": "ca-dmv-signs", "language": "en"},
    )
    assert made.status_code == 200
    payload = made.json()
    assert payload["category"] == "driver_education"
    assert payload["profile_adaptations"]["jurisdiction"] == "us-ca"
    assert payload["profile_adaptations"]["picture_led"] is True
    assert payload["slides"][0]["picture_url"].startswith("data:image/svg+xml")
    assert payload["slides"][0]["video_url"].startswith("data:image/svg+xml")
    assert builder.get_course(payload["course_id"]) is not None


def test_studio_shows_certification_panel_beside_kids():
    page = TestClient(app).get("/studio")
    assert page.status_code == 200
    assert "Make a children's lesson" in page.text
    assert "Certification prep" in page.text
    assert "examples, quiz, and a game" in page.text or "picture + motion" in page.text
    assert "Watch video" in page.text
    assert "Come back later" in page.text
    assert "driver_education" in page.text
    assert "food_safety" in page.text


def test_soft_checkpoint_skips_kids_audience():
    assert soft_checkpoint_due(
        started_at_ms=0,
        path_pos=20,
        soft_limit_minutes=1,
        soft_limit_slides=1,
        now_ms=120_000,
        audience="pre_k",
    ) is False
    assert soft_checkpoint_due(
        started_at_ms=0,
        path_pos=0,
        soft_limit_minutes=1,
        soft_limit_slides=99,
        now_ms=120_000,
        audience="adult_cert_prep",
    ) is True


def test_teach_pause_and_resume_persists(tmp_path):
    course = build_cert_course(lesson_id="ca-dmv-basics")
    builder = CourseBuilder(data_dir=tmp_path / "data")
    builder.save_course(course)
    engine = TeachEngine(builder)

    start = engine.start(
        session_id="s1",
        course_id=course.course_id,
        learner_id="learner-a",
        use_voice_agent=False,
        soft_limit_minutes=15,
    )
    assert start["checkpoint"]["due"] is False or "choices" in start["checkpoint"]
    engine.advance("s1")
    engine.advance("s1")
    paused = engine.come_back_later("s1")
    assert paused["status"] == "paused"
    assert paused["checkpoint"]["path_pos"] >= 1

    # New engine instance simulates process restart.
    engine2 = TeachEngine(builder)
    resumed = engine2.start(
        session_id="s2",
        course_id=course.course_id,
        learner_id="learner-a",
        use_voice_agent=False,
        resume=True,
    )
    assert resumed["resumed"] is True
    assert resumed["path_pos"] == paused["checkpoint"]["path_pos"]
    assert "Resumed" in resumed["resume_message"]


def test_teach_payload_includes_synchronized_avatar_script(tmp_path):
    course = build_cert_course(lesson_id="ca-dmv-basics")
    builder = CourseBuilder(data_dir=tmp_path / "data")
    builder.save_course(course)
    payload = TeachEngine(builder).start(
        session_id="avatar-teach",
        course_id=course.course_id,
        use_voice_agent=False,
    )
    avatar = payload["avatar"]
    assert avatar["source"] == "explicit"
    assert avatar["state"] == "presenting"
    assert avatar["cues"]
    assert avatar["visemes"]
    assert avatar["duration_s"] > 0
    assert max(c["start_s"] + c["duration_s"] for c in avatar["cues"]) <= avatar["duration_s"] + 0.01
