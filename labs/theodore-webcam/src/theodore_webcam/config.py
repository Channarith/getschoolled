"""Environment-driven configuration for the Theodore webcam lab.

Every knob has a working default so the lab runs with no environment at all.
Mirrors the platform convention of selecting behaviour by env instead of code
forks, but the lab is deliberately standalone: it does not import aoep_shared,
so it can be split into its own private repository.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Mapping, Optional

DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"
DEFAULT_XAI_REALTIME_URL = "wss://api.x.ai/v1/realtime"
DEFAULT_VOICE_MODEL = "grok-voice-latest"
DEFAULT_TEXT_MODEL = "grok-4-fast"
DEFAULT_VOICE = "eve"


def _get(src: Mapping[str, str], key: str, default: str) -> str:
    value = src.get(key)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _float(src: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(_get(src, key, str(default)))
    except ValueError:
        return default


def _int(src: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(float(_get(src, key, str(default))))
    except ValueError:
        return default


def _bool(src: Mapping[str, str], key: str, default: bool) -> bool:
    raw = _get(src, key, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass
class SilhouetteConfig:
    """Tuning for the silhouette (human-shaped foreground) detector."""

    work_width: int = 320
    warmup_frames: int = 10
    diff_threshold: int = 26
    background_alpha: float = 0.04
    occluded_alpha: float = 0.0005
    min_area_ratio: float = 0.012
    max_area_ratio: float = 0.92
    open_kernel: int = 3
    close_kernel: int = 11
    human_score_threshold: float = 0.45
    max_silhouettes: int = 6


@dataclass
class PresenceConfig:
    """Timing for the presence / absence state machine (seconds)."""

    arrive_confirm_seconds: float = 0.8
    return_confirm_seconds: float = 1.0
    absence_grace_seconds: float = 10.0
    prolonged_absence_seconds: float = 60.0
    stale_seconds: float = 12.0


@dataclass
class ClassroomConfig:
    """Policy for how absence changes the lesson, per class mode."""

    group_min_present_ratio: float = 0.6
    solo_pause_on_absence: bool = True
    recap_after_absence_seconds: float = 20.0


@dataclass
class XaiConfig:
    """xAI Grok Voice Agent settings (speech-to-speech realtime + text turns)."""

    api_key: str = ""
    base_url: str = DEFAULT_XAI_BASE_URL
    realtime_url: str = DEFAULT_XAI_REALTIME_URL
    voice_model: str = DEFAULT_VOICE_MODEL
    text_model: str = DEFAULT_TEXT_MODEL
    voice: str = DEFAULT_VOICE
    reasoning_effort: str = "high"
    token_ttl_seconds: int = 300
    request_timeout: float = 20.0
    vad_threshold: float = 0.85
    vad_silence_ms: int = 700
    vad_prefix_padding_ms: int = 333
    audio_rate: int = 24000
    enable_web_search: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class LabConfig:
    silhouette: SilhouetteConfig = field(default_factory=SilhouetteConfig)
    presence: PresenceConfig = field(default_factory=PresenceConfig)
    classroom: ClassroomConfig = field(default_factory=ClassroomConfig)
    xai: XaiConfig = field(default_factory=XaiConfig)
    allow_origins: str = "*"
    demo_enabled: bool = True
    max_frame_bytes: int = 4_000_000

    def public_dict(self) -> dict:
        """Config safe to hand to a browser (never includes the API key)."""

        data = asdict(self)
        data["xai"].pop("api_key", None)
        data["xai"]["configured"] = self.xai.configured
        return data


def load_config(env: Optional[Mapping[str, str]] = None) -> LabConfig:
    src = env if env is not None else os.environ

    silhouette = SilhouetteConfig(
        work_width=_int(src, "WEBCAM_LAB_WORK_WIDTH", 320),
        warmup_frames=_int(src, "WEBCAM_LAB_WARMUP_FRAMES", 10),
        diff_threshold=_int(src, "WEBCAM_LAB_DIFF_THRESHOLD", 26),
        background_alpha=_float(src, "WEBCAM_LAB_BACKGROUND_ALPHA", 0.04),
        occluded_alpha=_float(src, "WEBCAM_LAB_OCCLUDED_ALPHA", 0.0005),
        min_area_ratio=_float(src, "WEBCAM_LAB_MIN_AREA_RATIO", 0.012),
        max_area_ratio=_float(src, "WEBCAM_LAB_MAX_AREA_RATIO", 0.92),
        human_score_threshold=_float(src, "WEBCAM_LAB_HUMAN_SCORE_THRESHOLD", 0.45),
        max_silhouettes=_int(src, "WEBCAM_LAB_MAX_SILHOUETTES", 6),
    )
    presence = PresenceConfig(
        arrive_confirm_seconds=_float(src, "WEBCAM_LAB_ARRIVE_CONFIRM_SECONDS", 0.8),
        return_confirm_seconds=_float(src, "WEBCAM_LAB_RETURN_CONFIRM_SECONDS", 1.0),
        absence_grace_seconds=_float(src, "WEBCAM_LAB_ABSENCE_GRACE_SECONDS", 10.0),
        prolonged_absence_seconds=_float(src, "WEBCAM_LAB_PROLONGED_ABSENCE_SECONDS", 60.0),
        stale_seconds=_float(src, "WEBCAM_LAB_STALE_SECONDS", 12.0),
    )
    classroom = ClassroomConfig(
        group_min_present_ratio=_float(src, "WEBCAM_LAB_GROUP_MIN_PRESENT_RATIO", 0.6),
        solo_pause_on_absence=_bool(src, "WEBCAM_LAB_SOLO_PAUSE_ON_ABSENCE", True),
        recap_after_absence_seconds=_float(src, "WEBCAM_LAB_RECAP_AFTER_ABSENCE_SECONDS", 20.0),
    )
    xai = XaiConfig(
        api_key=_get(src, "XAI_API_KEY", ""),
        base_url=_get(src, "XAI_BASE_URL", DEFAULT_XAI_BASE_URL).rstrip("/"),
        realtime_url=_get(src, "XAI_REALTIME_URL", DEFAULT_XAI_REALTIME_URL),
        voice_model=_get(src, "XAI_VOICE_MODEL", DEFAULT_VOICE_MODEL),
        text_model=_get(src, "XAI_TEXT_MODEL", DEFAULT_TEXT_MODEL),
        voice=_get(src, "XAI_VOICE", DEFAULT_VOICE),
        reasoning_effort=_get(src, "XAI_REASONING_EFFORT", "high"),
        token_ttl_seconds=_int(src, "XAI_TOKEN_TTL_SECONDS", 300),
        request_timeout=_float(src, "XAI_REQUEST_TIMEOUT", 20.0),
        vad_threshold=_float(src, "XAI_VAD_THRESHOLD", 0.85),
        vad_silence_ms=_int(src, "XAI_VAD_SILENCE_MS", 700),
        vad_prefix_padding_ms=_int(src, "XAI_VAD_PREFIX_PADDING_MS", 333),
        audio_rate=_int(src, "XAI_AUDIO_RATE", 24000),
        enable_web_search=_bool(src, "XAI_ENABLE_WEB_SEARCH", False),
    )
    return LabConfig(
        silhouette=silhouette,
        presence=presence,
        classroom=classroom,
        xai=xai,
        allow_origins=_get(src, "WEBCAM_LAB_ALLOW_ORIGINS", "*"),
        demo_enabled=_bool(src, "WEBCAM_LAB_DEMO", True),
        max_frame_bytes=_int(src, "WEBCAM_LAB_MAX_FRAME_BYTES", 4_000_000),
    )
