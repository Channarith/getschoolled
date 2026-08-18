"""Deterministic, offline movement and lip-sync direction for Theodore."""

from __future__ import annotations

import re

from .driver_avatar_cues import DRIVER_AVATAR_CUES, CueRow
from .food_avatar_cues import FOOD_AVATAR_CUES
from .types import AvatarCue, AvatarScript, AvatarViseme, CourseSlide

_TOKEN_RE = re.compile(r"[\w'-]+|[\u1780-\u17ff]|[\u3400-\u9fff]", re.UNICODE)
_VOWELS = {
    "a": "aa",
    "e": "ee",
    "i": "ee",
    "o": "oh",
    "u": "oh",
    "y": "ee",
}


def narration_duration(text: str) -> float:
    """Estimate speech duration for timeline planning before TTS metadata arrives."""
    tokens = _TOKEN_RE.findall(text or "")
    if not tokens:
        return 2.4
    latin_words = [token for token in tokens if len(token) > 1 and token.isascii()]
    # Khmer/Han are matched per character; do not pace them like Latin words.
    non_latin = [token for token in tokens if not token.isascii()]
    if non_latin and len(non_latin) >= max(1, len(latin_words)):
        return max(
            2.4,
            min(90.0, len(non_latin) / 11.0 + len(latin_words) / 2.45 + 0.7),
        )
    if latin_words:
        return max(2.4, min(90.0, len(tokens) / 2.45 + 0.7))
    return max(2.4, min(90.0, len(tokens) / 4.2 + 0.7))


def _shape(token: str) -> str:
    value = token.casefold()
    if value.startswith(("m", "b", "p")):
        return "mbp"
    if value.startswith(("f", "v")):
        return "fv"
    if value.startswith("l"):
        return "l"
    if value.startswith(("w", "q")):
        return "wq"
    for char in value:
        if char in _VOWELS:
            return _VOWELS[char]
    # Khmer and Han syllables use an open/rounded alternating shape.
    if any("\u1780" <= char <= "\u17ff" for char in value):
        return "aa"
    if any("\u3400" <= char <= "\u9fff" for char in value):
        return "oh"
    return "rest"


def visemes_for_text(text: str, duration_s: float) -> list[AvatarViseme]:
    tokens = _TOKEN_RE.findall(text or "")
    if not tokens:
        return [AvatarViseme(at_s=0, shape="rest", weight=0)]
    usable = max(0.4, duration_s - 0.3)
    step = usable / len(tokens)
    rows = [
        AvatarViseme(
            at_s=round(0.12 + i * step, 3),
            shape=_shape(token),
            weight=0.86,
        )
        for i, token in enumerate(tokens)
    ]
    rows.append(AvatarViseme(at_s=round(min(duration_s, 0.12 + len(tokens) * step), 3), shape="rest", weight=0))
    return rows


def _cue_rows(rows: tuple[CueRow, ...], duration_s: float) -> list[AvatarCue]:
    cues: list[AvatarCue] = []
    for start, duration, gesture, gaze, hand, intensity, expression in rows:
        start_s = min(duration_s - 0.1, max(0.0, start * duration_s))
        available = max(0.1, duration_s - start_s)
        # AvatarCue.duration_s is capped at 30s; long Khmer narrations scale
        # fractional cue rows past that, so clamp before validation.
        cue_dur = min(30.0, available, max(0.1, duration * duration_s))
        cues.append(
            AvatarCue(
                start_s=round(start_s, 3),
                duration_s=round(cue_dur, 3),
                gesture=gesture,
                gaze=gaze,
                hand=hand,
                intensity=intensity,
                expression=expression,
                target="slide" if gaze == "slide" else "learner",
            )
        )
    return cues


def _infer_rows(slide: CourseSlide) -> tuple[CueRow, ...]:
    text = f"{slide.title} {slide.body} {slide.activity_prompt}".casefold()
    first = "explain"
    expression = "warm"
    gaze = "learner"
    if any(word in text for word in ("warning", "danger", "never", "emergency", "dui")):
        first, expression = "caution", "serious"
    elif any(word in text for word in ("compare", "versus", "difference", "separate")):
        first = "compare"
    elif any(word in text for word in ("steps", "seconds", "first", "three", "list")):
        first = "count"
    elif slide.picture_url or slide.video_url:
        first, gaze = "point-to-slide", "slide"
    second = "ask" if slide.activity_prompt else "open-palm"
    return (
        (0.04, 0.4, first, gaze, "right", 0.78, expression),
        (0.52, 0.32, second, "learner", "left", 0.68, "encouraging"),
        (0.86, 0.12, "transition", "learner", "none", 0.42, "warm"),
    )


def avatar_script_for_slide(
    slide: CourseSlide,
    *,
    narration: str | None = None,
) -> AvatarScript:
    """Return explicit, curated, or inferred choreography for a slide."""
    spoken = (narration if narration is not None else slide.narration) or slide.body
    duration = narration_duration(spoken)
    if slide.avatar_script is not None:
        explicit = slide.avatar_script.model_copy(deep=True)
        explicit.source = "explicit"
        explicit.duration_s = max(explicit.duration_s, duration)
        if not explicit.visemes:
            explicit.visemes = visemes_for_text(spoken, explicit.duration_s)
        validate_avatar_script(explicit)
        return explicit

    rows = (
        DRIVER_AVATAR_CUES.get(slide.slide_key)
        or FOOD_AVATAR_CUES.get(slide.slide_key)
        or DRIVER_AVATAR_CUES.get(slide.title)
        or FOOD_AVATAR_CUES.get(slide.title)
    )
    source = "curated" if rows else "inferred"
    script = AvatarScript(
        state="presenting",
        duration_s=round(duration, 3),
        cues=_cue_rows(rows or _infer_rows(slide), duration),
        visemes=visemes_for_text(spoken, duration),
        source=source,
    )
    validate_avatar_script(script)
    return script


def validate_avatar_script(script: AvatarScript) -> None:
    """Reject choreography that would run beyond narration or overlap invalidly."""
    for cue in script.cues:
        if cue.start_s + cue.duration_s > script.duration_s + 0.01:
            raise ValueError(
                f"avatar cue {cue.gesture!r} ends after script duration "
                f"({cue.start_s + cue.duration_s:.2f} > {script.duration_s:.2f})"
            )
    for viseme in script.visemes:
        if viseme.at_s > script.duration_s + 0.01:
            raise ValueError(
                f"avatar viseme at {viseme.at_s:.2f}s exceeds duration {script.duration_s:.2f}s"
            )
