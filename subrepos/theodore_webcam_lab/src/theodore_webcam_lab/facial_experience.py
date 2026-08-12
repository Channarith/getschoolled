"""Heuristic facial-experience estimates from a luminance grid.

The live monitor often has no on-device ML model. When a client posts a
luminance grid without expression/gaze fields, we derive a coarse but
actionable mood + attention signal so happiness / sadness / away-from-webcam
show up in the dashboard instead of staying stuck at ``unknown`` / 75%.

This is intentionally a lightweight geometric + brightness heuristic — good
enough for teaching demos and gating, not a replacement for a trained
expression network (see VISION_TRAINING_OPERATIONS.txt).
"""

from __future__ import annotations

from dataclasses import dataclass

from .distance import face_size_ratio_from_dark_bbox


@dataclass(frozen=True)
class FacialExperienceEstimate:
    expression_label: str
    expression_confidence: float
    gaze_frontal: float
    gaze_down_score: float
    face_size_ratio: float | None
    face_present: bool
    attention: str  # looking | eyes_away | away_from_webcam
    smile_score: float
    sad_score: float
    yawn_score: float = 0.0


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _roi(grid: list[list[float]], y0: float, y1: float, x0: float, x1: float) -> list[float]:
    h = len(grid)
    w = len(grid[0]) if h else 0
    if h < 3 or w < 3:
        return []
    r0 = max(0, min(h - 1, int(h * y0)))
    r1 = max(r0 + 1, min(h, int(h * y1)))
    c0 = max(0, min(w - 1, int(w * x0)))
    c1 = max(c0 + 1, min(w, int(w * x1)))
    out: list[float] = []
    for y in range(r0, r1):
        row = grid[y]
        for x in range(c0, c1):
            out.append(float(row[x]))
    return out


def _horizontal_edge_energy(grid: list[list[float]], y0: float, y1: float, x0: float, x1: float) -> float:
    """Average absolute horizontal gradient in a ROI — smiles raise mouth-band edges."""
    h = len(grid)
    w = len(grid[0]) if h else 0
    if h < 3 or w < 3:
        return 0.0
    r0 = max(0, min(h - 1, int(h * y0)))
    r1 = max(r0 + 1, min(h, int(h * y1)))
    c0 = max(0, min(w - 2, int(w * x0)))
    c1 = max(c0 + 1, min(w - 1, int(w * x1)))
    total = 0.0
    n = 0
    for y in range(r0, r1):
        row = grid[y]
        for x in range(c0, c1):
            total += abs(float(row[x + 1]) - float(row[x]))
            n += 1
    return total / n if n else 0.0


