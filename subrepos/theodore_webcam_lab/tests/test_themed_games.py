"""Themed games and wand spell recognition."""

from theodore_webcam_lab.themed_games import (
    GAME_THEME_IDS,
    recognize_wand_spell,
    theme_spec,
    trail_heart_shape,
)


def test_theme_spec_maps_halloween_to_wand_game():
    spec = theme_spec("halloween")
    assert spec.theme_id == "halloween"
    assert spec.game_type is not None
    assert spec.default_costume == "wizard"
    assert spec.default_accessory == "wand"


def test_recognize_wand_swish_from_horizontal_trail():
    trail = [(0.2 + i * 0.03, 0.5) for i in range(10)]
    assert recognize_wand_spell(trail) == "swish"


def test_recognize_wand_flick_from_vertical_trail():
    trail = [(0.5, 0.2 + i * 0.03) for i in range(10)]
    assert recognize_wand_spell(trail) == "flick"


def test_recognize_wand_loop_and_heart():
    import math

    loop = [(0.5 + 0.08 * math.cos(i / 3), 0.5 + 0.08 * math.sin(i / 3)) for i in range(18)]
    assert recognize_wand_spell(loop) == "loop"
    circle = [
        (
            0.5 + 0.12 * math.cos(i * 2 * math.pi / 24),
            0.45 + 0.16 * math.sin(i * 2 * math.pi / 24),
        )
        for i in range(25)
    ]
    assert trail_heart_shape(circle) is False
    # Two high lobes, a dip between them, and a point at the bottom.
    heart = [
        (0.50, 0.40), (0.43, 0.34), (0.36, 0.30), (0.30, 0.36),
        (0.28, 0.46), (0.34, 0.56), (0.42, 0.62), (0.50, 0.70),
        (0.58, 0.62), (0.66, 0.56), (0.72, 0.46), (0.70, 0.36),
        (0.64, 0.30), (0.57, 0.34), (0.50, 0.40),
    ]
    assert trail_heart_shape(heart) is True


def test_game_theme_ids_include_all_holidays():
    assert "halloween" in GAME_THEME_IDS
    assert "christmas" in GAME_THEME_IDS
    assert "valentines" in GAME_THEME_IDS
    assert "mothers_day" in GAME_THEME_IDS
    assert "fathers_day" in GAME_THEME_IDS
    assert "cute" in GAME_THEME_IDS
    assert "jiggy" in GAME_THEME_IDS


def test_jiggy_theme_maps_to_dance_game():
    spec = theme_spec("jiggy")
    assert spec.theme_id == "jiggy"
    assert spec.label == "Come get jiggy with me"
    assert spec.game_type is not None
    assert spec.festive_overlay == "dance_floor"
