"""Curated Theodore movement beats for every Food Handler Safety slide."""

from __future__ import annotations

from .driver_avatar_cues import CueRow


def _c(
    first: str,
    second: str = "explain",
    *,
    gaze: str = "learner",
    expression: str = "warm",
    intensity: float = 0.82,
) -> tuple[CueRow, ...]:
    return (
        (0.03, 0.38, first, gaze, "both" if first in {"wash-hands", "sanitize", "compare"} else "right", intensity, expression),
        (0.46, 0.34, second, "slide" if second == "point-to-slide" else "learner", "left", 0.72, expression),
        (0.84, 0.14, "transition", "learner", "none", 0.48, "encouraging"),
    )


FOOD_AVATAR_CUES: dict[str, tuple[CueRow, ...]] = {
    "Prep card, not accreditation": _c("caution", "point-to-slide", expression="serious"),
    "Why food handler cards matter": _c("point-to-slide", "open-palm", gaze="slide"),
    "Handwashing that works": _c("wash-hands", "count", intensity=1.0),
    "Gloves done right": _c("gloves", "wash-hands"),
    "Illness reporting": _c("caution", "stop", expression="concerned"),
    "Personal cleanliness": _c("count", "demonstrate"),
    "Ready-to-eat foods": _c("gloves", "caution"),
    "Cuts and bandages": _c("gloves", "caution", expression="concerned"),
    "Customer allergen basics": _c("stop", "ask", expression="serious"),
    "Your next short block": _c("open-palm", "celebrate", expression="encouraging"),
    "Temperature danger zone": _c("compare", "point-to-slide", gaze="slide", expression="serious"),
    "Cold holding": _c("thermometer", "point-to-slide", gaze="slide"),
    "Hot holding": _c("thermometer", "caution", expression="serious"),
    "Safe cooking targets": _c("thermometer", "count"),
    "Cooling cooked food": _c("count", "thermometer"),
    "Reheating": _c("thermometer", "count", expression="serious"),
    "Thawing safely": _c("compare", "caution"),
    "Receiving checks": _c("demonstrate", "stop", expression="serious"),
    "Date marking": _c("count", "point-to-slide", gaze="slide"),
    "Thermometer habits": _c("thermometer", "demonstrate"),
    "Cross-contamination": _c("compare", "stop", expression="serious"),
    "Clean then sanitize": _c("sanitize", "count"),
    "Sanitizer strength": _c("sanitize", "thermometer"),
    "FIFO stock rotation": _c("demonstrate", "point-to-slide", gaze="slide"),
    "Pest prevention": _c("stop", "count", expression="serious"),
    "Allergen cross-contact": _c("compare", "stop", expression="serious", intensity=1.0),
    "Common pathogens": _c("caution", "point-to-slide", gaze="slide"),
    "Health inspections": _c("point-to-slide", "count", expression="serious"),
    "If a guest gets sick": _c("listen", "caution", expression="concerned"),
    "Finish strong": _c("open-palm", "celebrate", expression="celebrating"),
}


FOOD_AVATAR_TITLES = frozenset(FOOD_AVATAR_CUES)

from .slide_keys import register_title_aliases  # noqa: E402

register_title_aliases(FOOD_AVATAR_CUES)
