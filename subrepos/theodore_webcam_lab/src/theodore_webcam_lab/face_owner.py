"""Original-owner Face ID helpers (browser + server parity).

The live monitor enrolls the first stable face as a named Face ID, then keeps
tracking that person when others enter the frame. Matching is lightweight
(bbox IoU + a landmark geometry fingerprint) — enough to stop "wrong person
mesh" and pause teaching on substitution without a full recognition model.

Setup can overwrite the Face ID (re-enroll) and assign a display name. Non-
matching faces are secondary only: they do not drive attention / mood, and a
mismatch pauses solo teaching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# Keep in sync with MONITOR_JS FACE_OWNER_* constants.
FACE_OWNER_MAX_FACES = 4
OWNER_ENROLL_HOLD_MS = 1500
OWNER_MATCH_IOU_MIN = 0.22
OWNER_MATCH_FP_MAX = 0.38
# Above the IoU-only ceiling (0.45): continuity alone can never pass — the
# fingerprint (identity) must contribute.
OWNER_MATCH_SCORE_MIN = 0.55
# Softer gate while we are still holding the first-seen Face ID candidate.
OWNER_ENROLL_SCORE_MIN = 0.28
# Identity veto: below this fingerprint sub-score the face is not the owner no
# matter how well the box overlaps (a same-seat stranger passed on IoU alone).
OWNER_MATCH_FP_MIN = 0.25
# The template only adapts on a strong identity match — a marginal match must
# not drift the enrolled fingerprint toward a substitute.
OWNER_ADAPT_FP_MIN = 0.5

# MediaPipe Face Mesh indices used for the geometry fingerprint.
_FP_IDX = (33, 263, 1, 61, 291, 10, 152)


@dataclass
class FaceBox:
    x: float
    y: float
    w: float
    h: float

    @property
    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)


@dataclass
class OwnerState:
    enrolled: bool = False
    enroll_started_ms: int = 0
    fingerprint: list[float] | None = None
    last_box: FaceBox | None = None
    match_score: float = 0.0
    candidate_hold_ms: int = 0
    display_name: str = ""


@dataclass
class OwnerPick:
    index: int
    state: OwnerState
    owner_enrolled: bool
    owner_match: bool | None
    match_score: float
    secondary_count: int
    face_count: int
    display_name: str = ""


def face_box_from_landmarks(pts: Sequence[object]) -> FaceBox | None:
    if not pts:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for p in pts:
        if isinstance(p, dict):
            x, y = float(p["x"]), float(p["y"])
        else:
            x, y = float(getattr(p, "x")), float(getattr(p, "y"))
        xs.append(x)
        ys.append(y)
    if not xs:
        return None
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return FaceBox(x=min_x, y=min_y, w=max_x - min_x, h=max_y - min_y)


def box_iou(a: FaceBox | None, b: FaceBox | None) -> float:
    if a is None or b is None:
        return 0.0
    x0 = max(a.x, b.x)
    y0 = max(a.y, b.y)
    x1 = min(a.x + a.w, b.x + b.w)
    y1 = min(a.y + a.h, b.y + b.h)
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    if inter <= 0:
        return 0.0
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def _pt(pts: Sequence[object], idx: int) -> tuple[float, float] | None:
    if idx < 0 or idx >= len(pts):
        return None
    p = pts[idx]
    if isinstance(p, dict):
        return float(p["x"]), float(p["y"])
    return float(getattr(p, "x")), float(getattr(p, "y"))


def face_fingerprint(pts: Sequence[object]) -> list[float] | None:
    """Scale-normalized geometry signature of key landmarks."""
    left = _pt(pts, 33)
    right = _pt(pts, 263)
    if not left or not right:
        return None
    iod = ((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) ** 0.5
    if iod < 1e-6:
        return None
    mid_x = (left[0] + right[0]) / 2.0
    mid_y = (left[1] + right[1]) / 2.0
    out: list[float] = []
    for idx in _FP_IDX:
        p = _pt(pts, idx)
        if not p:
            return None
        out.append((p[0] - mid_x) / iod)
        out.append((p[1] - mid_y) / iod)
    return out


def fingerprint_distance(a: Sequence[float] | None, b: Sequence[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 1.0
    acc = sum((float(x) - float(y)) ** 2 for x, y in zip(a, b))
    return (acc / len(a)) ** 0.5


def largest_face_index(faces: Sequence[Sequence[object]]) -> int:
    best_i, best_a = 0, -1.0
    for i, pts in enumerate(faces):
        box = face_box_from_landmarks(pts)
        area = box.area if box else 0.0
        if area > best_a:
            best_a = area
            best_i = i
    return best_i


def match_parts_for_face(
    pts: Sequence[object],
    state: OwnerState,
) -> tuple[float, float]:
    """Return (combined 0..1 score, fingerprint sub-score 0..1)."""
    box = face_box_from_landmarks(pts)
    iou = box_iou(box, state.last_box)
    fp = face_fingerprint(pts)
    fp_dist = fingerprint_distance(fp, state.fingerprint)
    fp_part = max(0.0, 1.0 - fp_dist / max(OWNER_MATCH_FP_MAX, 1e-6))
    # Weight continuity (IoU) and identity (fingerprint) together.
    return max(0.0, min(1.0, 0.45 * iou + 0.55 * fp_part)), fp_part


def match_score_for_face(
    pts: Sequence[object],
    state: OwnerState,
) -> float:
    """0..1 similarity to the enrolled / candidate Face ID (IoU + fingerprint)."""
    return match_parts_for_face(pts, state)[0]


def best_face_index(
    faces: Sequence[Sequence[object]],
    state: OwnerState,
    *,
    min_score: float,
) -> tuple[int, float]:
    best_i, best_score = -1, -1.0
    for i, pts in enumerate(faces):
        score = match_score_for_face(pts, state)
        if score > best_score:
            best_score = score
            best_i = i
    if best_i < 0 or best_score < min_score:
        return -1, max(0.0, best_score)
    return best_i, best_score


def enroll_owner(
    pts: Sequence[object],
    state: OwnerState,
    *,
    name: str = "",
    now_ms: int = 0,
) -> OwnerState:
    """Overwrite Face ID with this face (setup / re-enroll)."""
    box = face_box_from_landmarks(pts)
    fp = face_fingerprint(pts)
    if box is None or fp is None:
        raise ValueError("Cannot enroll Face ID without a usable face mesh")
    state.enrolled = True
    state.fingerprint = list(fp)
    state.last_box = box
    state.match_score = 1.0
    state.enroll_started_ms = now_ms
    state.candidate_hold_ms = OWNER_ENROLL_HOLD_MS
    cleaned = (name or state.display_name or "").strip()
    state.display_name = cleaned or "Learner"
    return state


def clear_owner(state: OwnerState | None = None) -> OwnerState:
    _ = state  # name is intentionally cleared with the profile
    return OwnerState()


def pick_owner_face(
    faces: Sequence[Sequence[object]],
    state: OwnerState,
    now_ms: int,
) -> OwnerPick:
    """Choose the Face ID face; ignore non-matching faces for tracking."""
    face_count = len(faces)
    name = (state.display_name or "").strip()
    if face_count == 0:
        return OwnerPick(
            index=-1,
            state=state,
            owner_enrolled=state.enrolled,
            owner_match=None,
            match_score=0.0,
            secondary_count=0,
            face_count=0,
            display_name=name,
        )

    if not state.enrolled:
        # First sighting: lock the largest face as the candidate and do not
        # switch to a different (even larger) person mid-hold.
        has_candidate = state.fingerprint is not None or state.last_box is not None
        if has_candidate:
            idx, score = best_face_index(
                faces, state, min_score=OWNER_ENROLL_SCORE_MIN
            )
            if idx < 0:
                # Candidate left the frame — start over with whoever is largest.
                idx = largest_face_index(faces)
                state.enroll_started_ms = now_ms
                state.candidate_hold_ms = 0
                state.last_box = face_box_from_landmarks(faces[idx])
                fp = face_fingerprint(faces[idx])
                state.fingerprint = list(fp) if fp else None
                return OwnerPick(
                    index=idx,
                    state=state,
                    owner_enrolled=False,
                    owner_match=None,
                    match_score=0.0,
                    secondary_count=max(0, face_count - 1),
                    face_count=face_count,
                    display_name=name,
                )
            box = face_box_from_landmarks(faces[idx])
            fp = face_fingerprint(faces[idx])
            if state.enroll_started_ms <= 0:
                state.enroll_started_ms = now_ms
            held = now_ms - state.enroll_started_ms
            state.candidate_hold_ms = max(0, held)
            state.last_box = box
            if fp is not None:
                state.fingerprint = list(fp)
            if held >= OWNER_ENROLL_HOLD_MS and fp is not None and box is not None:
                state.enrolled = True
                state.match_score = 1.0
                if not state.display_name.strip():
                    state.display_name = "Learner"
                return OwnerPick(
                    index=idx,
                    state=state,
                    owner_enrolled=True,
                    owner_match=True,
                    match_score=1.0,
                    secondary_count=max(0, face_count - 1),
                    face_count=face_count,
                    display_name=state.display_name,
                )
            return OwnerPick(
                index=idx,
                state=state,
                owner_enrolled=False,
                owner_match=None,
                match_score=score,
                secondary_count=max(0, face_count - 1),
                face_count=face_count,
                display_name=name,
            )

        idx = largest_face_index(faces)
        box = face_box_from_landmarks(faces[idx])
        fp = face_fingerprint(faces[idx])
        state.enroll_started_ms = now_ms
        state.candidate_hold_ms = 0
        state.last_box = box
        state.fingerprint = list(fp) if fp else None
        return OwnerPick(
            index=idx,
            state=state,
            owner_enrolled=False,
            owner_match=None,
            match_score=0.0,
            secondary_count=max(0, face_count - 1),
            face_count=face_count,
            display_name=name,
        )

    # Enrolled Face ID: score every face; only a match drives tracking.
    best_i, best_score, best_fp_part = 0, -1.0, 0.0
    for i, pts in enumerate(faces):
        score, fp_part = match_parts_for_face(pts, state)
        if score > best_score:
            best_score = score
            best_fp_part = fp_part
            best_i = i
    # Combined threshold AND identity floor — IoU alone (max 0.45) can no
    # longer carry a same-seat stranger past the lock.
    matched = best_score >= OWNER_MATCH_SCORE_MIN and best_fp_part >= OWNER_MATCH_FP_MIN
    if matched:
        box = face_box_from_landmarks(faces[best_i])
        if box is not None:
            if state.last_box is None:
                state.last_box = box
            else:
                state.last_box = FaceBox(
                    x=0.7 * state.last_box.x + 0.3 * box.x,
                    y=0.7 * state.last_box.y + 0.3 * box.y,
                    w=0.7 * state.last_box.w + 0.3 * box.w,
                    h=0.7 * state.last_box.h + 0.3 * box.h,
                )
            fp = face_fingerprint(faces[best_i])
            if (
                fp is not None
                and state.fingerprint is not None
                and best_fp_part >= OWNER_ADAPT_FP_MIN
            ):
                state.fingerprint = [
                    0.85 * a + 0.15 * b for a, b in zip(state.fingerprint, fp)
                ]
        state.match_score = best_score
        return OwnerPick(
            index=best_i,
            state=state,
            owner_enrolled=True,
            owner_match=True,
            match_score=best_score,
            secondary_count=max(0, face_count - 1),
            face_count=face_count,
            display_name=name or state.display_name,
        )

    # Someone is in frame but nobody matches Face ID — do not hand metrics to
    # the stranger (index=-1). Teaching must pause until the enrolled person returns.
    _, raw_best = best_face_index(faces, state, min_score=0.0)
    state.match_score = raw_best
    return OwnerPick(
        index=-1,
        state=state,
        owner_enrolled=True,
        owner_match=False,
        match_score=raw_best,
        secondary_count=face_count,
        face_count=face_count,
        display_name=name or state.display_name,
    )


def reset_owner_state(*, display_name: str = "") -> OwnerState:
    return OwnerState(display_name=(display_name or "").strip())
