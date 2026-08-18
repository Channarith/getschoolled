"""Language learning: 20+ languages with multi-skill, gamified practice.

Covers the platform's supported languages (see ``languages.SUPPORTED_LANGUAGES``)
with display names + a curated multilingual phrasebook, and builds interactive,
gamified exercises across many skill areas:

  pronunciation (audio + machine-vision mouth coaching), listening, reading,
  writing, vocabulary, grammar, slang, idioms, common phrases, travel,
  conversation - plus fun extras (shadowing, story mode, culture notes).

Pure/offline + stdlib only. Real ASR/TTS/translation and camera mouth-tracking are
provider-wired (speech/perception services); this module supplies the content,
exercise generation, and the scoring/heuristics that work offline so the whole
experience is testable and fun without GPUs.
"""

from __future__ import annotations

import difflib
import enum
import random
import re
import unicodedata
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel

from .languages import SUPPORTED_LANGUAGES


# --------------------------------------------------------------------------- #
# Languages (display metadata for every supported code).
# --------------------------------------------------------------------------- #
LANGUAGE_META: Dict[str, dict] = {
    "en": {"name": "English", "native": "English", "flag": "🇬🇧"},
    "es": {"name": "Spanish", "native": "Español", "flag": "🇪🇸"},
    "fr": {"name": "French", "native": "Français", "flag": "🇫🇷"},
    "de": {"name": "German", "native": "Deutsch", "flag": "🇩🇪"},
    "it": {"name": "Italian", "native": "Italiano", "flag": "🇮🇹"},
    "pt": {"name": "Portuguese", "native": "Português", "flag": "🇵🇹"},
    "nl": {"name": "Dutch", "native": "Nederlands", "flag": "🇳🇱"},
    "pl": {"name": "Polish", "native": "Polski", "flag": "🇵🇱"},
    "ru": {"name": "Russian", "native": "Русский", "flag": "🇷🇺"},
    "uk": {"name": "Ukrainian", "native": "Українська", "flag": "🇺🇦"},
    "tr": {"name": "Turkish", "native": "Türkçe", "flag": "🇹🇷"},
    "ar": {"name": "Arabic", "native": "العربية", "flag": "🇸🇦"},
    "he": {"name": "Hebrew", "native": "עברית", "flag": "🇮🇱"},
    "hi": {"name": "Hindi", "native": "हिन्दी", "flag": "🇮🇳"},
    "bn": {"name": "Bengali", "native": "বাংলা", "flag": "🇧🇩"},
    "ur": {"name": "Urdu", "native": "اردو", "flag": "🇵🇰"},
    "fa": {"name": "Persian", "native": "فارسی", "flag": "🇮🇷"},
    "zh": {"name": "Chinese (Mandarin)", "native": "中文", "flag": "🇨🇳"},
    "ja": {"name": "Japanese", "native": "日本語", "flag": "🇯🇵"},
    "ko": {"name": "Korean", "native": "한국어", "flag": "🇰🇷"},
    "vi": {"name": "Vietnamese", "native": "Tiếng Việt", "flag": "🇻🇳"},
    "th": {"name": "Thai", "native": "ไทย", "flag": "🇹🇭"},
    "id": {"name": "Indonesian", "native": "Bahasa Indonesia", "flag": "🇮🇩"},
    "sw": {"name": "Swahili", "native": "Kiswahili", "flag": "🇰🇪"},
    "el": {"name": "Greek", "native": "Ελληνικά", "flag": "🇬🇷"},
    "cs": {"name": "Czech", "native": "Čeština", "flag": "🇨🇿"},
    "km": {"name": "Khmer", "native": "\u1781\u17d2\u1798\u17c2\u179a", "flag": "\U0001f1f0\U0001f1ed"},
}


class SkillArea(str, enum.Enum):
    PRONUNCIATION = "pronunciation"
    LISTENING = "listening"
    READING = "reading"
    WRITING = "writing"
    VOCABULARY = "vocabulary"
    GRAMMAR = "grammar"
    SLANG = "slang"
    IDIOMS = "idioms"
    PHRASES = "phrases"
    TRAVEL = "travel"
    CONVERSATION = "conversation"
    CULTURE = "culture"
    SHADOWING = "shadowing"
    STORY = "story"


SKILL_AREAS = [
    {"id": "pronunciation", "name": "Pronunciation", "icon": "🗣️",
     "desc": "Say it out loud - audio + camera mouth-shape coaching scores you."},
    {"id": "listening", "name": "Listening", "icon": "👂",
     "desc": "Hear a phrase and pick what it means."},
    {"id": "vocabulary", "name": "Vocabulary", "icon": "📖",
     "desc": "Flashcard-style word/phrase recall."},
    {"id": "phrases", "name": "Common phrases", "icon": "💬",
     "desc": "Everyday useful expressions."},
    {"id": "travel", "name": "Travel", "icon": "✈️",
     "desc": "Survival phrases for trips."},
    {"id": "conversation", "name": "Conversation", "icon": "🗨️",
     "desc": "Useful sentences to chat with people."},
    {"id": "grammar", "name": "Grammar", "icon": "🧩",
     "desc": "Bite-size grammar tips + practice."},
    {"id": "reading", "name": "Reading", "icon": "📰",
     "desc": "Short passages + comprehension."},
    {"id": "writing", "name": "Writing", "icon": "✍️",
     "desc": "Type a response to a prompt."},
    {"id": "slang", "name": "Slang & idioms", "icon": "😎",
     "desc": "Understand casual, real-world speech."},
    {"id": "culture", "name": "Culture notes", "icon": "🌍",
     "desc": "Context that makes the language click."},
    {"id": "shadowing", "name": "Shadowing", "icon": "🔁",
     "desc": "Repeat right after the speaker to build fluency."},
    {"id": "story", "name": "Story mode", "icon": "📚",
     "desc": "Learn through a fun mini-story."},
    {"id": "songs", "name": "Learn through songs", "icon": "🎵",
     "desc": "Play one verse, understand it, then sing the whole song."},
    {"id": "media-listening", "name": "Catch words in media", "icon": "🎧",
     "desc": "Study 10 words, listen for 10 seconds, pause, and identify what you heard."},
    {"id": "music-video", "name": "Music video translate", "icon": "🎬",
     "desc": "Play one section, pause, and translate the gist — RAG scores meaning, not word-for-word."},
]


