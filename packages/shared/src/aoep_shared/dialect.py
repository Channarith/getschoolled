"""Regional dialect and colloquial tone for narration and tutor replies.

Classroom audio/video sounded too formal because lesson scripts used neutral
English. This module applies locale-specific phrasing, discourse markers, and
light rewrites so a Californian, Texan, Mexican Spanish, or Brazilian Portuguese
session sounds like a real person from that area — without changing facts.

Pure/offline; pairs with :mod:`aoep_shared.slang` for inbound student slang.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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
            "Hey — welcome in. Today we're digging into {title}. "
            "We'll hit {preview}{tail}. Jump in whenever you have a question."
        ),
        outro_template=(
            "Alright, that's {title} in the bag. Nice work sticking with it. "
            "Go try it on your own — that's where it really clicks."
        ),
        discourse_markers=("So,", "Okay,", "Right —", "Here's the thing:"),
        replacements=(
            ("Welcome!", "Hey — welcome in."),
            ("We will walk through", "We're gonna walk through"),
            ("Let us get into it", "Let's dive in"),
            ("That is a wrap on", "Alright, that's"),
            ("Nice work getting through it", "Nice work sticking with it"),
            ("The best way to make this stick", "Best way this sticks"),
            ("Take your time", "No rush"),
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
}


def normalize_dialect(dialect: Optional[str], *, language: str = "en") -> str:
    if not dialect:
        return "us_general" if language.startswith("en") else dialect or "us_general"
    key = dialect.lower().replace("-", "_")
    if key in DIALECTS:
        return key
    # Aliases
    aliases = {
        "california": "us_ca", "ca": "us_ca", "californian": "us_ca",
        "texas": "us_tx", "tx": "us_tx", "texan": "us_tx",
        "mexican": "es_mx", "mexico": "es_mx", "mx": "es_mx",
        "brazilian": "pt_br", "brazil": "pt_br", "br": "pt_br",
        "en": "us_general", "us": "us_general",
    }
    return aliases.get(key, "us_general")


def get_dialect(dialect: Optional[str], *, language: str = "en") -> DialectProfile:
    return DIALECTS[normalize_dialect(dialect, language=language)]


def _apply_replacements(text: str, pairs: Sequence[tuple[str, str]]) -> str:
    out = text
    for src, dst in pairs:
        out = re.sub(re.escape(src), dst, out, flags=re.IGNORECASE)
    return out


def humanize_narration(text: str, dialect: Optional[str] = None, *, language: str = "en") -> str:
    """Rewrite neutral lesson copy into regional colloquial tone."""
    if not text or not text.strip():
        return text
    prof = get_dialect(dialect, language=language)
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
