"""Regression tests for the 2026-08-17 audit (webcam lab).

- Owner lock: a same-seat stranger (identical bbox, different geometry) must
  not pass on IoU alone, and the template must not adapt to them.
- Class-level pause/presence must use the empty-frame face-count correction
  (a thin client reporting face_count=1 over an empty grid).
"""

from __future__ import annotations

from theodore_webcam_lab.analysis import ClassMode, WebcamSessionAnalyzer
from theodore_webcam_lab.face_owner import (
    OWNER_ENROLL_HOLD_MS,
    pick_owner_face,
    reset_owner_state,
)
from theodore_webcam_lab.types import WebcamSignal


def _face(cx: float, cy: float, scale: float = 0.12, *, stretch: float = 1.0) -> list[dict[str, float]]:
    pts = [{"x": cx, "y": cy} for _ in range(300)]
    pts[33] = {"x": cx - scale * 0.45, "y": cy}
    pts[263] = {"x": cx + scale * 0.45, "y": cy}
    pts[1] = {"x": cx, "y": cy + scale * 0.15 * stretch}
    pts[61] = {"x": cx - scale * 0.25, "y": cy + scale * 0.45 * stretch}
    pts[291] = {"x": cx + scale * 0.25, "y": cy + scale * 0.45 * stretch}
    pts[10] = {"x": cx, "y": cy - scale * 0.55 * stretch}
    pts[152] = {"x": cx, "y": cy + scale * 0.85 * stretch}
    pts[0] = {"x": cx - scale * 0.55, "y": cy}
    pts[50] = {"x": cx + scale * 0.55, "y": cy}
    pts[100] = {"x": cx, "y": cy - scale * 0.7 * stretch}
    pts[200] = {"x": cx, "y": cy + scale * 0.95 * stretch}
    return pts


def test_same_seat_stranger_cannot_pass_on_iou_alone():
    state = reset_owner_state()
    owner = _face(0.4, 0.45, scale=0.15)
    pick_owner_face([owner], state, now_ms=100)
    pick_owner_face([owner], state, now_ms=100 + OWNER_ENROLL_HOLD_MS + 10)
    assert state.enrolled

    # Identical box, substantially different internal geometry.
    stranger = _face(0.4, 0.45, scale=0.15, stretch=1.9)
    pick = pick_owner_face([stranger], state, now_ms=5_000)
    assert pick.owner_match is False

    # The template must not have drifted toward the stranger: the real owner
    # still matches immediately and strongly.
    back = pick_owner_face([owner], state, now_ms=6_000)
    assert back.owner_match is True
    assert back.match_score >= 0.9


def _empty_grid() -> list[list[float]]:
    # Uniform mid-dark grid: no face-like blob (low variance, no edges).
    return [[0.05 for _ in range(64)] for _ in range(36)]


def test_class_pause_uses_empty_frame_face_correction():
    analyzer = WebcamSessionAnalyzer()
    # Thin client claims a face, but the luminance grid looks empty and no
    # expression/gaze data backs the claim.
    signal = WebcamSignal(
        participant_id="learner",
        timestamp_ms=1_000,
        face_count=1,
        liveness_state="live",
        foreground_ratio=0.0,
        motion_score=0.0,
        luminance_grid=_empty_grid(),
    )
    # First eval starts the no-presence clock; second eval past the default
    # pause window must pause training.
    analyzer.evaluate(session_id="s1", mode=ClassMode.SOLO, signals=[signal])
    signal2 = signal.model_copy(update={"timestamp_ms": 6_000})
    out = analyzer.evaluate(session_id="s1", mode=ClassMode.SOLO, signals=[signal2])
    assert out.no_one_present_for_ms > 0, (
        "class-level presence ignored the empty-frame correction"
    )
