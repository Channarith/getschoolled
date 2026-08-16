"""Stare geometry: known triangles, and JS/Python parity for the live lab.

The browser computes the residual itself (it needs it before the round trip),
so the formulas exist twice. These tests pin the duplicated constants and
formula shapes against the Python module so the two cannot drift.
"""

from __future__ import annotations

import math
import re

import pytest

from theodore_webcam_lab.monitor_page import MONITOR_JS
from theodore_webcam_lab.stare_geometry import (
    DEFAULT_STARE_TUNING,
    FACE_FRACTION_DEG_PER_UNIT,
    GEOMETRIC_PITCH_LIMIT_DEG,
    LAYOUT_PRESETS,
    NEUTRAL_FACE_UPPER_FRACTION,
    DeviceLayout,
    evaluate_stare,
    expected_screen_pitch_deg,
    gaze_down_from_residual,
    geometric_pitch_deg,
    phone_stare_score,
    resolve_layout,
    screen_match_score,
    stare_residual_deg,
)

LAYOUT = DeviceLayout("test", 0.18)


def test_expected_angle_is_the_triangle_the_seat_actually_makes():
    # 0.18 m below the webcam, seen from 0.60 m away.
    assert expected_screen_pitch_deg(0.60, LAYOUT) == pytest.approx(16.699, abs=0.01)
    # Leaning in makes the same screen a steeper look down.
    assert expected_screen_pitch_deg(0.35, LAYOUT) > expected_screen_pitch_deg(0.90, LAYOUT)
    assert expected_screen_pitch_deg(None, LAYOUT) is None


def test_absurdly_close_distances_clamp_instead_of_blowing_up():
    clamped = expected_screen_pitch_deg(0.01, LAYOUT)
    assert clamped == pytest.approx(expected_screen_pitch_deg(0.25, LAYOUT))


def test_residual_is_zero_when_the_tilt_matches_the_screen():
    assert stare_residual_deg(16.699, 0.60, LAYOUT) == pytest.approx(0.0, abs=0.01)
    assert stare_residual_deg(36.699, 0.60, LAYOUT) == pytest.approx(20.0, abs=0.01)
    assert stare_residual_deg(None, 0.60, LAYOUT) is None


def test_watching_the_lesson_scores_a_match_and_no_phone_stare():
    reading = evaluate_stare(theta_down_deg=16.7, distance_m=0.60, layout=LAYOUT)
    assert reading.screen_match_score == pytest.approx(1.0, abs=0.01)
    assert reading.phone_stare_score == 0.0
    # The point of the whole model: staring at the monitor is not "looking down".
    assert reading.gaze_down_score == 0.0


def test_a_stare_far_below_the_screen_separates_from_the_lesson():
    reading = evaluate_stare(theta_down_deg=45.0, distance_m=0.60, layout=LAYOUT)
    assert reading.residual_deg == pytest.approx(28.3, abs=0.1)
    assert reading.screen_match_score == 0.0
    assert reading.phone_stare_score > 0.8
    assert reading.gaze_down_score > 0.7


def test_a_low_laptop_does_not_read_as_a_phone_glance():
    """The neutral already cancels the seat, so theta_down starts at ~0."""
    reading = evaluate_stare(theta_down_deg=0.0, distance_m=0.45, layout=LAYOUT)
    assert reading.residual_deg < 0
    assert reading.phone_stare_score == 0.0
    assert reading.gaze_down_score == 0.0


def test_scores_are_none_without_a_measurement():
    assert screen_match_score(None) is None
    assert phone_stare_score(None) is None
    assert gaze_down_from_residual(None) is None


def test_layout_presets_can_be_overridden_with_a_measured_drop():
    assert resolve_layout("laptop_14").y_screen_m == LAYOUT_PRESETS["laptop_14"].y_screen_m
    assert resolve_layout("nonsense").y_screen_m == LAYOUT_PRESETS["laptop_16"].y_screen_m
    assert resolve_layout("laptop_14", 0.31).y_screen_m == pytest.approx(0.31)


def test_geometric_pitch_is_scale_invariant_and_signed():
    """Sitting closer scales both spans, so the ratio - and the angle - hold."""
    near = geometric_pitch_deg(0.42, 0.58)
    far = geometric_pitch_deg(0.21, 0.29)
    assert near == pytest.approx(far)
    assert near == pytest.approx(0.0, abs=0.01)
    # More of the face above the eye line = the top of the skull rotated toward
    # the camera = looking down.
    assert geometric_pitch_deg(0.52, 0.48) > 0
    assert geometric_pitch_deg(0.32, 0.68) < 0
    assert geometric_pitch_deg(1.0, 0.0) == GEOMETRIC_PITCH_LIMIT_DEG
    assert geometric_pitch_deg(0.0, 0.0) is None


def _project_head(theta_deg: float, camera_distance_m: float = 0.60):
    """Hairline / eye-line / chin heights in frame for a head pitched by theta.

    A coarse head: the hairline sits 9 cm above and 2 cm behind the eye-corner
    plane, the chin 10 cm below and 4 cm behind. Rotating about the ear axis and
    projecting with perspective is enough to check the sign and the scale.
    """
    points = {"forehead": (0.09, -0.02), "eye": (0.0, 0.0), "chin": (-0.10, -0.04)}
    out = {}
    t = math.radians(theta_deg)
    for name, (y, z) in points.items():
        y_rot = y * math.cos(t) - z * math.sin(t)
        z_rot = y * math.sin(t) + z * math.cos(t)
        out[name] = y_rot / (camera_distance_m - z_rot)
    return out


