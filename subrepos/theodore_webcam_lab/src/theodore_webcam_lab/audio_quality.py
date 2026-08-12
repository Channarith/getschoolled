"""Mic / noise-filter scoring helpers.

When a client sends noise-floor and SNR but omits an explicit noise-filter
score, we estimate filter effectiveness from those readings so the dashboard
does not stay stuck on ``n/a``.
"""

from __future__ import annotations

from .vision_tuning import VisionTuning


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def noise_db_to_quality(noise_db: float | None, tuning: VisionTuning) -> float | None:
    if noise_db is None:
        return None
    span = tuning.audio_noise_loud_db - tuning.audio_noise_clean_db
    if span <= 0:
        return None
    return _clamp01((tuning.audio_noise_loud_db - float(noise_db)) / span)


def snr_to_quality(snr_db: float | None, tuning: VisionTuning) -> float | None:
    if snr_db is None:
        return None
    return _clamp01((float(snr_db) - tuning.audio_snr_floor_db) / tuning.audio_snr_span_db)


def estimate_noise_filter_effectiveness(
    *,
    noise_filter_effectiveness_score: float | None,
    audio_noise_level_db: float | None,
    audio_snr_db: float | None,
    noise_suppression_enabled: bool | None = None,
    tuning: VisionTuning | None = None,
) -> float | None:
    """Return an explicit score, or derive one from noise floor + SNR."""
    if noise_filter_effectiveness_score is not None:
        return _clamp01(float(noise_filter_effectiveness_score))
    tuning = tuning or VisionTuning()
    noise_q = noise_db_to_quality(audio_noise_level_db, tuning)
    snr_q = snr_to_quality(audio_snr_db, tuning)
    parts: list[float] = []
    if noise_q is not None:
        parts.append(noise_q)
    if snr_q is not None:
        parts.append(snr_q)
    if not parts and noise_suppression_enabled is None:
        return None
    base = sum(parts) / len(parts) if parts else 0.45
    if noise_suppression_enabled is True:
        base = min(1.0, base * 0.7 + 0.35)
    elif noise_suppression_enabled is False:
        base = base * 0.75
    return round(_clamp01(base), 4)
