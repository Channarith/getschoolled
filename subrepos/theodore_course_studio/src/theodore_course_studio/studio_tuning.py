"""Course Studio tuning knobs — one frozen dataclass for the whole pipeline.

`StudioTuning` gathers every quality/pacing knob the studio exposes: quiz and
game pass criteria, slide/narration shaping, checkpoint pacing, early-learning
and certification caps, content-quality thresholds, voice/TTS behaviour, and the
engagement-game rotation. It loads from `AOEP_STUDIO_*` env vars, supports live
PATCH via `patched`, ships named `PRESETS`, and is held in a module-level store
so the API can retune a running server.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from typing import Any

_ENV_PREFIX = "AOEP_STUDIO_"

# Knobs constrained to the unit interval [0, 1].
_UNIT_KNOBS = frozenset(
    {
        "quiz_pass_score",
        "summary_quiz_pass_score",
        "game_pass_score",
        "content_cover_reject_weight",
        "content_dedupe_threshold",
        "quality_model_min_score",
        "profile_gap_boost",
    }
)

# Knobs that must be a positive integer (>= 1).
_POSITIVE_INT_KNOBS = frozenset(
    {
        "pop_quiz_interval_slides",
        "summary_quiz_max_questions",
        "slide_min_body_chars",
        "slide_max_body_chars",
        "narration_max_sentences",
        "teach_fade_ms",
        "animation_duration_ms",
        "checkpoint_soft_stop_min",
        "checkpoint_soft_stop_slides",
        "early_max_slides",
        "cert_max_slides",
        "voice_max_tokens",
        "voice_max_sentences",
        "voice_cache_ttl_s",
        "spot_gap_options",
        "order_steps_min_parts",
        "child_i18n_cache_hours",
        "offline_epoch_default",
        "builder_max_slides_per_source",
        "builder_min_title_chars",
        "telemetry_history_points",
    }
)


@dataclass(frozen=True)
class StudioTuning:
    # --- Assessment ----------------------------------------------------------
    quiz_pass_score: float = 0.7
    summary_quiz_pass_score: float = 0.7
    pop_quiz_interval_slides: int = 3
    summary_quiz_max_questions: int = 8
    game_pass_score: float = 0.7
    # --- Slide / narration shaping ------------------------------------------
    slide_min_body_chars: int = 40
    slide_max_body_chars: int = 600
    narration_max_sentences: int = 5
    teach_fade_ms: int = 650
    animation_duration_ms: int = 650
    # --- Checkpoint pacing ---------------------------------------------------
    checkpoint_soft_stop_min: int = 25
    checkpoint_soft_stop_slides: int = 8
    # --- Course size caps ----------------------------------------------------
    early_max_slides: int = 12
    cert_max_slides: int = 20
    builder_max_slides_per_source: int = 8
    builder_min_title_chars: int = 3
    # --- Content quality -----------------------------------------------------
    content_cover_reject_weight: float = 0.6
    content_dedupe_threshold: float = 0.85
    quality_model_min_score: float = 0.5
    # --- Voice / TTS ---------------------------------------------------------
    tts_timeout_s: float = 20.0
    voice_temperature: float = 0.3
    voice_max_tokens: int = 320
    voice_max_sentences: int = 4
    voice_cache_ttl_s: int = 3600
    # --- Profile adaptation --------------------------------------------------
    profile_gap_boost: float = 0.35
    # --- Engagement games ----------------------------------------------------
    engagement_rotate_games: int = 1
    spot_gap_options: int = 3
    order_steps_min_parts: int = 3
    media_prefer_real: int = 1
    # --- Localisation / offline ---------------------------------------------
    child_i18n_cache_hours: int = 24
    offline_epoch_default: int = 20
    # --- Telemetry -----------------------------------------------------------
    telemetry_history_points: int = 256

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for name in _POSITIVE_INT_KNOBS:
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be >= 1")
        for name in _UNIT_KNOBS:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0 (got {value})")
        if self.slide_min_body_chars > self.slide_max_body_chars:
            raise ValueError("slide_min_body_chars must not exceed slide_max_body_chars")
        if not 0.0 <= self.voice_temperature <= 2.0:
            raise ValueError("voice_temperature must be between 0.0 and 2.0")
        if self.tts_timeout_s <= 0.0:
            raise ValueError("tts_timeout_s must be > 0")
        for flag in ("engagement_rotate_games", "media_prefer_real"):
            if int(getattr(self, flag)) not in (0, 1):
                raise ValueError(f"{flag} must be 0 or 1")

    def knob_names(self) -> list[str]:
        return [f.name for f in dataclasses.fields(self)]

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}

    def patched(self, overrides: dict[str, Any]) -> "StudioTuning":
        coerced: dict[str, Any] = {}
        fields = {f.name for f in dataclasses.fields(self)}
        for key, value in (overrides or {}).items():
            if key not in fields or value is None:
                continue
            coerced[key] = _coerce(getattr(self, key), value)
        return dataclasses.replace(self, **coerced)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "StudioTuning":
        env = environ if environ is not None else os.environ
        overrides: dict[str, Any] = {}
        default = cls()
        for field in dataclasses.fields(cls):
            raw = env.get(_ENV_PREFIX + field.name.upper())
            if raw is None or raw == "":
                continue
            try:
                overrides[field.name] = _coerce(getattr(default, field.name), raw)
            except (TypeError, ValueError):
                continue
        return default.patched(overrides)

    @classmethod
    def preset(cls, name: str) -> "StudioTuning":
        key = (name or "").strip().lower()
        if key not in PRESETS:
            raise ValueError(
                f"Unknown preset '{name}'. Available: {', '.join(sorted(PRESETS))}"
            )
        return cls(**PRESETS[key])


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


PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {},
    "kids_fast": {
        "quiz_pass_score": 0.6,
        "game_pass_score": 0.6,
        "pop_quiz_interval_slides": 2,
        "narration_max_sentences": 3,
        "slide_max_body_chars": 320,
        "early_max_slides": 8,
        "checkpoint_soft_stop_min": 12,
        "checkpoint_soft_stop_slides": 5,
        "engagement_rotate_games": 1,
    },
    "cert_strict": {
        "quiz_pass_score": 0.85,
        "summary_quiz_pass_score": 0.85,
        "game_pass_score": 0.8,
        "summary_quiz_max_questions": 12,
        "quality_model_min_score": 0.65,
        "cert_max_slides": 24,
        "checkpoint_soft_stop_min": 30,
    },
    "adult_deep": {
        "narration_max_sentences": 7,
        "slide_max_body_chars": 900,
        "summary_quiz_max_questions": 10,
        "checkpoint_soft_stop_min": 35,
        "checkpoint_soft_stop_slides": 12,
        "profile_gap_boost": 0.25,
    },
}


# --- Live tuning store -------------------------------------------------------
_TUNING: StudioTuning = StudioTuning.from_env()


def get_tuning() -> StudioTuning:
    return _TUNING


def set_tuning(tuning: StudioTuning) -> StudioTuning:
    global _TUNING
    _TUNING = tuning
    return _TUNING


def patch_tuning(overrides: dict[str, Any]) -> StudioTuning:
    return set_tuning(_TUNING.patched(overrides))


def apply_preset(name: str) -> StudioTuning:
    return set_tuning(StudioTuning.preset(name))


def reset_tuning() -> StudioTuning:
    return set_tuning(StudioTuning.from_env())
