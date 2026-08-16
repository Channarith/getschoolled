"""Pre-class lighting gate thresholds stay aligned with VisionTuning defaults."""

from __future__ import annotations

from theodore_webcam_lab.imaging import analyze_luminance_grid
from theodore_webcam_lab.vision_tuning import VisionTuning


def _flat(value: float, h: int = 36, w: int = 64) -> list[list[float]]:
    return [[value] * w for _ in range(h)]


def test_dark_room_trips_underexposure_like_the_class_gate():
    analysis = analyze_luminance_grid(_flat(0.04), tuning=VisionTuning())
    assert analysis.underexposed
    assert "lighting_underexposed" in analysis.flags or analysis.light_quality_score < 0.35


def test_blown_out_room_trips_overexposure_like_the_class_gate():
    analysis = analyze_luminance_grid(_flat(0.97), tuning=VisionTuning())
    assert analysis.overexposed
    assert "lighting_overexposed" in analysis.flags


def test_mid_lit_contrast_grid_is_usable():
    # Soft face blob — enough structure for edges, not so dark it trips black clip.
    grid = [
        [0.35 if (8 <= y <= 27 and 20 <= x <= 43) else 0.58 for x in range(64)]
        for y in range(36)
    ]
    analysis = analyze_luminance_grid(grid, tuning=VisionTuning())
    assert not analysis.overexposed
    assert analysis.light_quality_score >= 0.20
    assert not analysis.blurry