# --------------------------------------------------------------------------- #
# Curated phrasebook. Rich languages carry the full concept set; the rest carry
# a starter set (hello/thanks/yes/no) so EVERY supported language is practiceable.
# Values are (target, romanization); romanization "" for Latin scripts.
# --------------------------------------------------------------------------- #
_CONCEPTS = [
    ("hello", "phrases", "Hello"),
    ("goodbye", "phrases", "Goodbye"),
    ("thanks", "phrases", "Thank you"),
    ("please", "phrases", "Please"),
    ("yes", "phrases", "Yes"),
    ("no", "phrases", "No"),
    ("excuseme", "phrases", "Excuse me"),
    ("howareyou", "conversation", "How are you?"),
    ("myname", "conversation", "My name is..."),
    ("nicemeet", "conversation", "Nice to meet you"),
    ("bathroom", "travel", "Where is the bathroom?"),
    ("howmuch", "travel", "How much is this?"),
    ("help", "travel", "Help!"),
]

_T: Dict[str, Dict[str, tuple]] = {
    "en": {c[0]: (c[2], "") for c in _CONCEPTS},
    "es": {
        "hello": ("Hola", ""), "goodbye": ("Adiós", ""), "thanks": ("Gracias", ""),
        "please": ("Por favor", ""), "yes": ("Sí", ""), "no": ("No", ""),
        "excuseme": ("Perdón", ""), "howareyou": ("¿Cómo estás?", ""),
        "myname": ("Me llamo...", ""), "nicemeet": ("Mucho gusto", ""),
        "bathroom": ("¿Dónde está el baño?", ""), "howmuch": ("¿Cuánto cuesta?", ""),
        "help": ("¡Ayuda!", ""),
    },
    "fr": {
        "hello": ("Bonjour", ""), "goodbye": ("Au revoir", ""), "thanks": ("Merci", ""),
        "please": ("S'il vous plaît", ""), "yes": ("Oui", ""), "no": ("Non", ""),
        "excuseme": ("Excusez-moi", ""), "howareyou": ("Comment allez-vous ?", ""),
        "myname": ("Je m'appelle...", ""), "nicemeet": ("Enchanté", ""),
        "bathroom": ("Où sont les toilettes ?", ""), "howmuch": ("Combien ça coûte ?", ""),
        "help": ("Au secours !", ""),
    },
    "de": {
        "hello": ("Hallo", ""), "goodbye": ("Auf Wiedersehen", ""), "thanks": ("Danke", ""),
        "please": ("Bitte", ""), "yes": ("Ja", ""), "no": ("Nein", ""),
        "excuseme": ("Entschuldigung", ""), "howareyou": ("Wie geht es dir?", ""),
        "myname": ("Ich heiße...", ""), "nicemeet": ("Freut mich", ""),
        "bathroom": ("Wo ist die Toilette?", ""), "howmuch": ("Wie viel kostet das?", ""),
        "help": ("Hilfe!", ""),
    },
    "it": {
        "hello": ("Ciao", ""), "goodbye": ("Arrivederci", ""), "thanks": ("Grazie", ""),
        "please": ("Per favore", ""), "yes": ("Sì", ""), "no": ("No", ""),
        "excuseme": ("Scusi", ""), "howareyou": ("Come stai?", ""),
        "myname": ("Mi chiamo...", ""), "nicemeet": ("Piacere", ""),
        "bathroom": ("Dov'è il bagno?", ""), "howmuch": ("Quanto costa?", ""),
        "help": ("Aiuto!", ""),
    },
    "pt": {
        "hello": ("Olá", ""), "goodbye": ("Adeus", ""), "thanks": ("Obrigado", ""),
        "please": ("Por favor", ""), "yes": ("Sim", ""), "no": ("Não", ""),
        "excuseme": ("Com licença", ""), "howareyou": ("Como vai?", ""),
        "myname": ("Meu nome é...", ""), "nicemeet": ("Prazer", ""),
        "bathroom": ("Onde fica o banheiro?", ""), "howmuch": ("Quanto custa?", ""),
        "help": ("Socorro!", ""),
    },
    "nl": {
        "hello": ("Hallo", ""), "goodbye": ("Tot ziens", ""), "thanks": ("Dank je", ""),
        "please": ("Alsjeblieft", ""), "yes": ("Ja", ""), "no": ("Nee", ""),
        "excuseme": ("Pardon", ""), "howareyou": ("Hoe gaat het?", ""),
        "myname": ("Ik heet...", ""), "nicemeet": ("Aangenaam", ""),
        "bathroom": ("Waar is het toilet?", ""), "howmuch": ("Hoeveel kost dit?", ""),
        "help": ("Help!", ""),
    },
    "ja": {
        "hello": ("こんにちは", "Konnichiwa"), "goodbye": ("さようなら", "Sayōnara"),
        "thanks": ("ありがとう", "Arigatō"), "please": ("お願いします", "Onegaishimasu"),
        "yes": ("はい", "Hai"), "no": ("いいえ", "Iie"), "excuseme": ("すみません", "Sumimasen"),
        "howareyou": ("お元気ですか", "Ogenki desu ka"), "myname": ("私の名前は…", "Watashi no namae wa…"),
        "nicemeet": ("はじめまして", "Hajimemashite"), "bathroom": ("トイレはどこですか", "Toire wa doko desu ka"),
        "howmuch": ("いくらですか", "Ikura desu ka"), "help": ("助けて", "Tasukete"),
    },
    "zh": {
        "hello": ("你好", "Nǐ hǎo"), "goodbye": ("再见", "Zàijiàn"), "thanks": ("谢谢", "Xièxiè"),
        "please": ("请", "Qǐng"), "yes": ("是", "Shì"), "no": ("不", "Bù"),
        "excuseme": ("对不起", "Duìbùqǐ"), "howareyou": ("你好吗", "Nǐ hǎo ma"),
        "myname": ("我叫…", "Wǒ jiào…"), "nicemeet": ("很高兴认识你", "Hěn gāoxìng rènshì nǐ"),
        "bathroom": ("厕所在哪里", "Cèsuǒ zài nǎlǐ"), "howmuch": ("这个多少钱", "Zhège duōshǎo qián"),
        "help": ("救命", "Jiùmìng"),
    },
    "ko": {
        "hello": ("안녕하세요", "Annyeonghaseyo"), "goodbye": ("안녕히 가세요", "Annyeonghi gaseyo"),
        "thanks": ("감사합니다", "Gamsahamnida"), "please": ("주세요", "Juseyo"),
        "yes": ("네", "Ne"), "no": ("아니요", "Aniyo"), "excuseme": ("실례합니다", "Sillyehamnida"),
        "howareyou": ("어떻게 지내세요", "Eotteoke jinaeseyo"), "myname": ("제 이름은…", "Je ireumeun…"),
        "nicemeet": ("만나서 반갑습니다", "Mannaseo bangapseumnida"),
        "bathroom": ("화장실이 어디예요", "Hwajangsiri eodiyeyo"),
        "howmuch": ("이거 얼마예요", "Igeo eolmayeyo"), "help": ("도와주세요", "Dowajuseyo"),
    },
    # Starter sets (hello/thanks/yes/no) so every supported language is practiceable.
    "pl": {"hello": ("Cześć", ""), "thanks": ("Dziękuję", ""), "yes": ("Tak", ""), "no": ("Nie", "")},
    "ru": {"hello": ("Привет", "Privet"), "thanks": ("Спасибо", "Spasibo"), "yes": ("Да", "Da"), "no": ("Нет", "Net")},
    "uk": {"hello": ("Привіт", "Pryvit"), "thanks": ("Дякую", "Dyakuyu"), "yes": ("Так", "Tak"), "no": ("Ні", "Ni")},
    "tr": {"hello": ("Merhaba", ""), "thanks": ("Teşekkürler", ""), "yes": ("Evet", ""), "no": ("Hayır", "")},
    "ar": {"hello": ("مرحبا", "Marhaba"), "thanks": ("شكرا", "Shukran"), "yes": ("نعم", "Na'am"), "no": ("لا", "La")},
    "he": {"hello": ("שלום", "Shalom"), "thanks": ("תודה", "Toda"), "yes": ("כן", "Ken"), "no": ("לא", "Lo")},
    "hi": {"hello": ("नमस्ते", "Namaste"), "thanks": ("धन्यवाद", "Dhanyavaad"), "yes": ("हाँ", "Haan"), "no": ("नहीं", "Nahin")},
    "bn": {"hello": ("নমস্কার", "Nomoshkar"), "thanks": ("ধন্যবাদ", "Dhonnobad"), "yes": ("হ্যাঁ", "Hyan"), "no": ("না", "Na")},
    "ur": {"hello": ("السلام علیکم", "Assalam-o-alaikum"), "thanks": ("شکریہ", "Shukriya"), "yes": ("جی ہاں", "Ji haan"), "no": ("نہیں", "Nahin")},
    "fa": {"hello": ("سلام", "Salaam"), "thanks": ("ممنون", "Mamnoon"), "yes": ("بله", "Baleh"), "no": ("نه", "Na")},
    "vi": {"hello": ("Xin chào", ""), "thanks": ("Cảm ơn", ""), "yes": ("Vâng", ""), "no": ("Không", "")},
    "th": {"hello": ("สวัสดี", "Sawasdee"), "thanks": ("ขอบคุณ", "Khop khun"), "yes": ("ใช่", "Chai"), "no": ("ไม่", "Mai")},
    "id": {"hello": ("Halo", ""), "thanks": ("Terima kasih", ""), "yes": ("Ya", ""), "no": ("Tidak", "")},
    "sw": {"hello": ("Jambo", ""), "thanks": ("Asante", ""), "yes": ("Ndiyo", ""), "no": ("Hapana", "")},
    "el": {"hello": ("Γεια σας", "Yia sas"), "thanks": ("Ευχαριστώ", "Efcharistó"), "yes": ("Ναι", "Nai"), "no": ("Όχι", "Ohi")},
    "cs": {"hello": ("Ahoj", ""), "thanks": ("Děkuji", ""), "yes": ("Ano", ""), "no": ("Ne", "")},
    # Khmer (km) is a rich language because the platform brand "Salareen"
    # derives from the Khmer word for school (sala-rian); Khmer must be
    # first-class. Romanization uses the loose ALA-LC style commonly seen
    # in Phnom Penh phrasebooks (not strict IPA).
    "km": {
        "hello":     ("\u1787\u17c6\u179a\u17b6\u1794\u179f\u17bd\u179a", "Chum reap suor"),
        "goodbye":   ("\u1787\u17c6\u179a\u17b6\u1794\u179b\u17b6", "Chum reap lear"),
        "thanks":    ("\u17a2\u179a\u1782\u17bb\u178e", "Aw kohn"),
        "please":    ("\u179f\u17bc\u1798", "Som"),
        "yes":       ("\u1794\u17b6\u1791/\u1785\u17b6\u179f", "Baat / Chas"),
        "no":        ("\u1791\u17c1", "Te"),
        "excuseme":  ("\u179f\u17bc\u1798\u1791\u17c4\u179f", "Som tos"),
        "howareyou": ("\u179f\u17bb\u1781\u179f\u1794\u17d2\u1794\u17b6\u1799\u1791\u17c1?", "Sok sabbai te?"),
        "myname":    ("\u1781\u17d2\u1789\u17bb\u17c6\u1788\u17d2\u1798\u17c4\u17c7\u2026", "Khnyom chhmuah…"),
        "nicemeet":  ("\u179a\u17b8\u1780\u179a\u17b6\u1799\u178e\u17b6\u179f\u17cd\u1787\u17bd\u1794\u17a2\u17d2\u1793\u1780", "Rikreay nas chuob anak"),
        "bathroom":  ("\u1794\u1793\u17d2\u1791\u1794\u17cb\u1791\u17b9\u1780\u1793\u17c5\u17af\u178e\u17b6?", "Bantob tuek neuv aenah?"),
        "howmuch":   ("\u1798\u17bd\u1799\u1793\u17c1\u17c7\u178f\u1798\u17d2\u179b\u17c3\u1794\u17bb\u1793\u17d2\u1798\u17b6\u1793?", "Muoy nih tamlay ponman?"),
        "help":      ("\u1787\u17bd\u1799\u1781\u17d2\u1789\u17bb\u17c6\u1795\u1784!", "Chuoy khnyom phong!"),
    },
}

