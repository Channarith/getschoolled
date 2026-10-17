"""Offline travel-sign lexicon.

Lesson phrasebooks cover greetings, not doorway signs. This table answers
"what does that sign say?" when OCR (or a typed sign) matches a known phrase.
"""

from __future__ import annotations

from typing import Optional

# concept -> language -> phrase. Latin phrases are matched case-insensitively.
_SIGNS: dict[str, dict[str, str]] = {
    "exit": {
        "en": "exit", "es": "salida", "fr": "sortie", "de": "Ausgang",
        "it": "uscita", "pt": "saída", "zh": "出口", "ja": "出口", "ko": "출구",
        "ru": "выход", "ar": "مخرج", "th": "ทางออก", "vi": "lối ra", "hi": "निकास",
    },
    "entrance": {
        "en": "entrance", "es": "entrada", "fr": "entrée", "de": "Eingang",
        "it": "entrata", "pt": "entrada", "zh": "入口", "ja": "入口", "ko": "입구",
        "ru": "вход", "ar": "مدخل", "th": "ทางเข้า", "vi": "lối vào", "hi": "प्रवेश",
    },
    "stop": {
        "en": "stop", "es": "alto", "fr": "stop", "de": "stop", "it": "stop",
        "pt": "pare", "zh": "停", "ja": "止まれ", "ko": "정지", "ru": "стоп",
        "ar": "قف", "th": "หยุด", "vi": "dừng", "hi": "रुकें",
    },
    "open": {
        "en": "open", "es": "abierto", "fr": "ouvert", "de": "geöffnet",
        "it": "aperto", "pt": "aberto", "zh": "营业", "ja": "開店", "ko": "영업중",
        "ru": "открыто", "ar": "مفتوح", "th": "เปิด", "vi": "mở cửa", "hi": "खुला",
    },
    "closed": {
        "en": "closed", "es": "cerrado", "fr": "fermé", "de": "geschlossen",
        "it": "chiuso", "pt": "fechado", "zh": "关闭", "ja": "閉店", "ko": "휴무",
        "ru": "закрыто", "ar": "مغلق", "th": "ปิด", "vi": "đóng cửa", "hi": "बंद",
    },
    "danger": {
        "en": "danger", "es": "peligro", "fr": "danger", "de": "Gefahr",
        "it": "pericolo", "pt": "perigo", "zh": "危险", "ja": "危険", "ko": "위험",
        "ru": "опасность", "ar": "خطر", "th": "อันตราย", "vi": "nguy hiểm",
        "hi": "खतरा",
    },
    "caution": {
        "en": "caution", "es": "precaución", "fr": "attention", "de": "Vorsicht",
        "it": "attenzione", "pt": "cuidado", "zh": "小心", "ja": "注意", "ko": "주의",
        "ru": "осторожно", "ar": "احذر", "th": "ระวัง", "vi": "cẩn thận",
        "hi": "सावधानी",
    },
    "toilet": {
        "en": "toilet", "es": "baño", "fr": "toilettes", "de": "Toilette",
        "it": "bagno", "pt": "banheiro", "zh": "厕所", "ja": "トイレ", "ko": "화장실",
        "ru": "туалет", "ar": "مرحاض", "th": "ห้องน้ำ", "vi": "nhà vệ sinh",
        "hi": "शौचालय",
    },
    "men": {
        "en": "men", "es": "hombres", "fr": "hommes", "de": "Herren",
        "it": "uomini", "pt": "homens", "zh": "男", "ja": "男性", "ko": "남성",
        "ru": "мужчины", "ar": "رجال", "th": "ชาย", "vi": "nam", "hi": "पुरुष",
    },
    "women": {
        "en": "women", "es": "mujeres", "fr": "femmes", "de": "Damen",
        "it": "donne", "pt": "mulheres", "zh": "女", "ja": "女性", "ko": "여성",
        "ru": "женщины", "ar": "نساء", "th": "หญิง", "vi": "nữ", "hi": "महिला",
    },
    "pull": {
        "en": "pull", "es": "tirar", "fr": "tirer", "de": "ziehen",
        "it": "tirare", "pt": "puxar", "zh": "拉", "ja": "引く", "ko": "당기세요",
        "ru": "на себя", "ar": "اسحب", "th": "ดึง", "vi": "kéo", "hi": "खींचो",
    },
    "push": {
        "en": "push", "es": "empujar", "fr": "pousser", "de": "drücken",
        "it": "spingere", "pt": "empurre", "zh": "推", "ja": "押す", "ko": "미세요",
        "ru": "от себя", "ar": "ادفع", "th": "ผลัก", "vi": "đẩy", "hi": "धक्का",
    },
    "no entry": {
        "en": "no entry", "es": "prohibido el paso", "fr": "entrée interdite",
        "de": "kein Zutritt", "it": "divieto di accesso", "pt": "entrada proibida",
        "zh": "禁止入内", "ja": "進入禁止", "ko": "출입금지", "ru": "входа нет",
        "ar": "ممنوع الدخول", "th": "ห้ามเข้า", "vi": "cấm vào", "hi": "प्रवेश निषेध",
    },
    "taxi": {
        "en": "taxi", "es": "taxi", "fr": "taxi", "de": "Taxi", "it": "taxi",
        "pt": "táxi", "zh": "出租车", "ja": "タクシー", "ko": "택시", "ru": "такси",
        "ar": "تاكسي", "th": "แท็กซี่", "vi": "taxi", "hi": "टैक्सी",
    },
    "police": {
        "en": "police", "es": "policía", "fr": "police", "de": "Polizei",
        "it": "polizia", "pt": "polícia", "zh": "警察", "ja": "警察", "ko": "경찰",
        "ru": "полиция", "ar": "شرطة", "th": "ตำรวจ", "vi": "cảnh sát", "hi": "पुलिस",
    },
    "hospital": {
        "en": "hospital", "es": "hospital", "fr": "hôpital", "de": "Krankenhaus",
        "it": "ospedale", "pt": "hospital", "zh": "医院", "ja": "病院", "ko": "병원",
        "ru": "больница", "ar": "مستشفى", "th": "โรงพยาบาล", "vi": "bệnh viện",
        "hi": "अस्पताल",
    },
}


def _norm(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in (text or ""))
    return " ".join(cleaned.casefold().split())


def translate_sign(text: str, target: str, source: str = "auto") -> Optional[str]:
    """Translate a known sign into ``target``. Unknown signs return None."""
    needle = _norm(text)
    if not needle:
        return None
    target = (target or "en").split("-")[0].casefold()
    source = (source or "auto").split("-")[0].casefold()
    phrases: list[tuple[str, str, str]] = []
    for concept, langs in _SIGNS.items():
        for lang, phrase in langs.items():
            if source not in ("auto", lang):
                continue
            phrases.append((concept, lang, _norm(phrase)))
    phrases.sort(key=lambda item: len(item[2]), reverse=True)
    for concept, _lang, phrase in phrases:
        if phrase and phrase == needle:
            return _SIGNS[concept].get(target) or _SIGNS[concept].get("en")
    # A sign photo often includes extra words. Accept the longest known phrase
    # that appears inside the OCR line.
    for concept, _lang, phrase in phrases:
        if phrase and len(phrase) >= 3 and phrase in needle:
            return _SIGNS[concept].get(target) or _SIGNS[concept].get("en")
    return None
