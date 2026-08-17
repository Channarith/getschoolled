"""Responsiveness knobs for live webcam evaluation and dashboard refresh.

VisionTuning shapes *what* is scored; this set shapes *how quickly and smoothly*
the lab reacts — debounce, hysteresis, chart density, alert cooldowns, and
quality-gate floors for promotion-grade telemetry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .tuning_base import env_overrides, patch_knobs

_ENV_PREFIX = "AOEP_RESP_"


@dataclass(frozen=True)
class ResponsivenessTuning:
    # --- Evaluation cadence --------------------------------------------------
    eval_min_interval_ms: int = 120
    eval_target_fps: float = 8.0
    chart_max_points: int = 180
    chart_emit_interval_ms: int = 250
    metrics_history_sessions: int = 512

    # --- Presence / absence hysteresis --------------------------------------
    presence_debounce_ms: int = 350
    absence_confirm_ms: int = 900
    silhouette_confirm_ms: int = 600
    return_grace_ms: int = 1500
    unexpected_face_confirm_ms: int = 800

    # --- Alert / intervention cooldowns -------------------------------------
    alert_cooldown_ms: int = 8000
    integrity_alert_cooldown_ms: int = 12000
    fatigue_alert_cooldown_ms: int = 10000
    confusion_alert_cooldown_ms: int = 9000
    engagement_praise_cooldown_ms: int = 15000
    private_nudge_cooldown_ms: int = 20000

    # --- Observatory decision floors ----------------------------------------
    engagement_deep_min: float = 0.62
    engagement_focus_min: float = 0.55
    fatigue_alert_min: float = 0.62
    confusion_alert_min: float = 0.58
    boredom_alert_min: float = 0.58
    multitask_risk_min: float = 0.75
    flow_min: float = 0.68
    curiosity_explore_min: float = 0.55

    # --- Quality gates (promotion / demote confidence) ----------------------
    min_light_for_trust: float = 0.35
    min_sharpness_for_trust: float = 0.30
    min_mic_for_trust: float = 0.45
    min_recognition_for_trust: float = 0.50
    composite_quality_floor: float = 0.42
    latency_warn_ms: int = 250
    latency_critical_ms: int = 750

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for name in (
            "eval_min_interval_ms",
            "chart_emit_interval_ms",
            "presence_debounce_ms",
            "absence_confirm_ms",
            "silhouette_confirm_ms",
            "return_grace_ms",
            "unexpected_face_confirm_ms",
            "alert_cooldown_ms",
            "integrity_alert_cooldown_ms",
            "fatigue_alert_cooldown_ms",
            "confusion_alert_cooldown_ms",
            "engagement_praise_cooldown_ms",
            "private_nudge_cooldown_ms",
            "latency_warn_ms",
            "latency_critical_ms",
        ):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be >= 1")
        if self.eval_target_fps <= 0.0:
            raise ValueError("eval_target_fps must be > 0")
        if self.chart_max_points < 10:
            raise ValueError("chart_max_points must be >= 10")
        if self.metrics_history_sessions < 1:
            raise ValueError("metrics_history_sessions must be >= 1")
        unit = (
            "engagement_deep_min",
            "engagement_focus_min",
            "fatigue_alert_min",
            "confusion_alert_min",
            "boredom_alert_min",
            "multitask_risk_min",
            "flow_min",
            "curiosity_explore_min",
            "min_light_for_trust",
            "min_sharpness_for_trust",
            "min_mic_for_trust",
            "min_recognition_for_trust",
            "composite_quality_floor",
        )
        for name in unit:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0 (got {value})")
        if self.latency_warn_ms > self.latency_critical_ms:
            raise ValueError("latency_warn_ms must not exceed latency_critical_ms")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def patched(self, overrides: dict[str, Any]) -> ResponsivenessTuning:
        return patch_knobs(self, overrides)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> ResponsivenessTuning:
        return cls(**env_overrides(cls, _ENV_PREFIX, environ))

    @classmethod
    def preset(cls, name: str) -> ResponsivenessTuning:
        key = (name or "").strip().lower()
        if key not in PRESETS:
            raise ValueError(
                f"Unknown preset '{name}'. Available: {', '.join(sorted(PRESETS))}"
            )
        return cls(**PRESETS[key])


PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {},
    "low_latency": {
        "eval_min_interval_ms": 80,
        "eval_target_fps": 12.0,
        "chart_emit_interval_ms": 150,
        "presence_debounce_ms": 200,
        "alert_cooldown_ms": 5000,
        "latency_warn_ms": 180,
        "latency_critical_ms": 500,
    },
    "stable_classroom": {
        "eval_min_interval_ms": 200,
        "eval_target_fps": 5.0,
        "presence_debounce_ms": 500,
        "absence_confirm_ms": 1500,
        "alert_cooldown_ms": 12000,
        "engagement_deep_min": 0.68,
        "fatigue_alert_min": 0.70,
    },
    "high_sensitivity": {
        "presence_debounce_ms": 150,
        "absence_confirm_ms": 500,
        "fatigue_alert_min": 0.50,
        "confusion_alert_min": 0.48,
        "multitask_risk_min": 0.60,
        "composite_quality_floor": 0.50,
    },
}
