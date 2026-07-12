"""Catalog of narration voices across accents, languages, and regional slang.

Each voice maps to a real provider voice:
  * ``edge_voice`` — a Microsoft neural voice (edge-tts). These give TRUE
    per-accent coverage (British, Australian, Irish, Indian, Mandarin, Cantonese,
    Mexican Spanish, Québécois French, …).
  * ``elevenlabs_voice_id`` — optional specific ElevenLabs voice.
  * ``dialect`` — optional :mod:`aoep_shared.dialect` id so narration also picks
    up the region's SLANG/phrasing (e.g. Texan "howdy y'all", Aussie "no worries").

The speech gateway resolves a chosen ``voice`` id to the right provider voice so
"give me a British/Texan/Australian/Chinese/Spanish voice" just works.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    language: str      # base code: en, es, zh, fr, ...
    locale: str        # BCP-47: en-GB, es-MX, zh-CN
    accent: str        # human accent/region name
    gender: str        # "female" | "male"
    edge_voice: str    # edge-tts neural voice name (accent-accurate)
    elevenlabs_voice_id: str = ""   # optional specific ElevenLabs voice
    dialect: str = ""               # aoep_shared.dialect id for slang flavor

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "language": self.language,
            "locale": self.locale, "accent": self.accent, "gender": self.gender,
            "dialect": self.dialect,
        }


# Curated multi-accent, multi-language catalog. edge-tts voice names are real
# Microsoft neural voices; add more by dropping rows in here.
VOICE_CATALOG: List[Voice] = [
    # --- English accents ------------------------------------------------- #
    Voice("en_us_f", "American — Aria (F)", "en", "en-US", "American", "female", "en-US-AriaNeural", dialect="us_general"),
    Voice("en_us_m", "American — Guy (M)", "en", "en-US", "American", "male", "en-US-GuyNeural", dialect="us_general"),
    Voice("en_us_tx_m", "Texan — Davis (M)", "en", "en-US", "Texan (US South)", "male", "en-US-DavisNeural", dialect="us_tx"),
    Voice("en_us_tx_f", "Texan — Jenny (F)", "en", "en-US", "Texan (US South)", "female", "en-US-JennyNeural", dialect="us_tx"),
    Voice("en_us_ca_f", "Californian — Ana (F)", "en", "en-US", "Californian", "female", "en-US-AnaNeural", dialect="us_ca"),
    Voice("en_gb_f", "British — Sonia (F)", "en", "en-GB", "British", "female", "en-GB-SoniaNeural", dialect="en_gb"),
    Voice("en_gb_m", "British — Ryan (M)", "en", "en-GB", "British", "male", "en-GB-RyanNeural", dialect="en_gb"),
    Voice("en_au_f", "Australian — Natasha (F)", "en", "en-AU", "Australian", "female", "en-AU-NatashaNeural", dialect="en_au"),
    Voice("en_au_m", "Australian — William (M)", "en", "en-AU", "Australian", "male", "en-AU-WilliamNeural", dialect="en_au"),
    Voice("en_ie_f", "Irish — Emily (F)", "en", "en-IE", "Irish", "female", "en-IE-EmilyNeural"),
    Voice("en_in_f", "Indian — Neerja (F)", "en", "en-IN", "Indian", "female", "en-IN-NeerjaNeural"),
    Voice("en_in_m", "Indian — Prabhat (M)", "en", "en-IN", "Indian", "male", "en-IN-PrabhatNeural"),
    Voice("en_ca_f", "Canadian — Clara (F)", "en", "en-CA", "Canadian", "female", "en-CA-ClaraNeural"),
    Voice("en_za_f", "South African — Leah (F)", "en", "en-ZA", "South African", "female", "en-ZA-LeahNeural"),
    # --- Spanish --------------------------------------------------------- #
    Voice("es_es_f", "Spanish (Spain) — Elvira (F)", "es", "es-ES", "Castilian", "female", "es-ES-ElviraNeural"),
    Voice("es_es_m", "Spanish (Spain) — Álvaro (M)", "es", "es-ES", "Castilian", "male", "es-ES-AlvaroNeural"),
    Voice("es_mx_f", "Spanish (México) — Dalia (F)", "es", "es-MX", "Mexican", "female", "es-MX-DaliaNeural", dialect="es_mx"),
    Voice("es_mx_m", "Spanish (México) — Jorge (M)", "es", "es-MX", "Mexican", "male", "es-MX-JorgeNeural", dialect="es_mx"),
    Voice("es_ar_f", "Spanish (Argentina) — Elena (F)", "es", "es-AR", "Rioplatense", "female", "es-AR-ElenaNeural"),
    Voice("es_us_f", "Spanish (US) — Paloma (F)", "es", "es-US", "US Spanish", "female", "es-US-PalomaNeural"),
    # --- Chinese --------------------------------------------------------- #
    Voice("zh_cn_f", "Chinese (Mandarin) — Xiaoxiao (F)", "zh", "zh-CN", "Mandarin (China)", "female", "zh-CN-XiaoxiaoNeural"),
    Voice("zh_cn_m", "Chinese (Mandarin) — Yunxi (M)", "zh", "zh-CN", "Mandarin (China)", "male", "zh-CN-YunxiNeural"),
    Voice("zh_hk_f", "Chinese (Cantonese) — HiuMaan (F)", "zh", "zh-HK", "Cantonese (HK)", "female", "zh-HK-HiuMaanNeural"),
    Voice("zh_tw_f", "Chinese (Taiwan) — HsiaoChen (F)", "zh", "zh-TW", "Mandarin (Taiwan)", "female", "zh-TW-HsiaoChenNeural"),
    # --- French ---------------------------------------------------------- #
    Voice("fr_fr_f", "French (France) — Denise (F)", "fr", "fr-FR", "Metropolitan", "female", "fr-FR-DeniseNeural"),
    Voice("fr_ca_f", "French (Canada) — Sylvie (F)", "fr", "fr-CA", "Québécois", "female", "fr-CA-SylvieNeural"),
    # --- Other major languages ------------------------------------------ #
    Voice("de_de_f", "German — Katja (F)", "de", "de-DE", "German", "female", "de-DE-KatjaNeural"),
    Voice("de_de_m", "German — Conrad (M)", "de", "de-DE", "German", "male", "de-DE-ConradNeural"),
    Voice("it_it_f", "Italian — Elsa (F)", "it", "it-IT", "Italian", "female", "it-IT-ElsaNeural"),
    Voice("pt_br_f", "Portuguese (Brazil) — Francisca (F)", "pt", "pt-BR", "Brazilian", "female", "pt-BR-FranciscaNeural", dialect="pt_br"),
    Voice("pt_pt_f", "Portuguese (Portugal) — Raquel (F)", "pt", "pt-PT", "European", "female", "pt-PT-RaquelNeural"),
    Voice("ja_jp_f", "Japanese — Nanami (F)", "ja", "ja-JP", "Japanese", "female", "ja-JP-NanamiNeural"),
    Voice("ko_kr_f", "Korean — SunHi (F)", "ko", "ko-KR", "Korean", "female", "ko-KR-SunHiNeural"),
    Voice("hi_in_f", "Hindi — Swara (F)", "hi", "hi-IN", "Hindi", "female", "hi-IN-SwaraNeural"),
    Voice("ar_sa_f", "Arabic (Gulf) — Zariyah (F)", "ar", "ar-SA", "Gulf", "female", "ar-SA-ZariyahNeural"),
    Voice("ar_eg_f", "Arabic (Egypt) — Salma (F)", "ar", "ar-EG", "Egyptian", "female", "ar-EG-SalmaNeural"),
    Voice("ru_ru_f", "Russian — Svetlana (F)", "ru", "ru-RU", "Russian", "female", "ru-RU-SvetlanaNeural"),
    Voice("vi_vn_f", "Vietnamese — HoaiMy (F)", "vi", "vi-VN", "Vietnamese", "female", "vi-VN-HoaiMyNeural"),
    Voice("th_th_f", "Thai — Premwadee (F)", "th", "th-TH", "Thai", "female", "th-TH-PremwadeeNeural"),
    Voice("tr_tr_f", "Turkish — Emel (F)", "tr", "tr-TR", "Turkish", "female", "tr-TR-EmelNeural"),
]

_BY_ID: Dict[str, Voice] = {v.id: v for v in VOICE_CATALOG}


def get_voice(voice_id: str) -> Optional[Voice]:
    return _BY_ID.get((voice_id or "").strip())


def default_voice_for_language(language: str) -> Optional[Voice]:
    """First catalog voice whose base language matches (e.g. 'en' -> American)."""
    lang = (language or "en").split("-")[0].lower()
    for v in VOICE_CATALOG:
        if v.language == lang:
            return v
    return None


def resolve_voice(voice_id: str = "", *, language: str = "en") -> Optional[Voice]:
    """Resolve a chosen voice id, falling back to the language default."""
    return get_voice(voice_id) or default_voice_for_language(language)


def catalog_grouped() -> List[dict]:
    """Voices grouped by language for a UI picker (stable order)."""
    order: List[str] = []
    groups: Dict[str, List[dict]] = {}
    for v in VOICE_CATALOG:
        if v.language not in groups:
            groups[v.language] = []
            order.append(v.language)
        groups[v.language].append(v.to_dict())
    return [{"language": lang, "voices": groups[lang]} for lang in order]
