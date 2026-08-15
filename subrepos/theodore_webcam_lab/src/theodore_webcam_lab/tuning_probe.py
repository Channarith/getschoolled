"""Prove that every vision knob actually changes a scoring decision.

Validating that a knob is in range (what selfcheck used to do) says nothing about
whether the pipeline reads it. A knob can be declared, rendered as a slider,
PATCHed successfully and echoed back in the API response while being completely
disconnected from scoring — and every check would still pass.

This module closes that gap empirically: it perturbs one knob at a time and
re-scores a small matrix of frames, looking for any observable difference in the
evaluation. A knob that cannot move any output under any scenario is dead, and
the operator has a real answer to "the knobs don't do anything".

Scenarios exist because a knob is only observable when the frame reaches its
branch: silhouette knobs need a face-less filled frame, exposure knobs need a
blown-out one, audio knobs need audio. One frame cannot exercise all 50.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .analysis import WebcamSessionAnalyzer
from .types import ClassMode, WebcamSignal
from .vision_tuning import VisionTuning

GRID_W, GRID_H = 64, 36


# --------------------------------------------------------------------- frames
def _flat(value: float) -> list[list[float]]:
    return [[value] * GRID_W for _ in range(GRID_H)]


def _face_blob() -> list[list[float]]:
    """A dark head-and-shoulders blob on a lighter background."""
    return [
        [0.20 if (8 <= y <= 27 and 20 <= x <= 43) else 0.72 for x in range(GRID_W)]
        for y in range(GRID_H)
    ]


def _blown_out() -> list[list[float]]:
    """Mostly clipped-white pixels, so the overexposure knobs are reachable."""
    return [
        [0.99 if x < 48 else 0.30 for x in range(GRID_W)] for y in range(GRID_H)
    ]


def _blurred() -> list[list[float]]:
    """A smooth ramp: no real edges, so the Sobel/sharpness knobs are reachable."""
    return [
        [0.35 + 0.30 * x / (GRID_W - 1) for x in range(GRID_W)] for _ in range(GRID_H)
    ]


def _signal(**overrides: Any) -> WebcamSignal:
    base: dict[str, Any] = {
        "participant_id": "learner",
        "timestamp_ms": 0,
        "face_count": 1,
        "liveness_state": "live",
        "foreground_ratio": 0.45,
        "motion_score": 0.22,
        "detector_source": "face_mesh",
    }
    base.update(overrides)
    return WebcamSignal(**base)


def _scenarios() -> list[tuple[str, list[WebcamSignal]]]:
    """Frame batches ordered so the most widely-read knobs are hit first."""
    return [
        (
            "framed_learner",
            [
                _signal(
                    timestamp_ms=5_000,
                    gaze_frontal=0.55,
                    gaze_down_score=0.30,
                    eyes_closed_score=0.30,
                    yawn_score=0.30,
                    hands_on_face_score=0.30,
                    typing_activity_score=0.30,
                    keyboard_typing_audio_score=0.30,
                    attention=0.6,
                    audio_snr_db=18.0,
                    audio_noise_level_db=40.0,
                    mic_clipping_ratio=0.05,
                    microphone_input_level_score=0.7,
                    luminance_grid=_face_blob(),
                )
            ],
        ),
        (
            "distracted_only",
            # Distraction must be the sole live signal: eyes closed / yawning /
            # hands-on-face are checked first and would mask the distraction knob.
            [
                _signal(
                    gaze_down_score=0.60,
                    gaze_frontal=0.30,
                    eyes_closed_score=0.0,
                    yawn_score=0.0,
                    hands_on_face_score=0.0,
                    typing_activity_score=0.62,
                    keyboard_typing_audio_score=0.60,
                    luminance_grid=_face_blob(),
                )
            ],
        ),
        (
            "silhouette",
            [
                _signal(
                    timestamp_ms=t,
                    face_count=0,
                    liveness_state="unknown",
                    detector_source=None,
                    foreground_ratio=0.97,
                    motion_score=0.02,
                    luminance_grid=_flat(0.15),
                )
                for t in (0, 600, 1_200, 1_800, 2_400)
            ],
        ),
        (
            "no_face",
            [
                _signal(
                    face_count=0,
                    liveness_state="unknown",
                    detector_source=None,
                    foreground_ratio=0.30,
                )
            ],
        ),
        ("no_light_reading", [_signal()]),
        ("blown_out", [_signal(luminance_grid=_blown_out())]),
        ("blurred", [_signal(luminance_grid=_blurred())]),
        (
            "noisy_audio",
            [
                _signal(
                    audio_snr_db=9.0,
                    audio_noise_level_db=58.0,
                    mic_clipping_ratio=0.02,
                    microphone_input_level_score=0.6,
                    luminance_grid=_face_blob(),
                )
            ],
        ),
        (
            "happy",
            [
                _signal(
                    expression_label="happy",
                    expression_confidence=0.9,
                    luminance_grid=_face_blob(),
                )
            ],
        ),
        (
            "far_away",
            [_signal(face_size_ratio=0.07, luminance_grid=_face_blob())],
        ),
        (
            "very_close",
            [_signal(face_size_ratio=0.55, luminance_grid=_face_blob())],
        ),
    ]


# ----------------------------------------------------------------- candidates
# Deliberately wide: values that violate a cross-field rule (e.g. a noise floor
# below audio_noise_clean_db) are rejected by validate() and simply skipped, so
# one list can cover unit-interval, decibel, percentile and metre knobs alike.
_FLOAT_CANDIDATES = (
    0.0, 1.0, 0.5, 0.01, 0.2, 0.35, 0.65, 0.8, 0.95, 0.99,
    1.5, 2.0, 3.0, 5.0, 8.0, 15.0, 25.0, 45.0, 55.0, 60.0, 75.0, 85.0, 99.0, 100.0,
)
_INT_CANDIDATES = (1, 2, 5, 9)


def _candidates(value: Any) -> tuple[Any, ...]:
    if isinstance(value, bool):
        return (not value,)
    if isinstance(value, int):
        return _INT_CANDIDATES
    return _FLOAT_CANDIDATES


def _fingerprint(tuning: VisionTuning, frames: list[WebcamSignal]) -> Any:
    """Everything a knob could plausibly move, for one scenario.

    Frames go through a single fresh analyzer under one session id so streak
    knobs (silhouette_consecutive_frames, the dwell timers) can accumulate.
    """
    analyzer = WebcamSessionAnalyzer(tuning=tuning)
    out = []
    for frame in frames:
        evaluation = analyzer.evaluate(
            session_id="knob-probe",
            mode=ClassMode.SOLO,
            signals=[frame],
        )
        out.append(
            (
                [p.model_dump() for p in evaluation.participants],
                evaluation.quality_summary.model_dump(),
            )
        )
    return out


@dataclass
class KnobProbeResult:
    live: dict[str, str] = field(default_factory=dict)
    dead: list[str] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.dead

    @property
    def total(self) -> int:
        return len(self.live) + len(self.dead)

    def summary(self) -> str:
        return (
            f"{len(self.live)}/{self.total} knobs change a scoring decision "
            f"across {len(self.scenarios)} frame scenarios"
        )


def probe_knob_effects(
    baseline: VisionTuning | None = None,
    *,
    only: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> KnobProbeResult:
    """Perturb each knob and report which ones measurably change an evaluation."""
    baseline = baseline or VisionTuning()
    scenarios = _scenarios()
    result = KnobProbeResult(scenarios=[name for name, _ in scenarios])

    # One baseline fingerprint per scenario, reused across every knob.
    reference = {name: _fingerprint(baseline, frames) for name, frames in scenarios}
    defaults = baseline.to_dict()
    names = [n for n in sorted(defaults) if only is None or n in only]

    for knob in names:
        if on_progress is not None:
            on_progress(knob)
        default = defaults[knob]
        hit: str | None = None
        for scenario_name, frames in scenarios:
            for candidate in _candidates(default):
                if candidate == default:
                    continue
                try:
                    probe = baseline.patched({knob: type(default)(candidate)})
                except (ValueError, TypeError):
                    continue
                if probe.to_dict()[knob] == default:
                    continue
                try:
                    changed = _fingerprint(probe, frames) != reference[scenario_name]
                except Exception:  # noqa: BLE001 - a raising knob is still "live"
                    changed = True
                if changed:
                    hit = scenario_name
                    break
            if hit:
                break
        if hit:
            result.live[knob] = hit
        else:
            result.dead.append(knob)
    return result
