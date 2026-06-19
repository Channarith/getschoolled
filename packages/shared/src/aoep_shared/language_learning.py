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
}

RICH_LANGUAGES = {"en", "es", "fr", "de", "it", "pt", "nl", "ja", "zh", "ko"}

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
            "tier": "rich" if code in RICH_LANGUAGES else "starter",
            "phrase_count": len(_T.get(code, {})),
        })
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
    return out


def course_outline(language: str) -> dict:
    meta = LANGUAGE_META.get(language, {"name": language, "native": language, "flag": "🏳️"})
    rich = language in RICH_LANGUAGES
    # Skills available depend on content depth; starter languages still get the
    # core practice skills (pronunciation/vocab/phrases/listening).
    core = {"pronunciation", "vocabulary", "phrases", "listening", "shadowing"}
    skills = [s for s in SKILL_AREAS if rich or s["id"] in core]
    return {
        "code": language, **meta, "tier": "rich" if rich else "starter",
        "skills": skills,
        "phrase_count": len(_T.get(language, {})),
        "grammar_tip": _GRAMMAR_TIPS.get(language, ""),
        "culture_note": _CULTURE_NOTES.get(language, ""),
    }


# --------------------------------------------------------------------------- #
# Exercises
# --------------------------------------------------------------------------- #
def _label(p: dict) -> str:
    return f"{p['target']}" + (f" ({p['roman']})" if p["roman"] else "")


def vocabulary_exercise(language: str, *, n: int = 5, seed: Optional[int] = None) -> dict:
    """Show a phrase in the target language; pick its English meaning."""
    rng = random.Random(seed)
    pool = phrases_for(language)
    rng.shuffle(pool)
    pool = pool[: max(1, min(n, len(pool)))]
    all_meanings = [p["en"] for p in phrases_for(language)] or [c[2] for c in _CONCEPTS]
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


def practice_xp(skill: str, correct: int, total: int) -> int:
    """XP for completing a practice set (feeds points/rewards)."""
    base = correct * 8
    bonus = 16 if total and correct == total else 0
    hard = {"pronunciation", "writing", "conversation"}
    return int((base + bonus) * (1.25 if skill in hard else 1.0))
