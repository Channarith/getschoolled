"""Short in-lesson pulse surveys (2–3 questions) between content blocks.

Shown intermittently during a live class so we can learn what is working while
the learner is still in context. Responses feed the LX score, strategy bandit,
and course-improvement rollups.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .survey import SurveyQuestion

PULSE_SURVEY_VERSION = "1.0"
PULSE_EVERY_N_SLIDES = 5

PULSE_SURVEY: List[SurveyQuestion] = [
    SurveyQuestion(
        "going_well", "rating",
        "How is this lesson going so far?",
        required=True,
    ),
    SurveyQuestion(
        "pace", "choice",
        "Is the pace right for you?",
        options=("too slow", "just right", "too fast"),
        required=True,
    ),
    SurveyQuestion(
        "working_best", "choice",
        "What's working best for you right now?",
        options=("examples", "explanations", "quizzes", "practice checks", "not sure"),
    ),
]

WORKING_BEST_TO_STRATEGY = {
    "examples": "worked_examples",
    "explanations": "gentle_recap",
    "quizzes": "drill",
    "practice checks": "drill",
}


class PulseSurveyResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"ps-{int(time.time()*1000)}")
    course_id: str
    class_type: str = "group"
    student_id: Optional[str] = None
    slide_index: int = 0
    teaching_strategy: str = ""
    going_well: int
    pace: str = "just right"
    working_best: Optional[str] = None
    created_at: float = Field(default_factory=lambda: time.time())


def template() -> dict:
    return {
        "version": PULSE_SURVEY_VERSION,
        "title": "Quick check-in",
        "subtitle": "Two taps help us adapt the rest of this lesson for you.",
        "interval_slides": PULSE_EVERY_N_SLIDES,
        "questions": [
            {"id": q.id, "type": q.type, "prompt": q.prompt,
             "options": list(q.options), "required": q.required}
            for q in PULSE_SURVEY
        ],
    }


def should_show_pulse(slide_index: int, *, every_n: int = PULSE_EVERY_N_SLIDES) -> bool:
    """True on checkpoint slides (1-based: every 5th slide)."""
    if slide_index < 0:
        return False
    return (slide_index + 1) % every_n == 0


def pulse_lx_sample(going_well: int) -> float:
    """Map 1–5 rating to 0–100 LX sample."""
    score = int(going_well)
    score = max(1, min(5, score))
    return round((score / 5.0) * 100.0, 1)


def pace_fit_from_pulse(pace: str) -> float:
    p = (pace or "").strip().lower()
    if p == "just right":
        return 1.0
    if p in ("too slow", "too fast"):
        return 0.4
    return 0.7


def interpret_pulse(
    *,
    going_well: int,
    pace: str,
    working_best: Optional[str],
    teaching_strategy: str = "",
) -> dict:
    """Turn pulse answers into adaptation hints."""
    lx_score = pulse_lx_sample(going_well)
    strategy = (teaching_strategy or "").strip().lower()
    mapped = WORKING_BEST_TO_STRATEGY.get((working_best or "").strip().lower(), "")
    strategy_success = bool(mapped and strategy and mapped == strategy and going_well >= 4)
    strategy_failure = bool(mapped and strategy and mapped != strategy and going_well <= 2)
    triggers: List[dict] = []
    if pace == "too fast":
        triggers.append({"trigger": "pace too fast", "reason": "pulse survey: pace too fast"})
    elif pace == "too slow":
        triggers.append({"trigger": "pace too slow", "reason": "pulse survey: pace too slow"})
    if going_well <= 2:
        triggers.append({"trigger": "low pulse rating", "reason": f"going_well={going_well}"})
    return {
        "lx_score": lx_score,
        "pace_fit": pace_fit_from_pulse(pace),
        "strategy_success": strategy_success,
        "strategy_failure": strategy_failure,
        "preferred_strategy": mapped,
        "current_strategy": strategy,
        "triggers": triggers,
    }


class PulseSurveyStore:
    """In-memory pulse responses with strategy/course rollups."""

    def __init__(self) -> None:
        self._responses: List[PulseSurveyResponse] = []

    def submit(self, resp: PulseSurveyResponse) -> PulseSurveyResponse:
        if not (1 <= int(resp.going_well) <= 5):
            raise ValueError("going_well must be 1-5")
        self._responses.append(resp)
        return resp

    def count(self) -> int:
        return len(self._responses)

    def for_course(self, course_id: str) -> List[PulseSurveyResponse]:
        return [r for r in self._responses if r.course_id == course_id]

    def summary(self, course_id: str | None = None) -> dict:
        rows = self._responses if course_id is None else self.for_course(course_id)
        if not rows:
            return {"responses": 0, "avg_going_well": 0.0, "pace_counts": {}, "working_best": []}
        avg = sum(r.going_well for r in rows) / len(rows)
        pace_counts = Counter(r.pace for r in rows)
        working = Counter((r.working_best or "not sure") for r in rows)
        by_strategy: Dict[str, List[int]] = defaultdict(list)
        for r in rows:
            if r.teaching_strategy:
                by_strategy[r.teaching_strategy].append(r.going_well)
        strategy_avg = {
            k: round(sum(v) / len(v), 2) for k, v in by_strategy.items() if v
        }
        return {
            "responses": len(rows),
            "avg_going_well": round(avg, 2),
            "pace_counts": dict(pace_counts),
            "working_best": [{"item": k, "count": c} for k, c in working.most_common(5)],
            "avg_by_strategy": strategy_avg,
        }
