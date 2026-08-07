"""Adapt Theodore's teach/present delivery to learner profile scores."""

from __future__ import annotations

from .types import CourseSlide, LearnerProfileScores, TeachTurn


def adapt_slide(slide: CourseSlide, profile: LearnerProfileScores) -> TeachTurn:
    """Reshape display + narration without rewriting the source course file."""
    adaptations: list[str] = []
    body = slide.body
    narration = slide.narration or slide.body

    if profile.fatigue >= 0.55 or profile.attention <= 0.4:
        # Shorter turns when tired / low attention.
        body = _first_sentences(body, 1)
        narration = _first_sentences(narration, 1)
        adaptations.append("shorten_for_fatigue_or_low_attention")

    if profile.confusion >= 0.55 or profile.literacy <= 0.4:
        narration = (
            f"Let's take this slowly. {narration} "
            "In plain terms: focus on the main idea first, then the details."
        )
        adaptations.append("simplify_for_confusion_or_literacy")

    if profile.accessibility_need >= 0.6:
        narration = (
            f"{narration} I will also repeat the key phrase: {slide.title}."
        )
        adaptations.append("repeat_key_phrase_for_accessibility")

    if profile.pace_preference >= 0.7 and profile.fatigue < 0.4:
        narration = narration  # keep full
        adaptations.append("keep_full_pace")
    elif profile.pace_preference <= 0.35:
        narration = f"Pause with me for a beat. {narration}"
        adaptations.append("slow_pace_pref")

    if profile.engagement >= 0.75 and profile.confusion < 0.35:
        narration = f"{narration} You're tracking well — stay with this."
        adaptations.append("affirm_high_engagement")

    return TeachTurn(
        slide_index=slide.index,
        title=slide.title,
        display_body=body,
        narration=narration,
        adaptations_applied=adaptations,
        profile_snapshot=profile,
    )


def _first_sentences(text: str, n: int) -> str:
    parts = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
    if not parts:
        return text
    clipped = ". ".join(parts[:n]).strip()
    if not clipped.endswith("."):
        clipped += "."
    return clipped
