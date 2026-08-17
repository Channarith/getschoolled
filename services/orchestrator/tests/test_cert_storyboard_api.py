"""Orchestrator storyboard API for the complete course library."""

from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_storyboard_list_for_dmv_basics() -> None:
    r = client.get("/api/lessons/ca-dmv-permit-basics/storyboard?include_svg=false")
    assert r.status_code == 200
    body = r.json()
    assert body["lesson_id"] == "ca-dmv-permit-basics"
    assert body["segment_count"] >= 12
    assert body["segments"][0]["title"]


def test_storyboard_slide_includes_svg() -> None:
    r = client.get("/api/lessons/ca-alameda-food-handler-temps/storyboard/0")
    assert r.status_code == 200
    body = r.json()
    assert "danger" in body["title"].lower() or "41" in body["concept"]
    assert body["svg"].startswith("<svg")


def test_storyboard_missing_lesson_404() -> None:
    r = client.get("/api/lessons/definitely-not-a-real-course/storyboard")
    assert r.status_code == 404


def test_driver_ed_index() -> None:
    r = client.get("/api/lessons/storyboards/driver-ed")
    assert r.status_code == 200
    body = r.json()
    assert body["scenario_count"] >= 200
    assert body["lesson_count"] >= 20
    assert any(x["lesson_id"].startswith("ca-driver-ed-") for x in body["lessons"])


def test_driver_ed_lesson_storyboard() -> None:
    r = client.get(
        "/api/lessons/ca-driver-ed-11-school-buses/storyboard?include_svg=false"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["segment_count"] >= 10
    assert body["segments"][0]["title"]


def test_generic_storyboard_for_non_cert_course() -> None:
    lessons = client.get("/api/lessons").json()
    generic = next(
        lesson
        for lesson in lessons
        if lesson["lesson_id"] == "algebra-1"
    )
    r = client.get(
        f"/api/lessons/{generic['lesson_id']}/storyboard/0"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["svg"].startswith("<svg")
    assert body["translation_ready"] is True
    assert {"scene", "narration", "captions", "examples", "activity"}.issubset(
        set(body["modalities"])
    )


def test_every_library_course_has_storyboard_coverage() -> None:
    lessons = client.get("/api/lessons").json()
    assert len(lessons) >= 100
    for lesson in lessons:
        lesson_id = lesson["lesson_id"]
        r = client.get(
            f"/api/lessons/{lesson_id}/storyboard?include_svg=false"
        )
        assert r.status_code == 200, lesson_id
        payload = r.json()
        if payload.get("audio_only"):
            # Audio / Drive Mode courses are intentionally visual-free.
            assert payload["segment_count"] == 0, lesson_id
            continue
        assert payload["segment_count"] == len(lesson["slides"]), lesson_id
        assert all(seg["translation_ready"] for seg in payload["segments"])


def test_audio_and_driving_courses_have_no_storyboards() -> None:
    """Audio + Drive Mode (while-driving) courses get NO pictures/animations."""
    from orchestrator.curriculum import Lesson, Slide, lesson_is_audio_only
    from orchestrator.main import get_sessions

    # Predicate: audio/drive delivery is suppressed; driving-SUBJECT study is not.
    assert lesson_is_audio_only(mode="audio")
    assert lesson_is_audio_only(mode="drive")
    assert lesson_is_audio_only(delivery="Audio only · Drive Mode")
    assert not lesson_is_audio_only(track="Certifications", delivery="15-20 min short session")
    # A driving-subject lesson id is NOT mistaken for a while-driving audio course.
    assert not lesson_is_audio_only()

    store = get_sessions().curriculum
    audio_lesson = Lesson(
        lesson_id="test-audio-drive-course",
        title="Commute Audio Briefing",
        mode="audio",
        delivery="Audio only · Drive Mode",
        slides=[
            Slide(index=0, title="Segment 1", body="Listen while driving.",
                  narration="Listen while driving."),
            Slide(index=1, title="Segment 2", body="Eyes on the road.",
                  narration="Eyes on the road."),
        ],
    )
    store.register_lesson("test-audio-drive-course", audio_lesson, [])
    assert store.get("test-audio-drive-course").audio_only is True

    r = client.get("/api/lessons/test-audio-drive-course/storyboard?include_svg=false")
    assert r.status_code == 200
    body = r.json()
    assert body["audio_only"] is True
    assert body["segment_count"] == 0
    assert body["segments"] == []

    slide = client.get("/api/lessons/test-audio-drive-course/storyboard/0")
    assert slide.status_code == 404


def test_driver_ed_study_courses_keep_storyboards() -> None:
    """Seated driver's-ed STUDY courses still get full animated scenes."""
    for lesson_id in ("ca-dmv-permit-basics", "ca-driver-ed-05-intersections"):
        r = client.get(f"/api/lessons/{lesson_id}/storyboard?include_svg=false")
        assert r.status_code == 200, lesson_id
        body = r.json()
        assert not body.get("audio_only"), lesson_id
        assert body["segment_count"] >= 10, lesson_id
