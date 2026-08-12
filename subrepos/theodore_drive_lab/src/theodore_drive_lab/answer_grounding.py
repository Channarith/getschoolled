"""Segment Q&A grounding harness for Drive Mode answers."""

from __future__ import annotations

import re
from typing import List, Sequence

from .drive_tuning import DriveTuning
from .wake_eval import token_set


def answer_from_segments(
    question: str,
    segments: Sequence[str],
    *,
    top_k: int = 3,
) -> str:
    """Lexical Drive-style answer: pick best overlapping course segments."""
    q = token_set(question)
    if not q or not segments:
        return ""
    scored = []
    for seg in segments:
        s = token_set(seg)
        if not s:
            continue
        score = len(q & s) / len(q | s)
        scored.append((score, seg))
    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [seg for score, seg in scored[: max(1, top_k)] if score > 0]
    if not picked:
        return ""
    # Return first sentence-ish of best segment.
    best = picked[0].strip()
    parts = re.split(r"(?<=[.!?])\s+", best)
    return parts[0] if parts else best


def score_answer(question: str, answer: str, segments: Sequence[str], tuning: DriveTuning) -> dict:
    generated = answer_from_segments(
        question, segments, top_k=tuning.answer_top_segments
    )
    ref = token_set(answer or generated)
    gen = token_set(generated)
    overlap = (len(ref & gen) / len(ref | gen)) if ref and gen else 0.0
    grounded = overlap >= tuning.answer_min_overlap and bool(generated)
    return {
        "question": question,
        "generated": generated,
        "overlap": round(overlap, 4),
        "grounded": grounded,
    }


DEFAULT_SEGMENTS = [
    "Photosynthesis lets plants convert sunlight into chemical energy in chloroplasts.",
    "Gravity is the force that pulls objects toward the earth.",
    "In Python, variables hold values with types like int, str, list, and dict.",
    "A fraction has a numerator above and a denominator below the line.",
    "When demand rises and supply stays fixed, market prices tend to increase.",
]

DEFAULT_QA = [
    ("how do plants use sunlight", "Photosynthesis lets plants convert sunlight into chemical energy in chloroplasts."),
    ("what is gravity", "Gravity is the force that pulls objects toward the earth."),
    ("python variable types", "In Python, variables hold values with types like int, str, list, and dict."),
]


def evaluate_answers(
    pairs: Sequence[tuple[str, str]] | None = None,
    segments: Sequence[str] | None = None,
    tuning: DriveTuning | None = None,
) -> dict:
    tuning = tuning or DriveTuning()
    pairs = list(pairs or DEFAULT_QA)
    segments = list(segments or DEFAULT_SEGMENTS)
    rows = [score_answer(q, a, segments, tuning) for q, a in pairs]
    grounded_n = sum(1 for r in rows if r["grounded"])
    avg_overlap = sum(r["overlap"] for r in rows) / max(1, len(rows))
    return {
        "n": len(rows),
        "grounded_rate": round(grounded_n / max(1, len(rows)), 4),
        "avg_overlap": round(avg_overlap, 4),
        "answer_quality": round(0.6 * (grounded_n / max(1, len(rows))) + 0.4 * avg_overlap, 4),
        "rows": rows,
    }
