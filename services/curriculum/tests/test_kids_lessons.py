"""Kids picture lessons must be fetchable so mobile can play them.

The Kids rails always listed these adventures, but the content lived only in the
web bundle, so mobile could never open one. Serving it keeps the two clients on
one source of truth.
"""

from __future__ import annotations

from aoep_shared.kids_lessons import get_kids_lesson, kids_lesson_ids, list_kids_lessons
from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_every_kids_rail_course_has_playable_lesson_content():
    """The gap users hit: a card in the rail with nothing behind it."""
    rails = client.get("/home?kids=true").json()["rails"]
    learning = next(r for r in rails if r["key"] == "kids-learning")
    assert learning["courses"], "kids-learning rail should not be empty"

    for course in learning["courses"]:
        lesson = get_kids_lesson(course["course_id"])
        assert lesson is not None, f"no lesson content for {course['course_id']}"
        assert lesson["scenes"], f"{course['course_id']} has no scenes"


def test_list_endpoint_returns_all_lessons():
    resp = client.get("/kids/lessons")
    assert resp.status_code == 200
    lessons = resp.json()["lessons"]
    assert len(lessons) == len(kids_lesson_ids())
    assert lessons == sorted(lessons, key=lambda item: item["title"])


def test_single_lesson_endpoint_shape():
    resp = client.get("/kids/lessons/kids-abc-adventures")
    assert resp.status_code == 200
    lesson = resp.json()
    assert lesson["id"] == "kids-abc-adventures"
    assert lesson["title"] and lesson["emoji"] and lesson["color"]

    scene = lesson["scenes"][0]
    assert scene["title"] and scene["instruction"] and scene["question"]
    assert scene["pictures"]
    # The answer must be one of the offered choices or the quiz is unwinnable.
    assert scene["answer"] in scene["choices"]


def test_every_scene_answer_is_one_of_its_choices():
    for lesson in list_kids_lessons():
        for scene in lesson["scenes"]:
            assert scene["answer"] in scene["choices"], (
                f"{lesson['id']} scene {scene['title']!r} has an unreachable answer"
            )


def test_unknown_lesson_returns_404():
    assert client.get("/kids/lessons/not-a-lesson").status_code == 404


def test_kids_rail_games_deep_link_to_the_arcade():
    """Game cards must carry the deep link mobile routes on."""
    rails = client.get("/home?kids=true").json()["rails"]
    games = next(r for r in rails if r["key"] == "games")
    assert games["courses"]
    for course in games["courses"]:
        assert course.get("deep_link", "").startswith("/arcade?subject=")