# Every supported language now exposes the complete learning path. Content packs
# grow phrase, dialogue, slang and song depth without another code release.
RICH_LANGUAGES = set(SUPPORTED_LANGUAGES)

# Bite-size grammar tips + culture notes for the rich languages.
_GRAMMAR_TIPS: Dict[str, str] = {
    "es": "Nouns have gender: el (m) / la (f). Adjectives agree: gato negro, casa blanca.",
    "fr": "Articles carry gender: le/la/les. Most adjectives follow the noun.",
    "de": "Nouns are capitalized and have 3 genders (der/die/das) and 4 cases.",
    "it": "Verbs conjugate by person; drop the subject pronoun (parlo = I speak).",
    "pt": "Two 'to be' verbs: ser (permanent) vs estar (temporary).",
    "nl": "Word order: the verb goes second in main clauses (V2).",
    "ja": "Sentence order is Subject-Object-Verb; particles (は, を, が) mark roles.",
    "zh": "No verb conjugation or plurals; tone changes meaning (mā/má/mǎ/mà).",
    "ko": "Subject-Object-Verb order; politeness levels change verb endings.",
    "en": "Word order is Subject-Verb-Object; add -s for plurals and 3rd person.",
    "km": "Khmer has no tones and no verb conjugation; meaning comes from word "
          "order (Subject-Verb-Object) and politeness particles like \u1794\u17b6\u1791 "
          "(baat, men) / \u1785\u17b6\u179f (chas, women).",
}
_CULTURE_NOTES: Dict[str, str] = {
    "es": "A friendly greeting is often two cheek kisses in Spain, a handshake in much of Latin America.",
    "fr": "Always greet with 'Bonjour' before asking anything - it's considered polite.",
    "de": "Punctuality matters; arriving on time is a sign of respect.",
    "it": "Cappuccino is a morning drink - ordering one after lunch is unusual.",
    "pt": "In Brazil, people stand close and are warm; small talk is welcome.",
    "nl": "Directness is valued and not seen as rude - it's honesty.",
    "ja": "Bowing shows respect; removing shoes indoors is expected.",
    "zh": "Offer and receive items (and business cards) with both hands.",
    "ko": "Use two hands when giving/receiving, especially with elders.",
    "en": "Small talk about the weather is a common, friendly icebreaker.",
    "km": "Greet with the sampeah - palms together, fingertips at chest "
          "height - and say 'chum reap suor'. Show respect with two hands "
          "when offering or receiving.",
}

