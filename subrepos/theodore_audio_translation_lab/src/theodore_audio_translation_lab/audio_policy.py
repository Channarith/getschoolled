"""Low-latency capture, noise-gate, and quality policy shared with the UI.

`AudioPolicy` is a single frozen dataclass of every tunable knob the lab
exposes — capture windows, the browser Web Audio filter/compressor chain, the
adaptive noise gate, provider timeouts, Theodore reply shaping, and the latency
/ quality targets used by telemetry. It is loaded once from the environment and
can be patched live over the API via the module-level policy store.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AudioPolicy:
    # --- Capture windows -----------------------------------------------------
    # Known-language windows can be short; auto language ID needs more context.
    capture_window_ms: int = 1200
    auto_detect_window_ms: int = 2000
    min_window_ms: int = 600
    max_window_ms: int = 4000
    # --- Browser getUserMedia + Web Audio processing -------------------------
    sample_rate_hz: int = 16000
    channel_count: int = 1
    highpass_hz: int = 80
    lowpass_hz: int = 7500
    compressor_threshold_db: float = -30.0
    compressor_knee_db: float = 18.0
    compressor_ratio: float = 4.0
    compressor_attack_s: float = 0.003
    compressor_release_s: float = 0.18
    agc_target_db: float = -18.0
    # --- Adaptive gate: upload when frames exceed calibrated floor + margin --
    noise_gate_margin_db: float = 9.0
    absolute_gate_db: float = -48.0
    min_speech_ratio: float = 0.12
    calibration_ms: int = 900
    gate_attack_ms: int = 40
    gate_release_ms: int = 220
    vad_hangover_ms: int = 320
    max_upload_bytes: int = 8 * 1024 * 1024
    # --- Provider timeouts ---------------------------------------------------
    mt_timeout_s: float = 15.0
    xai_timeout_s: float = 20.0
    asr_timeout_s: float = 45.0
    whisper_temperature: float = 0.0
    # --- Theodore reply shaping ---------------------------------------------
    theodore_max_sentences: int = 3
    theodore_temperature: float = 0.3
    theodore_max_tokens: int = 320
    # --- Realtime hub --------------------------------------------------------
    ws_heartbeat_s: float = 20.0
    max_history_events: int = 200
    interim_translate_default: int = 0
    # --- Latency / quality targets (used by telemetry scoring) ---------------
    latency_target_p50_ms: int = 900
    latency_target_p95_ms: int = 2200
    phrasebook_min_confidence: float = 0.55
    fallback_honesty_score: float = 0.4

    @classmethod
    def from_env(cls) -> "AudioPolicy":
        return cls(
            capture_window_ms=_int("AUDIO_CAPTURE_WINDOW_MS", 1200, 600, 4000),
            auto_detect_window_ms=_int("AUDIO_AUTO_WINDOW_MS", 2000, 1000, 5000),
            highpass_hz=_int("AUDIO_HIGHPASS_HZ", 80, 20, 400),
            lowpass_hz=_int("AUDIO_LOWPASS_HZ", 7500, 3000, 12000),
            agc_target_db=_float("AUDIO_AGC_TARGET_DB", -18.0, -40.0, -3.0),
            noise_gate_margin_db=_float("AUDIO_GATE_MARGIN_DB", 9.0, 3.0, 24.0),
            absolute_gate_db=_float("AUDIO_ABSOLUTE_GATE_DB", -48.0, -80.0, -20.0),
            min_speech_ratio=_float("AUDIO_MIN_SPEECH_RATIO", 0.12, 0.01, 0.9),
            calibration_ms=_int("AUDIO_CALIBRATION_MS", 900, 250, 3000),
            gate_attack_ms=_int("AUDIO_GATE_ATTACK_MS", 40, 1, 500),
            gate_release_ms=_int("AUDIO_GATE_RELEASE_MS", 220, 20, 2000),
            vad_hangover_ms=_int("AUDIO_VAD_HANGOVER_MS", 320, 0, 2000),
            max_upload_bytes=_int(
                "ASR_MAX_AUDIO_BYTES", 8 * 1024 * 1024, 64 * 1024, 64 * 1024 * 1024
            ),
            mt_timeout_s=_float("TRANSLATION_TIMEOUT_S", 15.0, 1.0, 120.0),
            xai_timeout_s=_float("XAI_TIMEOUT_S", 20.0, 1.0, 120.0),
            asr_timeout_s=_float("ASR_TIMEOUT_S", 45.0, 1.0, 300.0),
            whisper_temperature=_float("ASR_TEMPERATURE", 0.0, 0.0, 1.0),
            theodore_max_sentences=_int("THEODORE_MAX_SENTENCES", 3, 1, 12),
            theodore_temperature=_float("THEODORE_TEMPERATURE", 0.3, 0.0, 2.0),
            theodore_max_tokens=_int("THEODORE_MAX_TOKENS", 320, 32, 4000),
            ws_heartbeat_s=_float("WS_HEARTBEAT_S", 20.0, 1.0, 120.0),
            max_history_events=_int("AUDIO_MAX_HISTORY_EVENTS", 200, 10, 2000),
            interim_translate_default=_int("AUDIO_INTERIM_TRANSLATE", 0, 0, 1),
            latency_target_p50_ms=_int("AUDIO_LATENCY_P50_MS", 900, 50, 10000),
            latency_target_p95_ms=_int("AUDIO_LATENCY_P95_MS", 2200, 100, 20000),
            phrasebook_min_confidence=_float("AUDIO_PHRASEBOOK_MIN_CONF", 0.55, 0.0, 1.0),
            fallback_honesty_score=_float("AUDIO_FALLBACK_HONESTY", 0.4, 0.0, 1.0),
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

    def patched(self, overrides: dict[str, Any]) -> "AudioPolicy":
        """Return a copy with `overrides` applied, coerced to each field type.

        Unknown keys are ignored so a partial PATCH body cannot inject junk.
        """
        coerced: dict[str, Any] = {}
        fields = {f.name: f.type for f in dataclasses.fields(self)}
        for key, value in (overrides or {}).items():
            if key not in fields or value is None:
                continue
            coerced[key] = _coerce(getattr(self, key), value)
        return dataclasses.replace(self, **coerced)

    def knob_names(self) -> list[str]:
        return [f.name for f in dataclasses.fields(self)]

    def public_dict(self) -> dict[str, Any]:
        """Every knob, flat, plus the nested compressor + browser constraints.

        Flat knobs make the API round-trippable (PATCH accepts the same names);
        the nested `compressor`/`browser_constraints` blocks stay for the UI.
        """
        flat = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
        flat["compressor"] = {
            "threshold_db": self.compressor_threshold_db,
            "knee_db": self.compressor_knee_db,
            "ratio": self.compressor_ratio,
            "attack_s": self.compressor_attack_s,
            "release_s": self.compressor_release_s,
        }
        flat["browser_constraints"] = {
            "echoCancellation": True,
            "noiseSuppression": True,
            "autoGainControl": True,
        }
        return flat


def _coerce(current: Any, value: Any) -> Any:
    if isinstance(current, bool):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if isinstance(current, int):
        return int(float(value))
    if isinstance(current, float):
        return float(value)
    return value


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


# --- Live policy store -------------------------------------------------------
# A single mutable policy the API can read and PATCH at runtime. Initialized
# from the environment; `reset_policy()` re-reads the environment.
_POLICY: AudioPolicy = AudioPolicy.from_env()


def get_policy() -> AudioPolicy:
    return _POLICY


def set_policy(policy: AudioPolicy) -> AudioPolicy:
    global _POLICY
    _POLICY = policy
    return _POLICY


def patch_policy(overrides: dict[str, Any]) -> AudioPolicy:
    return set_policy(_POLICY.patched(overrides))


def reset_policy() -> AudioPolicy:
    return set_policy(AudioPolicy.from_env())
