"""Dictionary, dialect rehearsal, and regurgitation drills for the RAG lab.

Regurgitation = hear/see a regional slang or idiom, then recall its plain
meaning (and optionally produce it back in the target dialect). Feedback
learning records confirm/correct/reject so the dictionary matures.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from aoep_shared.dialect import (
    dialect_intro,
    get_dialect,
    humanize_narration,
    list_dialects,
    normalize_dialect,
)
from aoep_shared.slang import SlangEntry, default_lexicon, lexicon_stats
from aoep_shared.slang_feedback import default_feedback_store
from aoep_shared.voice_catalog import VOICE_CATALOG, catalog_grouped


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9\u4e00-\u9fff']+", (text or "").lower()) if t}


def dictionary_search(
    *,
    q: str = "",
    language: str = "",
    region: str = "",
    kind: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    lex = default_lexicon()
    needle = (q or "").strip().lower()
    clean: List[dict[str, Any]] = []
    for e in lex._entries:
        if language and e.language != language:
            continue
        if region and e.region != region:
            continue
        if kind and e.kind != kind:
            continue
        if needle and needle not in e.phrase.lower() and needle not in e.meaning.lower():
            continue
        clean.append({
            "phrase": e.phrase,
            "meaning": e.meaning,
            "language": e.language,
            "region": e.region,
            "kind": e.kind,
            "register": e.register,
        })
        if len(clean) >= max(1, min(int(limit or 50), 200)):
            break
    return {
        "query": q,
        "count": len(clean),
        "stats": lexicon_stats(),
        "entries": clean,
    }


def dictionary_browse(*, limit: int = 40) -> dict[str, Any]:
    stats = lexicon_stats()
    sample = dictionary_search(limit=limit)["entries"]
    return {"stats": stats, "sample": sample, "dialects": list_dialects()}


def dialect_probe(text: str, dialect: str, *, language: str = "", title: str = "Practice") -> dict[str, Any]:
    did = normalize_dialect(dialect, language=language or "en") or dialect
    # Prefer the profile language so zh_* dialects are not forced through English.
    probe_lang = language or ""
    if did in {"zh_bj", "zh_sh", "zh_yue_gz", "zh_min_fj"}:
        probe_lang = "zh"
    elif did.startswith("es_"):
        probe_lang = probe_lang or "es"
    elif did.startswith("pt_"):
        probe_lang = probe_lang or "pt"
    else:
        probe_lang = probe_lang or "en"
    prof = get_dialect(did, language=probe_lang)
    sample = text or "Welcome! We will walk through the lesson. Take your time. Nice work."
    humanized = humanize_narration(sample, did, language=probe_lang)
    intro = dialect_intro(title, ["Key idea", "Example", "Practice"], did, language=probe_lang)
    exact = [v for v in VOICE_CATALOG if v.dialect == prof.id]
    fallback = [v for v in VOICE_CATALOG if v.language == prof.language][:2]
    voices = [
        {"id": v.id, "label": v.label, "accent": v.accent, "locale": v.locale, "edge_voice": v.edge_voice}
        for v in (exact or fallback)
    ]
    gloss = ""
    if text:
        gloss = default_lexicon().normalize(
            text, language=prof.language, region=prof.region
        ).plain
    return {
        "dialect": {
            "id": prof.id,
            "label": prof.label,
            "language": prof.language,
            "region": prof.region,
            "tone": prof.tutor_tone_hint,
            "markers": list(prof.discourse_markers),
        },
        "intro": intro,
        "humanized": humanized,
        "voices": voices,
        "normalize": gloss,
    }


def _pick_entries(*, dialect: str = "", region: str = "", language: str = "", n: int = 12) -> List[SlangEntry]:
    prof = None
    if dialect:
        did = normalize_dialect(dialect, language=language or "en")
        if did:
            prof = get_dialect(did, language=language or "en")
            region = region or prof.region
            language = language or prof.language
    lex = default_lexicon()
    pool = list(lex._entries)
    if language:
        pool = [e for e in pool if e.language == language] or pool
    if region:
        regional = [e for e in pool if e.region == region]
        if not regional:
            # soft fallback: same language
            regional = [e for e in pool if e.language == (language or "en")]
        pool = regional or pool
    # stable shuffle by dialect key
    key = f"{dialect}|{region}|{language}"
    seed = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16)

    def sort_key(e: SlangEntry) -> int:
        h = int(hashlib.sha1(f"{seed}:{e.phrase}".encode()).hexdigest()[:8], 16)
        return h

    pool = sorted(pool, key=sort_key)
    return pool[: max(1, min(n, 40))]


def regurgitation_deck(*, dialect: str = "", region: str = "", language: str = "", n: int = 8) -> dict[str, Any]:
    cards = []
    for i, e in enumerate(_pick_entries(dialect=dialect, region=region, language=language, n=n)):
        cards.append({
            "id": f"{e.language}:{e.region}:{e.phrase}",
            "index": i,
            "phrase": e.phrase,
            "prompt": f"What does “{e.phrase}” mean?",
            "language": e.language,
            "region": e.region,
            "kind": e.kind,
            "hint": e.kind,
            # answer withheld until grade
            "answer_preview": e.meaning[:18] + ("…" if len(e.meaning) > 18 else ""),
        })
    return {
        "dialect": dialect,
        "region": region,
        "language": language,
        "n": len(cards),
        "cards": cards,
        "instructions": (
            "Regurgitation drill: read the phrase, recall the plain meaning, submit your answer. "
            "Correct recalls reinforce feedback learning; misses show the gloss."
        ),
    }


def grade_regurgitation(
    *,
    phrase: str,
    answer: str,
    language: str = "en",
    region: str = "global",
    dialect: str = "",
    learn: bool = True,
) -> dict[str, Any]:
    lex = default_lexicon()
    entry = lex.lookup(phrase, language=language or None, region=region or None)
    if entry is None:
        # try without region filter
        entry = lex.lookup(phrase, language=language or None)
    expected = entry.meaning if entry else ""
    got = (answer or "").strip()
    exp_toks = _tokens(expected)
    got_toks = _tokens(got)
    if not expected:
        score = 0.0
        ok = False
        detail = "Phrase not found in dictionary."
    elif not got_toks:
        score = 0.0
        ok = False
        detail = "Empty answer."
    else:
        overlap = len(exp_toks & got_toks) / max(1, len(exp_toks))
        # also accept if answer contains a long substring of meaning
        if expected.lower() in got.lower() or got.lower() in expected.lower():
            overlap = max(overlap, 0.85)
        score = round(min(1.0, overlap), 3)
        ok = score >= 0.45
        detail = "Strong recall." if score >= 0.75 else ("Partial credit." if ok else "Review the gloss and try again.")

    feedback = None
    if learn and entry and ok:
        feedback = default_feedback_store().record(
            phrase=entry.phrase,
            meaning=entry.meaning,
            language=entry.language,
            region=entry.region,
            kind=entry.kind,
            action="confirm",
            dialect=dialect or "",
            note="regurgitation_hit",
            weight=1.0 + score,
        )
    return {
        "ok": ok,
        "score": score,
        "phrase": phrase,
        "expected": expected,
        "answer": got,
        "detail": detail,
        "learned": asdict(feedback) if feedback else None,
    }


def submit_feedback(
    *,
    phrase: str,
    meaning: str,
    language: str = "en",
    region: str = "global",
    kind: str = "idiom",
    action: str = "correct",
    dialect: str = "",
    note: str = "",
) -> dict[str, Any]:
    ev = default_feedback_store().record(
        phrase=phrase,
        meaning=meaning,
        language=language,
        region=region,
        kind=kind,
        action=action,
        dialect=dialect,
        note=note,
    )
    return {"event": asdict(ev), "stats": default_feedback_store().stats()}


def feedback_snapshot() -> dict[str, Any]:
    store = default_feedback_store()
    return {"stats": store.stats(), "recent": store.recent(20)}


def lab_catalog() -> dict[str, Any]:
    return {
        "dialects": list_dialects(),
        "voices": catalog_grouped(),
        "lexicon": lexicon_stats(),
        "feedback": default_feedback_store().stats(),
        "featured_dialects": [
            "us_south", "us_ny", "us_ne", "us_ca", "en_ca", "en_gb", "en_au",
            "en_sg", "zh_bj", "zh_sh", "zh_yue_gz", "zh_min_fj", "en_ie", "en_in", "en_za",
        ],
    }