LEARNING_TIPS = [
    "Practice a little every day - streaks beat cramming.",
    "Say words out loud; your mouth needs reps too.",
    "Learn phrases, not just words - context sticks better.",
    "Don't fear mistakes; they're how you improve.",
    "Label things around your home in the target language.",
]


# --------------------------------------------------------------------------- #
# Catalog / course
# --------------------------------------------------------------------------- #
def language_list() -> List[dict]:
    """All supported languages with display metadata + content tier."""
    out = []
    for code in SUPPORTED_LANGUAGES:
        meta = LANGUAGE_META.get(code, {"name": code, "native": code, "flag": "🏳️"})
        out.append({
            "code": code, **meta,
            "tier": "full",
            "phrase_count": len(phrases_for(code)),
            "vocabulary_count": len(vocabulary_for(code)),
            "dialogue_count": len(dialogues_for(code)),
            "slang_count": slang_count(code),
            "song_count": len(songs_for(code)),
        })
    return out


def vocabulary_for(language: str, category: Optional[str] = None) -> List[dict]:
    """Curated single-word vocabulary from extensible content packs."""
    try:
        from .content_packs import load_records
    except Exception:  # pragma: no cover - packs are optional
        return []

    out: List[dict] = []
    seen_ids = set()
    seen_targets = set()
    for rec in load_records("vocabulary"):
        if rec.get("language") != language or not rec.get("id"):
            continue
        item_category = str(rec.get("category", "core"))
        if category and item_category != category:
            continue
        item_id = str(rec["id"])
        target = str(rec.get("target", "")).strip()
        english = str(rec.get("en", "")).strip()
        if not target or not english or item_id in seen_ids or target in seen_targets:
            continue
        out.append({
            "id": item_id,
            "category": item_category,
            "en": english,
            "target": target,
            "roman": str(rec.get("roman", "")).strip(),
        })
        seen_ids.add(item_id)
        seen_targets.add(target)
    return out


def phrases_for(language: str, category: Optional[str] = None) -> List[dict]:
    table = _T.get(language, {})
    out = []
    for cid, cat, en in _CONCEPTS:
        if category and cat != category:
            continue
        if cid not in table:
            continue
        target, roman = table[cid]
        out.append({"id": cid, "category": cat, "en": en, "target": target, "roman": roman})
    try:
        from .content_packs import load_records

        seen = {p["id"] for p in out}
        for rec in load_records("phrases"):
            if rec.get("language") != language or not rec.get("id"):
                continue
            if category and rec.get("category", "phrases") != category:
                continue
            if rec["id"] in seen:
                continue
            out.append({
                "id": str(rec["id"]),
                "category": str(rec.get("category", "phrases")),
                "en": str(rec.get("en", "")),
                "target": str(rec.get("target", "")),
                "roman": str(rec.get("roman", "")),
            })
            seen.add(rec["id"])
    except Exception:  # pragma: no cover - packs are optional
        pass
    return out


def dialogues_for(language: str) -> List[dict]:
    """Structured real-world conversations for a language.

    Curated packs win. Until a language-specific dialogue pack lands, build 20
    short drills from that language's verified phrasebook so no course is a
    four-button dead end.
    """
    try:
        from .content_packs import load_records

        curated = [
            dict(rec) for rec in load_records("dialogues")
            if rec.get("language") == language and rec.get("turns")
        ]
    except Exception:  # pragma: no cover
        curated = []
    if curated:
        return curated

    phrases = phrases_for(language)
    if not phrases:
        return []
    situations = [
        "Meeting someone", "Saying goodbye", "Being polite", "Checking in",
        "Introducing yourself", "At a café", "At a restaurant", "At a market",
        "Asking the price", "Finding the bathroom", "Asking for help",
        "At a hotel", "Taking a taxi", "At the station", "Shopping",
        "Making a friend", "Clarifying", "Thanking someone", "Saying no politely",
        "Ending a conversation",
    ]
    rows: List[dict] = []
    for i, situation in enumerate(situations):
        first = phrases[i % len(phrases)]
        second = phrases[(i + 1) % len(phrases)]
        rows.append({
            "language": language,
            "id": f"practice-{i + 1:02d}",
            "situation_en": situation,
            "turns": [
                {"speaker": "A", "target": first["target"], "roman": first["roman"], "en": first["en"]},
                {"speaker": "B", "target": second["target"], "roman": second["roman"], "en": second["en"]},
            ],
        })
    return rows


def slang_count(language: str) -> int:
    from .slang import all_entries

    return sum(1 for entry in all_entries() if entry.language == language)


