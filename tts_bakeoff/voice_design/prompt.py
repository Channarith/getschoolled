"""Voice-design descriptions: built from a closed vocabulary, and a guard for any free text.

A designed voice must not imitate a real person (VoxCPM2's terms forbid impersonation). Registry voices are therefore built ONLY from the
enums below (safe by construction); a free-text description (``--description``) goes through ``validate_description`` first.
"""
from __future__ import annotations

import re

GENDERS = {"f": "woman", "m": "man"}
AGES = {
    "young": "young adult",
    "adult": "adult",
    "older": "older, mature",
    "child": "child-like, bright",   # vocabulary only: validate_registry() keeps it out of the registry (see CHILD_NOTE)
}
TIMBRES = {
    "warm": "warm, rounded voice",
    "bright": "bright, clear voice",
    "deep": "deep, resonant voice",
    "soft": "soft, airy voice",
    "crisp": "crisp, articulate voice",
    "smooth": "smooth, even voice",
    "clear": "clear, steady voice",
    "rich": "rich, full voice",
}
ACCENTS = {   # optional; a language-neutral voice leaves this out
    "us": "American English accent", "uk": "British English accent", "au": "Australian English accent",
    "in": "Indian English accent", "sg": "Singaporean English accent",
}
# The nine tones of tts_bakeoff.voice_types.PRESETS, as descriptions the model can act on.
TONES = {
    "professional": "professional, confident, measured pace",
    "warm": "warm, friendly, reassuring",
    "calm": "calm, soft-spoken, slow and steady",
    "energetic": "energetic, upbeat, slightly faster",
    "cute": "cute, sweet, bright and playful, clearly an adult voice",
    "anime": "anime-style, lively, expressive and high-energy, youthful but clearly an adult voice",
    "tough": "tough, firm, a little gruff",
    "heavy": "heavy, deep and slow",
    "light": "light, gentle and airy",
}
# Tones are DESCRIPTIONS the model acts on, never pitch/formant DSP: Cantonese has six tones whose pitch contours carry the word, and shifting
# pitch or formants after synthesis bends those contours (a wrong tone is a different word). 'cute' and 'anime' say 'adult' on purpose: the
# registry has no child-like voices and a cute or anime tone must not turn into one.
CHILD_NOTE = ("'child' would be a synthetic child-like voice for a children's platform. It is kept out of the registry (validate_registry rejects it) "
              "until the owner has decided; there is no switch that renders it.")


def build_description(gender: str, age: str, timbre: str, accent: str | None = None, tone: str | None = None) -> str:
    """'A young adult woman, warm, rounded voice, professional, confident, measured pace' - enums only."""
    if gender not in GENDERS or age not in AGES or timbre not in TIMBRES:
        raise ValueError(f"unknown gender/age/timbre: {gender!r}/{age!r}/{timbre!r}")
    if accent is not None and accent not in ACCENTS:
        raise ValueError(f"unknown accent {accent!r}")
    if tone is not None and tone not in TONES:
        raise ValueError(f"unknown tone {tone!r}")
    who = f"{AGES[age]} {GENDERS[gender]}"
    parts = [f"{'An' if who[0] in 'aeiou' else 'A'} {who}", TIMBRES[timbre]]
    if accent:
        parts.append(ACCENTS[accent])
    if tone:
        parts.append(TONES[tone])
    return ", ".join(parts)


class DescriptionRejected(ValueError):
    pass


_CHILDLIKE = re.compile(
    r"\b(child\w*|kids?|toddlers?|babies|baby|infants?|little\s+(?:girl|boy|one)s?|small\s+(?:girl|boy)|boys?|girls?|schoolgirls?|schoolboys?|"
    r"teen\w*|minors?|pre-?teen\w*|juvenile|kindergarten\w*|preschool\w*|tween\w*|loli\w*|shota)\b",
    re.IGNORECASE,
)


_IMITATE = re.compile(
    r"\b(sounds?\s+like|sound\s+of|voice\s+of|in\s+the\s+style\s+of|style\s+of|imitat\w*|impersonat\w*|mimic\w*|clone\s+of|copy\s+of|"
    r"famous|celebrit\w*|politician|president|actor|actress|singer|youtuber|streamer|as\s+if\s+(?:he|she|they)\s+were)\b",
    re.IGNORECASE,
)
# Capitalised words that are fine in a description (accents, languages, regions). Anything else capitalised mid-sentence reads as a name.
_ALLOWED_PROPER = {
    "A", "An", "The", "American", "British", "English", "Australian", "Indian", "Singaporean", "Irish", "Scottish", "Canadian", "Chinese",
    "Mandarin", "Cantonese", "Spanish", "French", "German", "Japanese", "Korean", "Thai", "Vietnamese", "Khmer", "Hindi", "Swahili", "Arabic",
    "Brazilian", "Mexican", "Latin", "African", "Southern", "Northern", "Midwestern", "Californian", "New", "York", "Zealand", "Standard", "TV",
}


def validate_description(text: str) -> str:
    """Return the description if it is safe to give the model; raise DescriptionRejected if it could name or imitate a real person."""
    t = " ".join((text or "").split())
    if not t:
        raise DescriptionRejected("empty description")
    if len(t) > 240:
        raise DescriptionRejected("description too long (max 240 characters)")
    if "(" in t or ")" in t:
        raise DescriptionRejected("no parentheses in a description (they delimit it)")
    kid = _CHILDLIKE.search(t)
    if kid:
        raise DescriptionRejected(f"'{kid.group(0)}': child-like voices are not allowed; describe an adult voice ({CHILD_NOTE})")
    like = re.search(r"\blike\s+(?!(?:a|an|the)\b)\w+", t, re.IGNORECASE)
    if like:
        raise DescriptionRejected(f"'{like.group(0)}': 'like <name>' is not allowed; describe the voice itself (gender, age, tone)")
    m = _IMITATE.search(t)
    if m:
        raise DescriptionRejected(f"'{m.group(0)}': describe a kind of voice (gender, age, tone), never a person or 'sounds like'")
    for i, word in enumerate(re.findall(r"[A-Za-z][A-Za-z'’-]*", t)):
        w = word.strip("'’-")
        if w[:1].isupper() and w not in _ALLOWED_PROPER and not (i == 0 and w in _ALLOWED_PROPER):
            if i == 0 and w.lower() in {"a", "an", "the", "very", "slightly", "calm", "warm", "bright", "deep", "soft", "young"}:
                continue
            raise DescriptionRejected(f"'{w}' looks like a name: descriptions may not name people")
    return t
