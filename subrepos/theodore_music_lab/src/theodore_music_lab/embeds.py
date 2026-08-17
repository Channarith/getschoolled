"""YouTube embeds with pause-and-ask verses for language learning.

Each curated embed is a YouTube video (or playlist pointer) plus a cue sheet of
verses. At every ``pause_sec`` the player stops so the learner can read the
line in 27 languages, answer a grammar/vocabulary prompt, or ask the AI about
that verse before continuing.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from .curated_embeds import curated_embed
from .curated_lines import normalize
from .curated_love import curated_love
from .lexicon import EXAMPLES, gloss, terms_in_line, vocabulary_for_line
from .love_of_learning import love_of_learning_embed
from .translations import (
    TIER_NOTES,
    XAI_DEFAULT_MODEL,
    _load_cache,
    _save_cache,
    _xai_translate,
    language_name,
    validate_language,
)


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            if isinstance(rec, dict):
                rows.append(rec)
    return rows


def load_embeds(path: Optional[Path] = None) -> list[dict[str, Any]]:
    rows = _load_jsonl(path or _data_dir() / "embeds.jsonl")
    local = love_of_learning_embed()
    # Local karaoke leads the catalogue so learners see it first.
    return [local, *[row for row in rows if row.get("embed_id") != local["embed_id"]]]


def video_dir() -> Path:
    return _data_dir() / "video"


def get_embed(embed_id: str) -> dict[str, Any]:
    for row in load_embeds():
        if str(row.get("embed_id") or "") == embed_id:
            return row
    raise KeyError(embed_id)


def embed_url(youtube_id: str, *, start: float = 0.0) -> str:
    """Privacy-friendly embed URL with the IFrame API enabled for pause control."""
    yt = (youtube_id or "").strip()
    if not yt:
        return ""
    params = ["enablejsapi=1", "rel=0", "modestbranding=1"]
    if start > 0:
        params.append(f"start={int(start)}")
    return f"https://www.youtube-nocookie.com/embed/{yt}?{'&'.join(params)}"


def _translate_text(
    text: str,
    language: str,
    *,
    cache: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Best available translation for free-form English teaching text."""
    lang = validate_language(language)
    english = (text or "").strip()
    vocab = vocabulary_for_line(english, lang)
    if lang == "en" or not english:
        return {
            "text": english,
            "translation": english,
            "tier": "english",
            "note": TIER_NOTES["english"],
            "vocabulary": vocab,
        }
    translation = curated_love(english, lang) or curated_embed(english, lang)
    tier = "curated" if translation else ""
    if not translation and cache:
        translation = cache.get(normalize(english), "")
        tier = "cached" if translation else ""
    if not translation:
        words = [row["target"] for row in vocab if row.get("target")]
        if words:
            translation = " · ".join(words)
            tier = "lexicon"
        else:
            translation = english
            tier = "english"
    return {
        "text": english,
        "translation": translation,
        "tier": tier,
        "note": TIER_NOTES[tier],
        "vocabulary": vocab,
    }