def songs_for(language: str) -> List[dict]:
    """Return licensed/original learn-through-song lessons.

    A small original call-and-response song is generated from each phrasebook
    when no curated song exists. This keeps all languages song-enabled without
    embedding copyrighted recordings or lyrics.
    """
    try:
        from .content_packs import load_records

        curated = [
            dict(rec) for rec in load_records("songs")
            if rec.get("language") == language and rec.get("verses")
        ]
    except Exception:  # pragma: no cover
        curated = []
    if curated:
        return curated

    phrases = phrases_for(language)
    if not phrases:
        return []
    verses = []
    for i, phrase in enumerate(phrases[:4], start=1):
        verses.append({
            "verse_no": i,
            "target": phrase["target"],
            "roman": phrase["roman"],
            "en": phrase["en"],
            "explain_en": (
                f"This verse practices “{phrase['en']}”. Listen, pause, and "
                "repeat with the same rhythm."
            ),
            "tts_text": f"{phrase['target']}. {phrase['target']}.",
        })
    return [{
        "language": language,
        "song_id": f"{language}-everyday-phrases-song",
        "title_en": f"{LANGUAGE_META.get(language, {}).get('name', language)} Everyday Phrases Song",
        "license": "original-salareen",
        "source_url": "",
        "verses": verses,
    }]


def media_listening_challenge(
    language: str, *, study_size: int = 10, seed: Optional[int] = None
) -> dict:
    """Build a timed listen-pause-identify challenge from known vocabulary.

    Each segment is exactly ten seconds in the player. Bundled challenges use
    original TTS audio; the same schema accepts a licensed ``media_url`` for
    real audio/video packs without changing either client.
    """
    size = max(2, min(study_size, 10))
    pool = vocabulary_for(language)
    if len(pool) < size:
        pool = phrases_for(language)
    rng = random.Random(seed)
    study_words = list(pool)
    rng.shuffle(study_words)
    study_words = study_words[:size]
    segments = []
    for index, word in enumerate(study_words):
        options = [
            {
                "id": item["id"],
                "target": item["target"],
                "roman": item.get("roman", ""),
                "en": item["en"],
            }
            for item in study_words
        ]
        rng.shuffle(options)
        segments.append({
            "id": f"clip-{index + 1:02d}",
            "start_sec": index * 10,
            "end_sec": (index + 1) * 10,
            "duration_sec": 10,
            "tts_text": f"{word['target']}. {word['target']}.",
            "question": (
                f"Which vocabulary word did you hear during seconds "
                f"{index * 10}–{(index + 1) * 10}?"
            ),
            "options": options,
            "answer_id": word["id"],
        })
    return {
        "skill": "media-listening",
        "language": language,
        "title": "Ten-second vocabulary listening challenge",
        "instructions": (
            "Study the 10 words. Play one ten-second clip, let it pause, "
            "identify the word you heard, then continue."
        ),
        "media_type": "generated_audio",
        "media_url": "",
        "license": "original-salareen",
        "study_words": study_words,
        "segments": segments,
    }


def _annotate_story_text(text: str, words: List[dict]) -> List[dict]:
    """Split story text into display runs, linking known vocabulary words."""
    runs: List[dict] = []
    cursor = 0
    candidates = sorted(words, key=lambda word: len(word["target"]), reverse=True)
    while cursor < len(text):
        matches = [
            (text.find(word["target"], cursor), word)
            for word in candidates
            if text.find(word["target"], cursor) >= 0
        ]
        if not matches:
            runs.append({"text": text[cursor:]})
            break
        start, word = min(matches, key=lambda match: (match[0], -len(match[1]["target"])))
        if start > cursor:
            runs.append({"text": text[cursor:start]})
        end = start + len(word["target"])
        runs.append({
            "text": text[start:end],
            "word_id": word["id"],
            "target": word["target"],
            "roman": word.get("roman", ""),
            "en": word["en"],
        })
        cursor = end
    return runs


def reading_story(language: str) -> dict:
    """A short three-page reader with clickable vocabulary annotations."""
    vocabulary = vocabulary_for(language)
    if not vocabulary:
        vocabulary = phrases_for(language)
    by_english = {word["en"].lower(): word for word in vocabulary}

    if language == "km":
        requested = [
            "morning", "student", "road", "school", "notebook", "pen",
            "teacher", "friend", "read", "question", "evening", "home",
            "family", "food", "water",
        ]
        words = [by_english[key] for key in requested if key in by_english]
        page_specs = [
            (
                "A new morning",
                "ព្រឹកនេះ សិស្ស ម្នាក់ដើរតាម ផ្លូវ ទៅ សាលា។ "
                "គាត់កាន់ សៀវភៅសរសេរ និង ប៊ិច។ នៅមុខសាលា គ្រូ "
                "ឈររង់ចាំសិស្ស។",
                "This morning, a student walks along the road to school. "
                "The student carries a notebook and pen. A teacher waits "
                "for the students in front of the school.",
            ),
            (
                "The short story",
                "នៅក្នុង សាលា គ្រូ បើក សៀវភៅសរសេរ។ សិស្ស និង មិត្ត "
                "អាន រឿងខ្លី។ មិត្ត សួរ សំណួរ ហើយគ្រូពន្យល់ពាក្យថ្មី។",
                "Inside the school, the teacher opens a notebook. The student "
                "and a friend read a short story. The friend asks a question, "
                "and the teacher explains the new word.",
            ),
            (
                "Sharing at home",
                "ពេល ល្ងាច សិស្ស ត្រឡប់ទៅ ផ្ទះ។ គាត់ប្រាប់ គ្រួសារ "
                "អំពីរឿងដែលបាន អាន។ ពួកគេញ៉ាំ អាហារ និងផឹក ទឹក ជាមួយគ្នា។",
                "In the evening, the student returns home and tells the family "
                "about the story. They eat food and drink water together.",
            ),
        ]
        title = "A Student’s New Word"
    else:
        words = vocabulary[:12]
        page_specs = []
        for page_index in range(3):
            page_words = words[page_index * 4:(page_index + 1) * 4]
            target_text = "។ ".join(word["target"] for word in page_words) + "។"
            english_text = ". ".join(word["en"] for word in page_words) + "."
            page_specs.append((
                f"Word journey {page_index + 1}",
                target_text,
                english_text,
            ))
        title = "A Three-Page Word Journey"

    pages = [
        {
            "page_number": index,
            "title": page_title,
            "text": target_text,
            "translation_en": translation,
            "runs": _annotate_story_text(target_text, words),
        }
        for index, (page_title, target_text, translation) in enumerate(page_specs, 1)
    ]
    return {
        "skill": "reading",
        "language": language,
        "story_id": f"{language}-three-page-reader",
        "title": title,
        "instructions": (
            "Read one page at a time. Tap any highlighted word you do not "
            "understand and the AI Word Coach will explain it before you continue."
        ),
        "page_count": 3,
        "pages": pages,
    }


