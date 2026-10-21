"""Plain-language key for the line a learner sees while teaching adapts.

The 8-digit profile score stays internal. Clients translate ``key`` and the
``style`` / ``pace`` tokens. Priority is the most immediate change first.
"""

from __future__ import annotations

from typing import Any

_STYLES = {
    "visual": "visual",
    "auditory": "listening",
    "listening": "listening",
    "reading_writing": "reading",
    "reading": "reading",
    "hands_on": "practice",
    "practice": "practice",
    "kinesthetic": "practice",
    "mixed": "balanced",
    "balanced": "balanced",
}

_STAYS = {
    "visual": "adapt.staysVisual",
    "reading": "adapt.staysReading",
    "listening": "adapt.staysListening",
    "practice": "adapt.staysPractice",
}

_STORYBOARD = {
    "visual": "visual",
    "listening": "auditory",
    "reading": "reading_writing",
    "practice": "hands_on",
}


def style_token(raw: str) -> str:
    return _STYLES.get((raw or "").strip().lower(), "balanced")


def storyboard_style(live_style: str) -> str:
    """Map a live emphasis onto the storyboard primary_style vocabulary."""
    return _STORYBOARD.get(style_token(live_style), "")


def pace_dwell_factor(pacing: str) -> float:
    if pacing == "slow":
        return 1.45
    if pacing == "fast":
        return 0.7
    return 1.0


def _pace_token(pacing: str, declared_pace: str) -> str:
    if pacing in {"slow", "fast"}:
        return pacing
    if declared_pace in {"slow", "moderate", "fast"}:
        return declared_pace
    return "moderate"


def adaptation_line(
    *,
    pacing: str = "normal",
    difficulty: str = "medium",
    reteach: bool = False,
    attention: float | None = None,
    survey_style: str = "",
    live_style: str = "",
    declared_pace: str = "moderate",
) -> dict[str, str]:
    """Choose one learner-facing sentence key."""
    style = style_token(survey_style)
    pace = _pace_token(str(pacing or ""), str(declared_pace or ""))
    live = style_token(live_style) if (live_style or "").strip() else ""
    pacing_name = str(pacing or "")
    difficulty_name = str(difficulty or "")

    if attention is not None and attention < 0.5:
        key = "adapt.lookedAway"
    elif reteach:
        key = "adapt.reteach"
    elif difficulty_name == "easy":
        key = "adapt.easier"
    elif pacing_name == "fast":
        key = "adapt.movingAhead"
    elif live and live != style and live in _STAYS:
        key = _STAYS[live]
    elif pacing_name == "slow":
        key = "adapt.slowing"
    else:
        key = "adapt.starting"
    return {"key": key, "style": style, "pace": pace}


def adaptation_line_from_values(pacing: Any, difficulty: Any, **kwargs: Any) -> dict[str, str]:
    """Accept enum values from the teaching tick."""
    return adaptation_line(
        pacing=getattr(pacing, "value", pacing),
        difficulty=getattr(difficulty, "value", difficulty),
        **kwargs,
    )
