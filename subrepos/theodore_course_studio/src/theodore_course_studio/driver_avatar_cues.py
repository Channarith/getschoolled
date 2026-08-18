"""Curated Theodore movement beats for every California Driver's Ed slide."""

from __future__ import annotations

# start fraction, duration fraction, gesture, gaze, hand, intensity, expression
CueRow = tuple[float, float, str, str, str, float, str]


def _c(
    first: str,
    second: str = "explain",
    *,
    gaze: str = "learner",
    expression: str = "warm",
    intensity: float = 0.82,
) -> tuple[CueRow, ...]:
    return (
        (0.03, 0.38, first, gaze, "both" if first in {"compare", "steer"} else "right", intensity, expression),
        (0.46, 0.34, second, "slide" if second == "point-to-slide" else "learner", "left", 0.72, expression),
        (0.84, 0.14, "transition", "learner", "none", 0.48, "encouraging"),
    )


DRIVER_AVATAR_CUES: dict[str, tuple[CueRow, ...]] = {
    "Prep, not a DMV course": _c("caution", "point-to-slide", expression="serious"),
    "California learner's permit": _c("count", "open-palm"),
    "Right-of-way at stops": _c("stop", "compare", expression="serious"),
    "California speed basics": _c("caution", "point-to-slide", expression="serious"),
    "Following distance": _c("count", "demonstrate"),
    "Signals and lane changes": _c("shoulder-check", "point-to-slide"),
    "Turning and red lights": _c("stop", "point-to-slide", expression="serious"),
    "School buses in California": _c("stop", "compare", expression="serious"),
    "Seat belts and phones": _c("seatbelt", "phone-away", expression="serious"),
    "DUI limits (California)": _c("stop", "caution", expression="concerned", intensity=1.0),
    "What to do after a crash": _c("caution", "count", expression="concerned"),
    "Study next": _c("open-palm", "celebrate", expression="encouraging"),
    "Regulatory signs": _c("point-to-slide", "caution", gaze="slide"),
    "Yield and stop": _c("compare", "stop", expression="serious"),
    "Warning signs": _c("caution", "point-to-slide", gaze="slide"),
    "Guide and service signs": _c("compare", "point-to-slide", gaze="slide"),
    "Traffic signals": _c("count", "stop", gaze="slide"),
    "Pavement markings": _c("compare", "point-to-slide", gaze="slide"),
    "Railroad crossings": _c("stop", "point-to-slide", expression="serious", intensity=1.0),
    "Roundabouts": _c("steer", "point-to-slide", gaze="slide"),
    "Parking clearances": _c("count", "caution"),
    "Night headlights": _c("demonstrate", "point-to-slide", gaze="slide"),
    "Pedestrians and bikes": _c("caution", "point-to-slide", gaze="slide"),
    "Motorcycle awareness": _c("shoulder-check", "caution"),
    "Large truck no-zones": _c("compare", "point-to-slide", gaze="slide", expression="serious"),
    "Freeway merging": _c("shoulder-check", "steer"),
    "Weather and hydroplaning": _c("steer", "caution", expression="serious"),
    "Emergency vehicles": _c("caution", "point-right", expression="serious"),
    "Work zones": _c("caution", "stop", expression="serious"),
    "Before you drive": _c("count", "demonstrate"),
    "Handbook checkpoint": _c("point-to-slide", "ask", gaze="slide"),
    "Practice test habit": _c("count", "celebrate", expression="encouraging"),
}


DRIVER_AVATAR_TITLES = frozenset(DRIVER_AVATAR_CUES)