def explain_story_word(language: str, word_id: str) -> dict:
    """Explain a clicked reading word with context and clear examples."""
    vocabulary = vocabulary_for(language) or phrases_for(language)
    word = next((item for item in vocabulary if item["id"] == word_id), None)
    if word is None:
        return {
            "found": False,
            "language": language,
            "word_id": word_id,
            "explanation": "This word is not in the current vocabulary pack yet.",
            "examples": [],
        }
    story = reading_story(language)
    examples = []
    for page in story["pages"]:
        if any(run.get("word_id") == word_id for run in page["runs"]):
            examples.append({
                "page": page["page_number"],
                "target": page["text"],
                "en": page["translation_en"],
            })
    return {
        "found": True,
        "language": language,
        "word_id": word_id,
        "target": word["target"],
        "roman": word.get("roman", ""),
        "meaning": word["en"],
        "category": word.get("category", "core"),
        "explanation": (
            f"“{word['target']}” means “{word['en']}”. "
            f"It is used here as a {word.get('category', 'core').replace('_', ' ')} word."
        ),
        "pronunciation_tip": (
            f"Say it slowly as {word.get('roman') or word['target']}, then read "
            "the complete sentence once more."
        ),
        "examples": examples[:2],
    }


def music_videos_for(language: str) -> List[dict]:
    """Return licensed/original music-video translation lessons.

    Curated packs may include a real ``media_url``. When none exist, song verses
    are promoted into a section-by-section music-video challenge with TTS audio
    so every language stays practiceable without copyrighted commercial tracks.
    """
    try:
        from .content_packs import load_records

        curated = [
            dict(rec) for rec in load_records("music_videos")
            if rec.get("language") == language and rec.get("sections")
        ]
    except Exception:  # pragma: no cover
        curated = []
    if curated:
        return curated

    songs = songs_for(language)
    if not songs:
        return []
    out = []
    for song in songs:
        sections = []
        cursor = 0
        for verse in song.get("verses") or []:
            duration = 12
            sections.append({
                "section_no": int(verse.get("verse_no") or (len(sections) + 1)),
                "start_sec": cursor,
                "end_sec": cursor + duration,
                "duration_sec": duration,
                "target": verse.get("target", ""),
                "roman": verse.get("roman", ""),
                "en": verse.get("en", ""),
                "explain_en": verse.get("explain_en", ""),
                "tts_text": verse.get("tts_text") or verse.get("target", ""),
                "paraphrases_en": [],
            })
            cursor += duration
        out.append({
            "language": language,
            "video_id": f"{song.get('song_id', language)}-music-video",
            "title_en": f"{song.get('title_en', 'Learning song')} (music video)",
            "title_target": song.get("title_target", ""),
            "license": song.get("license", "original-salareen"),
            "media_type": "generated_audio",
            "media_url": "",
            "source_url": song.get("source_url", ""),
            "source_note": song.get("source_note", ""),
            "sections": sections,
        })
    return out


def music_video_challenge(language: str, *, video_id: Optional[str] = None) -> dict:
    """Build a play-section / pause / translate-the-gist challenge."""
    videos = music_videos_for(language)
    if not videos:
        return {
            "skill": "music-video",
            "language": language,
            "video_id": "",
            "title": "Music video translate",
            "instructions": "No music-video lesson is available for this language yet.",
            "media_type": "generated_audio",
            "media_url": "",
            "license": "original-salareen",
            "sections": [],
        }
    video = next((v for v in videos if v.get("video_id") == video_id), videos[0])
    sections = []
    for index, raw in enumerate(video.get("sections") or []):
        duration = int(raw.get("duration_sec") or max(1, int(raw.get("end_sec", 0)) - int(raw.get("start_sec", 0))) or 12)
        start = int(raw.get("start_sec", index * duration))
        end = int(raw.get("end_sec", start + duration))
        sections.append({
            "id": f"sec-{index + 1:02d}",
            "section_no": int(raw.get("section_no") or (index + 1)),
            "start_sec": start,
            "end_sec": end,
            "duration_sec": duration,
            "target": raw.get("target", ""),
            "roman": raw.get("roman", ""),
            "tts_text": raw.get("tts_text") or raw.get("target", ""),
            "prompt": (
                "Pause the video. In English, translate the gist of this section — "
                "you do not need every word, just the meaning."
            ),
            # Kept for scoring + post-attempt reveal (same honesty model as MCQ keys).
            "en": raw.get("en", ""),
            "explain_en": raw.get("explain_en", ""),
            "paraphrases_en": list(raw.get("paraphrases_en") or []),
        })
    return {
        "skill": "music-video",
        "language": language,
        "video_id": video.get("video_id", ""),
        "title": video.get("title_en") or "Music video translate",
        "title_target": video.get("title_target", ""),
        "instructions": (
            "Play one section of the music video, pause, and translate the meaning. "
            "RAG checks that you got the gist — not a word-for-word match. "
            "Earn a point for each correct section, then continue to the end."
        ),
        "media_type": video.get("media_type") or ("video" if video.get("media_url") else "generated_audio"),
        "media_url": video.get("media_url", ""),
        "license": video.get("license", "original-salareen"),
        "source_url": video.get("source_url", ""),
        "source_note": video.get("source_note", ""),
        "sections": sections,
    }


_GIST_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "to", "of", "in", "on", "at", "for",
    "is", "are", "was", "were", "be", "been", "it", "this", "that", "with",
    "from", "as", "by", "you", "your", "me", "my", "we", "our", "they", "their",
    "i", "am", "do", "does", "did", "not", "no", "yes", "very", "please",
})


def _content_tokens(text: str) -> List[str]:
    return [
        tok for tok in _normalize(text).split()
        if tok and tok not in _GIST_STOPWORDS and len(tok) > 1
    ]


def _music_video_rag_corpus(
    *,
    reference_en: str,
    explain_en: str = "",
    paraphrases_en: Optional[List[str]] = None,
    language: str = "",
) -> List[str]:
    """Build a small retrieval corpus for gist scoring.

    Passages come from the section meaning, explanation, curated paraphrases, and
    related phrasebook/vocabulary English glosses that share content words with
    the reference — a lightweight RAG index without an external vector DB.
    """
    corpus: List[str] = []
    for text in [reference_en, explain_en, *(paraphrases_en or [])]:
        cleaned = (text or "").strip()
        if cleaned and cleaned not in corpus:
            corpus.append(cleaned)
    ref_tokens = set(_content_tokens(reference_en))
    if language and ref_tokens:
        related: List[str] = []
        for row in phrases_for(language) + vocabulary_for(language):
            gloss = (row.get("en") or "").strip()
            if not gloss:
                continue
            if set(_content_tokens(gloss)) & ref_tokens:
                related.append(gloss)
        # Keep the index small and relevant.
        for gloss in related[:12]:
            if gloss not in corpus:
                corpus.append(gloss)
    return corpus or [reference_en or ""]


