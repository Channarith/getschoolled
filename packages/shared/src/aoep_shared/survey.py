"""End-of-class surveys + multi-dimensional aggregation for data mining.

A small, versioned survey template (rating + multiple-choice + free-text
suggestion) shown once at the end of a class to gauge course quality, plus a
``SurveyStore`` that records responses and rolls them up into a multi-dimensional
("data mart") view sliceable by course, class type, and rating bucket. The
suggestion text is mined into ranked keyword themes to drive course improvement.

Pure/offline + stdlib-only; the memory service holds the store and exposes it
over HTTP, and the post-class survey itself is gated by the
``engagement.post_class_survey`` feature flag.
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

SURVEY_VERSION = "1.0"


@dataclass(frozen=True)
class SurveyQuestion:
    id: str
    type: str            # "rating" | "choice" | "text" | "bool"
    prompt: str
    options: tuple = ()
    required: bool = False


# One-time post-class survey template. Kept short to maximize completion.
POST_CLASS_SURVEY: List[SurveyQuestion] = [
    SurveyQuestion("overall", "rating", "Overall, how would you rate this class?",
                   required=True),
    SurveyQuestion("clarity", "rating", "How clear were the explanations?"),
    SurveyQuestion("pace", "choice", "How was the pace?",
                   options=("too slow", "just right", "too fast")),
    SurveyQuestion("would_recommend", "bool", "Would you recommend this course?"),
    SurveyQuestion("suggestion", "text",
                   "What is one thing we could improve? (optional)"),
]

SURVEY_QUESTIONS_BY_ID = {q.id: q for q in POST_CLASS_SURVEY}

# Lightweight stopword set so suggestion mining surfaces meaningful themes.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "is",
    "it", "this", "that", "was", "were", "be", "more", "less", "with", "i",
    "you", "we", "they", "would", "could", "should", "have", "had", "too",
    "very", "so", "my", "me", "at", "as", "are", "if", "do", "not", "no",
}


class SurveyResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"sr-{int(time.time()*1000)}")
    course_id: str
    class_type: str = "self_paced"
    subject: str = ""
    student_id: Optional[str] = None
    overall: int                      # 1-5, required
    clarity: Optional[int] = None
    pace: Optional[str] = None
    would_recommend: Optional[bool] = None
    suggestion: str = ""
    created_at: float = Field(default_factory=lambda: time.time())


def template() -> Dict:
    return {
        "version": SURVEY_VERSION,
        "title": "Post-class feedback",
        "questions": [
            {"id": q.id, "type": q.type, "prompt": q.prompt,
             "options": list(q.options), "required": q.required}
            for q in POST_CLASS_SURVEY
        ],
    }


def _rating_bucket(score: int) -> str:
    if score >= 4:
        return "promoter"
    if score == 3:
        return "passive"
    return "detractor"


def mine_suggestions(texts: List[str], *, top_n: int = 10) -> List[Dict]:
    """Rank keyword themes from free-text suggestions (data mining)."""
    counter: Counter = Counter()
    for t in texts:
        for word in re.findall(r"[a-zA-Z][a-zA-Z'-]+", t.lower()):
            if len(word) > 2 and word not in _STOPWORDS:
                counter[word] += 1
    return [{"term": w, "count": c} for w, c in counter.most_common(top_n)]


class SurveyStore:
    """Records survey responses and serves multi-dimensional rollups."""

    def __init__(self) -> None:
        self._responses: List[SurveyResponse] = []

    def submit(self, resp: SurveyResponse) -> SurveyResponse:
        if not (1 <= int(resp.overall) <= 5):
            raise ValueError("overall rating must be 1-5")
        self._responses.append(resp)
        return resp

    def count(self) -> int:
        return len(self._responses)

    def for_course(self, course_id: str) -> List[SurveyResponse]:
        return [r for r in self._responses if r.course_id == course_id]

    def course_summary(self, course_id: str) -> Dict:
        rows = self.for_course(course_id)
        if not rows:
            return {"course_id": course_id, "responses": 0}
        overalls = [r.overall for r in rows]
        rec = [r.would_recommend for r in rows if r.would_recommend is not None]
        return {
            "course_id": course_id,
            "responses": len(rows),
            "avg_overall": round(sum(overalls) / len(overalls), 2),
            "nps_like": round(
                100 * (sum(1 for o in overalls if o >= 4) - sum(1 for o in overalls if o <= 2))
                / len(overalls), 1),
            "recommend_rate": round(100 * sum(1 for r in rec if r) / len(rec), 1) if rec else None,
            "top_suggestions": mine_suggestions([r.suggestion for r in rows if r.suggestion]),
        }

    def datamart(self) -> Dict:
        """Multi-dimensional rollup (course x class_type x rating bucket).

        Mirrors an OLAP cube: each cell carries response counts + average rating
        so the data can be sliced/diced for course improvement + data mining.
        """
        cube: Dict[tuple, Dict[str, float]] = defaultdict(lambda: {"n": 0, "sum": 0.0})
        dims_course: Counter = Counter()
        dims_class: Counter = Counter()
        dims_bucket: Counter = Counter()
        for r in self._responses:
            bucket = _rating_bucket(r.overall)
            key = (r.course_id, r.class_type, bucket)
            cube[key]["n"] += 1
            cube[key]["sum"] += r.overall
            dims_course[r.course_id] += 1
            dims_class[r.class_type] += 1
            dims_bucket[bucket] += 1
        cells = [
            {"course_id": c, "class_type": ct, "rating_bucket": b,
             "responses": int(v["n"]), "avg_overall": round(v["sum"] / v["n"], 2)}
            for (c, ct, b), v in cube.items()
        ]
        return {
            "total_responses": len(self._responses),
            "dimensions": {
                "course": dict(dims_course),
                "class_type": dict(dims_class),
                "rating_bucket": dict(dims_bucket),
            },
            "cells": cells,
            "top_suggestions": mine_suggestions(
                [r.suggestion for r in self._responses if r.suggestion]),
        }
