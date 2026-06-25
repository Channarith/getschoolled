"""Narration voice styles for Drive Mode / audio classes.

Maps user preference (or learning-profile signals) to prosody and voice-ranking
hints. Clients pick the best device voice for the locale + style.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Optional

VoiceStyleId = Literal["standard", "child", "accessible", "calm", "clear"]
NarrationVoicePref = Literal["auto", "standard", "child", "accessible", "calm", "clear"]

VOICE_STYLES: tuple[VoiceStyleId, ...] = (
    "standard",
    "child",
    "accessible",
    "calm",
    "clear",
)

VOICE_STYLE_LABELS: Dict[VoiceStyleId, str] = {
    "standard": "Standard",
    "child": "Child-friendly",
    "accessible": "Accessible (slower)",
    "calm": "Calm & gentle",
    "clear": "Clear & crisp",
}


@dataclass(frozen=True)
class VoiceProsody:
    """Relative speech rate and pitch (1.0 = platform default)."""

    rate: float
    pitch: float


def prosody_for_style(style: VoiceStyleId) -> VoiceProsody:
    if style == "child":
        return VoiceProsody(rate=0.88, pitch=1.12)
    if style == "accessible":
        return VoiceProsody(rate=0.78, pitch=1.0)
    if style == "calm":
        return VoiceProsody(rate=0.85, pitch=0.95)
    if style == "clear":
        return VoiceProsody(rate=0.92, pitch=1.0)
    return VoiceProsody(rate=0.95, pitch=1.0)


def suggest_voice_style_from_profile(profile: Optional[Dict]) -> VoiceStyleId:
    """Infer a narration style from persisted student / learning profile fields."""
    if not profile:
        return "standard"
    age = (profile.get("age_band") or "adult").lower()
    if age == "child":
        return "child"
    acc = profile.get("accessibility") or {}
    pace = (profile.get("learning_pace") or "").lower()
    reading = (profile.get("reading_level") or "").lower()
    if acc.get("needs_extra_time") or pace == "slow" or reading == "beginner":
        return "accessible"
    if acc.get("uses_assistive_tech") or acc.get("needs_captions"):
        return "clear"
    if age == "teen":
        return "clear"
    return "standard"


def resolve_voice_style(
    pref: str,
    profile: Optional[Dict] = None,
) -> VoiceStyleId:
    """Resolve ``auto`` from learning profile; otherwise return the explicit style."""
    if pref and pref != "auto" and pref in VOICE_STYLES:
        return pref  # type: ignore[return-value]
    return suggest_voice_style_from_profile(profile)


def voice_name_style_bonus(style: VoiceStyleId, voice_name: str) -> int:
    """Score adjustment when ranking OS voices by name (web + mobile)."""
    name = (voice_name or "").lower()
    if style == "child":
        if any(k in name for k in ("child", "kids", "junior", "nicky", "pip", "zoe")):
            return 6
        if "compact" in name:
            return 2
    if style == "accessible":
        if any(k in name for k in ("enhanced", "natural", "neural", "premium", "siri")):
            return 4
    if style == "calm":
        if any(k in name for k in ("samantha", "karen", "serena", "moira", "tessa")):
            return 3
    if style == "clear":
        if any(k in name for k in ("enhanced", "natural", "neural", "wavenet", "jenny", "guy")):
            return 5
    if any(k in name for k in ("albert", "zarvox", "whisper", "jester", "bahh")):
        return -8
    return 0
