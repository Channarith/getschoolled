"""Speak and show a lesson in any supported language.

Curated slides stay as written. Everything else is translated at teach time
into the language the learner selected, then read with that language's voice.
If translation is unavailable the original words stay, and the voice follows
those words instead of reading them in the wrong language.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .studio_languages import normalize_language

_LATIN = re.compile(r"[A-Za-z]")
_BLOCKED_UNTIL = 0.0


@dataclass
class LocalizedLesson:
    applied: bool = False
    title: str = ""
    body: str = ""
    narration: str = ""
    activity: str = ""
    examples: list[str] = field(default_factory=list)
    provider: str = ""


def _mostly_latin(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    latin = sum(1 for char in letters if _LATIN.match(char))
    return latin / len(letters) >= 0.8


def translate_text(text: str, source: str, target: str) -> tuple[str, bool, str]:
    """Return (text, translated, provider). Never raises for a provider miss."""
    raw = (text or "").strip()
    src = normalize_language(source) or "en"
    dst = normalize_language(target) or "en"
    if not raw or src == dst:
        return raw, False, ""
    if dst != "en" and not _mostly_latin(raw):
        return raw, False, ""
    global _BLOCKED_UNTIL
    if time.monotonic() < _BLOCKED_UNTIL:
        return raw, False, ""
    try:
        from theodore_audio_translation_lab.providers import TranslationEngine

        engine = TranslationEngine()
        engine.timeout_s = min(float(engine.timeout_s or 8), 8.0)
        result = engine.translate(raw, src, dst)
    except Exception:  # noqa: BLE001 — a missed translation must not stop the lesson
        _BLOCKED_UNTIL = time.monotonic() + 45
        return raw, False, ""
    if not getattr(result, "translated", False):
        warning = str(getattr(result, "warning", "") or "").lower()
        if any(token in warning for token in ("unreachable", "tunnel", "403", "unavailable")):
            _BLOCKED_UNTIL = time.monotonic() + 45
        return raw, False, str(getattr(result, "provider", "") or "")
    translated = str(getattr(result, "text", "") or "").strip()
    if not translated:
        return raw, False, ""
    return translated, True, str(getattr(result, "provider", "") or "")


def localize_lesson(
    *,
    title: str,
    body: str,
    narration: str,
    activity: str = "",
    examples: list[str] | None = None,
    source_language: str,
    target_language: str,
) -> LocalizedLesson:
    """Translate the spoken lesson when the learner's language is not the slide's."""
    original = LocalizedLesson(
        title=title or "",
        body=body or "",
        narration=narration or "",
        activity=activity or "",
        examples=list(examples or []),
    )
    spoken, ok, provider = translate_text(narration or body or title, source_language, target_language)
    if not ok:
        return original
    title_text, title_ok, _ = translate_text(title, source_language, target_language)
    body_text, body_ok, _ = translate_text(body, source_language, target_language)
    activity_text, activity_ok, _ = translate_text(activity, source_language, target_language)
    next_examples: list[str] = []
    for example in original.examples:
        translated, example_ok, _ = translate_text(example, source_language, target_language)
        next_examples.append(translated if example_ok else example)
    return LocalizedLesson(
        applied=True,
        title=title_text if title_ok else (title or spoken),
        body=body_text if body_ok else spoken,
        narration=spoken,
        activity=activity_text if activity_ok else activity,
        examples=next_examples,
        provider=provider or "translated",
    )


def localize_quiz(quiz: object, language: str) -> None:
    """Translate Latin quiz copy into the lesson language. Choice indexes stay put."""
    target = normalize_language(language) or "en"
    if target == "en":
        return
    questions = getattr(quiz, "questions", None) or []
    for question in questions:
        prompt, ok, _provider = translate_text(getattr(question, "prompt", ""), "en", target)
        if not ok:
            continue
        question.prompt = prompt
        choices = []
        for choice in list(getattr(question, "choices", []) or []):
            translated, choice_ok, _provider = translate_text(choice, "en", target)
            choices.append(translated if choice_ok else choice)
        question.choices = choices
        explanation, explanation_ok, _provider = translate_text(
            getattr(question, "explanation", ""), "en", target
        )
        if explanation_ok:
            question.explanation = explanation
