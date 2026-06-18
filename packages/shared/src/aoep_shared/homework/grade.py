"""Homework autograder (Phase 9).

Grades a Submission against an Assignment:
- objective (MCQ): match the student's answer text to the keyed option.
- open (short/essay): correctness by CORROBORATION - the answer's claims are
  checked against (a) our catalog/RAG passages and (b) trusted online sources
  (subject-restricted, e.g. webmd.com for medical) via validate_claim.

Returns per-item verdicts with citations + validity flags (validity combines
on-topic correctness with the authorship signal). Pure/offline-testable with a
MockSearchProvider + supplied context passages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from ..providers.base import SearchProvider
from ..validation import _recall, _tokens, validate_claim
from .authorship import AuthorshipVerdict
from .models import Assignment, Question, QuestionType
from .sources import restrict_to_domains, trusted_domains_for


@dataclass
class ItemGrade:
    question_id: str
    type: str
    correct: Optional[bool]
    score: float
    citations: List[dict] = field(default_factory=list)
    rationale: str = ""


@dataclass
class HomeworkGrade:
    score: float
    max_score: float
    percentage: float
    items: List[ItemGrade] = field(default_factory=list)
    validity_flags: List[str] = field(default_factory=list)
    authorship_label: Optional[str] = None


def _supported_by_context(answer: str, passages: Sequence[str], *, threshold: float = 0.4):
    """Best catalog passage supporting the answer (recall of answer tokens)."""
    at = _tokens(answer)
    best, best_p = 0.0, None
    for p in passages:
        ov = _recall(at, _tokens(p))
        if ov > best:
            best, best_p = ov, p
    return (best >= threshold), best, best_p


def _grade_mcq(q: Question, answer: str) -> ItemGrade:
    if not q.options:
        return ItemGrade(q.question_id, q.type.value, None, 0.0, rationale="no options")
    at = _tokens(answer)
    scores = [_recall(_tokens(opt), at) + _recall(at, _tokens(opt)) for opt in q.options]
    chosen = max(range(len(q.options)), key=lambda i: scores[i]) if any(scores) else None
    correct = chosen == q.answer_index
    return ItemGrade(
        q.question_id, q.type.value, correct, 1.0 if correct else 0.0,
        rationale=f"chose option {chosen}, key {q.answer_index}",
    )


def _grade_open(
    q: Question, answer: str, *, engines: Sequence[SearchProvider],
    passages: Sequence[str], subject: str,
) -> ItemGrade:
    citations: List[dict] = []
    # 1) Catalog/RAG corroboration.
    ctx_ok, ctx_overlap, ctx_passage = _supported_by_context(answer, passages)
    if ctx_passage and ctx_overlap > 0:
        citations.append({"source": "catalog", "overlap": round(ctx_overlap, 3),
                          "snippet": ctx_passage[:160]})
    # 2) Trusted online corroboration (subject-restricted).
    web_ok = False
    if engines and answer.strip():
        domains = trusted_domains_for(subject)
        verdict = validate_claim(answer, engines)
        trusted_cites = restrict_to_domains(verdict.citations, domains)
        web_ok = verdict.status == "supported" and (bool(trusted_cites) or not domains)
        for c in trusted_cites[:3]:
            citations.append({"source": c.engine, "url": c.url, "overlap": c.overlap})

    # 3) Answer-key overlap (short answers carry a reference key).
    key_ok = False
    if q.answer_key:
        key_ok = _recall(_tokens(q.answer_key), _tokens(answer)) >= 0.5

    supported = ctx_ok or web_ok or key_ok
    partial = (ctx_overlap >= 0.2) or bool(citations)
    score = 1.0 if supported else (0.5 if partial else 0.0)
    correct = True if supported else (None if partial else False)
    rationale = f"catalog={ctx_ok}, web={web_ok}, key={key_ok}"
    return ItemGrade(q.question_id, q.type.value, correct, score, citations=citations,
                     rationale=rationale)


def grade_submission(
    assignment: Assignment,
    answers: Sequence[str],
    *,
    engines: Optional[Sequence[SearchProvider]] = None,
    context_passages: Optional[Sequence[str]] = None,
    subject: Optional[str] = None,
    authorship: Optional[AuthorshipVerdict] = None,
) -> HomeworkGrade:
    engines = engines or []
    passages = context_passages or []
    subject = subject or assignment.subject
    items: List[ItemGrade] = []

    for i, q in enumerate(assignment.questions):
        answer = answers[i] if i < len(answers) else ""
        if q.type is QuestionType.MCQ:
            items.append(_grade_mcq(q, answer))
        else:
            items.append(_grade_open(q, answer, engines=engines, passages=passages, subject=subject))

    max_score = float(len(items))
    score = sum(it.score for it in items)
    pct = round(100.0 * score / max_score, 1) if max_score else 0.0

    flags: List[str] = []
    if authorship and authorship.label == "ai":
        flags.append("possible_ai_authorship")
    if any(it.correct is False for it in items):
        flags.append("incorrect_answers")
    if any(it.correct is None for it in items):
        flags.append("needs_human_review")

    return HomeworkGrade(
        score=round(score, 2), max_score=max_score, percentage=pct, items=items,
        validity_flags=flags, authorship_label=authorship.label if authorship else None,
    )
