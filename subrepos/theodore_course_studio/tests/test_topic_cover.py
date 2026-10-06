"""Live conversation can open any course section and still track coverage."""

from __future__ import annotations

from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.teach import TeachEngine
from theodore_course_studio.topic_cover import example_lines, match_slide
from theodore_course_studio.types import CourseSlide, StudioCourse


def _course(builder: CourseBuilder) -> StudioCourse:
    course = StudioCourse(
        course_id="topic-course",
        title="Road rules",
        category="other",
        slides=[
            CourseSlide(index=0, title="Following distance", body="Leave space behind the car ahead."),
            CourseSlide(
                index=1,
                title="Stop signs",
                body="Come to a full stop.",
                examples=["Count one-two-three before you go."],
            ),
            CourseSlide(index=2, title="Night driving", body="Use low beams around other cars."),
        ],
    )
    builder.save_course(course)
    return course


def test_match_finds_a_later_section():
    course = StudioCourse(
        course_id="match-only",
        title="Road rules",
        category="other",
        slides=[
            CourseSlide(index=0, title="Following distance", body="Leave space behind the car ahead."),
            CourseSlide(index=1, title="Stop signs", body="Come to a full stop."),
        ],
    )
    assert match_slide(course, "Tell me about stop signs") == 1
    assert match_slide(course, "hello there") is None


def test_example_lines_use_the_slide_when_none_are_authored():
    slide = CourseSlide(index=0, title="Night driving", body="Use low beams around other cars.")
    assert example_lines(slide) == ["Use low beams around other cars."]


def test_topic_jump_covers_out_of_order_and_counts_percent(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path)
    engine = TeachEngine(builder)
    course = _course(builder)
    engine.start(session_id="topic-1", course_id=course.course_id, use_voice_agent=False)
    jumped = engine.cover_topic("topic-1", "How do stop signs work?")
    assert jumped["matched"] is True
    assert jumped["slide_index"] == 1
    assert jumped["progress"]["completion_percent"] == 33
    assert jumped["topic_examples"] == ["Count one-two-three before you go."]
    assert "Count one-two-three" in jumped["example_svg"]

    plain = engine.cover_topic("topic-1", "What about night driving?")
    assert plain["slide_index"] == 2
    assert plain["progress"]["completion_percent"] == 67
    assert plain["example_svg"].startswith("<svg")
    assert "low beams" in plain["example_svg"]

    missed = engine.cover_topic("topic-1", "What is the weather?")
    assert missed["matched"] is False
    assert missed["slide_index"] == 2


def test_silence_resumes_the_uncovered_section(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path)
    engine = TeachEngine(builder)
    course = _course(builder)
    engine.start(session_id="topic-2", course_id=course.course_id, use_voice_agent=False)
    engine.cover_topic("topic-2", "stop signs")
    resumed = engine.resume_uncovered("topic-2")
    assert resumed["resumed_uncovered"] is True
    assert resumed["slide_index"] == 2
    assert resumed["course_complete"] is False
    engine.cover_topic("topic-2", "night driving")
    wrapped = engine.resume_uncovered("topic-2")
    assert wrapped["slide_index"] == 0
    engine._sessions["topic-2"].completed_slide_indexes = [0, 1, 2]
    done = engine.resume_uncovered("topic-2")
    assert done["course_complete"] is True
