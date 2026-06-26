"""Course complexity and finish-pace helpers."""

from aoep_shared.course_complexity import (
    complexity_score,
    expected_minutes_from_slides,
    finish_pace_label,
    infer_lesson_complexity,
)


def test_complexity_score_from_level_and_maturity():
    assert complexity_score(level="beginner", maturity="kids") <= 2
    assert complexity_score(level="advanced", maturity="mature") >= 4


def test_explicit_complexity_overrides():
    assert complexity_score(level="advanced", explicit=2) == 2


def test_infer_fractions_lesson_is_simple():
    assert infer_lesson_complexity("intro-to-fractions") == 1


def test_finish_pace_labels():
    assert finish_pace_label(10, 25) == "fast"
    assert finish_pace_label(25, 25) == "on_track"
    assert finish_pace_label(40, 25) == "slow"


def test_expected_minutes_from_slides():
    assert expected_minutes_from_slides(5) == 20
    assert expected_minutes_from_slides(20) == 40
