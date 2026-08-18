"""Distance × gaze × residual attention / cheating formula for the webcam lab.

The product rule (empirical seat-calibration bands):

* A directional gaze channel (down / up / left / right) staying active for more
  than ``gaze_hold_ms`` (default 4 s), **and**
* stare residual at or above the floor for the learner's distance band,

means the learner is not paying attention / may be cheating.

Distance bands (metres → minimum residual in degrees; residual convention is
the lab's: positive = looking below the lesson band, ~0 = on-screen)::

    0.30  → residual >= -2
    0.40  → residual >= -8
    0.50  → residual >= -9
    0.55  → residual >= -9
    0.60  → residual >= -9
    0.70  → residual >= -12
    >0.70 → too far to take class (ask to move closer)

Away-from-screen, poor camera quality / lighting, and pitch-dark frames are
separate pause gates handled by the analyzer (not this pure formula).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

# (band_center_m, min_residual_deg). Nearest-center matching; hard cutoff above
# ``max_class_distance_m``.
DEFAULT_DISTANCE_BANDS: tuple[tuple[float, float], ...] = (
    (0.30, -2.0),
    (0.40, -8.0),
    (0.50, -9.0),
    (0.55, -9.0),
    (0.60, -9.0),
    (0.70, -12.0),
)

DEFAULT_MAX_CLASS_DISTANCE_M = 0.70
DEFAULT_GAZE_HOLD_MS = 4_000
# Gaze channels are continuous scores; treat tiny noise as inactive.
DEFAULT_GAZE_ACTIVE_MIN = 0.05


@dataclass(frozen=True)
class AttentionFormulaTuning:
    """Knobs for the distance×gaze×residual attention rule."""

    distance_bands: tuple[tuple[float, float], ...] = DEFAULT_DISTANCE_BANDS
    max_class_distance_m: float = DEFAULT_MAX_CLASS_DISTANCE_M
    gaze_hold_ms: int = DEFAULT_GAZE_HOLD_MS
    gaze_active_min: float = DEFAULT_GAZE_ACTIVE_MIN
    # Sustained camera quality / lighting failure before pausing the course.
    quality_pause_hold_ms: int = 2_500
    # Sustained failure before recommending / auto-booting a poor webcam.
    quality_boot_hold_ms: int = 30_000
    # Mean luma below this is "pitch dark" → ask for lights + try auto-exposure.
    pitch_dark_luma: float = 0.08

    def validate(self) -> None:
        if self.max_class_distance_m <= 0:
            raise ValueError("max_class_distance_m must be > 0")
        if self.gaze_hold_ms < 0:
            raise ValueError("gaze_hold_ms must be >= 0")
        if not 0.0 <= self.gaze_active_min <= 1.0:
            raise ValueError("gaze_active_min must be in [0, 1]")
        if self.quality_pause_hold_ms < 0 or self.quality_boot_hold_ms < 0:
            raise ValueError("quality hold windows must be >= 0")
        prev = -1.0
        for center, _floor in self.distance_bands:
            if center <= prev:
                raise ValueError("distance_bands centers must be strictly increasing")
            prev = center
        if self.distance_bands and self.distance_bands[-1][0] > self.max_class_distance_m + 1e-9:
            raise ValueError("last distance band cannot exceed max_class_distance_m")


DEFAULT_ATTENTION_FORMULA = AttentionFormulaTuning()


@dataclass(frozen=True)
class AttentionFormulaResult:
    distance_m: float | None
    band_center_m: float | None
    min_residual_deg: float | None
    residual_deg: float | None
    gaze_active: bool
    gaze_active_channels: tuple[str, ...]
    gaze_away_for_ms: int
    too_far: bool
    inattentive_or_cheating: bool
    reasons: tuple[str, ...]
    coach_message: str


def residual_floor_for_distance(
    distance_m: float | None,
    *,
    tuning: AttentionFormulaTuning = DEFAULT_ATTENTION_FORMULA,
) -> tuple[float | None, float | None, bool]:
    """Return ``(band_center_m, min_residual_deg, too_far)`` for ``distance_m``."""
    if distance_m is None or distance_m <= 0:
        return None, None, False
    if distance_m > tuning.max_class_distance_m:
        return None, None, True
    best_center: float | None = None
    best_floor: float | None = None
    best_delta = float("inf")
    for center, floor in tuning.distance_bands:
        delta = abs(float(distance_m) - float(center))
        if delta < best_delta:
            best_delta = delta
            best_center = float(center)
            best_floor = float(floor)
    return best_center, best_floor, False


def active_gaze_channels(
    *,
    gaze_down: float = 0.0,
    gaze_up: float = 0.0,
    gaze_left: float = 0.0,
    gaze_right: float = 0.0,
    active_min: float = DEFAULT_GAZE_ACTIVE_MIN,
) -> tuple[str, ...]:
    """Which directional gaze scores are currently active (> ``active_min``)."""
    pairs: Sequence[tuple[str, float]] = (
        ("gaze_down", float(gaze_down or 0.0)),
        ("gaze_up", float(gaze_up or 0.0)),
        ("gaze_left", float(gaze_left or 0.0)),
        ("gaze_right", float(gaze_right or 0.0)),
    )
    return tuple(name for name, score in pairs if score > active_min)


def derive_directional_gaze(
    *,
    gaze_down_score: float | None,
    gaze_frontal: float | None,
    head_pose_pitch: float | None,
    head_pose_yaw: float | None,
    residual_deg: float | None,
    stare_tuning_deadband_deg: float = 6.0,
) -> dict[str, float]:
    """Fill gaze_up / left / right from head pose + residual when the client omits them.

    ``gaze_down`` prefers the explicit score; residual still informs upward look.
    """
    down = float(gaze_down_score or 0.0)
    up = 0.0
    left = 0.0
    right = 0.0

    if residual_deg is not None and residual_deg < -stare_tuning_deadband_deg:
        # Looking above the lesson band.
        up = max(up, min(1.0, (-residual_deg - stare_tuning_deadband_deg) / 30.0))
    if head_pose_pitch is not None:
        # Negative pitch ≈ looking up in MediaPipe-style degrees (approx).
        if head_pose_pitch < -8.0:
            up = max(up, min(1.0, (-head_pose_pitch - 8.0) / 25.0))
        elif head_pose_pitch > 12.0 and down < 0.2:
            down = max(down, min(1.0, (head_pose_pitch - 12.0) / 30.0))
    if head_pose_yaw is not None:
        if head_pose_yaw < -10.0:
            left = min(1.0, (-head_pose_yaw - 10.0) / 30.0)
        elif head_pose_yaw > 10.0:
            right = min(1.0, (head_pose_yaw - 10.0) / 30.0)
    # Low frontal without a strong down/up still counts as lateral/off-axis.
    if gaze_frontal is not None and gaze_frontal < 0.35 and down < 0.2 and up < 0.2:
        # Split unknown off-axis into a soft left+right so the "any channel > 0"
        # hold still trips without inventing a fifth channel.
        lateral = min(1.0, (0.35 - gaze_frontal) / 0.35)
        left = max(left, lateral * 0.5)
        right = max(right, lateral * 0.5)

    return {
        "gaze_down": max(0.0, min(1.0, down)),
        "gaze_up": max(0.0, min(1.0, up)),
        "gaze_left": max(0.0, min(1.0, left)),
        "gaze_right": max(0.0, min(1.0, right)),
    }


def evaluate_attention_formula(
    *,
    distance_m: float | None,
    residual_deg: float | None,
    gaze_away_for_ms: int,
    gaze_channels: Iterable[str] = (),
    tuning: AttentionFormulaTuning = DEFAULT_ATTENTION_FORMULA,
) -> AttentionFormulaResult:
    """Apply the distance-band residual + sustained-gaze attention rule."""
    tuning.validate()
    channels = tuple(gaze_channels)
    gaze_active = bool(channels) and gaze_away_for_ms >= tuning.gaze_hold_ms
    band_center, floor, too_far = residual_floor_for_distance(distance_m, tuning=tuning)

    reasons: list[str] = []
    coach = ""
    inattentive = False

    if too_far:
        reasons.append("too_far_from_camera")
        coach = "You are too far from the camera to take this class. Please move closer."
    elif (
        gaze_active
        and residual_deg is not None
        and floor is not None
        and residual_deg >= floor
    ):
        inattentive = True
        reasons.append("attention_formula")
        reasons.append(f"gaze_hold:{','.join(channels) or 'any'}:{gaze_away_for_ms}ms")
        reasons.append(f"residual:{residual_deg:.1f}>={floor:.1f}@~{band_center}m")
        coach = (
            "Please look at the lesson on screen. Looking away for several seconds "
            "counts as not paying attention."
        )
    elif gaze_active and residual_deg is None and floor is not None:
        # No residual yet (uncalibrated) — still flag sustained off-axis gaze so
        # the class does not wait forever for a stare calibration sample.
        inattentive = True
        reasons.append("attention_formula_gaze_only")
        reasons.append(f"gaze_hold:{','.join(channels) or 'any'}:{gaze_away_for_ms}ms")
        coach = "Please look at the lesson on screen."

    return AttentionFormulaResult(
        distance_m=distance_m,
        band_center_m=band_center,
        min_residual_deg=floor,
        residual_deg=residual_deg,
        gaze_active=gaze_active,
        gaze_active_channels=channels,
        gaze_away_for_ms=gaze_away_for_ms,
        too_far=too_far,
        inattentive_or_cheating=inattentive,
        reasons=tuple(reasons),
        coach_message=coach,
    )


def blocking_camera_quality_flags(flags: Iterable[str]) -> tuple[str, ...]:
    """Subset of quality flags that must pause the course until fixed."""
    blocking = {
        "lighting_below_min_quality",
        "lighting_underexposed",
        "lighting_overexposed",
        "shadow_clipping",
        "highlight_clipping",
        "image_blurry",
        "low_edge_detail",
        "detection_quality_low",
    }
    return tuple(f for f in flags if f in blocking)


def is_pitch_dark(*, mean_luminance: float | None, underexposed_ratio: float | None,
                  tuning: AttentionFormulaTuning = DEFAULT_ATTENTION_FORMULA) -> bool:
    if mean_luminance is not None and mean_luminance <= tuning.pitch_dark_luma:
        return True
    if underexposed_ratio is not None and underexposed_ratio >= 0.85:
        return True
    return False
