"""Harvested material is split into ~15-20 min lessons instead of one huge deck."""

from __future__ import annotations

import math

from aoep_shared.harvest.generate import (
    HARD_MAX_SLIDES_PER_LESSON,
    MAX_SLIDES_PER_LESSON,
    GeneratedCourse,
    GeneratedSlide,
    partition_course_into_lessons,
)


def _course(n_slides: int, *, course_id: str = "abc123", title: str = "Big Course") -> GeneratedCourse:
    slides = [
        GeneratedSlide(
            title=f"Section {i}",
            body=f"Body for section {i}.",
            narration=f"Narration {i}.",
            category="concept",
        )
        for i in range(n_slides)
    ]
    return GeneratedCourse(
        course_id=course_id, title=title, subject="history", language="en",
        source="file://x", fmt="lecture", slides=slides,
    )


def test_small_course_is_single_lesson_unchanged():
    course = _course(12)
    lessons = partition_course_into_lessons(course, max_slides=20)
    assert len(lessons) == 1
    assert lessons[0] is course
    assert lessons[0].lesson_index == 1 and lessons[0].lesson_count == 1
    assert lessons[0].title == "Big Course"


def test_exactly_at_cap_is_single_lesson():
    lessons = partition_course_into_lessons(_course(20), max_slides=20)
    assert len(lessons) == 1


def test_oversized_course_is_partitioned():
    lessons = partition_course_into_lessons(_course(1000), max_slides=20)
    assert len(lessons) == 50
    # No lesson exceeds the cap; slides are conserved; lessons are balanced.
    assert all(len(l.slides) <= 20 for l in lessons)
    assert sum(len(l.slides) for l in lessons) == 1000
    assert all(l.lesson_count == 50 for l in lessons)
    assert [l.lesson_index for l in lessons] == list(range(1, 51))
    assert lessons[0].title == "Big Course — Lesson 1 of 50"
    assert lessons[-1].title == "Big Course — Lesson 50 of 50"
    # Distinct course ids so each lesson is its own catalog entry.
    assert len({l.course_id for l in lessons}) == 50


def test_partition_is_balanced_no_tiny_stub():
    # 43 slides / 20 -> 3 lessons, balanced 15/14/14 (never 20/20/3).
    lessons = partition_course_into_lessons(_course(43), max_slides=20)
    assert len(lessons) == 3
    sizes = sorted(len(l.slides) for l in lessons)
    assert sizes == [14, 14, 15]
    assert max(sizes) - min(sizes) <= 1


def test_cap_is_clamped_to_hard_max():
    # Asking for a huge cap still splits at the hard ceiling.
    lessons = partition_course_into_lessons(_course(200), max_slides=10_000)
    expected = math.ceil(200 / HARD_MAX_SLIDES_PER_LESSON)
    assert len(lessons) == expected
    assert all(len(l.slides) <= HARD_MAX_SLIDES_PER_LESSON for l in lessons)


def test_each_lesson_rebuilds_composition():
    lessons = partition_course_into_lessons(_course(45), max_slides=20)
    for lesson in lessons:
        assert lesson.composition is not None
        assert lesson.composition.course_id == lesson.course_id


def test_default_cap_is_twelve():
    assert MAX_SLIDES_PER_LESSON == 12
    lessons = partition_course_into_lessons(_course(13))
    assert len(lessons) == 2
