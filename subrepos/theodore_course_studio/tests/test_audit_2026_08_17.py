"""Regression tests for the 2026-08-17 audit (course studio).

- Path traversal: get_course must not resolve ids outside the courses dir.
- Pop-quiz answer key must not point at a distractor when texts duplicate.
- Order-steps game must never ship an empty-string step.
- come_back_later must not mark the unfinished current slide completed.
- _turn_payload (via current()) must not grow history on read-only polls.
"""

from __future__ import annotations

from theodore_course_studio.assessment import build_pop_quiz_for_slide
from theodore_course_studio.engagement import build_order_steps_game
from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.knowledge import LearningObjective
from theodore_course_studio.types import CourseSlide


def test_get_course_rejects_path_traversal(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path)
    assert builder.get_course("../secret") is None
    assert builder.get_course("../../etc/passwd") is None
    assert builder.get_course("course-test1") is None  # missing, but not an error


def test_pop_quiz_answer_key_unique_with_duplicate_texts():
    slide = CourseSlide(index=1, title="Same", body="Same. Same.")
    objective = LearningObjective(objective_id="o1", course_id="c1", title="Same")
    quiz = build_pop_quiz_for_slide(slide, objective)
    assert quiz is not None
    # The correct text must appear exactly once and correct_index must find it.
    correct_text = quiz.choices[quiz.correct_index]
    assert quiz.choices.count(correct_text) == 1


def test_order_steps_game_never_emits_empty_step():
    slide = CourseSlide(index=0, title="", body="")
    game = build_order_steps_game(slide)
    assert all(s.strip() for s in game.payload["steps_correct"])
    assert all(s.strip() for s in game.payload["steps_shown"])


def test_come_back_later_does_not_complete_unfinished_slide(tmp_path):
    from theodore_course_studio.teach import TeachEngine

    builder = CourseBuilder(data_dir=tmp_path)
    engine = TeachEngine(builder)
    course = _mini_course(builder)
    started = engine.start(session_id="s-audit", course_id=course.course_id)
    assert started["path_pos"] == 0
    engine.come_back_later("s-audit")
    session = engine._sessions.get("s-audit")
    # Session is popped on pause; check the persisted checkpoint instead.
    assert session is None
    from theodore_course_studio.checkpoints import CheckpointStore

    store = CheckpointStore(builder.data_dir)
    cp = store.load("learner-demo", course.course_id)
    assert cp is not None
    assert 0 not in cp.completed_slide_indexes


def test_current_poll_does_not_grow_history(tmp_path):
    from theodore_course_studio.teach import TeachEngine

    builder = CourseBuilder(data_dir=tmp_path)
    engine = TeachEngine(builder)
    course = _mini_course(builder)
    engine.start(session_id="s-audit2", course_id=course.course_id)
    engine.current("s-audit2")
    engine.current("s-audit2")
    engine.current("s-audit2")
    session = engine._sessions["s-audit2"]
    assert len(session.history) <= 2  # start + at most one distinct slide turn


def test_game_grade_bad_payloads_are_422_not_500():
    from fastapi.testclient import TestClient

    from theodore_course_studio.main import _builder, app

    client = TestClient(app, raise_server_exceptions=False)
    course = _mini_course(_builder)
    started = client.post("/api/studio/teach/start", json={
        "session_id": "s-grade-audit", "course_id": course.course_id,
    })
    assert started.status_code == 200, started.text

    for body in (
        {"session_id": "s-grade-audit", "challenge": {}, "response": {}},
        {"session_id": "s-grade-audit", "response": {"selected_index": None}},
        {"session_id": "s-grade-audit", "response": {"selected_index": "abc"}},
    ):
        out = client.post("/api/studio/teach/game-grade", json=body)
        assert out.status_code in (400, 422), (out.status_code, out.text)


def _mini_course(builder: CourseBuilder):
    from theodore_course_studio.types import StudioCourse

    course = StudioCourse(
        course_id="audit-mini",
        title="Audit Mini",
        category="other",
        slides=[
            CourseSlide(index=0, title="One", body="First body."),
            CourseSlide(index=1, title="Two", body="Second body."),
        ],
    )
    builder.save_course(course)
    return course
