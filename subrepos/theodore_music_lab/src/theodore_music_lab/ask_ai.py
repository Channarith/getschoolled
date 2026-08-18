"""Ask-the-AI about any lyric line, at any time.

Two paths, same response shape:

* Grok/xAI when ``XAI_API_KEY`` is set — grounded with the focus line, its
  neighbours, and the line's translation so answers cannot drift off the song.
* A deterministic teacher fallback otherwise, built from the same grounding
  material (translation + key vocabulary + example sentence). The lab is
  offline-usable, so "no key" must still teach something true.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from .catalog import Song, SongLine
from .lexicon import EXAMPLES, gloss, terms_in_line
from .timing import syllable_count
from .translations import XAI_DEFAULT_MODEL, language_name, translate_line, validate_language

_CONTEXT_LINES = 2


def _focus_line(song: Song, line_no: int | None) -> SongLine | None:
    if not song.lines:
        return None
    if line_no is None:
        return song.lines[0]
    return next((ln for ln in song.lines if ln.line_no == line_no), song.lines[0])


def _neighbours(song: Song, line: SongLine) -> list[SongLine]:
    index = next((i for i, ln in enumerate(song.lines) if ln.line_no == line.line_no), 0)
    start = max(0, index - _CONTEXT_LINES)
    return song.lines[start : index + _CONTEXT_LINES + 1]


def pronunciation_hint(text: str) -> str:
    """Per-word syllable counts — a slow-reading cue for singing along."""
    parts = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    return " · ".join(f"{w} ({syllable_count(w)})" for w in parts)


def explain_line(song: Song, line_no: int | None, language: str) -> dict[str, Any]:
    """Meaning, translation, key vocabulary and worked examples for one line."""
    lang = validate_language(language)
    line = _focus_line(song, line_no)
    if line is None:
        raise ValueError("Song has no lines")
    translated = translate_line(line, lang)
    examples: list[dict[str, str]] = []
    for term in terms_in_line(line.text):
        sentence = EXAMPLES.get(term, "")
        if not sentence:
            continue
        examples.append(
            {
                "term_en": term,
                "term_target": gloss(term, lang),
                "example_en": sentence,
            }
        )
    return {
        "song_id": song.song_id,
        "title_en": song.title_en,
        "line_no": line.line_no,
        "text": line.text,
        "section": line.section,
        "language": lang,
        "language_name": language_name(lang),
        "meaning_en": translated["meaning_en"],
        "translation": translated["translation"],
        "tier": translated["tier"],
        "note": translated["note"],
        "vocabulary": translated["vocabulary"],
        "examples": examples[:3],
        "pronunciation": pronunciation_hint(line.text),
    }


def _grounding_text(song: Song, line: SongLine, language: str) -> str:
    rows = []
    for neighbour in _neighbours(song, line):
        marker = ">>" if neighbour.line_no == line.line_no else "  "
        rows.append(f"{marker} {neighbour.line_no}. {neighbour.text}")
    translated = translate_line(line, language)
    return (
        f"Song: {song.title_en} (topic: {song.topic})\n"
        f"Section: {line.section or 'verse'}\n"
        f"Lyrics around the question (>> is the focus line):\n" + "\n".join(rows) + "\n"
        f"Known translation of the focus line ({language_name(language)}): "
        f"{translated['translation']}"
    )


def _xai_answer(question: str, grounding: str, language: str) -> str:
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
        "max_tokens": 400,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a warm, plain-spoken language teacher inside a "
                    "learn-through-music lab. Answer only from the lyrics given to "
                    "you. Keep it to three short sentences, then add one example "
                    f"sentence a beginner could reuse. Reply in {name} "
                    "(add the English in brackets when the learner's language is "
                    "not English). Never invent lyrics that are not shown."
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


def _fallback_answer(question: str, detail: dict[str, Any]) -> str:
    """Deterministic, grounded teacher answer used when no LLM is reachable."""
    q = (question or "").lower()
    line = detail["text"]
    target = detail["translation"]
    lang_name = detail["language_name"]
    vocab = [row for row in detail["vocabulary"] if row.get("target")]
    example = detail["examples"][0]["example_en"] if detail["examples"] else ""

    # These songs are written in plain English, so the English "meaning" is often
    # the line itself — repeating it back would teach nothing.
    plain = re.sub(r"[^a-z0-9 ]+", "", line.lower()).strip()
    meaning = detail["meaning_en"]
    restates_line = re.sub(r"[^a-z0-9 ]+", "", meaning.lower()).strip() == plain

    parts: list[str] = []
    if any(word in q for word in ("other way", "another way", "different way", "paraphrase", "rephrase", "say the same")):
        parts.append(
            f'One clear way to say "{line}" in {lang_name} is: {target}.'
        )
        parts.append(
            "You can also shorten it, swap a synonym, or change the word order — "
            "open Other ways to say it for ready alternatives, then try one out loud."
        )
    elif any(word in q for word in ("pronounce", "pronunciation", "say it", "sing")):
        parts.append(f'"{line}" breaks into these syllables: {detail["pronunciation"]}.')
        parts.append("Clap once per syllable, then sing it with the track.")
    elif any(word in q for word in ("grammar", "why", "structure", "tense", "word order")):
        parts.append(
            f'"{line}" is a {detail["section"] or "verse"} line, so it keeps one '
            "simple pattern and repeats it — that is what makes it stick."
        )
        if not restates_line:
            parts.append(f"It means: {meaning}.")
    elif restates_line and detail["language"] == "en":
        parts.append(
            f'"{line}" is a {detail["section"] or "verse"} line — it says exactly '
            "what it means, so listen for the key words below."
        )
    elif restates_line:
        parts.append(f'"{line}" in {lang_name} is: {target}.')
    else:
        parts.append(f'"{line}" means: {meaning}.')
        parts.append(f"In {lang_name}: {target}.")

    if vocab:
        chips = ", ".join(f"{row['en']} = {row['target']}" for row in vocab[:4])
        parts.append(f"Key words here: {chips}.")
    if example:
        parts.append(f"Try saying: {example}")
    return " ".join(parts)


def ask(
    song: Song,
    question: str,
    *,
    line_no: int | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """Answer a learner question about the lyrics, with or without a network."""
    lang = validate_language(language)
    text = (question or "").strip()
    if not text:
        raise ValueError("Question is empty")
    detail = explain_line(song, line_no, lang)
    line = _focus_line(song, line_no)
    assert line is not None  # explain_line raises when the song has no lines

    answer = _xai_answer(text, _grounding_text(song, line, lang), lang)
    provider = "xai" if answer else "grounded-offline"
    if not answer:
        answer = _fallback_answer(text, detail)
    return {
        "song_id": song.song_id,
        "line_no": line.line_no,
        "question": text,
        "answer": answer,
        "provider": provider,
        "fallback_used": provider != "xai",
        "language": lang,
        "language_name": detail["language_name"],
        "cited_lines": [ln.line_no for ln in _neighbours(song, line)],
        "translation": detail["translation"],
        "vocabulary": detail["vocabulary"],
        "examples": detail["examples"],
    }
