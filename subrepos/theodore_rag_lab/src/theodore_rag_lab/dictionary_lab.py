"""Dictionary, dialect rehearsal, and regurgitation drills for the RAG lab.

Regurgitation = hear/see a regional slang or idiom, then recall its plain
meaning (and optionally produce it back in the target dialect). Feedback
learning records confirm/correct/reject so the dictionary matures.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from typing import Any, List

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


# Spoken Cambodian for the dialect check. English lesson text is not inserted,
# because an English voice skips Khmer letters and the line would sound English.
_KHMER_SAMPLE = "សួស្តី។ អត់បញ្ហាទេ។ ថ្ងៃនេះយើងរៀនជំហានបន្ទាប់។ យឺតៗទៅ។ ល្អណាស់។"
_KHMER_GLOSS = "Hello. No problem. Today we learn the next step. Take it easy. Very good."

_LANGUAGE_LINES = {
    "km": _KHMER_SAMPLE,
    "th": "สวัสดีค่ะ ฉันได้ยินคุณแล้ว {heard} เราไปขั้นถัดไปด้วยกันนะคะ",
    "vi": "Xin chào. Tôi nghe thấy bạn rồi. {heard} Chúng ta sẽ sang bước tiếp theo.",
    "tl": "Kumusta. Narinig kita. {heard} Tatalakayin natin ang susunod na hakbang.",
    "id": "Halo. Saya mendengar Anda. {heard} Kita lanjut ke langkah berikutnya.",
    "ja": "こんにちは。聞こえました。{heard} 次のステップに進みます。",
    "ko": "안녕하세요. 잘 들었습니다. {heard} 다음 단계로 갈게요.",
    "hi": "नमस्ते। मैंने सुना। {heard} हम अगला कदम देखेंगे।",
    "ar": "مرحبا. سمعتك. {heard} نكمل الخطوة التالية.",
    "ru": "Здравствуйте. Я вас слышу. {heard} Перейдём к следующему шагу.",
    "de": "Hallo. Ich habe Sie gehört. {heard} Wir gehen zum nächsten Schritt.",
    "fr": "Bonjour. Je vous ai entendu. {heard} On passe à l'étape suivante.",
    "es": "Hola. Te escuché. {heard} Seguimos con el siguiente paso.",
    "pt": "Olá. Eu ouvi você. {heard} Vamos ao próximo passo.",
    "it": "Ciao. Ti ho sentito. {heard} Passiamo al passo successivo.",
    "nl": "Hallo. Ik heb je gehoord. {heard} We gaan naar de volgende stap.",
    "pl": "Cześć. Słyszę cię. {heard} Przechodzimy do następnego kroku.",
    "uk": "Вітаю. Я вас чую. {heard} Переходимо до наступного кроку.",
    "cs": "Dobrý den. Slyším vás. {heard} Přejdeme k dalšímu kroku.",
    "el": "Γεια σας. Σας άκουσα. {heard} Πάμε στο επόμενο βήμα.",
    "tr": "Merhaba. Sizi duydum. {heard} Sonraki adıma geçiyoruz.",
    "he": "שלום. שמעתי אותך. {heard} נמשיך לשלב הבא.",
    "fa": "سلام. شنیدم. {heard} می‌رویم سراغ قدم بعد.",
    "bn": "হ্যালো। শুনেছি। {heard} আমরা পরের ধাপে যাব।",
    "ur": "سلام۔ میں نے سنا۔ {heard} اگلے مرحلے پر چلتے ہیں۔",
    "sw": "Habari. Nimekusikia. {heard} Tunaendelea hatua inayofuata.",
    "zh": "你好。我听到了。{heard} 我们看下一步。",
    "yue": "你好。我聽到。{heard} 我哋睇下一步。",
}


def _lookup_variety(token: str) -> dict[str, Any] | None:
    from aoep_shared.spoken_varieties import list_spoken_varieties

    key = (token or "").strip()
    if not key:
        return None
    rows = list_spoken_varieties()
    for row in rows:
        if row["id"] == key:
            return row
    for row in rows:
        if row.get("dialect") == key:
            return row
    return None


def _profile_id(dialect: str, language: str) -> str:
    direct = normalize_dialect(dialect, language=language or "en")
    if direct:
        return direct
    variety = _lookup_variety(dialect)
    if variety and variety.get("dialect"):
        return normalize_dialect(variety["dialect"], language=variety.get("language") or language or "en") or ""
    return ""


def _voice_rows(voices: List[Any]) -> list[dict[str, Any]]:
    return [
        {"id": v.id, "label": v.label, "accent": v.accent, "locale": v.locale, "edge_voice": v.edge_voice}
        for v in voices
    ]


def _voices_for_language(language: str, variety_id: str = "") -> list[dict[str, Any]]:
    locale = {
        "zh_tw": "zh-TW",
        "zh_cn": "zh-CN",
        "es_es": "es-ES",
        "es_ar": "es-AR",
        "es_us": "es-US",
        "fr_ca": "fr-CA",
        "fr_fr": "fr-FR",
        "pt_pt": "pt-PT",
        "ar_eg": "ar-EG",
        "ar_sa": "ar-SA",
        "km_kh": "km-KH",
        "tl_ph": "fil-PH",
        "th_th": "th-TH",
        "vi_vn": "vi-VN",
    }.get(variety_id, "")
    rows = [v for v in VOICE_CATALOG if locale and v.locale.lower() == locale.lower()]
    if not rows and language == "yue":
        rows = [v for v in VOICE_CATALOG if v.locale.lower().startswith("zh-hk")]
    if not rows:
        rows = [v for v in VOICE_CATALOG if v.language == language]
    return _voice_rows(rows[:4])


def _uses_language_script(language: str, heard: str) -> bool:
    """True when ``heard`` is already written in that language, not the English box."""
    if language == "km":
        return any("\u1780" <= ch <= "\u17ff" for ch in heard)
    if language == "th":
        return any("\u0e00" <= ch <= "\u0e7f" for ch in heard)
    if language in {"zh", "yue"}:
        return any("\u4e00" <= ch <= "\u9fff" for ch in heard)
    if language == "ja":
        return any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in heard)
    if language == "ko":
        return any("\uac00" <= ch <= "\ud7af" for ch in heard)
    if language in {"ar", "fa", "ur"}:
        return any("\u0600" <= ch <= "\u06ff" for ch in heard)
    if language == "hi":
        return any("\u0900" <= ch <= "\u097f" for ch in heard)
    if language == "bn":
        return any("\u0980" <= ch <= "\u09ff" for ch in heard)
    if language == "he":
        return any("\u0590" <= ch <= "\u05ff" for ch in heard)
    if language in {"ru", "uk"}:
        return any("\u0400" <= ch <= "\u04ff" for ch in heard)
    if language == "el":
        return any("\u0370" <= ch <= "\u03ff" for ch in heard)
    return True


def _plain_line(language: str, heard: str) -> str:
    if language == "km":
        if "អត់បញ្ហា" in heard and "យឺតៗ" in heard:
            return heard
        if _uses_language_script("km", heard):
            return f"សួស្តី។ {heard} អត់បញ្ហាទេ។ យឺតៗទៅ។ ល្អណាស់។"
        return _KHMER_SAMPLE
    template = _LANGUAGE_LINES.get(language) or "Hello. I heard you. {heard}"
    low = (heard or "").lower()
    english_box = "we will walk through" in low or low.startswith("welcome!")
    if english_box or not _uses_language_script(language, heard):
        return " ".join(template.replace("{heard}", "").split())
    return template.format(heard=heard).strip()


def _language_probe(text: str, variety: dict[str, Any] | None, language: str) -> dict[str, Any]:
    lang = ((variety or {}).get("language") or language or "en").strip() or "en"
    label = (variety or {}).get("label") or lang
    variety_id = (variety or {}).get("id") or lang
    heard = (text or "").strip()
    line = _plain_line(lang, heard)
    gloss = _KHMER_GLOSS if lang == "km" else ""
    return {
        "dialect": {
            "id": variety_id,
            "label": label,
            "language": lang,
            "region": (variety or {}).get("country") or "",
            "tone": f"{label} classroom voice.",
            "markers": [],
        },
        "intro": line,
        "humanized": line,
        "voices": _voices_for_language(lang, variety_id),
        "normalize": gloss,
        "gloss": gloss,
        "plain_language": True,
    }


def dialect_probe(text: str, dialect: str, *, language: str = "", title: str = "Practice") -> dict[str, Any]:
    variety = _lookup_variety(dialect)
    did = _profile_id(dialect, language or (variety or {}).get("language") or "en")
    if not did:
        return _language_probe(text, variety, language)
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


def sala_reply(text: str, dialect: str, *, language: str = "", voice: str = "") -> dict[str, Any]:
    """Build a spoken Sala reply for the selected dialect. No external voice API."""
    from .sala_validation import default_validation

    heard = (text or "").strip()
    probe = dialect_probe(
        heard or "Welcome! We will walk through the lesson. Take your time. Nice work.",
        dialect,
        language=language,
    )
    prof = probe["dialect"]
    voices = probe["voices"]
    chosen = next((row for row in voices if row.get("id") == voice), None) or (voices[0] if voices else {})
    saved = default_validation().correction_for(prof["id"], heard)
    if saved:
        reply = saved
    elif probe.get("plain_language"):
        reply = probe["humanized"]
    elif prof["language"] != "en":
        title = heard[:80] or prof["label"]
        headings = ["要点", "练习"] if prof["language"] == "zh" else ["the idea", "practice"]
        reply = dialect_intro(title, headings, prof["id"], language=prof["language"])
    else:
        line = (
            f"Welcome! I heard you. {heard} We will walk through the next step. Take your time. Nice work."
            if heard
            else "Welcome! We will walk through the lesson. Take your time. Nice work."
        )
        reply = humanize_narration(line, prof["id"], language=prof["language"])
    return {
        "heard": heard,
        "reply": reply,
        "from_correction": bool(saved),
        "dialect": prof,
        "voice": chosen,
        "language": prof["language"],
        "locale": (chosen or {}).get("locale") or "en-US",
        "gloss": probe.get("gloss") or "",
        "validation": default_validation().summary(),
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
    from aoep_shared.spoken_varieties import list_spoken_varieties

    return {
        "languages": list_spoken_varieties(),
        "dialects": list_dialects(),
        "voices": catalog_grouped(),
        "lexicon": lexicon_stats(),
        "feedback": default_feedback_store().stats(),
        "featured_dialects": [
            "us_south", "us_ny", "us_ne", "us_ca", "en_ca", "en_gb", "en_au",
            "en_sg", "zh_bj", "zh_sh", "zh_yue_gz", "zh_min_fj", "en_ie", "en_in", "en_za",
        ],
    }
