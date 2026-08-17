"""Sobel edge / exposure analysis for webcam frames.

The lab normally consumes scalar signals that a client computed on-device. This
module lets the server derive those signals itself from a luminance grid, so a
thin client can post raw brightness values and still get calibrated sharpness and
exposure readings.

Pure standard library on purpose: it runs on any box with no OpenCV/numpy wheel,
which keeps the offline teaching loop working. numpy is used automatically when
importable because it is ~50x faster on large grids.

Pipeline:
  1. 3x3 Sobel Gx/Gy -> gradient magnitude per interior pixel
  2. magnitudes normalised to 0..1 (Sobel's theoretical max is 4x the input range)
  3. binary threshold (tuning.sobel_binary_threshold) -> edge mask
  4. edge_density = edges / interior pixels; low density means defocus/blur
  5. exposure stats: mean luminance plus clipped-black / clipped-white ratios

Sharpness and lighting are then scored 0..1 against the active VisionTuning.
"""

from __future__ import annotations

from dataclasses import dataclass

from .vision_tuning import VisionTuning

try:  # pragma: no cover - exercised implicitly by whichever path is available
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None

# Sobel magnitude ceiling: each kernel can reach 4x the pixel range, and the
# magnitude combines two kernels, so normalise by 4 * sqrt(2).
_SOBEL_MAX = 4.0 * (2.0**0.5)

_SOBEL_X = ((-1.0, 0.0, 1.0), (-2.0, 0.0, 2.0), (-1.0, 0.0, 1.0))
_SOBEL_Y = ((-1.0, -2.0, -1.0), (0.0, 0.0, 0.0), (1.0, 2.0, 1.0))


@dataclass(frozen=True)
class ImagingAnalysis:
    width: int
    height: int
    mean_luminance: float
    underexposed_ratio: float
    overexposed_ratio: float
    mean_gradient: float
    percentile_gradient: float
    edge_density: float
    sharpness_score: float
    light_quality_score: float
    blurry: bool
    low_edge_detail: bool
    underexposed: bool
    overexposed: bool
    flags: list[str]
    backend: str

    def to_signal_fields(self) -> dict[str, float]:
        """The subset that maps directly onto WebcamSignal fields."""
        return {
            "light_quality_score": self.light_quality_score,
            "sharpness_score": self.sharpness_score,
            "edge_density": self.edge_density,
            "mean_luminance": self.mean_luminance,
            "underexposed_ratio": self.underexposed_ratio,
            "overexposed_ratio": self.overexposed_ratio,
        }


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def normalize_grid(grid: list[list[float]]) -> list[list[float]]:
    """Validate a luminance grid and scale 0..255 inputs down to 0..1."""
    if not grid or not isinstance(grid, list):
        raise ValueError("luminance_grid must be a non-empty list of rows")
    width = len(grid[0]) if isinstance(grid[0], list) else 0
    if width < 3 or len(grid) < 3:
        raise ValueError("luminance_grid must be at least 3x3 to run a Sobel kernel")
    peak = 0.0
    for row in grid:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError("luminance_grid rows must all be the same length")
        for value in row:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError("luminance_grid values must be numbers")
            if value < 0:
                raise ValueError("luminance_grid values must be >= 0")
            peak = max(peak, float(value))
    scale = 255.0 if peak > 1.0 else 1.0
    return [[_clamp01(float(v) / scale) for v in row] for row in grid]


