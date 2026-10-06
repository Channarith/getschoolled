"""Pop quizzes, summary quizzes, and pass criteria."""

from __future__ import annotations

import random
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


_ALL_ABOVE_RE = re.compile(r"^\s*(all|both) of (the )?(above|these)\W*$", re.IGNORECASE)
_NONE_ABOVE_RE = re.compile(r"^\s*(none|neither) of (the )?(above|these)\W*$", re.IGNORECASE)


def is_all_of_the_above(choice: str) -> bool:
    return bool(_ALL_ABOVE_RE.match(choice or ""))


def _is_positional(choice: str) -> bool:
    """Choices whose meaning depends on the others, so they must sit last."""
    return is_all_of_the_above(choice) or bool(_NONE_ABOVE_RE.match(choice or ""))


def _choice_key(choice: str) -> str:
    return re.sub(r"\s+", " ", (choice or "").strip()).casefold()


def arrange_choices(
    choices: list[str],
    correct_index: int,
    seed: str,
    max_choices: int = 0,
) -> tuple[list[str], int]:
    """Exactly one correct answer, real distractors, shuffled per question.

    Duplicates of the answer are dropped so only one slot can be correct. An
    "all/none of the above" option is only meaningful at the end, so at most
    one is kept and it is pinned last; the rest are shuffled deterministically
    so cached narration and retries see the same order.
    """
    if not choices:
        return [], 0
    correct_index = max(0, min(int(correct_index), len(choices) - 1))
    correct = choices[correct_index].strip()
    seen = {_choice_key(correct)}
    content: list[str] = []
    positional: list[str] = []
    for i, raw in enumerate(choices):
        choice = (raw or "").strip()
        key = _choice_key(choice)
        if i == correct_index or not key or key in seen:
            continue
        seen.add(key)
        (positional if _is_positional(choice) else content).append(choice)

    if max_choices:
        reserved = 1 + (1 if positional and not _is_positional(correct) else 0)
        content = content[: max(1, max_choices - reserved)]
    rng = random.Random(seed)
    rng.shuffle(content)
    if _is_positional(correct):
        arranged = content + [correct]
    else:
        pos = rng.randrange(len(content) + 1)
        arranged = content[:pos] + [correct] + content[pos:]
        if positional:
            arranged.append(positional[0])
    return arranged, arranged.index(correct)


def quiz_problems(question: QuizQuestion) -> list[str]:
    """Structural checks every learner-facing question must pass."""
    problems: list[str] = []
    choices = question.choices
    if len(choices) < 2:
        problems.append("fewer than two choices")
    if not 0 <= question.correct_index < len(choices):
        problems.append("correct_index out of range")
        return problems
    keys = [_choice_key(c) for c in choices]
    if len(set(keys)) != len(keys):
        problems.append("duplicate choices")
    positional = [i for i, c in enumerate(choices) if _is_positional(c)]
    if len(positional) > 1:
        problems.append("more than one all/none-of-the-above option")
    if positional and positional[-1] != len(choices) - 1:
        problems.append("all/none-of-the-above is not the last option")
    if is_all_of_the_above(choices[question.correct_index]) and len(choices) < 3:
        problems.append("all-of-the-above needs at least two statements above it")
    if not question.explanation.strip():
        problems.append("missing explanation")
    return problems


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
    choices, correct_index = arrange_choices(
        [correct, *distractors, f"Unrelated idea about {slide.title}"],
        0,
        seed=f"{slide.slide_key or slide.title}|{slide.index}",
        max_choices=4,
    )
    return QuizQuestion(
        question_id=str(uuid.uuid4()),
        objective_id=objective.objective_id,
        prompt=f"Pop check — which statement best matches “{slide.title}”?",
        choices=choices,
        correct_index=correct_index,
        kind="pop",
        explanation=f"The slide on “{slide.title}” teaches: {correct}",
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