def _retrieve_rag_passages(query: str, corpus: List[str], *, top_k: int = 5) -> List[str]:
    """Rank corpus passages by Jaccard overlap with the learner translation."""
    qtoks = set(_content_tokens(query))
    if not corpus:
        return []
    ranked = []
    for passage in corpus:
        ptoks = set(_content_tokens(passage))
        if not ptoks and not qtoks:
            score = 1.0 if _normalize(query) == _normalize(passage) else 0.0
        else:
            union = qtoks | ptoks
            score = (len(qtoks & ptoks) / len(union)) if union else 0.0
            # Soft boost for sequence similarity so near-paraphrases still rank.
            score = 0.65 * score + 0.35 * difflib.SequenceMatcher(
                None, _normalize(query), _normalize(passage)
            ).ratio()
        ranked.append((score, passage))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [passage for _, passage in ranked[: max(1, top_k)]]


def assess_translation_gist(
    reference_en: str,
    translation: str,
    *,
    explain_en: str = "",
    paraphrases_en: Optional[List[str]] = None,
    language: str = "",
) -> dict:
    """Score a free-text translation for gist, not word-for-word accuracy.

    Uses a tiny RAG retrieve-then-score loop: retrieve the best-matching meaning
    passages, then blend sequence similarity with content-word coverage so
    paraphrases still earn the point.
    """
    reference = (reference_en or "").strip()
    attempt = (translation or "").strip()
    corpus = _music_video_rag_corpus(
        reference_en=reference,
        explain_en=explain_en,
        paraphrases_en=paraphrases_en,
        language=language,
    )
    retrieved = _retrieve_rag_passages(attempt, corpus, top_k=5)
    if reference and reference not in retrieved:
        retrieved = [reference] + retrieved

    best_sim = 0.0
    best_passage = reference
    for passage in retrieved or [reference]:
        sim = difflib.SequenceMatcher(
            None, _normalize(attempt), _normalize(passage)
        ).ratio() if attempt and passage else 0.0
        if sim >= best_sim:
            best_sim = sim
            best_passage = passage

    ref_toks = set(_content_tokens(reference))
    hyp_toks = set(_content_tokens(attempt))
    # Also credit tokens matched against the best retrieved paraphrase.
    best_toks = set(_content_tokens(best_passage))
    coverage_ref = (len(ref_toks & hyp_toks) / len(ref_toks)) if ref_toks else 0.0
    coverage_best = (len(best_toks & hyp_toks) / len(best_toks)) if best_toks else 0.0
    coverage = max(coverage_ref, coverage_best)

    score = round(100 * (0.4 * best_sim + 0.6 * coverage))
    passed = bool(attempt) and (
        score >= 45
        or coverage >= 0.45
        or (coverage >= 0.3 and best_sim >= 0.35)
        or best_sim >= 0.55
    )
    stars = 3 if score >= 80 else 2 if score >= 60 else 1 if passed else 0
    if not attempt:
        feedback = "Type what you understood — the gist is enough."
    elif passed and score >= 80:
        feedback = "Excellent gist — you clearly got the meaning. +1 point"
    elif passed:
        feedback = "Nice! You caught the meaning (not every word is required). +1 point"
    else:
        feedback = (
            "Not quite — replay the section and try again with the main idea, "
            "not a word-for-word translation."
        )
    return {
        "score": score,
        "stars": stars,
        "passed": passed,
        "point": 1 if passed else 0,
        "translation": attempt,
        "reference_en": reference,
        "explain_en": explain_en,
        "best_match": best_passage,
        "retrieved": retrieved[:4],
        "coverage": round(coverage, 3),
        "similarity": round(best_sim, 3),
        "feedback": feedback,
    }


def score_music_video_section(
    language: str,
    *,
    video_id: str,
    section_id: str,
    translation: str,
) -> dict:
    """Look up a music-video section and RAG-score the learner's gist translation."""
    challenge = music_video_challenge(language, video_id=video_id or None)
    section = next(
        (row for row in challenge.get("sections") or [] if row.get("id") == section_id),
        None,
    )
    if section is None:
        return {
            "score": 0, "stars": 0, "passed": False, "point": 0,
            "translation": translation, "reference_en": "", "explain_en": "",
            "best_match": "", "retrieved": [], "coverage": 0.0, "similarity": 0.0,
            "feedback": "Unknown section — reload the music-video challenge.",
            "section_id": section_id, "video_id": challenge.get("video_id", video_id),
        }
    result = assess_translation_gist(
        section.get("en", ""),
        translation,
        explain_en=section.get("explain_en", ""),
        paraphrases_en=list(section.get("paraphrases_en") or []),
        language=language,
    )
    result["section_id"] = section_id
    result["video_id"] = challenge.get("video_id", video_id)
    result["section_no"] = section.get("section_no")
    return result


def course_outline(language: str) -> dict:
    meta = LANGUAGE_META.get(language, {"name": language, "native": language, "flag": "🏳️"})
    return {
        "code": language, **meta, "tier": "full",
        "skills": SKILL_AREAS,
        "phrase_count": len(phrases_for(language)),
        "vocabulary_count": len(vocabulary_for(language)),
        "dialogue_count": len(dialogues_for(language)),
        "slang_count": slang_count(language),
        "song_count": len(songs_for(language)),
        "music_video_count": len(music_videos_for(language)),
        "grammar_tip": _GRAMMAR_TIPS.get(language, ""),
        "culture_note": _CULTURE_NOTES.get(language, ""),
    }


# --------------------------------------------------------------------------- #
# Exercises
# --------------------------------------------------------------------------- #
def _label(p: dict) -> str:
    return f"{p['target']}" + (f" ({p['roman']})" if p["roman"] else "")


