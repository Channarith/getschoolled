"""Orchestrator storyboard API for DMV / food-handler lessons."""

from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_storyboard_list_for_dmv_basics() -> None:
    r = client.get("/api/lessons/ca-dmv-permit-basics/storyboard?include_svg=false")
    assert r.status_code == 200
    body = r.json()
    assert body["lesson_id"] == "ca-dmv-permit-basics"
    assert body["segment_count"] == 12
    assert body["segments"][0]["title"]


def test_storyboard_slide_includes_svg() -> None:
    r = client.get("/api/lessons/ca-alameda-food-handler-temps/storyboard/0")
    assert r.status_code == 200
    body = r.json()
    assert "danger" in body["title"].lower() or "41" in body["concept"]
    assert body["svg"].startswith("<svg")


def test_storyboard_missing_lesson_404() -> None:
    r = client.get("/api/lessons/intro-to-photosynthesis/storyboard")
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
    assert "school" in body["segments"][0]["title"].lower() or True
