"""Holiday themed webcam games + wand spell recognition from finger trails."""

from __future__ import annotations

from dataclasses import dataclass

from .types import WebcamGameType

# Theme ids exposed in the monitor games panel (order matches the <select>).
GAME_THEME_IDS: tuple[str, ...] = (
    "classic",
    "halloween",
    "christmas",
    "valentines",
    "mothers_day",
    "fathers_day",
    "cute",
    "jiggy",
)

WAND_SPELLS: tuple[str, ...] = ("swish", "flick", "loop")


@dataclass(frozen=True)
class GameThemeSpec:
    theme_id: str
    label: str
    game_type: WebcamGameType | None
    default_costume: str
    default_accessory: str
    festive_overlay: str


GAME_THEMES: dict[str, GameThemeSpec] = {
    "classic": GameThemeSpec(
        theme_id="classic",
        label="Classic focus games",
        game_type=None,
        default_costume="none",
        default_accessory="none",
        festive_overlay="none",
    ),
    "halloween": GameThemeSpec(
        theme_id="halloween",
        label="Halloween wand spells",
        game_type=WebcamGameType.HALLOWEEN_WAND,
        default_costume="wizard",
        default_accessory="wand",
        festive_overlay="halloween_moon",
    ),
    "christmas": GameThemeSpec(
        theme_id="christmas",
        label="Christmas gingerbread",
        game_type=WebcamGameType.CHRISTMAS_GINGERBREAD,
        default_costume="party_hat",
        default_accessory="none",
        festive_overlay="gingerbread_house",
    ),
    "valentines": GameThemeSpec(
        theme_id="valentines",
        label="Valentine heart match",
        game_type=WebcamGameType.VALENTINES_HEARTS,
        default_costume="makeup",
        default_accessory="heart_wand",
        festive_overlay="floating_hearts",
    ),
    "mothers_day": GameThemeSpec(
        theme_id="mothers_day",
        label="Mother's Day bouquet",
        game_type=WebcamGameType.MOTHERS_DAY,
        default_costume="makeup",
        default_accessory="flower_bouquet",
        festive_overlay="mothers_day",
    ),
    "fathers_day": GameThemeSpec(
        theme_id="fathers_day",
        label="Father's Day hero",
        game_type=WebcamGameType.FATHERS_DAY,
        default_costume="sunglasses",
        default_accessory="hero_hammer",
        festive_overlay="fathers_day",
    ),
    "cute": GameThemeSpec(
        theme_id="cute",
        label="Am I cute enough?",
        game_type=WebcamGameType.CUTE_ENOUGH,
        default_costume="glasses",
        default_accessory="none",
        festive_overlay="sparkle_frame",
    ),
    "jiggy": GameThemeSpec(
        theme_id="jiggy",
        label="Come get jiggy with me",
        game_type=WebcamGameType.JIGGY_DANCE,
        default_costume="party_hat",
        default_accessory="none",
        festive_overlay="dance_floor",
    ),
}


def theme_spec(theme_id: str | None) -> GameThemeSpec:
    if theme_id and theme_id in GAME_THEMES:
        return GAME_THEMES[theme_id]
    return GAME_THEMES["classic"]


def recognize_wand_spell(trail: list[tuple[float, float]]) -> str | None:
    """Classify index-finger trail as a Harry-Potter-style wand gesture.

    ``trail`` points are normalised 0..1 frame coordinates (mirrored space).
    """
    if len(trail) < 8:
        return None
    xs = [p[0] for p in trail]
    ys = [p[1] for p in trail]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    if span_x >= 0.22 and span_y <= 0.14:
        return "swish"
    if span_y >= 0.18 and span_x <= 0.12:
        return "flick"
    first, last = trail[0], trail[-1]
    if (
        len(trail) >= 12
        and ((first[0] - last[0]) ** 2 + (first[1] - last[1]) ** 2) ** 0.5 <= 0.08
    ):
        return "loop"
    return None


def trail_heart_shape(trail: list[tuple[float, float]]) -> bool:
    """A drawn heart has two top lobes and a bottom point. A circle does not.

    The live Valentine round does not use this. It accepts the two-hand heart
    pose only. This helper stays so a round finger loop cannot be labeled a heart.
    """
    if len(trail) < 12:
        return False
    xs = [p[0] for p in trail]
    ys = [p[1] for p in trail]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    if span_x < 0.10 or span_y < 0.14:
        return False
    first, last = trail[0], trail[-1]
    if ((first[0] - last[0]) ** 2 + (first[1] - last[1]) ** 2) ** 0.5 > 0.12:
        return False
    min_y = min(ys)
    top = [p for p in trail if p[1] <= min_y + 0.28 * span_y]
    if len(top) < 3:
        return False
    left = min(top, key=lambda p: p[0])
    right = max(top, key=lambda p: p[0])
    between = [
        p for p in top
        if left[0] + 0.15 * span_x < p[0] < right[0] - 0.15 * span_x
    ]
    if not between:
        return False
    cleft_drop = max(p[1] for p in between) - min(left[1], right[1])
    if cleft_drop < 0.08 * span_y:
        return False
    bottom = max(trail, key=lambda p: p[1])
    mid_x = (min(xs) + max(xs)) / 2
    return abs(bottom[0] - mid_x) <= 0.22 * span_x
