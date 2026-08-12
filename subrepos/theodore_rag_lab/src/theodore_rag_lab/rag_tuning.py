"""RAG retrieval quality knobs for continuous auto-tune."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .tuning_base import env_overrides, patch_knobs

_ENV_PREFIX = "AOEP_RAG_"


@dataclass(frozen=True)
class RagTuning:
    top_k: int = 3
    min_score: float = 0.02
    groundedness_pass: float = 0.55
    groundedness_support: float = 0.35
    prefer_fts: bool = True
    max_context_chars: int = 2400
    eval_batch_size: int = 32
    bakeoff_rounds_per_hour: int = 120
    promote_min_delta: float = 0.0  # primary metric must not regress
    primary_metric: str = "rag_quality"  # blended recall@k + groundedness

    def validate(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if not 0.0 <= self.min_score <= 1.0:
            raise ValueError("min_score must be in [0,1]")
        if not 0.0 <= self.groundedness_pass <= 1.0:
            raise ValueError("groundedness_pass must be in [0,1]")
        if not 0.0 <= self.groundedness_support <= 1.0:
            raise ValueError("groundedness_support must be in [0,1]")
        if self.max_context_chars < 200:
            raise ValueError("max_context_chars must be >= 200")
        if self.eval_batch_size < 1:
            raise ValueError("eval_batch_size must be >= 1")
        if self.bakeoff_rounds_per_hour < 1:
            raise ValueError("bakeoff_rounds_per_hour must be >= 1")

    def __post_init__(self) -> None:
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def patched(self, overrides: dict[str, Any]) -> "RagTuning":
        return patch_knobs(self, overrides)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "RagTuning":
        return cls(**env_overrides(cls, _ENV_PREFIX, environ))

    @classmethod
    def preset(cls, name: str) -> "RagTuning":
        key = (name or "").strip().lower()
        if key not in PRESETS:
            raise ValueError(f"Unknown preset '{name}'. Available: {', '.join(sorted(PRESETS))}")
        return cls(**{**asdict(cls()), **PRESETS[key]})


PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {},
    "recall": {"top_k": 5, "min_score": 0.01, "groundedness_pass": 0.45},
    "precision": {"top_k": 2, "min_score": 0.08, "groundedness_pass": 0.7, "groundedness_support": 0.5},
    "strict_ground": {"top_k": 4, "groundedness_pass": 0.8, "groundedness_support": 0.55},
    "snappy": {"top_k": 2, "max_context_chars": 1200, "eval_batch_size": 16},
    "hours_long": {"bakeoff_rounds_per_hour": 240, "eval_batch_size": 48},
}
