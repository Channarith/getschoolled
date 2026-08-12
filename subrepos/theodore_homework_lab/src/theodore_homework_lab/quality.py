"""Quality telemetry and bakeoff knobs for homework methodologies."""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .generate import generate_full_battery
from .grade import gold_answer_for as _gold
from .grade import grade_assignment
from .methodologies import METHODOLOGY_IDS, methodology_count
from .tuning_base import env_overrides, patch_knobs


@dataclass(frozen=True)
class HomeworkTuning:
    fuzzy_threshold: float = 0.4
    rubric_pass: float = 0.67
    max_items_default: int = 12
    require_media_uri: bool = False
    prefer_verse_methods: bool = True

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def patched(self, overrides: dict[str, Any]) -> "HomeworkTuning":
        return patch_knobs(self, overrides)

    @classmethod
    def from_env(cls) -> "HomeworkTuning":
        base = cls()
        return base.patched(env_overrides(cls, "HW_LAB_"))

    @classmethod
    def preset(cls, name: str) -> "HomeworkTuning":
        n = (name or "").strip().lower()
        if n == "strict":
            return cls(fuzzy_threshold=0.7, rubric_pass=0.8)
        if n == "lenient":
            return cls(fuzzy_threshold=0.25, rubric_pass=0.5)
        if n == "balanced":
            return cls()
        raise ValueError(f"Unknown preset '{name}'")


PRESETS = ("balanced", "strict", "lenient")


@dataclass
class QualityTelemetry:
    generate_calls: int = 0
    grade_calls: int = 0
    items_generated: int = 0
    items_graded: int = 0
    gold_pass_rate: float = 0.0
    methodology_gold: Dict[str, float] = field(default_factory=dict)
    last_battery_pct: float = 0.0
    bakeoff_rounds: int = 0

    def snapshot(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def run_gold_battery(
    *,
    passages: Optional[List[str]] = None,
    subject: str = "photosynthesis",
    locale: str = "en",
    verse: str = "Count with me one two three",
) -> dict[str, Any]:
    """Generate one item per methodology and grade with gold answers."""
    passages = passages or [
        "photosynthesis: plants make food using light water and carbon dioxide",
        "chlorophyll: green pigment that captures light energy",
    ]
    assignment = generate_full_battery(
        passages=passages,
        subject=subject,
        locale=locale,
        context={"verse": verse, "meaning_en": "Practice counting one through three."},
        title="Gold methodology battery",
    )
    answers = {it.item_id: _gold(it) for it in assignment.items}
    report = grade_assignment(assignment, answers)
    by_method = {
        g.methodology: float(g.score) for g in report.items
    }
    return {
        "assignment_id": assignment.assignment_id,
        "methodology_count": methodology_count(),
        "items": len(assignment.items),
        "percentage": report.percentage,
        "score": report.score,
        "max_score": report.max_score,
        "by_methodology": by_method,
        "flags": report.validity_flags,
        "methodologies": list(METHODOLOGY_IDS),
    }


class HomeworkBakeoff:
    def __init__(self) -> None:
        self.tuning = HomeworkTuning.from_env()
        self.telemetry = QualityTelemetry()
        self.champion: dict[str, Any] = {}

    def evaluate_once(self) -> dict[str, Any]:
        result = run_gold_battery()
        self.telemetry.generate_calls += 1
        self.telemetry.grade_calls += 1
        self.telemetry.items_generated += int(result["items"])
        self.telemetry.items_graded += int(result["items"])
        self.telemetry.last_battery_pct = float(result["percentage"])
        self.telemetry.gold_pass_rate = float(result["percentage"]) / 100.0
        self.telemetry.methodology_gold = {
            k: float(v) for k, v in result["by_methodology"].items()
        }
        self.telemetry.bakeoff_rounds += 1
        if (not self.champion) or result["percentage"] >= self.champion.get("percentage", 0):
            self.champion = {
                "percentage": result["percentage"],
                "tuning": self.tuning.to_dict(),
                "ts": int(time.time()),
            }
        return result

    def run_blocking(self, rounds: int = 2) -> dict[str, Any]:
        last = {}
        for _ in range(max(1, rounds)):
            last = self.evaluate_once()
        return {
            "rounds_done": rounds,
            "champion": self.champion,
            "last": last,
            "telemetry": self.telemetry.snapshot(),
        }


_RUNNER: Optional[HomeworkBakeoff] = None


def get_runner() -> HomeworkBakeoff:
    global _RUNNER
    if _RUNNER is None:
        _RUNNER = HomeworkBakeoff()
    return _RUNNER
