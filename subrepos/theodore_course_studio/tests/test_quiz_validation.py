"""Quiz integrity: one correct answer, real distractors, varied order, explained."""

from __future__ import annotations

from collections import Counter

from theodore_course_studio import cert_multimodal
from theodore_course_studio.assessment import (
    QuizQuestion,
    arrange_choices,
    build_pop_quiz_for_slide,
    quiz_problems,
)
from theodore_course_studio.cert_multimodal import (
    attach_kit_fields,
    game_from_slide,
    narration_with_examples,
    quiz_from_slide,
)
from theodore_course_studio.knowledge import LearningObjective
from theodore_course_studio.types import CourseSlide

OBJECTIVE = LearningObjective(objective_id="o1", course_id="c1", title="t")


def _curated_quizzes() -> list[tuple[str, QuizQuestion, cert_multimodal.SegmentKit]]:
    out = []
    for i, (key, kit) in enumerate(sorted(cert_multimodal._KITS.items())):
        slide = attach_kit_fields(
            CourseSlide(index=i % 50, slide_key=key, title=key, body="Body."), kit
        )
        quiz = quiz_from_slide(slide, OBJECTIVE)
        assert quiz is not None, key
        out.append((key, quiz, kit))
    return out


def test_every_curated_quiz_is_structurally_valid():
    bad = {key: quiz_problems(q) for key, q, _ in _curated_quizzes() if quiz_problems(q)}
    assert not bad, bad


def test_curated_answer_is_the_authored_answer_after_shuffle():
    for key, quiz, kit in _curated_quizzes():
        expected = kit.quiz_choices[kit.quiz_correct_index].strip()
        assert quiz.choices[quiz.correct_index] == expected, key
        assert quiz.choices.count(expected) == 1, key


def test_correct_answer_position_is_mixed_not_always_first():
    positions = Counter(q.correct_index for _, q, _ in _curated_quizzes())
    assert len(positions) >= 3, positions
    assert max(positions.values()) / sum(positions.values()) < 0.5, positions


def test_curated_match_games_also_shuffle_the_answer():
    positions = Counter()
    for i, (key, kit) in enumerate(sorted(cert_multimodal._KITS.items())):
        slide = attach_kit_fields(
            CourseSlide(index=i % 50, slide_key=key, title=key, body="Body."), kit
        )
        game = game_from_slide(slide)
        if game is None or "options" not in game.payload:
            continue
        options = game.payload["options"]
        idx = game.payload["correct_index"]
        assert options[idx] == kit.game_options[kit.game_correct_index].strip(), key
        positions[idx] += 1
    assert len(positions) >= 2, positions


def test_arrange_is_deterministic_per_seed():
    choices = ["right", "wrong a", "wrong b", "wrong c"]
    assert arrange_choices(choices, 0, "s") == arrange_choices(choices, 0, "s")


def test_all_of_the_above_as_answer_is_pinned_last():
    choices = ["All of the above", "Fact one", "Fact two", "Fact three"]
    arranged, idx = arrange_choices(choices, 0, "seed")
    assert arranged[-1] == "All of the above"
    assert idx == len(arranged) - 1
    q = QuizQuestion(
        question_id="q", objective_id="o", prompt="p",
        choices=arranged, correct_index=idx, explanation="All three are true.",
    )
    assert quiz_problems(q) == []


def test_all_of_the_above_distractor_stays_last_and_single():
    choices = ["Right", "Wrong", "All of the above", "none of the above", "Also wrong"]
    for seed in ("a", "b", "c", "d"):
        arranged, idx = arrange_choices(choices, 0, seed)
        assert arranged[idx] == "Right"
        positional = [c for c in arranged if "above" in c.lower()]
        assert positional == [arranged[-1]]


def test_duplicate_of_the_answer_cannot_be_a_second_correct_slot():
    arranged, idx = arrange_choices(["Stop", "stop ", "Go", "Yield"], 0, "x")
    assert [c.casefold().strip() for c in arranged].count("stop") == 1
    assert arranged[idx] == "Stop"


def test_fallback_pop_quiz_is_valid_and_explained():
    slide = CourseSlide(
        index=3, title="Following distance",
        body="Keep three seconds behind the car ahead. Add time in rain.",
    )
    quiz = build_pop_quiz_for_slide(slide, OBJECTIVE)
    assert quiz_problems(quiz) == []
    assert "Keep three seconds" in quiz.explanation


def test_regular_slide_narration_does_not_promise_a_quiz_or_game():
    said = [
        narration_with_examples(f"Rule number {i}.", ("ex",), "en") for i in range(40)
    ]
    forbidden = ("lock it in", "quiz", "game", "practice check")
    assert not any(word in s.lower() for s in said for word in forbidden)
    assert narration_with_examples("Same.", ("ex",), "en") == narration_with_examples(
        "Same.", ("ex",), "en"
    )
