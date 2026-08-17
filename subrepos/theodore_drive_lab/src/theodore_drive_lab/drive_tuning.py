"""Drive Mode audio-agent tuning knobs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .tuning_base import env_overrides, patch_knobs

_ENV_PREFIX = "AOEP_DRIVE_"


@dataclass(frozen=True)
class DriveTuning:
    # Wake / mic
    wake_required: bool = True
    echo_min_overlap: float = 0.55  # token overlap with last TTS => echo
    pause_submit_ms: int = 4500
    resume_delay_ms: int = 400
    # Answer grounding
    answer_min_overlap: float = 0.15
    answer_top_segments: int = 3
    # TTS preferences (hints for clients / speech gw)
    tts_rate: float = 1.0
    tts_prefer_neural: bool = True
    tts_max_chars_per_chunk: int = 280
    # Bakeoff
    bakeoff_rounds: int = 24
    primary_metric: str = "drive_quality"

    def validate(self) -> None:
        if not 0.0 <= self.echo_min_overlap <= 1.0:
            raise ValueError("echo_min_overlap must be in [0,1]")
        if not 500 <= self.pause_submit_ms <= 15000:
            raise ValueError("pause_submit_ms must be in [500,15000]")
        if self.resume_delay_ms < 0:
            raise ValueError("resume_delay_ms must be >= 0")
        if not 0.0 <= self.answer_min_overlap <= 1.0:
            raise ValueError("answer_min_overlap must be in [0,1]")
        if self.answer_top_segments < 1:
            raise ValueError("answer_top_segments must be >= 1")
        if not 0.5 <= self.tts_rate <= 2.0:
            raise ValueError("tts_rate must be in [0.5,2.0]")
        if self.tts_max_chars_per_chunk < 40:
            raise ValueError("tts_max_chars_per_chunk must be >= 40")
        if self.bakeoff_rounds < 1:
            raise ValueError("bakeoff_rounds must be >= 1")

    def __post_init__(self) -> None:
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def patched(self, overrides: dict[str, Any]) -> "DriveTuning":
        return patch_knobs(self, overrides)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "DriveTuning":
        return cls(**env_overrides(cls, _ENV_PREFIX, environ))

    @classmethod
    def preset(cls, name: str) -> "DriveTuning":
        key = (name or "").strip().lower()
        if key not in PRESETS:
            raise ValueError(f"Unknown preset '{name}'. Available: {', '.join(sorted(PRESETS))}")
        return cls(**{**asdict(cls()), **PRESETS[key]})


PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {},
    "strict_wake": {"wake_required": True, "echo_min_overlap": 0.4, "pause_submit_ms": 3500},
    "noisy_cabin": {"echo_min_overlap": 0.65, "pause_submit_ms": 5500, "resume_delay_ms": 600},
    "snappy": {"pause_submit_ms": 2500, "resume_delay_ms": 200, "tts_rate": 1.1},
    "careful_qa": {"answer_min_overlap": 0.25, "answer_top_segments": 5},
}