def estimate_from_luminance_grid(grid: list[list[float]] | None) -> FacialExperienceEstimate | None:
    """Return a facial-experience estimate, or None if the grid is unusable."""
    if not grid or not grid[0]:
        return None
    try:
        h = len(grid)
        w = len(grid[0])
        if h < 8 or w < 8:
            return None
        for row in grid:
            if len(row) != w:
                return None
    except (TypeError, ValueError):
        return None

    # Selfie framing: face usually sits in the central column, upper-middle rows.
    face_vals = _roi(grid, 0.08, 0.78, 0.22, 0.78)
    if not face_vals:
        return None
    face_mean = _mean(face_vals)
    face_var = _mean([(v - face_mean) ** 2 for v in face_vals])
    face_std = face_var**0.5

    # Empty room / stepped away: flat mid-tone scene with little structure.
    eye_band = _roi(grid, 0.12, 0.38, 0.28, 0.72)
    mouth_band = _roi(grid, 0.48, 0.72, 0.30, 0.70)
    cheek_band = _roi(grid, 0.38, 0.55, 0.22, 0.78)
    eye_mean = _mean(eye_band)
    mouth_mean = _mean(mouth_band)
    cheek_mean = _mean(cheek_band)
    mouth_edges = _horizontal_edge_energy(grid, 0.50, 0.70, 0.32, 0.68)
    eye_edges = _horizontal_edge_energy(grid, 0.14, 0.34, 0.30, 0.70)

    # Vertical mass of darker-than-average pixels approximates head position.
    dark_mass_y = 0.0
    dark_mass_x = 0.0
    dark_n = 0
    threshold = face_mean - 0.04
    # Restrict to the facial ROI so hats/clothing/dark backgrounds do not
    # pull the centroid away from the actual face and corrupt gaze estimates.
    cr0 = int(h * 0.08)
    cr1 = int(h * 0.78)
    cc0 = int(w * 0.22)
    cc1 = int(w * 0.78)
    for yi in range(cr0, cr1):
        row = grid[yi]
        for xi in range(cc0, cc1):
            v = float(row[xi])
            if v < threshold:
                dark_mass_y += yi
                dark_mass_x += xi
                dark_n += 1
    cy = (dark_mass_y / dark_n / max(1, h - 1)) if dark_n else 0.5
    cx = (dark_mass_x / dark_n / max(1, w - 1)) if dark_n else 0.5
    roi_area = max(1, (cr1 - cr0) * (cc1 - cc0))
    dark_ratio = dark_n / float(roi_area)

    # Away: almost no person-shaped contrast / dark mass in the frame.
    face_present = face_std >= 0.045 and dark_ratio >= 0.04 and dark_ratio <= 0.72
    if not face_present:
        return FacialExperienceEstimate(
            expression_label="unknown",
            expression_confidence=0.55,
            gaze_frontal=0.12,
            gaze_down_score=0.15,
            face_size_ratio=None,
            face_present=False,
            attention="away_from_webcam",
            smile_score=0.0,
            sad_score=0.0,
        )

    # Gaze: head mass lower in frame → looking down; off-center → less frontal.
    gaze_down = _clamp01((cy - 0.38) / 0.42)
    gaze_frontal = _clamp01(1.0 - abs(cx - 0.5) * 2.4 - max(0.0, gaze_down - 0.55) * 0.35)

    # Smile raises mouth-band horizontal structure relative to cheeks.
    smile_raw = _clamp01((mouth_edges - 0.035) / 0.08 + max(0.0, mouth_mean - cheek_mean) * 1.8)
    # Suppress smile when gaze_down indicates a drooping/sleepy head — the jaw and
    # chin slide into the mouth band at that angle and produce false smile edges.
    smile_score = smile_raw * max(0.0, 1.0 - max(0.0, gaze_down - 0.20) / 0.50)
    # Sad / flat affect: eyes relatively darker, mouth edges weak.
    sad_score = _clamp01(
        max(0.0, (cheek_mean - eye_mean) * 2.2)
        + max(0.0, 0.05 - mouth_edges) * 8.0
        + max(0.0, 0.55 - smile_score) * 0.35
    )

    if smile_score >= 0.55 and smile_score >= sad_score + 0.08:
        expression = "happy"
        confidence = _clamp01(0.45 + smile_score * 0.5)
    elif sad_score >= 0.52 and sad_score > smile_score + 0.05:
        expression = "sad"
        confidence = _clamp01(0.42 + sad_score * 0.5)
    else:
        expression = "neutral"
        confidence = _clamp01(0.40 + (1.0 - abs(smile_score - sad_score)) * 0.35)

    attention = "looking"
    if gaze_down >= 0.60 or gaze_frontal < 0.35:
        attention = "eyes_away"

    # Linear face size vs frame (larger ⇒ closer). Prefer dark-pixel bbox height.
    face_size_ratio = face_size_ratio_from_dark_bbox(grid)
    if face_size_ratio is None:
        face_size_ratio = _clamp01(dark_ratio * 1.8 + eye_edges * 2.0)
        face_size_ratio = face_size_ratio if face_size_ratio > 0.04 else 0.12

    return FacialExperienceEstimate(
        expression_label=expression,
        expression_confidence=confidence,
        gaze_frontal=gaze_frontal,
        gaze_down_score=gaze_down,
        face_size_ratio=face_size_ratio,
        face_present=True,
        attention=attention,
        smile_score=smile_score,
        sad_score=sad_score,
    )
