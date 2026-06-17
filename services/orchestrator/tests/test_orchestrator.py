from fastapi.testclient import TestClient

from orchestrator.director import ClassContext, Director, LessonState
from orchestrator.main import app

client = TestClient(app)


def test_health_reports_mode_and_components():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "orchestrator"
    assert body["deploy_mode"] == "local"
    assert "llm" in body["components"]


def test_create_class_and_join_returns_token():
    created = client.post("/classes", json={"title": "Intro", "class_type": "group"}).json()
    room = created["room"]
    join = client.get(f"/classes/{room}/join", params={"identity": "stu-1"}).json()
    assert join["room"] == room
    assert join["token"].count(".") == 2  # JWT-style


def test_director_prioritizes_questions():
    resp = client.post(
        "/director/tick",
        json={"slides_total": 10, "slide_index": 2, "pending_questions": 1},
    )
    assert resp.json()["next_state"] == "answering"


def test_director_reengages_on_low_attention():
    director = Director()
    state = director.decide(ClassContext(slides_total=10, slide_index=1, attention=0.2))
    assert state is LessonState.REENGAGING


def test_solo_quizzes_more_often_than_group():
    from aoep_shared.schemas import ClassType

    director = Director()
    solo = director.decide(
        ClassContext(class_type=ClassType.SOLO, slides_total=10, slide_index=3, slides_since_quiz=2)
    )
    assert solo is LessonState.QUIZZING
