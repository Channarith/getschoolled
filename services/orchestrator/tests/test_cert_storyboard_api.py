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
        assert payload["segment_count"] == len(lesson["slides"]), lesson_id
        assert all(seg["translation_ready"] for seg in payload["segments"])