def _sobel_stats(
    grid: list[list[float]], *, binary_threshold: float, percentile: float
) -> tuple[float, float, float, float, str]:
    """Return (mean_gradient, percentile_gradient, interior_pixels, edges, backend)."""
    if _np is not None:
        array = _np.asarray(grid, dtype=_np.float64)
        gx = (
            -array[:-2, :-2] + array[:-2, 2:]
            - 2.0 * array[1:-1, :-2] + 2.0 * array[1:-1, 2:]
            - array[2:, :-2] + array[2:, 2:]
        )
        gy = (
            -array[:-2, :-2] - 2.0 * array[:-2, 1:-1] - array[:-2, 2:]
            + array[2:, :-2] + 2.0 * array[2:, 1:-1] + array[2:, 2:]
        )
        magnitude = _np.sqrt(gx * gx + gy * gy) / _SOBEL_MAX
        return (
            float(magnitude.mean()),
            float(_np.percentile(magnitude, percentile)),
            float(magnitude.size),
            float((magnitude >= binary_threshold).sum()),
            "numpy",
        )

    height = len(grid)
    width = len(grid[0])
    magnitudes: list[float] = []
    edges = 0.0
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            gx = 0.0
            gy = 0.0
            for ky in range(3):
                row = grid[y - 1 + ky]
                for kx in range(3):
                    pixel = row[x - 1 + kx]
                    gx += _SOBEL_X[ky][kx] * pixel
                    gy += _SOBEL_Y[ky][kx] * pixel
            magnitude = ((gx * gx + gy * gy) ** 0.5) / _SOBEL_MAX
            magnitudes.append(magnitude)
            if magnitude >= binary_threshold:
                edges += 1.0
    if not magnitudes:
        return 0.0, 0.0, 0.0, 0.0, "python"
    magnitudes.sort()
    mean = sum(magnitudes) / len(magnitudes)
    # Linear-interpolated percentile, matching numpy's default method.
    position = (percentile / 100.0) * (len(magnitudes) - 1)
    low = int(position)
    high = min(low + 1, len(magnitudes) - 1)
    weight = position - low
    pct = magnitudes[low] * (1.0 - weight) + magnitudes[high] * weight
    return mean, pct, float(len(magnitudes)), edges, "python"


def analyze_luminance_grid(
    grid: list[list[float]], *, tuning: VisionTuning | None = None
) -> ImagingAnalysis:
    """Run Sobel + exposure analysis over a luminance grid.

    Values may be 0..1 or 0..255; 0..255 inputs are scaled automatically.
    """
    active = tuning or VisionTuning()
    normalized = normalize_grid(grid)
    height = len(normalized)
    width = len(normalized[0])

    flat = [value for row in normalized for value in row]
    mean_luminance = sum(flat) / len(flat)
    underexposed_ratio = sum(
        1 for v in flat if v <= active.light_underexposed_luma
    ) / len(flat)
    overexposed_ratio = sum(
        1 for v in flat if v >= active.light_overexposed_luma
    ) / len(flat)

    mean_gradient, percentile_gradient, interior, edge_count, backend = _sobel_stats(
        normalized,
        binary_threshold=active.sobel_binary_threshold,
        percentile=active.sharpness_gradient_percentile,
    )
    edge_density = (edge_count / interior) if interior else 0.0
    sharpness_score = _clamp01(percentile_gradient / active.sharpness_reference_gradient)

    # Lighting quality peaks at mid-exposure and is penalised by clipping.
    mid = (active.light_underexposed_luma + active.light_overexposed_luma) / 2.0
    half_span = max(1e-6, (active.light_overexposed_luma - active.light_underexposed_luma) / 2.0)
    exposure_centering = _clamp01(1.0 - abs(mean_luminance - mid) / half_span)
    clipping_penalty = _clamp01(underexposed_ratio + overexposed_ratio)
    light_quality_score = _clamp01(exposure_centering * (1.0 - clipping_penalty))

    underexposed = (
        mean_luminance <= active.light_underexposed_luma
        or underexposed_ratio > active.light_max_clipped_black_ratio
    )
    overexposed = (
        mean_luminance >= active.light_overexposed_luma
        or overexposed_ratio > active.light_max_clipped_white_ratio
    )
    # Kept separate on purpose: a sharp but low-contrast frame has few pixels above
    # the binary edge threshold without being blurred, so conflating the two would
    # mislabel it. Sharpness decides blur; edge density reports usable detail.
    blurry = sharpness_score < active.sharpness_min_quality
    low_edge_detail = edge_density < active.sobel_min_edge_density

    flags: list[str] = []
    if underexposed:
        flags.append("lighting_underexposed")
    if overexposed:
        flags.append("lighting_overexposed")
    if blurry:
        flags.append("image_blurry")
    if low_edge_detail:
        flags.append("low_edge_detail")
    if light_quality_score < active.light_min_quality:
        flags.append("lighting_below_min_quality")

    return ImagingAnalysis(
        width=width,
        height=height,
        mean_luminance=round(mean_luminance, 4),
        underexposed_ratio=round(underexposed_ratio, 4),
        overexposed_ratio=round(overexposed_ratio, 4),
        mean_gradient=round(mean_gradient, 4),
        percentile_gradient=round(percentile_gradient, 4),
        edge_density=round(edge_density, 4),
        sharpness_score=round(sharpness_score, 4),
        light_quality_score=round(light_quality_score, 4),
        blurry=blurry,
        low_edge_detail=low_edge_detail,
        underexposed=underexposed,
        overexposed=overexposed,
        flags=flags,
        backend=backend,
    )
