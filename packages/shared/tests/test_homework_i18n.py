"""Homework generator localizes prompts + rubrics into the student's UI language.

The orchestrator passes locale=<student-ui-language> when invoking
the (internal-only) /homework/generate endpoint, so the student
sees the question in their native language even though the AI
teacher agent is operating server-side.
"""

from __future__ import annotations

import pytest

from aoep_shared.homework.generate import (
    SUPPORTED_HOMEWORK_LOCALES, generate_assignment,
)


PASSAGES = [
    "Photosynthesis: plants turn sunlight, water, and CO2 into sugar.",
    "Mitochondria: the powerhouse of the cell - they generate ATP.",
]


def test_vietnamese_is_a_supported_homework_locale():
    assert "vi" in SUPPORTED_HOMEWORK_LOCALES


def test_khmer_is_a_supported_homework_locale():
    # Brand requirement (Salareen).
    assert "km" in SUPPORTED_HOMEWORK_LOCALES


def test_english_assignment_uses_english_prompts():
    a = generate_assignment(PASSAGES, title="HW", subject="biology", locale="en")
    short = [q for q in a.questions if q.type.value == "short"]
    assert short
    assert "In your own words, explain:" in short[0].prompt


@pytest.mark.parametrize("locale,marker", [
    ("vi", "lời của em"),         # Vietnamese: "Hãy dùng lời của em…"
    ("es", "tus propias palabras"),  # "Con tus propias palabras…"
    ("fr", "propres mots"),       # "Avec tes propres mots…"
    ("de", "eigenen Worten"),     # "Erkläre in eigenen Worten…"
    ("ja", "自分の言葉"),         # "自分の言葉で説明してください"
    ("zh", "你自己的话"),         # "用你自己的话解释…"
    ("ko", "자신의 말로"),        # "자신의 말로 설명하세요"
    ("ar", "بأسلوبك"),            # "بأسلوبك، اشرح:"
])
def test_short_answer_prompt_localizes(locale, marker):
    a = generate_assignment(PASSAGES, title="HW", subject="biology", locale=locale)
    short = [q for q in a.questions if q.type.value == "short"]
    assert short, f"no short-answer questions in {locale} run"
    assert any(marker in q.prompt for q in short), \
        f"{locale}: marker '{marker}' missing from prompts: {[q.prompt for q in short]}"


def test_vietnamese_essay_prompt_localizes():
    a = generate_assignment(PASSAGES, title="HW", subject="sinh học", locale="vi")
    essays = [q for q in a.questions if q.type.value == "essay"]
    assert essays
    assert "đoạn ngắn" in essays[0].prompt or "ý chính" in essays[0].prompt
    # Subject placeholder substituted.
    assert "sinh học" in essays[0].prompt


def test_vietnamese_rubrics_localized():
    a = generate_assignment(PASSAGES, title="HW", subject="biology", locale="vi")
    short = [q for q in a.questions if q.type.value == "short"][0]
    # Vietnamese rubric markers.
    assert "ý chính" in short.rubric[0]
    assert "chính xác" in short.rubric[1]
    essays = [q for q in a.questions if q.type.value == "essay"]
    if essays:
        assert any("khái niệm" in r for r in essays[0].rubric)


def test_unknown_locale_falls_back_to_english():
    a = generate_assignment(PASSAGES, title="HW", subject="biology", locale="xx-YY")
    short = [q for q in a.questions if q.type.value == "short"]
    assert short and "In your own words, explain:" in short[0].prompt


def test_locale_normalisation_strips_region():
    a_full = generate_assignment(PASSAGES, title="HW", subject="x", locale="vi-VN")
    a_base = generate_assignment(PASSAGES, title="HW", subject="x", locale="vi")
    sf = next(q for q in a_full.questions if q.type.value == "short").prompt
    sb = next(q for q in a_base.questions if q.type.value == "short").prompt
    assert sf == sb