def _line_display(
    raw: dict[str, Any],
    language: str,
    *,
    cache: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Pick the on-screen original + translation for a bilingual karaoke line."""
    lang = validate_language(language)
    text = str(raw.get("text") or "").strip()
    text_en = str(raw.get("text_en") or text).strip()
    text_km = str(raw.get("text_km") or "").strip()

    if lang == "km" and text_km:
        return {
            "text": text,
            "translation": text_km,
            "tier": "curated",
            "note": "Khmer line (source script or hand gloss).",
            "vocabulary": vocabulary_for_line(text_en, lang),
        }
    if lang == "en":
        return {
            "text": text,
            "translation": text_en,
            "tier": "english",
            "note": TIER_NOTES["english"],
            "vocabulary": vocabulary_for_line(text_en, lang),
        }
    # Translate from the English gloss so Khmer script is never fed to Latin tiers.
    return _translate_text(text_en, lang, cache=cache)


def _fill_llm_gaps(
    cache_key: str,
    language: str,
    rows: list[dict[str, Any]],
    *,
    allow_llm: bool,
) -> None:
    if language == "en" or not allow_llm:
        return
    cache = _load_cache(cache_key, language)
    missing: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row["tier"] in {"lexicon", "english"}:
            key = normalize(row["text"])
            if key and key not in seen:
                seen.add(key)
                missing.append(row["text"])
    if not missing:
        return
    fresh = _xai_translate(missing, language)
    if not fresh:
        return
    cache.update(fresh)
    _save_cache(cache_key, language, cache)
    for row in rows:
        if row["tier"] in {"lexicon", "english"}:
            got = fresh.get(normalize(row["text"]), "")
            if got:
                row["translation"] = got
                row["tier"] = "llm"
                row["note"] = TIER_NOTES["llm"]


def resolve_embed(
    embed: dict[str, Any],
    language: str = "en",
    *,
    allow_llm: bool = True,
) -> dict[str, Any]:
    """Attach translations, questions and the playable embed URL to one video."""
    lang = validate_language(language)
    embed_id = str(embed.get("embed_id") or "")
    cache = _load_cache(f"embed-{embed_id}", lang) if lang != "en" else {}
    youtube_id = str(embed.get("youtube_id") or "")
    verses_out: list[dict[str, Any]] = []
    text_rows: list[dict[str, Any]] = []

    for raw in embed.get("verses") or []:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        text_en = str(raw.get("text_en") or text).strip()
        text_km = str(raw.get("text_km") or "").strip()
        translated = _line_display(raw, lang, cache=cache)
        text_rows.append(translated)
        questions: list[dict[str, Any]] = []
        for q in raw.get("questions") or []:
            if not isinstance(q, dict):
                continue
            prompt = str(q.get("prompt") or "").strip()
            answer = str(q.get("answer") or text_en).strip()
            prompt_tr = _translate_text(prompt, lang, cache=cache)
            answer_tr = _line_display(
                {
                    "text": answer,
                    "text_en": answer,
                    "text_km": text_km if answer == text_en else "",
                    "source_lang": "en",
                },
                lang,
                cache=cache,
            )
            text_rows.extend([prompt_tr, answer_tr])
            questions.append(
                {
                    "kind": str(q.get("kind") or "vocabulary"),
                    "prompt": prompt,
                    "prompt_translation": prompt_tr["translation"],
                    "prompt_tier": prompt_tr["tier"],
                    "answer": answer,
                    "answer_translation": answer_tr["translation"],
                    "answer_tier": answer_tr["tier"],
                }
            )
        terms = [str(t) for t in (raw.get("terms") or []) if t]
        vocab = vocabulary_for_line(text_en, lang)
        for term in terms:
            if not any(row.get("en") == term for row in vocab):
                target = gloss(term, lang) if lang != "en" else term
                vocab.append({"en": term, "target": target or term})
        verses_out.append(
            {
                "verse_no": int(raw.get("verse_no") or len(verses_out) + 1),
                "section": str(raw.get("section") or ""),
                "source_lang": str(raw.get("source_lang") or "en"),
                "start_sec": float(raw.get("start_sec") or 0),
                "pause_sec": float(raw.get("pause_sec") or 0),
                "text": text,
                "text_en": text_en,
                "text_km": text_km,
                "translation": translated["translation"],
                "tier": translated["tier"],
                "note": translated["note"],
                "focus": str(raw.get("focus") or "vocabulary"),
                "terms": terms,
                "vocabulary": vocab,
                "questions": questions,
            }
        )

    _fill_llm_gaps(f"embed-{embed_id}", lang, text_rows, allow_llm=allow_llm)
    # text_rows is [verse, prompt, answer, prompt, answer, ...] per verse.
    cursor = 0
    for verse in verses_out:
        tr = text_rows[cursor]
        verse["translation"] = tr["translation"]
        verse["tier"] = tr["tier"]
        verse["note"] = tr["note"]
        cursor += 1
        for question in verse["questions"]:
            prompt_tr = text_rows[cursor]
            answer_tr = text_rows[cursor + 1]
            question["prompt_translation"] = prompt_tr["translation"]
            question["prompt_tier"] = prompt_tr["tier"]
            question["answer_translation"] = answer_tr["translation"]
            question["answer_tier"] = answer_tr["tier"]
            cursor += 2

    video_file = str(embed.get("video_file") or "").strip()
    video_url = ""
    if video_file:
        safe = Path(video_file).name
        if safe == video_file and (video_dir() / safe).is_file():
            video_url = f"/api/music/video/{safe}"
    elif str(embed.get("url") or "").startswith("/api/music/video/"):
        video_url = str(embed["url"])

    return {
        "embed_id": embed_id,
        "kind": str(embed.get("kind") or "video"),
        "youtube_id": youtube_id,
        "video_file": video_file,
        "video_url": video_url,
        "title": str(embed.get("title") or ""),
        "channel": str(embed.get("channel") or ""),
        "url": str(embed.get("url") or video_url or ""),
        "playlist_url": str(embed.get("playlist_url") or ""),
        "embed_url": embed_url(youtube_id) if youtube_id else "",
        "thumbnail_url": (
            f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg" if youtube_id else ""
        ),
        "duration_sec": float(embed.get("duration_sec") or 0),
        "language": lang,
        "language_name": language_name(lang),
        "topic": str(embed.get("topic") or ""),
        "note": str(embed.get("note") or ""),
        "verse_count": len(verses_out),
        "pause_points": len(verses_out),
        "verses": verses_out,
        "has_pause_ask": bool(verses_out),
        "bilingual": any(
            str(v.get("source_lang") or "") == "km" for v in verses_out
        ),
    }


def list_embeds(language: str = "en", *, allow_llm: bool = False) -> list[dict[str, Any]]:
    """Catalogue rows (playlist entries keep empty verses but stay listable)."""
    lang = validate_language(language)
    rows: list[dict[str, Any]] = []
    for embed in load_embeds():
        resolved = resolve_embed(embed, lang, allow_llm=allow_llm)
        rows.append(
            {
                "embed_id": resolved["embed_id"],
                "kind": resolved["kind"],
                "title": resolved["title"],
                "channel": resolved["channel"],
                "url": resolved["url"],
                "playlist_url": resolved["playlist_url"],
                "embed_url": resolved["embed_url"],
                "video_url": resolved.get("video_url") or "",
                "thumbnail_url": resolved["thumbnail_url"],
                "duration_sec": resolved["duration_sec"],
                "topic": resolved["topic"],
                "note": resolved["note"],
                "verse_count": resolved["verse_count"],
                "has_pause_ask": resolved["has_pause_ask"],
                "bilingual": resolved.get("bilingual", False),
            }
        )
    return rows


def _verse_or_first(embed: dict[str, Any], verse_no: int | None) -> dict[str, Any] | None:
    verses = [v for v in (embed.get("verses") or []) if isinstance(v, dict)]
    if not verses:
        return None
    if verse_no is None:
        return verses[0]
    return next((v for v in verses if int(v.get("verse_no") or 0) == verse_no), verses[0])


def explain_verse(
    embed_id: str,
    verse_no: int | None,
    language: str,
    *,
    allow_llm: bool = True,
) -> dict[str, Any]:
    """Meaning, translation, vocabulary and worked questions for one verse."""
    raw = get_embed(embed_id)
    resolved = resolve_embed(raw, language, allow_llm=allow_llm)
    verse = _verse_or_first(resolved, verse_no)
    if verse is None:
        raise ValueError(f"Embed '{embed_id}' has no verses to explain")
    examples: list[dict[str, str]] = []
    for term in terms_in_line(verse["text"]):
        sentence = EXAMPLES.get(term, "")
        if sentence:
            examples.append(
                {
                    "term_en": term,
                    "term_target": gloss(term, resolved["language"]),
                    "example_en": sentence,
                }
            )
    return {
        "embed_id": embed_id,
        "title": resolved["title"],
        "verse_no": verse["verse_no"],
        "text": verse["text"],
        "focus": verse["focus"],
        "language": resolved["language"],
        "language_name": resolved["language_name"],
        "translation": verse["translation"],
        "tier": verse["tier"],
        "vocabulary": verse["vocabulary"],
        "examples": examples[:3],
        "questions": verse["questions"],
    }


def _fallback_embed_answer(question: str, detail: dict[str, Any]) -> str:
    q = (question or "").lower()
    text = detail["text"]
    target = detail["translation"]
    lang_name = detail["language_name"]
    qs = detail.get("questions") or []

    for row in qs:
        prompt = str(row.get("prompt") or "").lower()
        kind = str(row.get("kind") or "")
        if prompt and (prompt in q or any(w in q for w in prompt.split() if len(w) > 4)):
            ans = row.get("answer_translation") or row.get("answer") or ""
            if ans:
                return str(ans)
        if kind and kind in q and (row.get("answer_translation") or row.get("answer")):
            return str(row.get("answer_translation") or row["answer"])

    parts: list[str] = [
        f'This verse says: "{text}".',
        f"In {lang_name}: {target}.",
    ]
    if any(w in q for w in ("grammar", "tense", "structure", "why")):
        parts.append(
            f"Focus: {detail.get('focus') or 'grammar'}. Look at the verbs and "
            "word order in the English line, then compare the translation."
        )
    elif any(w in q for w in ("vocab", "word", "mean", "phrase")):
        vocab = [row for row in detail.get("vocabulary") or [] if row.get("target")]
        if vocab:
            chips = ", ".join(f"{row['en']} → {row['target']}" for row in vocab[:4])
            parts.append(f"Key words: {chips}.")
    if qs:
        first = qs[0]
        parts.append(
            f"Try this prompt: {first.get('prompt_translation') or first.get('prompt')}"
        )
    return " ".join(parts)


def ask_verse(
    embed_id: str,
    question: str,
    *,
    verse_no: int | None = None,
    language: str = "en",
    allow_llm: bool = True,
) -> dict[str, Any]:
    """Ask about the current verse — Grok when keyed, otherwise grounded fallback."""
    detail = explain_verse(embed_id, verse_no, language, allow_llm=allow_llm)
    q = (question or "").strip()
    if not q:
        raise ValueError("Question is empty")
    grounding = (
        f"YouTube lesson: {detail['title']}\n"
        f"Verse {detail['verse_no']}: {detail['text']}\n"
        f"Translation ({detail['language_name']}): {detail['translation']}\n"
        f"Focus: {detail['focus']}\n"
        "Prepared teaching Q&A:\n"
        + "\n".join(
            f"- ({row['kind']}) {row['prompt']} → {row['answer']}"
            for row in detail["questions"]
        )
    )
    answer = ""
    source = "fallback"
    if allow_llm and os.getenv("XAI_API_KEY", "").strip():
        answer = _xai_embed_answer(q, grounding, detail["language"])
        if answer:
            source = "llm"
    if not answer:
        answer = _fallback_embed_answer(q, detail)
    return {
        "embed_id": embed_id,
        "verse_no": detail["verse_no"],
        "question": q,
        "answer": answer,
        "source": source,
        "language": detail["language"],
        "language_name": detail["language_name"],
        "cited_verse": {
            "verse_no": detail["verse_no"],
            "text": detail["text"],
            "translation": detail["translation"],
        },
        "questions": detail["questions"],
    }


def _xai_embed_answer(question: str, grounding: str, language: str) -> str:
    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        return ""
    base = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    model = os.getenv("XAI_MODEL", XAI_DEFAULT_MODEL).strip() or XAI_DEFAULT_MODEL
    try:
        timeout = float(os.getenv("XAI_TIMEOUT_S", "40") or 40)
    except ValueError:
        timeout = 40.0
    name = language_name(language)
    payload = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 420,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a warm language teacher inside a YouTube pause-and-ask "
                    "lesson. Answer only from the verse and prepared Q&A given to you. "
                    "Cover grammar and vocabulary plainly in at most three short "
                    f"sentences, then one reusable example. Reply in {name} "
                    "(add English in brackets when the learner language is not English)."
                ),
            },
            {"role": "user", "content": f"{grounding}\n\nLearner asks: {question}"},
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"]).strip()
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
        return ""