def test_geometric_pitch_tracks_a_rotating_head_about_one_to_one():
    """Degrees have to mean degrees: the residual subtracts a real atan angle.

    The absolute offset is irrelevant (the neutral calibration subtracts it), but
    the slope is not - a proxy reading 2x the true tilt would read a mid-screen
    glance as a phone glance.
    """
    readings = {}
    for theta in (-10, 0, 10, 20, 30):
        p = _project_head(theta)
        readings[theta] = geometric_pitch_deg(p["forehead"] - p["eye"], p["eye"] - p["chin"])

    # Monotonic in the right direction: nodding down raises the estimate.
    values = [readings[t] for t in sorted(readings)]
    assert values == sorted(values)

    slope = (readings[30] - readings[-10]) / 40.0
    assert 0.75 <= slope <= 1.3, f"one degree of pitch reads as {slope:.2f} degrees"


# --- Parity with the duplicated browser formulas ---------------------------


def _js_const(name: str) -> float:
    match = re.search(rf"const {name} = (-?[\d.]+);", MONITOR_JS)
    assert match, f"{name} is missing from the monitor JS"
    return float(match.group(1))


def test_js_constants_match_the_python_tuning():
    t = DEFAULT_STARE_TUNING
    assert _js_const("STARE_MIN_DISTANCE_M") == t.min_distance_m
    assert _js_const("STARE_RESIDUAL_SOFT_DEG") == t.residual_soft_deg
    assert _js_const("STARE_PHONE_RESIDUAL_DEG") == t.phone_residual_deg
    assert _js_const("STARE_RESIDUAL_SPAN_DEG") == t.residual_span_deg
    assert _js_const("STARE_GAZE_DOWN_DEADBAND_DEG") == t.gaze_down_deadband_deg
    assert _js_const("STARE_GAZE_DOWN_SPAN_DEG") == t.gaze_down_span_deg
    assert _js_const("STARE_NEUTRAL_UPPER_FRACTION") == NEUTRAL_FACE_UPPER_FRACTION
    assert _js_const("STARE_FRACTION_DEG_PER_UNIT") == FACE_FRACTION_DEG_PER_UNIT
    assert _js_const("STARE_GEOM_PITCH_LIMIT_DEG") == GEOMETRIC_PITCH_LIMIT_DEG


def test_js_layout_presets_match_the_python_presets():
    block = MONITOR_JS.split("const STARE_LAYOUTS = {")[1].split("};")[0]
    for key, layout in LAYOUT_PRESETS.items():
        match = re.search(rf"{key}: {{[^}}]*yScreen: ([\d.]+)", block)
        assert match, f"layout preset {key} is missing from the monitor JS"
        assert float(match.group(1)) == pytest.approx(layout.y_screen_m)


def test_js_formulas_are_the_same_arithmetic_as_python():
    expected = MONITOR_JS.split("function expectedScreenPitchDeg(distanceM)")[1].split(
        "\n    }"
    )[0]
    assert "Math.max(distanceM, STARE_MIN_DISTANCE_M)" in expected
    assert "Math.atan(stareYScreenM / d) * (180 / Math.PI)" in expected

    match_fn = MONITOR_JS.split("function screenMatchScore(residual)")[1].split("\n    }")[0]
    assert "1 - Math.abs(residual) / STARE_RESIDUAL_SOFT_DEG" in match_fn

    phone = MONITOR_JS.split("function phoneStareScore(residual)")[1].split("\n    }")[0]
    assert "(residual - STARE_PHONE_RESIDUAL_DEG) / STARE_RESIDUAL_SPAN_DEG" in phone

    gaze = MONITOR_JS.split("function gazeDownFromResidual(residual)")[1].split("\n    }")[0]
    assert "(residual - STARE_GAZE_DOWN_DEADBAND_DEG) / STARE_GAZE_DOWN_SPAN_DEG" in gaze

    pitch = MONITOR_JS.split("function geometricPitchDeg(upper, lower)")[1].split("\n    }")[0]
    assert "(fraction - STARE_NEUTRAL_UPPER_FRACTION) * STARE_FRACTION_DEG_PER_UNIT" in pitch


def test_js_residual_reproduces_a_python_reading():
    """Same triangle, run through the JS constants, lands on the Python numbers."""
    y_screen = 0.18
    distance = 0.60
    theta_down = 30.0
    d = max(distance, _js_const("STARE_MIN_DISTANCE_M"))
    js_expected = math.degrees(math.atan(y_screen / d))
    js_residual = theta_down - js_expected
    js_match = max(0.0, min(1.0, 1 - abs(js_residual) / _js_const("STARE_RESIDUAL_SOFT_DEG")))
    js_phone = max(
        0.0,
        min(
            1.0,
            (js_residual - _js_const("STARE_PHONE_RESIDUAL_DEG"))
            / _js_const("STARE_RESIDUAL_SPAN_DEG"),
        ),
    )
    reading = evaluate_stare(
        theta_down_deg=theta_down, distance_m=distance, layout=DeviceLayout("js", y_screen)
    )
    assert reading.expected_screen_pitch_deg == pytest.approx(js_expected)
    assert reading.residual_deg == pytest.approx(js_residual)
    assert reading.screen_match_score == pytest.approx(js_match)
    assert reading.phone_stare_score == pytest.approx(js_phone)
