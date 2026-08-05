"""Environment-driven configuration for the webcam-classroom lab.

Every field has an offline-safe default so the detectors, the absence tracker,
and the xAI voice agent all run with no network, GPU, or API key. Real paths
(live Grok, GPU frame decode) activate only when the matching env/deps exist.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# xAI (Grok) defaults. The chat API is OpenAI-compatible; the Voice Agent API is
# a WebSocket (speech-to-speech) endpoint. Models are pinned via env so a newer
# Grok voice/text model can be selected without a code change.
DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"
DEFAULT_XAI_REALTIME_URL = "wss://api.x.ai/v1/realtime"
DEFAULT_XAI_TEXT_MODEL = "grok-4.5"
DEFAULT_XAI_VOICE_MODEL = "grok-voice-latest"
DEFAULT_XAI_VOICE = "eve"


def _get(name: str, default: str) -> str:
    val = os.environ.get(name)
    return default if val is None or val.strip() == "" else val.strip()


def _getf(name: str, default: float) -> float:
    try:
        return float(_get(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass
class WebcamLabConfig:
    # --- xAI (Grok) voice agent ------------------------------------------- #
    xai_api_key: str = ""
    xai_base_url: str = DEFAULT_XAI_BASE_URL
    xai_realtime_url: str = DEFAULT_XAI_REALTIME_URL
    xai_text_model: str = DEFAULT_XAI_TEXT_MODEL
    xai_voice_model: str = DEFAULT_XAI_VOICE_MODEL
    xai_voice: str = DEFAULT_XAI_VOICE

    # --- silhouette detection thresholds (fraction of frame occupied) ----- #
    present_coverage: float = 0.10
    partial_coverage: float = 0.03
    # Difference from the estimated background needed to count a pixel as
    # foreground (0..1 of the luminance range).
    foreground_delta: float = 0.18

    # --- absence state machine (seconds) ---------------------------------- #
    looking_away_after: float = 4.0
    brief_absent_after: float = 6.0
    absent_after: float = 20.0
    # Attention (0..1) below which a present learner counts as "looking away".
    looking_away_attention: float = 0.35

    @property
    def xai_configured(self) -> bool:
        """True when a real Grok endpoint should be used (an API key is set)."""
        return bool((self.xai_api_key or "").strip())

    @classmethod
    def from_env(cls) -> "WebcamLabConfig":
        return cls(
            xai_api_key=_get("XAI_API_KEY", ""),
            xai_base_url=_get("XAI_BASE_URL", DEFAULT_XAI_BASE_URL),
            xai_realtime_url=_get("XAI_REALTIME_URL", DEFAULT_XAI_REALTIME_URL),
            xai_text_model=_get("XAI_TEXT_MODEL", DEFAULT_XAI_TEXT_MODEL),
            xai_voice_model=_get("XAI_VOICE_MODEL", DEFAULT_XAI_VOICE_MODEL),
            xai_voice=_get("XAI_VOICE", DEFAULT_XAI_VOICE),
            present_coverage=_getf("WEBCAM_PRESENT_COVERAGE", 0.10),
            partial_coverage=_getf("WEBCAM_PARTIAL_COVERAGE", 0.03),
            foreground_delta=_getf("WEBCAM_FOREGROUND_DELTA", 0.18),
            looking_away_after=_getf("WEBCAM_LOOKING_AWAY_AFTER", 4.0),
            brief_absent_after=_getf("WEBCAM_BRIEF_ABSENT_AFTER", 6.0),
            absent_after=_getf("WEBCAM_ABSENT_AFTER", 20.0),
            looking_away_attention=_getf("WEBCAM_LOOKING_AWAY_ATTENTION", 0.35),
        )
