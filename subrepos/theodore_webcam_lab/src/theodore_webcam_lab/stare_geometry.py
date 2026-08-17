"""Stare geometry: is the head tilted the way watching *this* screen requires?

Looking at the lesson and looking at a phone both pitch the head down, so an
absolute tilt cannot separate them. What separates them is the *expected*
angle: from a seat ``D`` metres away, the lesson band sits ``y_screen`` metres
below the webcam, which is ``atan(y_screen / D)`` degrees down. Tilt measured
from a calibrated neutral minus that expectation is the **residual** — near
zero means the learner is on the lesson, large positive means they are staring
below the screen.

Two conventions the rest of the lab relies on:

* Angles are degrees, positive = **down**.
* Pitch is measured from the learner's calibrated neutral, never from level.
  A low-mounted laptop makes a resting head pitch down; the neutral cancels it.

The browser lab duplicates these formulas in JavaScript (it has to run before
the round trip), so ``tests/test_stare_geometry.py`` parses the JS out of
``monitor_page.py`` and asserts both sides agree number for number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# The face-mesh fallback pitch is a ratio, not an angle: how much of the
# hairline-to-chin span sits above the eye line. Tilting down rotates the top
# of the skull toward the camera and foreshortens the chin, so the fraction
# grows. These constants convert that fraction into degrees.
# The scale is chosen so one degree of real pitch reads as about one degree here
# (test_geometric_pitch_tracks_a_rotating_head_about_one_to_one pins it against a
# rotating head model), because the residual subtracts a true atan angle from it.
NEUTRAL_FACE_UPPER_FRACTION = 0.42
FACE_FRACTION_DEG_PER_UNIT = 250.0
GEOMETRIC_PITCH_LIMIT_DEG = 60.0


@dataclass(frozen=True)
class DeviceLayout:
    """Where the lesson content sits relative to the webcam.

    ``y_screen_m`` is the drop from the camera to the middle of the lesson
    band (webcam-to-bezel plus roughly half the screen height), which is the
    only quantity the expected angle needs.
    """

    label: str
    y_screen_m: float
    screen_height_m: float | None = None


LAYOUT_PRESETS: dict[str, DeviceLayout] = {
    "laptop_14": DeviceLayout("14\" laptop", 0.14, 0.19),
    "laptop_16": DeviceLayout("16\" laptop", 0.18, 0.22),
    "external_monitor_webcam_top": DeviceLayout("Monitor, webcam on top", 0.24, 0.34),
}
DEFAULT_LAYOUT_KEY = "laptop_16"


@dataclass(frozen=True)
class StareTuning:
    """Knobs for the stare instrument.

    Deliberately *not* part of ``VisionTuning``: nothing here changes a scoring
    gate yet (this pass is a measuring instrument), and every ``VisionTuning``
    knob is required to move a scoring decision.
    """

    default_y_screen_m: float = 0.18
    # |residual| at which "you are on the lesson" has decayed to zero.
    residual_soft_deg: float = 12.0
    # Residual where a below-the-screen stare starts reading as a phone glance.
    phone_residual_deg: float = 14.0
    # Residual span over which phone_stare climbs from 0 to 1.
    residual_span_deg: float = 16.0
    # Closer than this the atan blows up; clamp instead of dividing by ~0.
    min_distance_m: float = 0.25
    # Micro-nods while reading are not "looking down".
    gaze_down_deadband_deg: float = 6.0
    gaze_down_span_deg: float = 30.0


DEFAULT_STARE_TUNING = StareTuning()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def resolve_layout(key: str | None, y_screen_m: float | None = None) -> DeviceLayout:
    """Preset by key, optionally overridden with a measured ``y_screen``."""
    base = LAYOUT_PRESETS.get(key or DEFAULT_LAYOUT_KEY, LAYOUT_PRESETS[DEFAULT_LAYOUT_KEY])
    if y_screen_m is None:
        return base
    return DeviceLayout(base.label, max(0.0, float(y_screen_m)), base.screen_height_m)


def expected_screen_pitch_deg(
    distance_m: float | None,
    layout: DeviceLayout,
    tuning: StareTuning = DEFAULT_STARE_TUNING,
) -> float | None:
    """Degrees below the camera axis the lesson band sits at, from ``distance_m``."""
    if distance_m is None or not math.isfinite(distance_m) or distance_m <= 0:
        return None
    d = max(float(distance_m), tuning.min_distance_m)
    return math.degrees(math.atan(layout.y_screen_m / d))


def stare_residual_deg(
    theta_down_deg: float | None,
    distance_m: float | None,
    layout: DeviceLayout,
    tuning: StareTuning = DEFAULT_STARE_TUNING,
) -> float | None:
    """Calibrated downward tilt minus the tilt this screen actually requires."""
    if theta_down_deg is None or not math.isfinite(theta_down_deg):
        return None
    expected = expected_screen_pitch_deg(distance_m, layout, tuning)
    if expected is None:
        return None
    return float(theta_down_deg) - expected


def screen_match_score(
    residual_deg: float | None,
    tuning: StareTuning = DEFAULT_STARE_TUNING,
) -> float | None:
    """1.0 when the stare lands on the lesson band, decaying either side."""
    if residual_deg is None:
        return None
    soft = max(1e-6, tuning.residual_soft_deg)
    return _clamp01(1.0 - abs(residual_deg) / soft)


def phone_stare_score(
    residual_deg: float | None,
    tuning: StareTuning = DEFAULT_STARE_TUNING,
) -> float | None:
    """How far *below* the lesson band the stare has dropped, 0..1.

    Instrument only in this pass: nothing consumes it for cheating decisions.
    """
    if residual_deg is None:
        return None
    span = max(1e-6, tuning.residual_span_deg)
    return _clamp01((residual_deg - tuning.phone_residual_deg) / span)


def gaze_down_from_residual(
    residual_deg: float | None,
    tuning: StareTuning = DEFAULT_STARE_TUNING,
) -> float | None:
    """``gaze_down`` 0..1 from the residual, not from absolute face geometry.

    The old client scored gaze_down from the nose sitting below the eye line
    and from face height in frame. Both are true of every seated learner, so a
    person staring straight at the monitor scored ~0.55 "looking down". Scoring
    the residual instead means sitting on the lesson band reads as 0.
    """
    if residual_deg is None:
        return None
    span = max(1e-6, tuning.gaze_down_span_deg)
    return _clamp01((residual_deg - tuning.gaze_down_deadband_deg) / span)


def geometric_pitch_deg(upper_span: float, lower_span: float) -> float | None:
    """Signed pitch proxy from face landmarks; positive = looking down.

    ``upper_span`` is hairline-to-eye-line, ``lower_span`` eye-line-to-chin,
    both measured along the face's own vertical axis so head roll cancels.
    Being a *ratio* it is scale invariant, which is the whole point: the pitch
    this replaces was ``(chin_y - forehead_y - 0.32) * 140``, i.e. face height
    in frame, which reports how close you sit rather than how you are tilted.
    """
    total = upper_span + lower_span
    if not math.isfinite(total) or total <= 1e-6:
        return None
    fraction = upper_span / total
    deg = (fraction - NEUTRAL_FACE_UPPER_FRACTION) * FACE_FRACTION_DEG_PER_UNIT
    return max(-GEOMETRIC_PITCH_LIMIT_DEG, min(GEOMETRIC_PITCH_LIMIT_DEG, deg))


@dataclass(frozen=True)
class StareReading:
    distance_m: float | None
    theta_down_deg: float | None
    expected_screen_pitch_deg: float | None
    residual_deg: float | None
    screen_match_score: float | None
    phone_stare_score: float | None
    gaze_down_score: float | None
    layout_label: str


def evaluate_stare(
    *,
    theta_down_deg: float | None,
    distance_m: float | None,
    layout: DeviceLayout | None = None,
    tuning: StareTuning = DEFAULT_STARE_TUNING,
) -> StareReading:
    """One frame of the stare instrument."""
    lay = layout or LAYOUT_PRESETS[DEFAULT_LAYOUT_KEY]
    expected = expected_screen_pitch_deg(distance_m, lay, tuning)
    residual = stare_residual_deg(theta_down_deg, distance_m, lay, tuning)
    return StareReading(
        distance_m=distance_m,
        theta_down_deg=theta_down_deg,
        expected_screen_pitch_deg=expected,
        residual_deg=residual,
        screen_match_score=screen_match_score(residual, tuning),
        phone_stare_score=phone_stare_score(residual, tuning),
        gaze_down_score=gaze_down_from_residual(residual, tuning),
        layout_label=lay.label,
    )
