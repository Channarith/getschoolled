"""Original-owner face lock: enroll largest face, match by IoU + fingerprint."""

from __future__ import annotations

from theodore_webcam_lab.face_owner import (
    FACE_OWNER_MAX_FACES,
    OWNER_ENROLL_HOLD_MS,
    FaceBox,
    box_iou,
    face_box_from_landmarks,
    face_fingerprint,
    fingerprint_distance,
    largest_face_index,
    pick_owner_face,
    reset_owner_state,
)
from theodore_webcam_lab.monitor_page import MONITOR_JS


def _face(cx: float, cy: float, scale: float = 0.12, *, stretch: float = 1.0) -> list[dict[str, float]]:
    """Sparse landmark list with the fingerprint indices populated.

    Unused landmarks sit at the face center so they do not inflate the bbox.
    ``stretch`` scales vertical features to create a distinct fingerprint.
    """
    pts = [{"x": cx, "y": cy} for _ in range(300)]
    # Eyes left/right of center; nose/mouth/chin/forehead relative to mid-eye.
    pts[33] = {"x": cx - scale * 0.45, "y": cy}
    pts[263] = {"x": cx + scale * 0.45, "y": cy}
    pts[1] = {"x": cx, "y": cy + scale * 0.15 * stretch}
    pts[61] = {"x": cx - scale * 0.25, "y": cy + scale * 0.45 * stretch}
    pts[291] = {"x": cx + scale * 0.25, "y": cy + scale * 0.45 * stretch}
    pts[10] = {"x": cx, "y": cy - scale * 0.55 * stretch}
    pts[152] = {"x": cx, "y": cy + scale * 0.85 * stretch}
    # Oval extremes so bbox area reflects scale (not origin zeros).
    pts[0] = {"x": cx - scale * 0.55, "y": cy}
    pts[50] = {"x": cx + scale * 0.55, "y": cy}
    pts[100] = {"x": cx, "y": cy - scale * 0.7 * stretch}
    pts[200] = {"x": cx, "y": cy + scale * 0.95 * stretch}
    return pts


def test_constants_match_monitor_js():
    assert f"const FACE_OWNER_MAX_FACES = {FACE_OWNER_MAX_FACES};" in MONITOR_JS
    assert f"const OWNER_ENROLL_HOLD_MS = {OWNER_ENROLL_HOLD_MS};" in MONITOR_JS
    assert "numFaces: FACE_OWNER_MAX_FACES" in MONITOR_JS
    assert "function pickOwnerFace(" in MONITOR_JS
    assert "function quietMediaPipeConsole(" in MONITOR_JS
    assert "function resetFaceOwner(" in MONITOR_JS


def test_largest_face_is_preferred_before_enrollment():
    small = _face(0.7, 0.4, scale=0.06)
    large = _face(0.3, 0.45, scale=0.18)
    assert largest_face_index([small, large]) == 1
    assert largest_face_index([large, small]) == 0


def test_enrolls_after_hold_then_tracks_owner_not_intruder():
    state = reset_owner_state()
    owner = _face(0.35, 0.42, scale=0.16)
    # Hold the same largest face across the enrollment window.
    pick1 = pick_owner_face([owner], state, now_ms=1_000)
    assert pick1.owner_enrolled is False
    assert pick1.index == 0
    pick2 = pick_owner_face([owner], state, now_ms=1_000 + OWNER_ENROLL_HOLD_MS + 50)
    assert pick2.owner_enrolled is True
    assert pick2.owner_match is True

    # Second person is larger / more frontal — still track the enrolled owner.
    intruder = _face(0.72, 0.40, scale=0.22, stretch=1.6)
    pick3 = pick_owner_face([intruder, owner], state, now_ms=3_000)
    assert pick3.owner_enrolled is True
    assert pick3.owner_match is True
    assert pick3.index == 1  # owner, not the larger intruder
    assert pick3.secondary_count == 1
    assert pick3.face_count == 2


def test_substitution_when_owner_leaves_and_stranger_remains():
    state = reset_owner_state()
    owner = _face(0.4, 0.45, scale=0.15)
    pick_owner_face([owner], state, now_ms=100)
    pick_owner_face([owner], state, now_ms=100 + OWNER_ENROLL_HOLD_MS + 10)
    assert state.enrolled is True

    # Different proportions + far bbox → below OWNER_MATCH_SCORE_MIN.
    stranger = _face(0.78, 0.55, scale=0.11, stretch=2.2)
    pick = pick_owner_face([stranger], state, now_ms=5_000)
    assert pick.owner_enrolled is True
    assert pick.owner_match is False
    assert pick.face_count == 1
    assert pick.secondary_count == 0


def test_empty_frame_after_enroll_is_not_a_mismatch():
    state = reset_owner_state()
    owner = _face(0.4, 0.45, scale=0.15)
    pick_owner_face([owner], state, now_ms=100)
    pick_owner_face([owner], state, now_ms=100 + OWNER_ENROLL_HOLD_MS + 10)
    empty = pick_owner_face([], state, now_ms=5_000)
    assert empty.owner_enrolled is True
    assert empty.owner_match is None
    assert empty.face_count == 0


def test_fingerprint_distance_is_small_for_same_geometry():
    a = _face(0.5, 0.5, scale=0.12)
    b = _face(0.55, 0.48, scale=0.12)  # translated — fingerprint is mid-eye relative
    fa, fb = face_fingerprint(a), face_fingerprint(b)
    assert fa is not None and fb is not None
    assert fingerprint_distance(fa, fb) < 0.05


def test_box_iou_and_area_helpers():
    a = FaceBox(0.1, 0.1, 0.4, 0.4)
    b = FaceBox(0.3, 0.3, 0.4, 0.4)
    assert 0.1 < box_iou(a, b) < 0.5
    box = face_box_from_landmarks(_face(0.5, 0.5, 0.1))
    assert box is not None and box.area > 0
