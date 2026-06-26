"""Course complexity ratings and finish-pace vs expected duration."""

from __future__ import annotations

from typing import Optional

LEVEL_COMPLEXITY = {
    "beginner": 2,
    "intermediate": 3,
    "advanced": 5,
}

MATURITY_COMPLEXITY = {
    "all": 2,
    "kids": 1,
    "teen": 3,
    "mature": 4,
}


def complexity_score(
    *,
    level: str = "beginner",
    maturity: str = "all",
    duration_min: int = 0,
    explicit: Optional[int] = None,
) -> int:
    """Return 1 (simplest) – 5 (most demanding) cognitive load."""
    if explicit is not None and 1 <= explicit <= 5:
        return int(explicit)
    base = LEVEL_COMPLEXITY.get((level or "beginner").lower(), 3)
    mat = MATURITY_COMPLEXITY.get((maturity or "all").lower(), 2)
    dur_boost = 1 if duration_min > 40 else 0
    return max(1, min(5, round((base + mat) / 2) + dur_boost))


def infer_lesson_complexity(
    lesson_id: str,
    *,
    audience: str = "general",
    level: str = "",
    slide_count: int = 0,
) -> int:
    """Heuristic complexity for live-class lessons from sample-curriculum."""
    lid = (lesson_id or "").lower()
    aud = (audience or "general").lower()
    if "fraction" in lid or "kids" in aud:
        return 1
    if aud == "corporate" or "fellowship" in lid or "architect" in lid:
        return 4
    if level:
        return complexity_score(level=level, duration_min=max(20, slide_count * 2))
    if slide_count > 30:
        return 4
    return 3


def finish_pace_label(actual_min: float, expected_min: float) -> str:
    """Compare wall-clock finish time to expected course duration."""
    if expected_min <= 0 or actual_min <= 0:
        return "unknown"
    ratio = actual_min / expected_min
    if ratio < 0.75:
        return "fast"
    if ratio > 1.35:
        return "slow"
    return "on_track"


def expected_minutes_from_slides(slide_count: int, *, minutes_per_slide: float = 2.0) -> int:
    """Default expected duration when catalog metadata is absent."""
    return max(20, round(slide_count * minutes_per_slide))
