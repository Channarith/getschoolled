"""Map a learner language onto the xAI realtime voice session.

xAI speech-to-speech (docs.x.ai Speech to Speech, ``language_hint``) natively
accepts ``en``, ``ar-EG``, ``ar-SA``, ``ar-AE``, ``bn``, ``zh``, ``fr``, ``de``,
``hi``, ``id``, ``it``, ``ja``, ``ko``, ``pt-BR``, ``pt-PT``, ``ru``, ``es-MX``,
``es-ES``, ``tr``, and ``vi``. ``zh`` is Mandarin (Chinese, Simplified). Bare
``es`` and ``pt`` are rejected. Unrecognized hints are ignored and the session
falls back to automatic language detection.

Cantonese is not in that speech-to-speech table. The speech-to-text API
documents it as ``yue``. ``zh-HK`` is not accepted either. An unrecognized
``language_hint`` is ignored, and the session then auto-detects. For a Hong
Kong or Guangdong speaker that detection lands on Mandarin (``zh``), the only
Chinese code the realtime voice accepts. Do not send ``yue`` or ``zh-HK`` into
the realtime socket. Narrate Cantonese with edge-tts ``zh-HK-HiuMaanNeural``.
Mandarin stays on xAI with ``language_hint`` ``zh``.

Khmer is in neither list. A session with no hint auto-detects, and Khmer is
then spoken with a Thai-like accent: Thai is a Southeast Asian language the
transcription model knows, and Khmer is not. Do not send ``th``, a Thai voice
id, or instructions that tell the model it is speaking Thai. Narrate Khmer
with edge-tts ``km-KH-SreymomNeural`` (a Cambodian voice). If that render
fails, the speech gateway's existing ElevenLabs fallback still runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from .languages import LANGUAGE_NAMES, english_variety

# xAI speech-to-speech has one English hint: ``en``. The regional neural
# voice and the instruction keep the accent when Grok is not the renderer.
_REGIONAL_ENGLISH = {
    "en-GB": (
        "Speak British English. Use British vocabulary and pronunciation, not American English.",
        "en-GB-SoniaNeural",
        "British English uses a British voice (en-GB).",
    ),
    "en-AU": (
        "Speak Australian English. Use Australian vocabulary and pronunciation, not American English.",
        "en-AU-NatashaNeural",
        "Australian English uses an Australian voice (en-AU).",
    ),
    "en-SG": (
        "Speak Singapore English (Singlish) with a clear teaching tone. "
        "Light particles such as lah and can are fine. Do not speak American English.",
        "en-SG-LunaNeural",
        "Singlish uses a Singapore voice (en-SG).",
    ),
}

# Speech-to-speech language_hint values from the xAI voice docs.
# Regional variants are required for Spanish, Portuguese, and Arabic.
_XAI_HINT = {
    "en": "en",
    "ar": "ar-SA",
    "bn": "bn",
    "zh": "zh",
    "fr": "fr",
    "de": "de",
    "hi": "hi",
    "id": "id",
    "it": "it",
    "ja": "ja",
    "ko": "ko",
    "pt": "pt-BR",
    "ru": "ru",
    "es": "es-ES",
    "tr": "tr",
    "vi": "vi",
}

KHMER_EDGE_VOICE = "km-KH-SreymomNeural"
CANTONESE_EDGE_VOICE = "zh-HK-HiuMaanNeural"
MANDARIN_EDGE_VOICE = "zh-CN-XiaoxiaoNeural"


def spoken_tag(language: str) -> str:
    """Lowercase BCP-47-ish tag. Underscores become hyphens."""
    return (language or "").strip().lower().replace("_", "-")


def is_cantonese_tag(language: str) -> bool:
    """Hong Kong / Macau / Guangdong Cantonese, not Mandarin."""
    raw = spoken_tag(language)
    if not raw:
        return False
    if raw in {"yue", "zh-hk", "zh-mo", "zh-yue", "cantonese"}:
        return True
    return (
        raw.startswith("yue-")
        or raw.startswith("zh-hk")
        or raw.startswith("zh-mo")
        or raw.startswith("zh-yue")
    )


def is_khmer_tag(language: str) -> bool:
    raw = spoken_tag(language)
    return raw == "km" or raw.startswith("km-")


def normalize_spoken_code(language: str) -> str:
    """Product code for a voice session: ``km``, ``zh``, ``yue``, or a base code.

    Blank stays blank so an unspecified session is unchanged. ``zh-HK`` is
    Cantonese here even though content translation still treats that regional
    tag as Mandarin ``zh``.
    """
    raw = spoken_tag(language)
    if not raw:
        return ""
    if is_cantonese_tag(raw):
        return "yue"
    if is_khmer_tag(raw):
        return "km"
    if raw in {"zh-cn", "zh-hans", "zh-sg", "cmn", "mandarin"} or raw.startswith("zh-cn"):
        return "zh"
    return raw.split("-")[0]


@dataclass(frozen=True)
class SpokenLanguagePlan:
    """How one learner language should be spoken."""

    requested: str
    engine: str
    use_xai: bool
    xai_language: str
    instructions: str
    edge_voice: str
    hint: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "requested": self.requested,
            "engine": self.engine,
            "use_xai": self.use_xai,
            "xai_language": self.xai_language,
            "instructions": self.instructions,
            "edge_voice": self.edge_voice,
            "hint": self.hint,
            "reason": self.reason,
        }


def plan_spoken_language(language: str) -> SpokenLanguagePlan:
    """Decide the xAI hint, or the Khmer narration engine that replaces it."""
    regional = _REGIONAL_ENGLISH.get(english_variety(language))
    if regional:
        instructions, edge, hint = regional
        return SpokenLanguagePlan(
            requested=english_variety(language),
            engine="xai-grok-voice",
            use_xai=True,
            xai_language="en",
            instructions=instructions,
            edge_voice=edge,
            hint=hint,
            reason=(
                "xAI speech-to-speech has one English hint, en. "
                "British, Australian, and Singapore English keep that hint "
                "and use their own neural voice and instructions."
            ),
        )
    requested = normalize_spoken_code(language)
    if not requested:
        return SpokenLanguagePlan(
            requested="",
            engine="xai-grok-voice",
            use_xai=True,
            xai_language="",
            instructions="",
            edge_voice="",
            hint="",
            reason="No language was requested, so the session keeps automatic detection.",
        )
    if requested == "km":
        return SpokenLanguagePlan(
            requested="km",
            engine="edge-tts",
            use_xai=False,
            xai_language="",
            instructions=(
                "Speak Khmer (Cambodian, ខ្មែរ), the language of Cambodia. "
                "Do not speak Thai."
            ),
            edge_voice=KHMER_EDGE_VOICE,
            hint=(
                "Khmer uses a Cambodian voice (km-KH), not Grok. "
                "xAI has no Khmer voice."
            ),
            reason=(
                "xAI speech-to-speech has no Khmer voice. With no language hint "
                "the session auto-detected Khmer as Thai-like speech. Narration "
                "uses edge-tts km-KH-SreymomNeural. If that render fails, the "
                "speech gateway still falls through to ElevenLabs."
            ),
        )
    if requested == "yue":
        return SpokenLanguagePlan(
            requested="yue",
            engine="edge-tts",
            use_xai=False,
            xai_language="",
            instructions=(
                "Speak only Hong Kong Cantonese (粵語), the language of Hong Kong "
                "and Guangdong. Do not speak Mandarin Chinese."
            ),
            edge_voice=CANTONESE_EDGE_VOICE,
            hint=(
                "Cantonese uses a Hong Kong voice (zh-HK), not Grok. "
                "xAI speech-to-speech has no Cantonese code."
            ),
            reason=(
                "xAI speech-to-speech accepts zh for Mandarin only. yue is a "
                "speech-to-text code, and zh-HK is not in the realtime language "
                "table; either hint is ignored and the session auto-detects "
                "Mandarin. Narration uses edge-tts zh-HK-HiuMaanNeural. "
                "Mandarin stays on xAI with language_hint zh."
            ),
        )
    if requested == "zh":
        return SpokenLanguagePlan(
            requested="zh",
            engine="xai-grok-voice",
            use_xai=True,
            xai_language="zh",
            instructions=(
                "Speak Mandarin Chinese (普通话). Do not speak Cantonese."
            ),
            edge_voice=MANDARIN_EDGE_VOICE,
            hint="Grok voice is speaking Mandarin.",
            reason="xAI speech-to-speech code for Chinese (Simplified) is zh.",
        )
    hint = _XAI_HINT.get(requested, "")
    name = LANGUAGE_NAMES.get(requested, requested)
    instructions = ""
    if requested != "en":
        if hint:
            instructions = f"Speak {name} ({hint})."
        else:
            instructions = (
                f"Speak {name} ({requested}). Do not switch to another language."
            )
    return SpokenLanguagePlan(
        requested=requested,
        engine="xai-grok-voice",
        use_xai=True,
        xai_language=hint,
        instructions=instructions,
        edge_voice="",
        hint="",
        reason=(
            f"xAI language_hint {hint}."
            if hint
            else f"{requested} is not an xAI speech-to-speech code; instructions name it and no hint is sent."
        ),
    )


def tutoring_instruction(language: str) -> str:
    """One spoken-language sentence for an xAI system prompt. Blank for English."""
    plan = plan_spoken_language(language)
    if not plan.requested or plan.requested == "en":
        return ""
    if plan.requested == "km":
        return (
            "Respond entirely in Khmer (Cambodian, km), the language of Cambodia. "
            "Do not respond in Thai. "
            "Keep the tone warm, concise, and suitable for spoken tutoring."
        )
    if plan.requested == "yue":
        return (
            "Respond entirely in Hong Kong Cantonese (粵語, yue), the language of "
            "Hong Kong and Guangdong. Do not respond in Mandarin. "
            "Keep the tone warm, concise, and suitable for spoken tutoring."
        )
    if plan.requested == "zh":
        return (
            "Respond entirely in Mandarin Chinese (普通话, zh). "
            "Do not respond in Cantonese. "
            "Keep the tone warm, concise, and suitable for spoken tutoring."
        )
    text = plan.instructions.strip()
    if not text:
        return ""
    return text + " Keep the tone warm, concise, and suitable for spoken tutoring."
