"""Low-latency capture and noise-gate policy shared with the browser UI."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioPolicy:
    # Known-language windows can be short; auto language ID needs more context.
    capture_window_ms: int = 1200
    auto_detect_window_ms: int = 2000
    min_window_ms: int = 600
    max_window_ms: int = 4000
    # Browser getUserMedia + Web Audio processing.
    sample_rate_hz: int = 16000
    channel_count: int = 1
    highpass_hz: int = 80
    lowpass_hz: int = 7500
    compressor_threshold_db: float = -30.0
    compressor_knee_db: float = 18.0
    compressor_ratio: float = 4.0
    compressor_attack_s: float = 0.003
    compressor_release_s: float = 0.18
    # Adaptive gate: upload when enough frames exceed calibrated floor + margin.
    noise_gate_margin_db: float = 9.0
    absolute_gate_db: float = -48.0
    min_speech_ratio: float = 0.12
    calibration_ms: int = 900

    @classmethod
    def from_env(cls) -> "AudioPolicy":
        return cls(
            capture_window_ms=_int("AUDIO_CAPTURE_WINDOW_MS", 1200, 600, 4000),
            auto_detect_window_ms=_int("AUDIO_AUTO_WINDOW_MS", 2000, 1000, 5000),
            highpass_hz=_int("AUDIO_HIGHPASS_HZ", 80, 20, 400),
            lowpass_hz=_int("AUDIO_LOWPASS_HZ", 7500, 3000, 12000),
            noise_gate_margin_db=_float("AUDIO_GATE_MARGIN_DB", 9.0, 3.0, 24.0),
            absolute_gate_db=_float("AUDIO_ABSOLUTE_GATE_DB", -48.0, -80.0, -20.0),
            min_speech_ratio=_float("AUDIO_MIN_SPEECH_RATIO", 0.12, 0.01, 0.9),
            calibration_ms=_int("AUDIO_CALIBRATION_MS", 900, 250, 3000),
        )

    def window_ms(self, source_language: str) -> int:
        return (
            self.auto_detect_window_ms
            if source_language == "auto"
            else self.capture_window_ms
        )

    def gate_threshold_db(self, noise_floor_db: float) -> float:
        return max(self.absolute_gate_db, noise_floor_db + self.noise_gate_margin_db)

    def should_upload(
        self,
        *,
        noise_floor_db: float,
        peak_db: float,
        speech_ratio: float,
        bytes_size: int,
    ) -> bool:
        if bytes_size <= 0:
            return False
        threshold = self.gate_threshold_db(noise_floor_db)
        return peak_db >= threshold and speech_ratio >= self.min_speech_ratio

    def public_dict(self) -> dict:
        return {
            "capture_window_ms": self.capture_window_ms,
            "auto_detect_window_ms": self.auto_detect_window_ms,
            "sample_rate_hz": self.sample_rate_hz,
            "channel_count": self.channel_count,
            "highpass_hz": self.highpass_hz,
            "lowpass_hz": self.lowpass_hz,
            "compressor": {
                "threshold_db": self.compressor_threshold_db,
                "knee_db": self.compressor_knee_db,
                "ratio": self.compressor_ratio,
                "attack_s": self.compressor_attack_s,
                "release_s": self.compressor_release_s,
            },
            "noise_gate_margin_db": self.noise_gate_margin_db,
            "absolute_gate_db": self.absolute_gate_db,
            "min_speech_ratio": self.min_speech_ratio,
            "calibration_ms": self.calibration_ms,
            "browser_constraints": {
                "echoCancellation": True,
                "noiseSuppression": True,
                "autoGainControl": True,
            },
        }


def _int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(low, min(high, value))


def _float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(low, min(high, value))
