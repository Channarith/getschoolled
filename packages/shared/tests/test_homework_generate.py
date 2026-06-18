"""Homework generation tests (Phase 6)."""

from aoep_shared.homework import QuestionType, assignment_from_slides, generate_assignment

PASSAGES = [
    "Photosynthesis: plants convert light, water, and CO2 into glucose and oxygen.",
    "Respiration: cells release energy from glucose using oxygen.",
    "Chlorophyll: the green pigment that captures light energy.",
]


def test_generate_assignment_has_mixed_question_types():
    a = generate_assignment(PASSAGES, title="Bio HW", subject="biology", num_questions=4)
    types = {q.type for q in a.questions}
    assert QuestionType.MCQ in types
    assert QuestionType.SHORT in types
    assert QuestionType.ESSAY in types
    assert a.subject == "biology"


def test_mcq_has_options_and_key():
    a = generate_assignment(PASSAGES, title="HW", subject="biology")
    mcqs = [q for q in a.questions if q.type == QuestionType.MCQ]
    assert mcqs
    assert all(len(q.options) >= 2 and q.answer_index is not None for q in mcqs)


def test_short_answer_has_key_and_rubric():
    a = generate_assignment(PASSAGES, title="HW")
    shorts = [q for q in a.questions if q.type == QuestionType.SHORT]
    assert shorts
    assert all(q.answer_key and q.rubric for q in shorts)


def test_assignment_from_slides_objects():
    class S:
        def __init__(self, t, b):
            self.title, self.body = t, b

    slides = [S("Photosynthesis", "plants make glucose"), S("Respiration", "cells use glucose")]
    a = assignment_from_slides(slides, title="HW", subject="biology", source="deck:1")
    assert a.source == "deck:1"
    assert len(a.questions) >= 2
