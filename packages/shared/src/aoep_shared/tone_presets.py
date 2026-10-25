"""Voice tones as edge-tts prosody (rate / pitch / volume), shared by the speech gateway and the course studio.

A tone is a short id: ``neutral`` (no change), a preset (``professional``, ``cute``, ``anime`` ...) or a blend of presets
(``blend-professional75-cute25``). The values mirror tts_bakeoff/voice_types.py (a test keeps the two tables identical), and the
pre-rendered clips under voice-assets/edge.<Voice>~<tone>/ are made with the same numbers, so a live render and a stored clip match.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

NEUTRAL = "neutral"
PRESETS: Dict[str, Tuple[str, str, str]] = {  # name: (rate, pitch, volume)
    "professional": ("-3%", "+0Hz", "+0%"),
    "warm": ("-8%", "-2Hz", "+0%"),
    "calm": ("-12%", "-4Hz", "-5%"),
    "energetic": ("+12%", "+6Hz", "+5%"),
    "cute": ("+8%", "+30Hz", "+0%"),
    "anime": ("+18%", "+40Hz", "+10%"),
    "tough": ("-4%", "-18Hz", "+10%"),
    "heavy": ("-15%", "-30Hz", "+0%"),
    "light": ("+4%", "+14Hz", "-10%"),
}
_PARTS = ("professional", "cute", "anime")
BLEND_WEIGHTS: Dict[str, Dict[str, int]] = {
    **{f"{a}{w}-{b}{100 - w}": {a: w, b: 100 - w} for i, a in enumerate(_PARTS) for b in _PARTS[i + 1:] for w in (75, 50, 25)},
    "pro34-cute33-anime33": {"professional": 34, "cute": 33, "anime": 33},
    "pro60-cute20-anime20": {"professional": 60, "cute": 20, "anime": 20},
    "cute60-pro20-anime20": {"cute": 60, "professional": 20, "anime": 20},
    "anime60-pro20-cute20": {"anime": 60, "professional": 20, "cute": 20},
}


def blend(weights: Dict[str, int]) -> Tuple[str, str, str]:
    """Weighted average of the presets' rate (%), pitch (Hz) and volume (%)."""
    total = sum(weights.values())
    out = []
    for i, unit in enumerate(("%", "Hz", "%")):
        v = sum(float(PRESETS[n][i].rstrip("%Hz")) * w for n, w in weights.items()) / total
        out.append(f"{int(round(v)):+d}{unit}")   # int() keeps "-0" out: edge-tts wants +0
    return out[0], out[1], out[2]


TONE_IDS = (NEUTRAL, *PRESETS, *(f"blend-{k}" for k in BLEND_WEIGHTS))


def tone_prosody(tone: Optional[str]) -> Optional[Tuple[str, str, str]]:
    """(rate, pitch, volume) for a known non-neutral tone, else None (neutral, empty or unknown: the caller keeps its defaults)."""
    t = (tone or "").strip().lower()
    if not t or t == NEUTRAL:
        return None
    if t in PRESETS:
        return PRESETS[t]
    if t.startswith("blend-") and t[6:] in BLEND_WEIGHTS:
        return blend(BLEND_WEIGHTS[t[6:]])
    return None
