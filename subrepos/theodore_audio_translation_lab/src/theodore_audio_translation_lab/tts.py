"""Server-side neural speech for Theodore — thin re-export of aoep_shared.lab_tts.

Kept as ``theodore_audio_translation_lab.tts`` so existing imports/tests keep
working while music/webcam labs share one implementation.

Patchable aliases (``_edge_tts_available``, ``_gateway_url``) exist so tests that
historically monkeypatched this module still work.
"""

from __future__ import annotations

import aoep_shared.lab_tts as _lab
from aoep_shared.languages import LANGUAGE_NAMES, normalize_language

ProviderUnavailable = _lab.ProviderUnavailable
MAX_TTS_CHARS = _lab.MAX_TTS_CHARS
reset_disabled_engines = _lab.reset_disabled_engines


def _gateway_url() -> str:
    return _lab.gateway_url()


def _edge_tts_available() -> bool:
    return _lab._edge_tts_available()


def _elevenlabs_key() -> str:
    return _lab._elevenlabs_key()


def engine_chain() -> list[str]:
    """Honor local monkeypatches on ``_edge_tts_available`` / env."""
    chain: list[str] = []
    if _gateway_url():
        chain.append("speech-gateway")
    if _elevenlabs_key():
        chain.append("elevenlabs")
    if _edge_tts_available():
        chain.append("edge-tts")
    return [e for e in chain if e not in _lab._disabled_engines]


def tts_status() -> dict[str, object]:
    chain = engine_chain()
    return {
        "available": bool(chain),
        "engine": chain[0] if chain else "",
        "engines": chain,
        "disabled": sorted(_lab._disabled_engines),
        "gateway_url": _gateway_url(),
        "elevenlabs_configured": bool(_elevenlabs_key()),
        "xai_configured": bool(__import__("os").environ.get("XAI_API_KEY", "").strip()),
        "languages": sorted(set(_lab._EDGE_VOICES)),
        "note": (
            f"Server neural speech via {' → '.join(chain)}."
            if chain
            else "No server TTS configured; the page uses the device voice. "
            "Set TTS_BASE_URL/SPEECH_BASE_URL, ELEVENLABS_API_KEY, or install edge-tts."
        ),
    }


def synthesize(text: str, *, language: str = "en", style: str = "warm"):
    clean = (text or "").strip()
    if not clean:
        raise ValueError("tts text is empty")
    if len(clean) > MAX_TTS_CHARS:
        clean = clean[:MAX_TTS_CHARS]
    lang = normalize_language(language) or "en"

    errors: list[str] = []
    for engine in list(engine_chain()):
        try:
            if engine == "speech-gateway":
                return (*_lab._gateway_tts(clean, lang, style), "speech-gateway")
            if engine == "elevenlabs":
                return (*_lab._elevenlabs_tts(clean, lang), "elevenlabs")
            if engine == "edge-tts":
                return (*_lab._edge_tts(clean, lang), "edge-tts")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{engine}: {exc}")
            _lab._disabled_engines.add(engine)

    detail = f" Tried: {'; '.join(errors)}" if errors else ""
    raise ProviderUnavailable(
        f"No server TTS engine could render {LANGUAGE_NAMES.get(lang, lang)}."
        f"{detail} Configure TTS_BASE_URL/SPEECH_BASE_URL, ELEVENLABS_API_KEY, "
        "or install edge-tts; the client can still use the device voice."
    )


configured_engines = engine_chain
gateway_url = _gateway_url
