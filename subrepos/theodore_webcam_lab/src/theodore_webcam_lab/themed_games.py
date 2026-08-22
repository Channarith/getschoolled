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
    """Simple heart-ish closed loop for Valentine matching."""
    spell = recognize_wand_spell(trail)
    if spell != "loop":
        return False
    xs = [p[0] for p in trail]
    ys = [p[1] for p in trail]
    # Heart loops tend to be taller than wide in portrait framing.
    return (max(ys) - min(ys)) >= 0.14 and (max(xs) - min(xs)) >= 0.10
