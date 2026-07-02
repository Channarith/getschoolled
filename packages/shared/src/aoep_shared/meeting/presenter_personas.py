"""Named presenter personas: neural voice + delivery personality presets."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PresenterPersona:
    """Maps a human-facing persona to TTS voice and optional delivery overrides."""

    id: str
    label: str
    voice: str
    language: str = "en"
    description: str = ""
    wpm_factor: float = 1.0
    present_mode: str = ""
    tts_rate: str = "+0%"

    def to_dict(self) -> dict:
        return asdict(self)


# Edge neural voices — run ``edge-tts --list-voices`` for the full catalog.
PRESENTER_PERSONAS: Dict[str, PresenterPersona] = {
    "aria": PresenterPersona(
        "aria",
        "Warm guide",
        "en-US-AriaNeural",
        description="Friendly default; clear pacing for general lessons.",
    ),
    "jenny": PresenterPersona(
        "jenny",
        "Clear instructor",
        "en-US-JennyNeural",
        description="Crisp, professional classroom tone.",
    ),
    "guy": PresenterPersona(
        "guy",
        "Energetic coach",
        "en-US-GuyNeural",
        wpm_factor=1.08,
        tts_rate="+4%",
        description="Upbeat delivery; good for workshops and drills.",
    ),
    "davis": PresenterPersona(
        "davis",
        "Theatrical demo host",
        "en-US-DavisNeural",
        present_mode="lewin",
        wpm_factor=1.05,
        tts_rate="+2%",
        description="Lewin-style demos: predict-before-reveal, demo climax.",
    ),
    "sonia": PresenterPersona(
        "sonia",
        "Calm scholar (UK)",
        "en-GB-SoniaNeural",
        language="en-GB",
        wpm_factor=0.94,
        tts_rate="-4%",
        description="Measured British accent; survey and deep-dive arcs.",
    ),
    "emma": PresenterPersona(
        "emma",
        "Workshop facilitator",
        "en-US-EmmaNeural",
        present_mode="workshop",
        wpm_factor=1.02,
        description="Collaborative, hands-on classroom energy.",
    ),
    "brian": PresenterPersona(
        "brian",
        "Newsreader (UK)",
        "en-GB-BrianNeural",
        language="en-GB",
        wpm_factor=1.1,
        present_mode="condensed",
        tts_rate="+6%",
        description="Fast, concise bullet delivery.",
    ),
    "nanami": PresenterPersona(
        "nanami",
        "Japanese instructor",
        "ja-JP-NanamiNeural",
        language="ja",
        description="Japanese neural voice (content should match language).",
    ),
}


def list_presenter_personas(*, repo_root: Optional[Path] = None) -> List[dict]:
    from .voice_profiles import list_voice_profiles

    rows = [
        {
            "id": p.id,
            "label": p.label,
            "voice": p.voice,
            "language": p.language,
            "present_mode": p.present_mode,
            "description": p.description,
            "kind": "preset",
        }
        for p in PRESENTER_PERSONAS.values()
    ]
    for v in list_voice_profiles(repo_root=repo_root):
        rows.append({
            "id": v["id"],
            "label": v.get("label", v["id"]),
            "voice": v.get("voice_token", f"clone:{v['id']}"),
            "language": v.get("language", "en"),
            "present_mode": v.get("present_mode", ""),
            "description": v.get("description", "custom cloned voice"),
            "kind": "clone",
            "sample": v.get("sample_resolved"),
            "tts_engine": v.get("tts_engine", "clone"),
        })
    return rows


def resolve_persona(name: Optional[str], *, repo_root: Optional[Path] = None) -> Optional[PresenterPersona]:
    if not name or not str(name).strip():
        return None
    key = str(name).strip().lower().replace(" ", "_").replace("-", "_")
    if key in PRESENTER_PERSONAS:
        return PRESENTER_PERSONAS[key]
    for p in PRESENTER_PERSONAS.values():
        if key in (p.id, p.label.lower(), p.voice.lower()):
            return p
    from .voice_profiles import get_voice_profile

    profile = get_voice_profile(key, repo_root=repo_root)
    if profile:
        return PresenterPersona(
            id=profile.id,
            label=profile.label,
            voice=profile.voice_token,
            language=profile.language,
            description=profile.description,
            wpm_factor=profile.wpm_factor,
            present_mode=profile.present_mode,
            tts_rate=profile.tts_rate,
        )
    raise ValueError(
        f"unknown persona {name!r}; choose one of: {', '.join(sorted(PRESENTER_PERSONAS))} "
        f"or register a custom voice under voices/<id>/"
    )


def personas_json() -> str:
    return json.dumps(list_presenter_personas(), indent=2)
