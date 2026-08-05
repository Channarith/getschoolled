"""Tunable knobs for the xAI (Theodore) voice agent.

The transport settings (key, model, timeouts, cache) were already environment
driven, but the knobs that actually shape what a learner hears - sampling
temperature, token budget, and how long a spoken reply should be - were hardcoded
at three separate call sites. They live here instead so conversation style can be
tuned per deployment without editing code.

Set them via XAI_TUNE_<KNOB_NAME_UPPERCASE> environment variables, live via
PATCH /api/theodore/voice/tuning, or in bulk from a named preset.

Reply length matters for spoken delivery specifically: a reply that reads fine on
screen is tiring to listen to, so reply_max_sentences is injected into the system
prompt and also bounds the token budget.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .tuning_base import env_overrides, patch_knobs

_ENV_PREFIX = "XAI_TUNE_"


@dataclass(frozen=True)
class VoiceTuning:
    # --- Conversational replies ---------------------------------------------
    # fast_mode is the low-latency path used for live chat/audio turns.
    reply_temperature_fast: float = 0.45
    reply_temperature_full: float = 0.55
    reply_max_tokens_fast: int = 140
    reply_max_tokens_full: int = 240
    # Injected into the system prompt so spoken answers stay listenable.
    reply_max_sentences: int = 2

    # --- Generated questions -------------------------------------------------
    question_temperature: float = 0.60
    question_max_tokens: int = 280

    # --- Spoken-answer assessment -------------------------------------------
    assessment_temperature: float = 0.40
    assessment_max_tokens: int = 320

    # --- Latency / transport -------------------------------------------------
    fast_timeout_s: float = 6.0
    full_timeout_s: float = 25.0
    cache_ttl_s: float = 20.0
    max_history_turns: int = 4

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for name in (
            "reply_temperature_fast",
            "reply_temperature_full",
            "question_temperature",
            "assessment_temperature",
        ):
            value = float(getattr(self, name))
            # xAI/OpenAI-compatible sampling temperature range.
            if not 0.0 <= value <= 2.0:
                raise ValueError(f"{name} must be between 0.0 and 2.0 (got {value})")
        for name in (
            "reply_max_tokens_fast",
            "reply_max_tokens_full",
            "question_max_tokens",
            "assessment_max_tokens",
        ):
            value = int(getattr(self, name))
            if value < 16:
                raise ValueError(f"{name} must be at least 16 tokens (got {value})")
        if self.reply_max_sentences < 1:
            raise ValueError("reply_max_sentences must be >= 1")
        if self.max_history_turns < 1:
            raise ValueError("max_history_turns must be >= 1")
        for name in ("fast_timeout_s", "full_timeout_s", "cache_ttl_s"):
            if float(getattr(self, name)) <= 0.0:
                raise ValueError(f"{name} must be > 0")
        if self.fast_timeout_s > self.full_timeout_s:
            raise ValueError("fast_timeout_s must not exceed full_timeout_s")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def patched(self, overrides: dict[str, Any]) -> VoiceTuning:
        return patch_knobs(self, overrides)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> VoiceTuning:
        return cls(**env_overrides(cls, _ENV_PREFIX, environ))

    @classmethod
    def preset(cls, name: str) -> VoiceTuning:
        key = (name or "").strip().lower()
        if key not in PRESETS:
            available = ", ".join(sorted(PRESETS))
            raise ValueError(f"Unknown preset '{name}'. Available: {available}")
        return cls(**PRESETS[key])


# Presets are partial: unspecified knobs keep their default.
PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {},
    # Live back-and-forth: shortest possible spoken turns, tight timeout so the
    # local fallback fires rather than leaving a learner waiting in silence.
    "snappy": {
        "reply_temperature_fast": 0.35,
        "reply_max_tokens_fast": 90,
        "reply_max_sentences": 1,
        "fast_timeout_s": 4.0,
        "cache_ttl_s": 30.0,
    },
    # Explaining a hard concept: longer, warmer answers and more remembered turns.
    "thorough": {
        "reply_temperature_fast": 0.55,
        "reply_temperature_full": 0.65,
        "reply_max_tokens_fast": 260,
        "reply_max_tokens_full": 420,
        "reply_max_sentences": 5,
        "fast_timeout_s": 10.0,
        "max_history_turns": 8,
    },
    # Assessment/proctoring: near-deterministic so scoring is repeatable.
    "precise": {
        "reply_temperature_fast": 0.15,
        "reply_temperature_full": 0.20,
        "question_temperature": 0.25,
        "assessment_temperature": 0.10,
        "reply_max_sentences": 2,
    },
    # Young learners: more varied, expressive phrasing in short bursts.
    "storyteller": {
        "reply_temperature_fast": 0.80,
        "reply_temperature_full": 0.90,
        "question_temperature": 0.85,
        "reply_max_tokens_fast": 200,
        "reply_max_sentences": 3,
    },
}