def vocabulary_exercise(language: str, *, n: int = 5, seed: Optional[int] = None) -> dict:
    """Show a word in the target language; pick its English meaning."""
    rng = random.Random(seed)
    vocabulary = vocabulary_for(language)
    pool = vocabulary or phrases_for(language)
    rng.shuffle(pool)
    pool = pool[: max(1, min(n, len(pool)))]
    all_meanings = [p["en"] for p in (vocabulary or phrases_for(language))]
    if not all_meanings:
        all_meanings = [c[2] for c in _CONCEPTS]
    items = []
    for p in pool:
        distractors = [m for m in all_meanings if m != p["en"]]
        rng.shuffle(distractors)
        opts = distractors[:3] + [p["en"]]
        rng.shuffle(opts)
        items.append({
            "id": uuid.uuid4().hex[:8], "prompt": _label(p),
            "options": opts, "answer_index": opts.index(p["en"]),
            "explain": f"{_label(p)} = {p['en']}",
        })
    return {"skill": "vocabulary", "language": language, "items": items}


def listening_exercise(language: str, *, n: int = 5, seed: Optional[int] = None) -> dict:
    """Frame as 'you hear ... what does it mean?' (audio via TTS in the client)."""
    ex = vocabulary_exercise(language, n=n, seed=seed)
    ex["skill"] = "listening"
    for it in ex["items"]:
        it["audio_prompt"] = it["prompt"]
        it["prompt"] = f"You hear: {it['prompt']} — what does it mean?"
    return ex


def match_exercise(language: str, *, n: int = 4, seed: Optional[int] = None) -> dict:
    """Match target phrases to English meanings."""
    rng = random.Random(seed)
    pool = phrases_for(language)
    rng.shuffle(pool)
    pool = pool[: max(2, min(n, len(pool)))]
    pairs = [{"id": uuid.uuid4().hex[:8], "term": _label(p), "match": p["en"]} for p in pool]
    return {"skill": "match", "language": language, "pairs": pairs}


def dialogue_exercise(language: str, *, n: int = 5) -> dict:
    rows = dialogues_for(language)[:max(1, n)]
    return {"skill": "conversation", "language": language, "dialogues": rows}


def slang_exercise(language: str, *, n: int = 8) -> dict:
    from .slang import all_entries

    entries = [
        {
            "phrase": entry.phrase,
            "meaning": entry.meaning,
            "region": entry.region,
            "kind": entry.kind,
            "register": entry.register,
        }
        for entry in all_entries()
        if entry.language == language
    ]
    return {"skill": "slang", "language": language, "entries": entries[:max(1, n)]}


def pronunciation_prompt(language: str, *, category: Optional[str] = None,
                         seed: Optional[int] = None) -> dict:
    rng = random.Random(seed)
    pool = phrases_for(language, category)
    if not pool:
        pool = phrases_for(language)
    p = rng.choice(pool) if pool else {"target": LANGUAGE_META.get(language, {}).get("native", ""),
                                       "roman": "", "en": "Hello"}
    return {
        "skill": "pronunciation", "language": language,
        "target": p["target"], "roman": p.get("roman", ""), "en": p["en"],
        "mouth_tip": mouth_shape_tip(p.get("roman") or p["target"]),
    }


# --------------------------------------------------------------------------- #
# Pronunciation assessment (audio recognition + machine-vision mouth coaching)
# --------------------------------------------------------------------------- #
def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def mouth_shape_tip(text: str) -> str:
    """Camera mouth-shape coaching cue inferred from the leading sound.

    The perception service can measure actual mouth openness from face landmarks;
    offline we infer a viseme cue from the (romanized) target so the tip is always
    useful.
    """
    t = _normalize(text)
    if not t:
        return "Relax your mouth and start gently."
    first = t[0]
    if first in "ao":
        return "Open your mouth wide for the 'ah/oh' sound."
    if first in "ou":
        return "Round your lips for the 'oo' sound."
    if first in "ei":
        return "Spread your lips into a slight smile."
    if first in "mbp":
        return "Press your lips together, then release."
    if first in "fv":
        return "Touch your top teeth to your bottom lip."
    if first in "tdn":
        return "Tongue tip behind your top teeth."
    return "Mouth relaxed; keep an even, steady pace."


def assess_pronunciation(target: str, heard: str, *,
                         mouth_openness: Optional[float] = None) -> dict:
    """Score a spoken/typed attempt against the target.

    `heard` is what the ASR transcribed (or what the learner typed). `mouth_openness`
    (0-1), when provided by the camera/vision pipeline, nudges feedback. Returns a
    0-100 score, stars, per-word hints, and coaching - all offline-computable.
    """
    nt, nh = _normalize(target), _normalize(heard)
    ratio = difflib.SequenceMatcher(None, nt, nh).ratio() if nt else 0.0
    score = round(ratio * 100)
    stars = 3 if score >= 85 else 2 if score >= 60 else 1 if score >= 1 else 0

    tw, hw = nt.split(), set(nh.split())
    missed = [w for w in tw if w not in hw]
    if score >= 85:
        feedback = "Excellent! Clear and accurate. 🎉"
    elif score >= 60:
        feedback = "Good - close! Focus on the highlighted words."
    elif score >= 1:
        feedback = "Keep practicing - listen again and slow down."
    else:
        feedback = "Give it a try - tap the speaker to hear it first."

    mouth = mouth_shape_tip(target)
    if mouth_openness is not None:
        if mouth_openness < 0.2:
            mouth = "Open your mouth a bit more - the camera sees it nearly closed."
        elif mouth_openness > 0.8:
            mouth = "Great mouth movement! Keep that articulation."

    return {
        "score": score, "stars": stars, "passed": score >= 60,
        "target": target, "heard": heard, "missed_words": missed,
        "feedback": feedback, "mouth_tip": mouth,
    }


def grammar_tip(language: str) -> str:
    return _GRAMMAR_TIPS.get(language, "Listen for patterns - grammar emerges from exposure.")


def culture_note(language: str) -> str:
    return _CULTURE_NOTES.get(language, "Every language carries its culture - stay curious and respectful.")


class PracticeResult(BaseModel):
    language: str
    skill: str
    correct: int = 0
    total: int = 0
    score: int = 0
    xp: int = 0
    stars: int = 0


# One practice set never legitimately exceeds this many items; the cap bounds
# how many points a single self-reported /language/practice call can mint.
MAX_PRACTICE_ITEMS = 500


def practice_xp(skill: str, correct: int, total: int) -> int:
    """XP for completing a practice set (feeds points/rewards)."""
    total = max(0, min(int(total), MAX_PRACTICE_ITEMS))
    # Never mint XP against a forged/empty set size — correct cannot exceed total.
    correct = max(0, min(int(correct), total))
    base = correct * 8
    bonus = 16 if total and correct == total else 0
    hard = {"pronunciation", "writing", "conversation", "music-video"}
    return int((base + bonus) * (1.25 if skill in hard else 1.0))
