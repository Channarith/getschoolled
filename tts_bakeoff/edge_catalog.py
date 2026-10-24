"""Language catalog for the edge-tts listening set: which voices exist per platform and extra language.

Derived from the committed snapshot (edge_voices.json, written by snapshot_edge_voices.py), so it needs no network.

DEFAULT-VOICE RULE (documented, deterministic): inside the language's primary locale, the default female / male voice is the
one pinned in PINNED when we already ship or tested one (the adapter's historical voices), else the first voice of that gender
in alphabetical order of its short name, skipping 'Multilingual' voices unless nothing else exists. The primary locale is
PRIMARY_LOCALE when set (en-US, es-MX, fr-FR, de-DE, pt-BR, ar-SA, zh-CN, ...) else the locale with the most voices
(ties: alphabetical). Regional variants list EVERY locale of the language with its own default female / male voice.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "edge_voices.json"

PLATFORM = ("en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "uk", "tr", "ar", "he", "hi", "bn", "ur", "fa", "zh", "ja",
            "ko", "vi", "th", "id", "sw", "el", "cs", "km")  # = aoep_shared.languages.SUPPORTED_LANGUAGES (a test keeps them equal)

# code: (English name, native name, rtl)
NAMES = {
    "en": ("English", "English", False), "es": ("Spanish", "Español", False), "fr": ("French", "Français", False),
    "de": ("German", "Deutsch", False), "it": ("Italian", "Italiano", False), "pt": ("Portuguese", "Português", False),
    "nl": ("Dutch", "Nederlands", False), "pl": ("Polish", "Polski", False), "ru": ("Russian", "Русский", False),
    "uk": ("Ukrainian", "Українська", False), "tr": ("Turkish", "Türkçe", False), "ar": ("Arabic", "العربية", True),
    "he": ("Hebrew", "עברית", True), "hi": ("Hindi", "हिन्दी", False), "bn": ("Bengali", "বাংলা", False),
    "ur": ("Urdu", "اردو", True), "fa": ("Persian", "فارسی", True), "zh": ("Chinese (Mandarin)", "中文", False),
    "ja": ("Japanese", "日本語", False), "ko": ("Korean", "한국어", False), "vi": ("Vietnamese", "Tiếng Việt", False),
    "th": ("Thai", "ไทย", False), "id": ("Indonesian", "Bahasa Indonesia", False), "sw": ("Swahili", "Kiswahili", False),
    "el": ("Greek", "Ελληνικά", False), "cs": ("Czech", "Čeština", False), "km": ("Khmer", "ខ្មែរ", False),
    "yue": ("Cantonese", "粵語", False), "ms": ("Malay", "Bahasa Melayu", False), "fil": ("Filipino", "Filipino", False),
    "my": ("Burmese", "မြန်မာ", False), "lo": ("Lao", "ລາວ", False), "ta": ("Tamil", "தமிழ்", False),
    "te": ("Telugu", "తెలుగు", False), "ne": ("Nepali", "नेपाली", False), "si": ("Sinhala", "සිංහල", False),
    "gu": ("Gujarati", "ગુજરાતી", False), "kn": ("Kannada", "ಕನ್ನಡ", False), "mr": ("Marathi", "मराठी", False),
    "ml": ("Malayalam", "മലയാളം", False), "pa": ("Punjabi", "ਪੰਜਾਬੀ", False), "am": ("Amharic", "አማርኛ", False),
    "zu": ("Zulu", "isiZulu", False), "af": ("Afrikaans", "Afrikaans", False), "bg": ("Bulgarian", "Български", False),
    "hr": ("Croatian", "Hrvatski", False), "hu": ("Hungarian", "Magyar", False), "ro": ("Romanian", "Română", False),
    "sk": ("Slovak", "Slovenčina", False), "sl": ("Slovenian", "Slovenščina", False), "sr": ("Serbian", "Српски", False),
    "lt": ("Lithuanian", "Lietuvių", False), "lv": ("Latvian", "Latviešu", False), "et": ("Estonian", "Eesti", False),
    "fi": ("Finnish", "Suomi", False), "sv": ("Swedish", "Svenska", False), "da": ("Danish", "Dansk", False),
    "nb": ("Norwegian (Bokmål)", "Norsk bokmål", False), "is": ("Icelandic", "Íslenska", False),
    "ca": ("Catalan", "Català", False), "eu": ("Basque", "Euskara", False), "gl": ("Galician", "Galego", False),
    "cy": ("Welsh", "Cymraeg", False), "mt": ("Maltese", "Malti", False), "ga": ("Irish", "Gaeilge", False),
    "ka": ("Georgian", "ქართული", False), "hy": ("Armenian", "Հայերեն", False), "az": ("Azerbaijani", "Azərbaycanca", False),
    "kk": ("Kazakh", "Қазақша", False), "uz": ("Uzbek", "Oʻzbekcha", False), "mn": ("Mongolian", "Монгол", False),
    "ps": ("Pashto", "پښتو", True), "so": ("Somali", "Soomaali", False), "jv": ("Javanese", "Basa Jawa", False),
    "su": ("Sundanese", "Basa Sunda", False), "mk": ("Macedonian", "Македонски", False), "sq": ("Albanian", "Shqip", False),
    "bs": ("Bosnian", "Bosanski", False), "iu": ("Inuktitut", "ᐃᓄᒃᑎᑐᑦ", False),
    "ha": ("Hausa", "Hausa", False), "yo": ("Yoruba", "Yorùbá", False), "tg": ("Tajik", "Тоҷикӣ", False),
    "ky": ("Kyrgyz", "Кыргызча", False), "be": ("Belarusian", "Беларуская", False),
}
RTL = frozenset(code for code, (_, _, rtl) in NAMES.items() if rtl)

# Languages with no edge voice that people ask about. The reason is the fact we checked; the alternative is a proposal, not a substitute.
NO_VOICE = {
    "eu": ("Basque: the service lists no eu voice", "none in edge-tts; a cloud TTS that covers Basque would be the route (not checked here). The Spanish voice must not read Basque text."),
    "pa": ("Punjabi: the service lists no pa voice", "none in edge-tts; closest sibling voices are Hindi (hi-IN) and Urdu (ur-PK) but they cannot read Gurmukhi/Shahmukhi text of the same language; use a cloud TTS."),
    "hy": ("Armenian: the service lists no hy voice", "none in edge-tts; a cloud TTS that covers Armenian would be the route (not checked here)."),
    "ha": ("Hausa: the service lists no ha voice", "none in edge-tts; no other edge voice reads Hausa."),
    "yo": ("Yoruba: the service lists no yo voice", "none in edge-tts; no other edge voice reads Yoruba."),
    "tg": ("Tajik: the service lists no tg voice", "none in edge-tts; Persian (fa-IR) is a related language but a different script and not a substitute."),
    "ky": ("Kyrgyz: the service lists no ky voice", "none in edge-tts; Kazakh (kk-KZ) is related, a separate language, not a substitute."),
    "be": ("Belarusian: the service lists no be voice", "none in edge-tts; Russian (ru-RU) and Ukrainian (uk-UA) are related, not substitutes."),
}
SKIPPED_EXTRAS = {"iu": "Inuktitut has edge voices (iu-Cans-CA, iu-Latn-CA) but no machine translator we trust for it: not generated, nothing faked."}

PRIMARY_LOCALE = {"en": "en-US", "es": "es-MX", "fr": "fr-FR", "de": "de-DE", "pt": "pt-BR", "ar": "ar-SA", "zh": "zh-CN",
                  "yue": "zh-HK", "ta": "ta-IN", "bn": "bn-BD", "ur": "ur-PK", "sw": "sw-KE", "nl": "nl-NL"}
PINNED = {  # the voices the adapter and the first listening sets already used
    "en": ("en-US-AvaNeural", "en-US-AndrewNeural"), "es": ("es-MX-DaliaNeural", "es-MX-JorgeNeural"),
    "zh": ("zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"), "yue": ("zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural"),
    "km": ("km-KH-SreymomNeural", "km-KH-PisethNeural"), "th": ("th-TH-PremwadeeNeural", "th-TH-NiwatNeural"),
    "vi": ("vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"), "sw": ("sw-KE-ZuriNeural", "sw-KE-RafikiNeural"),
    "hi": ("hi-IN-SwaraNeural", "hi-IN-MadhurNeural"),
}
RULE = ("pinned voice if we already used one; else the first voice of that gender, alphabetical by short name, in the primary "
        "locale (Multilingual voices only if nothing else exists)")


def load_voices(path: Path = SNAPSHOT) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["voices"]


def edge_language(code: str) -> str:
    return "zh-HK" if code == "yue" else code


def _voice_lang(voice: dict) -> str:
    return voice["locale"].split("-")[0]


def voices_for(code: str, voices: list[dict]) -> list[dict]:
    if code == "yue":
        return [v for v in voices if v["locale"] == "zh-HK"]
    return [v for v in voices if _voice_lang(v) == code and not (code == "zh" and v["locale"] == "zh-HK")]


def region_of(locale: str) -> str:
    parts = locale.split("-")
    return "-".join(p for p in parts[1:])


def _pick(voices: list[dict], gender: str, locale: str | None = None) -> str | None:
    pool = [v for v in voices if v["gender"] == gender and (locale is None or v["locale"] == locale)]
    plain = [v for v in pool if "Multilingual" not in v["name"]]
    pool = plain or pool
    return sorted(pool, key=lambda v: v["name"])[0]["name"] if pool else None


def primary_locale(code: str, voices: list[dict]) -> str | None:
    if not voices:
        return None
    wanted = PRIMARY_LOCALE.get(code)
    if wanted and any(v["locale"] == wanted for v in voices):
        return wanted
    counts: dict[str, int] = {}
    for v in voices:
        counts[v["locale"]] = counts.get(v["locale"], 0) + 1
    return sorted(counts, key=lambda loc: (-counts[loc], loc))[0]


def extra_codes(voices: list[dict]) -> list[str]:
    langs = {_voice_lang(v) for v in voices}
    extras = {c for c in langs if c not in PLATFORM and c not in SKIPPED_EXTRAS}
    return sorted(extras | {"yue"})


def derive(voices: list[dict]) -> dict:
    """Catalog: code -> entry. Platform languages first, then extras, then explicit 'no voice' entries."""
    out: dict[str, dict] = {}
    codes = list(PLATFORM) + extra_codes(voices) + sorted(NO_VOICE)
    for code in codes:
        english, native, rtl = NAMES[code]
        entry = {"code": code, "name": english, "native": native, "rtl": rtl, "platform": code in PLATFORM,
                 "edge_language": edge_language(code)}
        vs = voices_for(code, voices)
        if not vs:
            reason, alt = NO_VOICE.get(code, (f"{english}: the service lists no voice", ""))
            entry.update(status="no_voice", reason=reason, alternative=alt, default={"female": None, "male": None},
                         regions=[], voice_count=0, choice=RULE)
            out[code] = entry
            continue
        loc = primary_locale(code, vs)
        female, male = PINNED.get(code, (None, None))
        known = {v["name"] for v in vs}
        female = female if female in known else _pick(vs, "Female", loc) or _pick(vs, "Female")
        male = male if male in known else _pick(vs, "Male", loc) or _pick(vs, "Male")
        regions = []
        for locale in sorted({v["locale"] for v in vs}):
            lv = [v for v in vs if v["locale"] == locale]
            regions.append({"locale": locale, "region": region_of(locale), "female": _pick(lv, "Female"), "male": _pick(lv, "Male"),
                            "voices": sorted(v["name"] for v in lv)})
        entry.update(status="voice", reason="", alternative="", default={"female": female, "male": male}, primary_locale=loc,
                     regions=regions, voice_count=len(vs), choice=RULE)
        out[code] = entry
    return out


def load_catalog(path: Path = SNAPSHOT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["catalog"]
