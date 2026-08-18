"""Pronunciation practice for lyric lines.

The browser captures what the learner said (Web Speech API or a typed attempt).
This module scores it against the expected line, lists missed/wrong words, and
returns coaching so the learner can try again — offline, no ASR on the server.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any

from .ask_ai import _focus_line, pronunciation_hint
from .catalog import Song
from .sing import VOICE_TAGS, speakable
from .timing import syllable_count
from .translations import language_name, translate_line, validate_language

# BCP-47 tags for browser SpeechRecognition (fall back to VOICE_TAGS).
REC_LANG: dict[str, str] = {
    **VOICE_TAGS,
    "zh": "zh-CN",
    "km": "km-KH",
    "he": "he-IL",
    "fa": "fa-IR",
    "bn": "bn-BD",
    "ur": "ur-PK",
    "sw": "sw-KE",
}


def _fold(text: str) -> str:
    """Lowercase, strip accents/punctuation, collapse spaces."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> list[str]:
    return [t for t in _fold(text).split() if t]


def _mouth_tip(text: str) -> str:
    folded = _fold(text)
    if not folded:
        return "Relax your mouth and start gently."
    first = folded[0]
    if first in "ao":
        return "Open your mouth wider for the opening vowel."
    if first in "ou":
        return "Round your lips for the 'oo' sound."
    if first in "ei":
        return "Spread your lips into a slight smile."
    if first in "mbp":
        return "Press your lips together, then release."
    if first in "fv":
        return "Touch your top teeth lightly to your bottom lip."
    if first in "tdnl":
        return "Put the tip of your tongue behind your top teeth."
    if first in "kg":
        return "Raise the back of your tongue toward the soft palate."
    return "Keep an even pace — clap once per syllable, then say the line."


def _word_diff(expected: list[str], heard: list[str]) -> list[dict[str, str]]:
    """Per-token status for teaching: ok / missed / extra / wrong."""
    matcher = difflib.SequenceMatcher(a=expected, b=heard)
    rows: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for w in expected[i1:i2]:
                rows.append({"word": w, "status": "ok", "heard": w})
        elif tag == "delete":
            for w in expected[i1:i2]:
                rows.append({"word": w, "status": "missed", "heard": ""})
        elif tag == "insert":
            for w in heard[j1:j2]:
                rows.append({"word": "", "status": "extra", "heard": w})
        elif tag == "replace":
            exp = expected[i1:i2]
            got = heard[j1:j2]
            for idx in range(max(len(exp), len(got))):
                e = exp[idx] if idx < len(exp) else ""
                h = got[idx] if idx < len(got) else ""
                if e and h:
                    rows.append({"word": e, "status": "wrong", "heard": h})
                elif e:
                    rows.append({"word": e, "status": "missed", "heard": ""})
                else:
                    rows.append({"word": "", "status": "extra", "heard": h})
    return rows


def _corrections(words: list[dict[str, str]], target: str) -> list[dict[str, str]]:
    """Human coaching chips for the words that need another try."""
    tips: list[dict[str, str]] = []
    for row in words:
        status = row["status"]
        if status == "ok":
            continue
        if status == "missed":
            w = row["word"]
            tips.append(
                {
                    "word": w,
                    "issue": "missed",
                    "tip": f'Say "{w}" — {syllable_count(w)} syllable'
                    f'{"s" if syllable_count(w) != 1 else ""}.',
                }
            )
        elif status == "wrong":
            tips.append(
                {
                    "word": row["word"],
                    "issue": "wrong",
                    "tip": f'You said "{row["heard"]}" — try "{row["word"]}" instead.',
                }
            )
        elif status == "extra":
            tips.append(
                {
                    "word": row["heard"],
                    "issue": "extra",
                    "tip": f'"{row["heard"]}" is not in this line — skip it.',
                }
            )
    if not tips and target:
        tips.append(
            {
                "word": "",
                "issue": "rhythm",
                "tip": "Close — slow down and match the beat of the song.",
            }
        )
    return tips[:6]


def score_attempt(target: str, heard: str) -> dict[str, Any]:
    """Score one spoken/typed attempt against an expected phrase."""
    expected = _tokens(target)
    got = _tokens(heard)
    ratio = (
        difflib.SequenceMatcher(a=" ".join(expected), b=" ".join(got)).ratio()
        if expected
        else 0.0
    )
    score = int(round(ratio * 100))
    words = _word_diff(expected, got)
    missed = [w["word"] for w in words if w["status"] == "missed" and w["word"]]
    wrong = [w["word"] for w in words if w["status"] == "wrong" and w["word"]]
    if score >= 90:
        verdict = "excellent"
        feedback = "Excellent — clear and accurate. Sing it with the track next."
    elif score >= 75:
        verdict = "great"
        feedback = "Great job — almost perfect. Polish the highlighted words."
    elif score >= 55:
        verdict = "good"
        feedback = "Good start — listen once, then try the missed words slowly."
    elif score >= 1:
        verdict = "retry"
        feedback = "Keep going — hear the model, then say the line one word at a time."
    else:
        verdict = "try"
        feedback = "Tap Hear model, then speak into the mic (or type what you said)."
    stars = 3 if score >= 85 else 2 if score >= 60 else 1 if score >= 1 else 0
    return {
        "score": score,
        "stars": stars,
        "passed": score >= 60,
        "verdict": verdict,
        "feedback": feedback,
        "target": target,
        "heard": (heard or "").strip(),
        "missed_words": missed,
        "wrong_words": wrong,
        "words": words,
        "corrections": _corrections(words, target),
        "mouth_tip": _mouth_tip(target),
        "syllables": pronunciation_hint(target),
    }


def check_pronunciation(
    song: Song,
    *,
    line_no: int | None,
    heard: str,
    language: str = "en",
    practice: str = "english",
    target_override: str = "",
) -> dict[str, Any]:
    """Score the learner against the lyric (English) or its translation."""
    lang = validate_language(language)
    mode = (practice or "english").strip().lower()
    if mode not in {"english", "translation"}:
        raise ValueError("practice must be 'english' or 'translation'")
    line = _focus_line(song, line_no)
    if line is None:
        raise ValueError("Song has no lines")

    english = (line.text or "").strip()
    translated = translate_line(line, lang)
    if (target_override or "").strip():
        target = target_override.strip()
    else:
        target = english if mode == "english" else (translated["translation"] or english)
    # Strip romanization / mid-dots so ASR-like typed input compares fairly.
    target_speak = speakable(target) if mode == "translation" else target
    result = score_attempt(target_speak, heard)

    rec_lang = REC_LANG.get(lang if mode == "translation" else "en", "en-US")
    return {
        "song_id": song.song_id,
        "title_en": song.title_en,
        "line_no": line.line_no,
        "section": line.section,
        "practice": mode,
        "language": lang if mode == "translation" else "en",
        "language_name": language_name(lang if mode == "translation" else "en"),
        "english": english,
        "translation": translated["translation"],
        "target": target_speak,
        "target_display": target,
        "model_speak": target_speak,
        "recognition_lang": rec_lang,
        "voice_tag": VOICE_TAGS.get(lang if mode == "translation" else "en", "en-US"),
        **result,
    }
