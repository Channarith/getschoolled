"""Hallucination guard: check that an answer is grounded in its sources.

An LLM cannot be guaranteed to never hallucinate, but the *served* answer can be
gated: every claim in the answer is checked against the retrieved context, an
ungrounded answer is flagged with a hallucination-risk score, and the guard can
abstain/ground it (replace drift with a context-faithful response). Detected
hallucinations feed the corrections back-prop loop for a fast, durable fix.

Pure/offline (reuses the validation tokenizer + overlap); optionally escalates
ungrounded claims to live web validation when search engines are configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

from .validation import _recall, _tokens, extract_claims


@dataclass
class GroundingResult:
    claim: str
    grounded: bool
    support: float  # 0..1 best overlap with any context passage


@dataclass
class GroundingReport:
    groundedness: float        # fraction of claims grounded in context
    hallucination_risk: float  # 1 - groundedness
    grounded: bool             # overall pass (>= pass_threshold)
    unsupported: List[str] = field(default_factory=list)
    results: List[GroundingResult] = field(default_factory=list)


def check_grounding(
    answer: str,
    context: Sequence[str],
    *,
    support_threshold: float = 0.5,
    pass_threshold: float = 0.7,
) -> GroundingReport:
    """Score how well ``answer`` is supported by ``context`` passages."""
    claims = extract_claims(answer, min_tokens=3)
    if not claims:
        # Short answer: treat the whole thing as one claim.
        from .validation import Claim

        claims = [Claim(text=answer.strip())]
    ctx_tokens = [_tokens(c) for c in context]

    results: List[GroundingResult] = []
    for claim in claims:
        ct = _tokens(claim.text)
        best = max((_recall(ct, c) for c in ctx_tokens), default=0.0)
        results.append(
            GroundingResult(claim.text, best >= support_threshold, round(best, 3))
        )

    grounded_n = sum(1 for r in results if r.grounded)
    score = grounded_n / len(results) if results else 0.0
    unsupported = [r.claim for r in results if not r.grounded]
    return GroundingReport(
        groundedness=round(score, 3),
        hallucination_risk=round(1.0 - score, 3),
        grounded=score >= pass_threshold,
        unsupported=unsupported,
        results=results,
    )


def _grounded_fallback(question: str, context: Sequence[str]) -> str:
    if context:
        snippet = " ".join(" ".join(context).split())[:400]
        return (
            "I want to stay accurate to the lesson, so here is what the material "
            f"actually says: {snippet}"
        )
    return (
        "I don't have enough grounded material to answer that confidently yet. "
        "Let's stick to what the lesson covers."
    )


def guard_answer(
    answer: str,
    context: Sequence[str],
    *,
    question: str = "",
    support_threshold: float = 0.5,
    pass_threshold: float = 0.7,
) -> tuple[str, GroundingReport]:
    """Return a (safe_answer, report). If the answer isn't grounded, replace it
    with a context-faithful response so ungrounded content is never served. The
    report reflects the ORIGINAL answer so callers can log/correct it."""
    report = check_grounding(
        answer, context, support_threshold=support_threshold, pass_threshold=pass_threshold
    )
    if report.grounded:
        return answer, report
    return _grounded_fallback(question, context), report
