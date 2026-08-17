"""Pop quizzes, summary quizzes, and pass criteria."""

from __future__ import annotations

import re
import uuid

from pydantic import BaseModel, Field

from .knowledge import LearningObjective
from .types import CourseSlide


class QuizQuestion(BaseModel):
    question_id: str
    objective_id: str
    prompt: str
    choices: list[str] = Field(default_factory=list)
    correct_index: int = 0
    kind: str = "pop"
    explanation: str = ""


class QuizAttempt(BaseModel):
    question_id: str
    selected_index: int
    correct: bool
    objective_id: str = ""


class QuizResult(BaseModel):
    quiz_id: str
    kind: str
    total: int
    correct: int
    pass_threshold: float
    passed: bool
    attempts: list[QuizAttempt] = Field(default_factory=list)
    weak_objective_ids: list[str] = Field(default_factory=list)


class GeneratedQuiz(BaseModel):
    quiz_id: str
    kind: str
    questions: list[QuizQuestion] = Field(default_factory=list)


def _stem_choice(text: str) -> str:
    s = re.sub(r"\s+", " ", (text or "").strip())
    if len(s) > 140:
        s = s[:137].rstrip() + "…"
    return s or "Review the material"


def build_pop_quiz_for_slide(
    slide: CourseSlide,
    objective: LearningObjective,
) -> QuizQuestion:
    """One quick check tied to the current learning point."""
    try:
        from .cert_multimodal import quiz_from_slide

        curated = quiz_from_slide(slide, objective)
        if curated is not None:
            return curated
    except Exception:
        pass
    body = (slide.body or objective.description or slide.title or "").strip()
    # Prefer the rule text before the Examples block when present.
    rule = body.split("\nExamples:", 1)[0].strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", rule) if s.strip()]
    correct = _stem_choice(sentences[0] if sentences else slide.title)
    distractors = [
        _stem_choice(sentences[1])
        if len(sentences) > 1
        else f"Unrelated idea about {slide.title}",
        "This topic is optional and can be skipped entirely.",
        f"The opposite of: {slide.title}",
    ]
    # Dedupe by text: if a distractor equals the correct sentence (duplicate
    # sentences in the slide, or a fixed distractor string colliding),
    # choices.index(correct) after rotation could point at the distractor's
    # slot — the identical correct text at the other position graded wrong.
    seen: set[str] = set()
    unique_choices: list[str] = []
    for choice in [correct, distractors[0], distractors[1], distractors[2]]:
        key = choice.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique_choices.append(choice)
    if len(unique_choices) < 2:
        unique_choices.append(f"Unrelated idea about {slide.title}")
    rot = slide.index % len(unique_choices)
    choices = unique_choices[rot:] + unique_choices[:rot]
    correct_index = choices.index(correct)
    return QuizQuestion(
        question_id=str(uuid.uuid4()),
        objective_id=objective.objective_id,
        prompt=f"Pop check — which statement best matches “{slide.title}”?",
        choices=choices,
        correct_index=correct_index,
        kind="pop",
        explanation=f"Key learning point: {correct}",
    )


def build_summary_quiz(
    slides: list[CourseSlide],
    objectives: list[LearningObjective],
    max_questions: int = 8,
) -> GeneratedQuiz:
    questions: list[QuizQuestion] = []
    by_slide = {s.index: s for s in slides}
    for obj in objectives:
        if len(questions) >= max_questions:
            break
        slide = None
        for idx in obj.slide_indexes:
            slide = by_slide.get(idx)
            if slide:
                break
        if slide is None:
            continue
        q = build_pop_quiz_for_slide(slide, obj)
        q.kind = "summary"
        q.prompt = f"Summary — what should you remember about “{slide.title}”?"
        questions.append(q)
    return GeneratedQuiz(
        quiz_id=f"summary-{uuid.uuid4().hex[:10]}",
        kind="summary",
        questions=questions,
    )


def grade_quiz(
    *,
    quiz_id: str,
    kind: str,
    questions: list[QuizQuestion],
    answers: dict[str, int],
    pass_threshold: float = 0.7,
) -> QuizResult:
    attempts: list[QuizAttempt] = []
    correct_n = 0
    weak: list[str] = []
    for q in questions:
        selected = int(answers.get(q.question_id, -1))
        ok = selected == q.correct_index
        if ok:
            correct_n += 1
        else:
            if q.objective_id:
                weak.append(q.objective_id)
        attempts.append(
            QuizAttempt(
                question_id=q.question_id,
                selected_index=selected,
                correct=ok,
                objective_id=q.objective_id,
            )
        )
    total = max(len(questions), 1)
    ratio = correct_n / total
    return QuizResult(
        quiz_id=quiz_id,
        kind=kind,
        total=len(questions),
        correct=correct_n,
        pass_threshold=pass_threshold,
        passed=ratio >= pass_threshold,
        attempts=attempts,
        weak_objective_ids=sorted(set(weak)),
    )
