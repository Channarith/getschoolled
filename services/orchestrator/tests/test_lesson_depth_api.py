"""Orchestrator curriculum loader enriches lessons to 20+ minute sessions."""

import os

from fastapi.testclient import TestClient

from aoep_shared.lesson_depth import TARGET_MIN_MINUTES, duration_minutes
from orchestrator.curriculum import CurriculumStore, curriculum_root
from orchestrator.main import app

client = TestClient(app)


def test_loaded_lesson_has_enriched_slide_count():
    store = CurriculumStore()
    lesson = store.get("intro-to-photosynthesis")
    assert lesson is not None
    assert len(lesson.slides) >= 10


def test_every_lesson_has_enough_slides_for_a_full_session():
    """Every lesson must carry a substantial deck — at least 20 slides — so a
    group/solo class fills a ~30-minute session and never stalls with 0-1 slides.
    Free-form lessons (no SLIDE markers) must parse + enrich past this floor too."""
    store = CurriculumStore()
    thin = [(l.lesson_id, len(l.slides)) for l in store.list_lessons() if len(l.slides) < 20]
    assert not thin, f"lessons with fewer than 20 slides: {thin}"


def test_loaded_lesson_meets_target_duration():
    store = CurriculumStore()
    lesson = store.get("intro-to-photosynthesis")
    assert lesson is not None
    assert duration_minutes(lesson.slides) >= TARGET_MIN_MINUTES


def test_lessons_api_returns_enriched_catalog():
    r = client.get("/api/lessons")
    assert r.status_code == 200
    photosynthesis = next(l for l in r.json() if l["lesson_id"] == "intro-to-photosynthesis")
    assert len(photosynthesis["slides"]) >= 10


def test_session_on_enriched_lesson_advances_many_slides():
    start = client.post(
        "/api/sessions",
        json={"lesson_id": "intro-to-photosynthesis", "class_type": "group"},
    )
    assert start.status_code == 200
    body = start.json()
    sid = body["session"]["session_id"]
    total = len(body["lesson"]["slides"])
    assert total >= 10
    for _ in range(3):
        adv = client.post(f"/api/sessions/{sid}/advance")
        assert adv.status_code == 200


def test_same_lesson_builds_different_paths_for_two_time_budgets():
    short = client.post(
        "/api/lessons/intro-to-photosynthesis/plan",
        json={"session_budget_min": 10},
    )
    standard = client.post(
        "/api/lessons/intro-to-photosynthesis/plan",
        json={"session_budget_min": 30},
    )
    assert short.status_code == standard.status_code == 200
    short_plan = short.json()
    standard_plan = standard.json()
    assert short_plan["lesson_id"] == standard_plan["lesson_id"]
    assert short_plan["planned_slide_count"] < standard_plan["planned_slide_count"]
    assert short_plan["source_slide_indices"][0] == 0
    assert short_plan["mastery_target"] == "unchanged"


def test_profile_score_duration_digit_controls_session_path():
    # visual, moderate, step-by-step, short, group, intermediate, career, no access
    start = client.post(
        "/api/sessions",
        json={
            "lesson_id": "intro-to-photosynthesis",
            "class_type": "solo",
            "student_id": "person-a",
            "profile_score": "15115510",
        },
    )
    assert start.status_code == 200
    body = start.json()
    assert body["session"]["student_id"] == "person-a"
    assert body["session"]["session_budget_min"] == 10
    assert len(body["lesson"]["slides"]) == len(body["session"]["slide_indices"])


def test_curriculum_root_respects_env(monkeypatch):
    root = curriculum_root()
    assert os.path.isdir(root)
    custom = "/tmp/custom-curriculum-test"
    monkeypatch.setenv("CURRICULUM_DIR", custom)
    assert curriculum_root() == custom
