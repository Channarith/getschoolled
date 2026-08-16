"""Trajectory geometry + music/held-object helpers, with JS parity pins."""

from __future__ import annotations

import re

import pytest

from theodore_webcam_lab.monitor_page import MONITOR_JS
from theodore_webcam_lab.trajectory_geometry import (
    DEFAULT_TRAJECTORY_TUNING,
    LandmarkSample,
    evaluate_trajectory,
    excitement_score,
    external_music_score,
    held_object_score,
    interest_score,
)


def _history(*, pitch_start: float = 0.0, pitch_end: float = 0.0, n: int = 6, face_grow: float = 0.0):
    samples = []
    for i in range(n):
        t = i / max(1, n - 1)
        samples.append(
            LandmarkSample(
                timestamp_ms=i * 300,
                nose_y=0.50 + (0.02 if i % 2 else 0.0),
                brow_y=0.30,
                chin_y=0.70,
                eye_mid_x=0.50,
                eye_mid_y=0.40,
                face_size=0.22 + face_grow * t,
                pitch_deg=pitch_start + (pitch_end - pitch_start) * t,
                brow_raise=0.4 if face_grow > 0 else 0.1,
                smile=0.3 if face_grow > 0 else 0.05,
                gaze_frontal=0.85,
                hand_wrist_y=0.80 if i % 2 else 0.82,
                hand_tip_y=0.75 if i % 2 else 0.78,
            )
        )
    return samples


def test_excitement_ignores_whole_frame_camera_shifts():
    assert excitement_score(face_energy=0.7, hand_energy=0.5, global_motion=0.80) == 0.0
    assert excitement_score(face_energy=0.7, hand_energy=0.5, global_motion=0.20) > 0.4


def test_interest_requires_lean_in_and_quiet_fidget():
    assert interest_score(
        face_size_delta=0.10,
        gaze_frontal=0.9,
        brow_raise=0.4,
        face_energy=0.15,
        global_motion=0.1,
        fidget=0.1,
    ) > 0.5
    assert interest_score(
        face_size_delta=0.10,
        gaze_frontal=0.9,
        brow_raise=0.4,
        face_energy=0.15,
        global_motion=0.1,
        fidget=0.85,
    ) == 0.0


def test_dozing_from_head_sag_and_still_face():
    reading = evaluate_trajectory(
        _history(pitch_start=0.0, pitch_end=25.0),
        global_motion=0.05,
        eyes_closed_score=0.2,
    )
    assert reading.head_sag_rate > 0.4
    assert reading.dozing_score > 0.35


def test_lean_in_history_raises_interest():
    reading = evaluate_trajectory(
        _history(face_grow=0.10),
        global_motion=0.05,
        fidget=0.1,
    )
    assert reading.interest_score > 0.35


def test_external_music_is_opposite_of_ringtone():
    # Ringtone-like: high prominence, steady peak, low flux → not music.
    assert external_music_score(
        elevated=True, flux=1.0, prominence=18.0, steady_peak=True,
        speech_ratio=0.3, sharp_attack=False, music_active_ms=3000,
    ) == 0.0
    # Music-like: high flux, low prominence → scores.
    score = external_music_score(
        elevated=True, flux=3.5, prominence=6.0, steady_peak=False,
        speech_ratio=0.4, sharp_attack=False, music_active_ms=2500,
    )
    assert score >= 0.9


def test_held_object_needs_a_visual_cue():
    assert held_object_score(phone_grid=0.0, phone_stare=0.0, hand_below_face=0.9) == 0.0
    assert held_object_score(phone_grid=0.7, phone_stare=0.4, hand_below_face=0.8) > 0.5


def _js_const(name: str) -> float:
    match = re.search(rf"const {name} = (-?[\d.]+);", MONITOR_JS)
    assert match, f"{name} missing from monitor JS"
    return float(match.group(1))


def test_js_trajectory_constants_match_python():
    t = DEFAULT_TRAJECTORY_TUNING
    assert _js_const("TRAJ_GLOBAL_MOTION_SUPPRESS") == t.global_motion_suppress
    assert _js_const("TRAJ_FACE_ENERGY_REF") == t.face_energy_ref
    assert _js_const("TRAJ_HAND_ENERGY_REF") == t.hand_energy_ref
    assert _js_const("TRAJ_SAG_REF_DEG_PER_S") == t.sag_ref_deg_per_s


def test_js_trajectory_formulas_are_present():
    for name in (
        "trajExcitementScore",
        "trajInterestScore",
        "trajDozingScore",
        "trajExternalMusicScore",
        "trajHeldObjectScore",
        "computeTrajectoryFeatures",
    ):
        assert f"function {name}" in MONITOR_JS


def test_js_music_accumulates_separately_from_ringtone():
    assert "musicActiveMs" in MONITOR_JS
    poll = MONITOR_JS.split("function pollAudioDetector()")[1].split("function sampleClickDetector")[0]
    assert "const musical =" in poll
    assert "musicActiveMs" in poll
    # Ringtone path must stay narrow-tone.
    assert "prominence > 14" in poll
    assert "flux < 2.5" in poll
