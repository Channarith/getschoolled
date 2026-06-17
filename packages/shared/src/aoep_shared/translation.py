"""Phase 2 - multilingual delivery routing.

Given a lesson's language and the languages of the students in the room, decide
per student whether translation is needed, whether the language pair is
supported (ASR + NLLB cover all 26 supported languages), and which TTS engine
renders their language (native XTTS vs cloud-TTS fallback). Pure and testable;
the actual ASR/MT/TTS inference lives behind the SpeechProvider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .languages import SUPPORTED_LANGUAGES, tts_needs_fallback


def is_supported(language: str) -> bool:
    return language in SUPPORTED_LANGUAGES


def is_pair_supported(source: str, target: str) -> bool:
    """NLLB-200 covers translation between any two supported languages."""
    return is_supported(source) and is_supported(target)


def tts_engine_for(language: str) -> str:
    if not is_supported(language):
        raise ValueError(f"Unsupported language: {language}")
    return "cloud-tts-fallback" if tts_needs_fallback(language) else "xtts"


@dataclass
class DeliveryPlan:
    student_id: str
    language: str
    supported: bool          # language itself is supported at all
    translate: bool          # differs from lesson language -> needs MT
    translation_supported: bool
    tts_engine: str          # "xtts" | "cloud-tts-fallback" | "none"


def plan_delivery(
    lesson_language: str, students: Sequence[Tuple[str, str]]
) -> List[DeliveryPlan]:
    """Build a per-student delivery plan.

    ``students`` is a sequence of ``(student_id, language)`` pairs.
    """
    if not is_supported(lesson_language):
        raise ValueError(f"Unsupported lesson language: {lesson_language}")

    plans: List[DeliveryPlan] = []
    for student_id, language in students:
        supported = is_supported(language)
        translate = supported and language != lesson_language
        pair_ok = is_pair_supported(lesson_language, language) if supported else False
        engine = tts_engine_for(language) if supported else "none"
        plans.append(
            DeliveryPlan(
                student_id=student_id,
                language=language,
                supported=supported,
                translate=translate,
                translation_supported=pair_ok,
                tts_engine=engine,
            )
        )
    return plans


def unsupported_languages(languages: Sequence[str]) -> List[str]:
    return [lang for lang in languages if not is_supported(lang)]
