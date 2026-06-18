"""Homework generation (Phase 6).

Builds an assignment (MCQ + short-answer + an essay prompt) from curriculum
passages, reusing the assessment item generator. Deterministic/offline; an LLM
can author richer items behind the same shapes in production.
"""

from __future__ import annotations

from typing import List, Sequence

from ..adaptive import Difficulty
from ..assessment import definition_items_from_passages
from .models import Assignment, Question, QuestionType


def _split(passage: str):
    if ":" in passage:
        term, body = passage.split(":", 1)
        return term.strip(), body.strip()
    return None


def generate_assignment(
    passages: Sequence[str],
    *,
    title: str,
    subject: str = "general",
    source: str = "",
    num_questions: int = 4,
    difficulty: Difficulty = Difficulty.MEDIUM,
) -> Assignment:
    questions: List[Question] = []

    # MCQs from the assessment generator (definition checks).
    mcqs = definition_items_from_passages(
        list(passages), subject, max_items=max(1, num_questions // 2), difficulty=difficulty
    )
    for item in mcqs:
        questions.append(Question(
            type=QuestionType.MCQ, topic=item.topic, prompt=item.prompt,
            options=item.options, answer_index=item.answer_index, difficulty=difficulty,
        ))

    # Short-answer questions from term/definition passages.
    for passage in passages:
        if len(questions) >= num_questions:
            break
        parsed = _split(passage)
        if not parsed:
            continue
        term, definition = parsed
        questions.append(Question(
            type=QuestionType.SHORT, topic=term,
            prompt=f"In your own words, explain: {term}.",
            answer_key=definition,
            rubric=["mentions the key idea", "accurate", "in the student's own words"],
            difficulty=difficulty,
        ))

    # One essay prompt to round it out.
    if passages:
        questions.append(Question(
            type=QuestionType.ESSAY, topic=subject,
            prompt=f"Write a short paragraph connecting the key ideas in this {subject} lesson.",
            rubric=["covers >=2 concepts", "coherent", "uses correct terminology"],
            difficulty=difficulty,
        ))

    return Assignment(title=title, subject=subject, source=source, questions=questions)


def assignment_from_slides(slides, *, title: str, subject: str = "general",
                           source: str = "", num_questions: int = 4) -> Assignment:
    """slides: objects/dicts with .title/.body (or ['title']/['body'])."""
    passages = []
    for s in slides:
        st = getattr(s, "title", None) if not isinstance(s, dict) else s.get("title")
        sb = getattr(s, "body", None) if not isinstance(s, dict) else s.get("body")
        if st:
            passages.append(f"{st}: {sb or ''}")
    return generate_assignment(passages, title=title, subject=subject, source=source,
                               num_questions=num_questions)
