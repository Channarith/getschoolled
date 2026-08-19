"""Regional dialect and colloquial tone for narration and tutor replies.

Classroom audio/video sounded too formal because lesson scripts used neutral
English. This module applies locale-specific phrasing, discourse markers, and
light rewrites so a Californian, Texan, Mexican Spanish, or Brazilian Portuguese
session sounds like a real person from that area — without changing facts.

Pure/offline; pairs with :mod:`aoep_shared.slang` for inbound student slang.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class DialectProfile:
    """How a teacher from a region speaks."""

    id: str
    language: str
    label: str
    region: str  # matches slang region tags where applicable
    intro_template: str
    outro_template: str
    discourse_markers: tuple[str, ...] = ()
  # (pattern, replacement) — applied in order after lowercasing keys for match
    replacements: tuple[tuple[str, str], ...] = ()
    tutor_tone_hint: str = ""


DIALECTS: Dict[str, DialectProfile] = {
    "us_general": DialectProfile(
        id="us_general", language="en", label="US (general)", region="us",
        intro_template=(
            "Welcome to our course on {title}. "
            "Today we'll cover {preview}{tail}. Jump in whenever you have a question."
        ),
        outro_template=(
            "That's our session on {title}. Nice work sticking with it. "
            "Practice one idea on your own today — that's where it really clicks."
        ),
        discourse_markers=("So,", "Okay,", "Right —", "Here's the thing:"),
        replacements=(
            ("We will walk through", "We're going to walk through"),
            ("Let us get into it", "Let's get into it"),
            ("That is a wrap on", "That wraps up"),
            ("Nice work getting through it", "Nice work sticking with it"),
            ("The best way to make this stick", "The best way to make this stick"),
            ("Take your time", "Take your time"),
        ),
        tutor_tone_hint="Friendly American English, conversational, not corporate.",
    ),
    "us_ca": DialectProfile(
        id="us_ca", language="en", label="California", region="us",
        intro_template=(
            "Hey — stoked you're here. Today we're covering {title}. "
            "We'll go through {preview}{tail}. Holler if anything's confusing."
        ),
        outro_template=(
            "Cool — that's {title} wrapped. You showed up, that counts. "
            "Mess around with it IRL and it'll stick way better."
        ),
        discourse_markers=("So like,", "Okay cool —", "Real talk:", "Basically,"),
        replacements=(
            ("Welcome!", "Hey — stoked you're here."),
            ("We will walk through", "We're gonna cruise through"),
            ("Take your time", "No stress"),
            ("get into it", "dive in"),
            ("That is a wrap on", "Cool — that's"),
            ("practice", "mess around with it"),
            ("come back any time", "hop back in whenever"),
        ),
        tutor_tone_hint="Relaxed West Coast vibe — warm, casual, 'like' sparingly.",
    ),
    "us_tx": DialectProfile(
        id="us_tx", language="en", label="Texas", region="us",
        intro_template=(
            "Howdy — glad y'all made it. Today we're on {title}. "
            "We'll work through {preview}{tail}. Speak up if something don't sit right."
        ),
        outro_template=(
            "Well, that's {title} done. Good on y'all for hanging in there. "
            "Get your hands dirty with it — that's how it sticks."
        ),
        discourse_markers=("Now look,", "Alright y'all,", "Thing is,", "Here's how I see it:"),
        replacements=(
            ("Welcome!", "Howdy — glad y'all made it."),
            ("We will walk through", "We'll work through"),
            ("Take your time", "No hurry"),
            ("That is a wrap on", "Well, that's"),
            ("Nice work", "Good on y'all"),
            ("try it yourself", "get your hands dirty"),
        ),
        tutor_tone_hint="Warm Southern US tone — direct, folksy but respectful.",
    ),
    "en_gb": DialectProfile(
        id="en_gb", language="en", label="British", region="gb",
        intro_template=(
            "Right, lovely to have you. Today we're looking at {title}. "
            "We'll go through {preview}{tail}. Do chime in if anything's unclear."
        ),
        outro_template=(
            "And that's {title} sorted. Well done for sticking with it. "
            "Have a go on your own — that's when it properly lands."
        ),
        discourse_markers=("Right,", "So,", "The thing is,", "To be fair,"),
        replacements=(
            ("Welcome!", "Right, lovely to have you."),
            ("We will walk through", "We'll go through"),
            ("That is a wrap on", "And that's"),
            ("Nice work", "Well done"),
            ("try it yourself", "have a go"),
            ("awesome", "brilliant"),
        ),
        tutor_tone_hint="Polite British English — understated, 'brilliant/lovely', dry warmth.",
    ),
    "en_au": DialectProfile(
        id="en_au", language="en", label="Australian", region="au",
        intro_template=(
            "G'day — good on ya for turning up. Today we're on {title}. "
            "We'll run through {preview}{tail}. Sing out if something's not clicking."
        ),
        outro_template=(
            "Righto, that's {title} done. No worries hanging in there. "
            "Give it a crack yourself — that's how it sticks."
        ),
        discourse_markers=("Righto,", "Look,", "No worries,", "Fair enough,"),
        replacements=(
            ("Welcome!", "G'day — good on ya for turning up."),
            ("We will walk through", "We'll run through"),
            ("Take your time", "No rush"),
            ("That is a wrap on", "Righto, that's"),
            ("Nice work", "Good on ya"),
            ("try it yourself", "give it a crack"),
        ),
        tutor_tone_hint="Easy-going Australian — 'g'day/no worries/give it a crack', friendly.",
    ),
    "es_mx": DialectProfile(
        id="es_mx", language="es", label="México", region="mx",
        intro_template=(
            "¡Qué onda! Hoy vemos {title}. "
            "Vamos con {preview}{tail}. Si algo no cuadra, pregunta sin pena."
        ),
        outro_template=(
            "Listo — eso fue {title}. Muy bien por quedarte. "
            "Échale ganas practicando y se te va a quedar."
        ),
        discourse_markers=("O sea,", "Mira,", "Básicamente,", "La onda es que"),
        replacements=(
            ("Welcome", "Qué onda"),
            ("Today we are learning", "Hoy vemos"),
            ("Take your time", "Sin prisa"),
        ),
        tutor_tone_hint="Mexican Spanish casual — tú, modismos mexicanos naturales.",
    ),
    "pt_br": DialectProfile(
        id="pt_br", language="pt", label="Brasil", region="br",
        intro_template=(
            "E aí — que bom você aqui. Hoje a gente vê {title}. "
            "Vamos passar por {preview}{tail}. Pode mandar pergunta quando quiser."
        ),
        outro_template=(
            "Fechou — isso foi {title}. Mandou bem ficar até aqui. "
            "Pratica na prática que fixa de verdade."
        ),
        discourse_markers=("Então,", "Tipo assim,", "Olha só,", "O negócio é o seguinte:"),
        replacements=(
            ("Welcome", "E aí"),
            ("Today we are learning", "Hoje a gente vê"),
            ("Take your time", "Sem pressa"),
        ),
        tutor_tone_hint="Brazilian Portuguese colloquial — gente, tá, natural carioca-neutral.",
    ),
    "us_south": DialectProfile(
        id="us_south", language="en", label="US Southern", region="us-south",
        intro_template=(
            "Hey y'all — glad you made it. Today we're talking {title}. "
            "We'll go through {preview}{tail}. Holler if something ain't clear."
        ),
        outro_template=(
            "Alright, that's {title} for today. Y'all did good sticking with it. "
            "Practice a little on your own and it'll stick."
        ),
        discourse_markers=("Now look,", "Alright now,", "Listen,", "Here's the thing,"),
        replacements=(
            ("Welcome!", "Hey y'all — glad you made it."),
            ("We will walk through", "We're gonna go through"),
            ("going to", "gonna"),
            ("want to", "wanna"),
            ("Take your time", "No rush now"),
            ("That is a wrap on", "Alright, that's"),
            ("Nice work", "Y'all did good"),
        ),
        tutor_tone_hint="Southern US English — warm, y'all, ain't sparingly, unhurried.",
    ),
    "us_ny": DialectProfile(
        id="us_ny", language="en", label="New York", region="us-ny",
        intro_template=(
            "Alright — let's get into {title}. "
            "We're covering {preview}{tail}. Ask if you're stuck — don't sit on it."
        ),
        outro_template=(
            "That's {title}. Good work. "
            "Go practice it — talking about it only gets you so far."
        ),
        discourse_markers=("Listen,", "Look,", "Real talk —", "Here's the deal:"),
        replacements=(
            ("Welcome!", "Alright — let's get into it."),
            ("We will walk through", "We're gonna cover"),
            ("Take your time", "Take a beat"),
            ("That is a wrap on", "That's"),
            ("Nice work", "Good work"),
            ("awesome", "solid"),
        ),
        tutor_tone_hint="New York / metro Northeast — direct, fast, plainspoken warmth.",
    ),
    "us_ne": DialectProfile(
        id="us_ne", language="en", label="New England", region="us-ne",
        intro_template=(
            "Hi there — good to have you. Today we're on {title}. "
            "We'll go over {preview}{tail}. Jump in if something's unclear."
        ),
        outro_template=(
            "That covers {title}. Nice job hanging in. "
            "Try it once on your own and it'll click."
        ),
        discourse_markers=("So,", "Anyway,", "Right,", "Here's what matters:"),
        replacements=(
            ("Welcome!", "Hi there — good to have you."),
            ("We will walk through", "We'll go over"),
            ("Take your time", "No hurry"),
            ("That is a wrap on", "That covers"),
            ("awesome", "wicked good"),
        ),
        tutor_tone_hint="New England English — dry, understated, 'wicked' lightly, practical.",
    ),
    "en_ca": DialectProfile(
        id="en_ca", language="en", label="Canadian", region="ca",
        intro_template=(
            "Hey — glad you're here, eh? Today we're on {title}. "
            "We'll walk through {preview}{tail}. Ask anytime if something's fuzzy."
        ),
        outro_template=(
            "That's {title} — nice work. "
            "Give it a try on your own and it'll stick, eh?"
        ),
        discourse_markers=("So,", "Alright,", "For sure,", "Here's the thing,"),
        replacements=(
            ("Welcome!", "Hey — glad you're here, eh?"),
            ("We will walk through", "We'll walk through"),
            ("Take your time", "No rush"),
            ("That is a wrap on", "That's"),
            ("awesome", "pretty great"),
        ),
        tutor_tone_hint="Canadian English — polite, eh lightly, friendly and clear.",
    ),
    "en_sg": DialectProfile(
        id="en_sg", language="en", label="Singaporean", region="sg",
        intro_template=(
            "Okay lah — today we cover {title}. "
            "We go through {preview}{tail}. Any question, just ask, can."
        ),
        outro_template=(
            "Finish already for {title}. Good job. "
            "Practice yourself a bit — then sure confirm."
        ),
        discourse_markers=("Okay lah,", "So,", "Actually,", "Then,"),
        replacements=(
            ("Welcome!", "Okay lah — welcome."),
            ("We will walk through", "We go through"),
            ("Take your time", "No need rush"),
            ("That is a wrap on", "Finish already for"),
            ("Nice work", "Good job"),
            ("very easy", "very easy one"),
        ),
        tutor_tone_hint="Singapore English / Singlish-lite — lah/can sparingly, clear teaching tone.",
    ),
    "en_ie": DialectProfile(
        id="en_ie", language="en", label="Irish", region="ie",
        intro_template=(
            "Ah you're welcome. Today we're looking at {title}. "
            "We'll go through {preview}{tail}. Give a shout if you're stuck."
        ),
        outro_template=(
            "That's {title} done. Fair play for sticking with it. "
            "Have a go yourself — that's when it lands."
        ),
        discourse_markers=("Right,", "So,", "Look,", "Here's the craic:"),
        replacements=(
            ("Welcome!", "Ah you're welcome."),
            ("We will walk through", "We'll go through"),
            ("Nice work", "Fair play"),
            ("awesome", "brilliant"),
        ),
        tutor_tone_hint="Irish English — warm, fair play, understated humour.",
    ),
    "en_in": DialectProfile(
        id="en_in", language="en", label="Indian English", region="in",
        intro_template=(
            "Welcome. Today we will cover {title}. "
            "We will go through {preview}{tail}. Please ask doubts anytime."
        ),
        outro_template=(
            "That completes {title}. Very good. "
            "Please do the needful and practise on your own."
        ),
        discourse_markers=("So,", "Basically,", "Actually,", "Please note:"),
        replacements=(
            ("Welcome!", "Welcome."),
            ("We will walk through", "We will go through"),
            ("questions", "doubts"),
            ("try it yourself", "please practise on your own"),
        ),
        tutor_tone_hint="Indian English — clear, polite, 'doubts/do the needful' naturally.",
    ),
    "en_za": DialectProfile(
        id="en_za", language="en", label="South African", region="za",
        intro_template=(
            "Howzit — good to have you. Today we're on {title}. "
            "We'll go through {preview}{tail}. Shout if something's lekker confusing."
        ),
        outro_template=(
            "Sharp — that's {title}. Well done. "
            "Give it a bash yourself and it'll stick."
        ),
        discourse_markers=("So,", "Look,", "Ja,", "Here's the thing:"),
        replacements=(
            ("Welcome!", "Howzit — good to have you."),
            ("Nice work", "Well done"),
            ("awesome", "lekker"),
            ("try it yourself", "give it a bash"),
        ),
        tutor_tone_hint="South African English — howzit/sharp/lekker lightly, friendly.",
    ),
    "zh_bj": DialectProfile(
        id="zh_bj", language="zh", label="北京话 (Beijing)", region="cn-bj",
        intro_template=(
            "来来来，今天咱们学 {title}。"
            "主要看看 {preview}{tail}。有问题随时说啊。"
        ),
        outro_template=(
            "行，{title} 就到这儿。干得不错。"
            "自己再练练，记得更牢。"
        ),
        discourse_markers=("哎,", "得嘞,", "您看,", "说白了,"),
        replacements=(
            ("Welcome", "来来来"),
            ("Take your time", "不着急"),
            ("Nice work", "干得不错"),
        ),
        tutor_tone_hint="Beijing Mandarin colloquial — 咱们/您/得嘞, warm and direct.",
    ),
    "zh_sh": DialectProfile(
        id="zh_sh", language="zh", label="上海话 (Shanghai)", region="cn-sh",
        intro_template=(
            "侬好 — 今朝吾伲学 {title}。"
            "主要是 {preview}{tail}。勿明白就问。"
        ),
        outro_template=(
            "好哉，{title} 到此结束。侬蛮好。"
            "自家再练练，会更牢靠。"
        ),
        discourse_markers=("欸,", "晓得伐,", "讲起来,", "其实呢,"),
        replacements=(
            ("Welcome", "侬好"),
            ("Take your time", "慢慢来"),
            ("Nice work", "侬蛮好"),
        ),
        tutor_tone_hint="Shanghai Wu-flavored teaching Chinese — 侬/吾伲 markers, gentle pace.",
    ),
    "zh_yue_gz": DialectProfile(
        id="zh_yue_gz", language="zh", label="广州话 (Cantonese)", region="cn-gz",
        intro_template=(
            "唔该晒 — 今日我哋学 {title}。"
            "会讲吓 {preview}{tail}。有唔明就问啦。"
        ),
        outro_template=(
            "得，{title} 就到呢度。做得好。"
            "自己再练下，会更稳阵。"
        ),
        discourse_markers=("噉,", "其实,", "即系,", "睇嚟,"),
        replacements=(
            ("Welcome", "唔该晒"),
            ("Take your time", "唔使急"),
            ("Nice work", "做得好"),
        ),
        tutor_tone_hint="Guangzhou / HK Cantonese teaching tone — 我哋/唔该/啦 particles.",
    ),
    "zh_min_fj": DialectProfile(
        id="zh_min_fj", language="zh", label="福建话 (Hokkien/Min)", region="cn-fj",
        intro_template=(
            "你好 — 今仔日咱来学 {title}。"
            "会讲 {preview}{tail}。若无清楚就问。"
        ),
        outro_template=(
            "好，{title} 到遮。做了真好。"
            "家己阁练，会较记牢。"
        ),
        discourse_markers=("按呢,", "其实,", "咱看,", "简单讲,"),
        replacements=(
            ("Welcome", "你好"),
            ("Take your time", "免紧张"),
            ("Nice work", "做了真好"),
        ),
        tutor_tone_hint="Fujian / Hokkien-Min teaching Chinese — 咱/今仔日 flavor, clear and warm.",
    ),
}


def normalize_dialect(dialect: Optional[str], *, language: str = "en") -> Optional[str]:
    """Return a dialect id, or None for neutral (non-regional) narration."""
    if not dialect:
        return None
    key = dialect.lower().replace("-", "_")
    if key in DIALECTS:
        return key
    aliases = {
        "california": "us_ca", "ca": "us_ca", "californian": "us_ca",
        "texas": "us_tx", "tx": "us_tx", "texan": "us_tx",
        "southern": "us_south", "south": "us_south", "us_southern": "us_south",
        "dixie": "us_south",
        "newyork": "us_ny", "new_york": "us_ny", "nyc": "us_ny", "ny": "us_ny",
        "newengland": "us_ne", "new_england": "us_ne", "boston": "us_ne", "ne": "us_ne",
        "british": "en_gb", "uk": "en_gb", "gb": "en_gb", "england": "en_gb",
        "australian": "en_au", "australia": "en_au", "au": "en_au", "aussie": "en_au",
        "canadian": "en_ca", "canada": "en_ca",
        "singapore": "en_sg", "singaporean": "en_sg", "singlish": "en_sg", "sg": "en_sg",
        "irish": "en_ie", "ireland": "en_ie", "ie": "en_ie",
        "indian": "en_in", "india": "en_in",
        "southafrican": "en_za", "south_african": "en_za", "za": "en_za",
        "beijing": "zh_bj", "beijingese": "zh_bj", "mandarin_beijing": "zh_bj",
        "shanghai": "zh_sh", "shanghainese": "zh_sh", "wu": "zh_sh",
        "cantonese": "zh_yue_gz", "guangzhou": "zh_yue_gz", "guangdong": "zh_yue_gz",
        "yue": "zh_yue_gz", "hk": "zh_yue_gz", "hongkong": "zh_yue_gz",
        "fujian": "zh_min_fj", "fujianese": "zh_min_fj", "hokkien": "zh_min_fj",
        "minnan": "zh_min_fj", "min": "zh_min_fj",
        "mexican": "es_mx", "mexico": "es_mx", "mx": "es_mx",
        "brazilian": "pt_br", "brazil": "pt_br", "br": "pt_br",
        "en": "us_general", "us": "us_general", "general": "us_general",
    }
    return aliases.get(key)


def get_dialect(dialect: Optional[str], *, language: str = "en") -> DialectProfile:
    key = normalize_dialect(dialect, language=language) or "us_general"
    return DIALECTS[key]


def _apply_replacements(text: str, pairs: Sequence[tuple[str, str]]) -> str:
    out = text
    for src, dst in pairs:
        out = re.sub(re.escape(src), dst, out, flags=re.IGNORECASE)
    return out


def humanize_narration(text: str, dialect: Optional[str] = None, *, language: str = "en") -> str:
    """Rewrite neutral lesson copy into regional colloquial tone."""
    if not text or not text.strip():
        return text
    dialect_id = normalize_dialect(dialect, language=language)
    if not dialect_id:
        return text
    prof = get_dialect(dialect_id, language=language)
    out = _apply_replacements(text, prof.replacements)
    # Sprinkle an occasional discourse marker at sentence starts (deterministic hash).
    if prof.discourse_markers and len(out) > 40:
        marker = prof.discourse_markers[len(out) % len(prof.discourse_markers)]
        if not out.startswith(marker):
            first = out.split(". ", 1)
            if len(first) == 2:
                out = f"{marker} {first[0]}. {first[1]}"
    return out


def dialect_intro(title: str, headings: List[str], dialect: Optional[str] = None,
                  *, language: str = "en") -> str:
    prof = get_dialect(dialect, language=language)
    preview = ", ".join(h for h in headings[:4] if h)
    tail = "" if len(headings) <= 4 else ", and more"
    return prof.intro_template.format(title=title, preview=preview, tail=tail)


def dialect_outro(title: str, dialect: Optional[str] = None, *, language: str = "en") -> str:
    prof = get_dialect(dialect, language=language)
    return prof.outro_template.format(title=title)


def tutor_tone_hint(dialect: Optional[str] = None, *, language: str = "en") -> str:
    return get_dialect(dialect, language=language).tutor_tone_hint


def list_dialects() -> List[dict]:
    return [
        {"id": p.id, "language": p.language, "label": p.label, "region": p.region}
        for p in DIALECTS.values()
    ]
