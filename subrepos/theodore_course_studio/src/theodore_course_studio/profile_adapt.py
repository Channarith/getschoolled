"""Adapt Theodore's teach/present delivery to learner profile scores."""

from __future__ import annotations

import re

from .cert_i18n import CertScaffold, scaffold_for
from .cert_multimodal import preferred_modalities
from .types import CourseSlide, LearnerProfileScores, TeachTurn


def adapt_slide(slide: CourseSlide, profile: LearnerProfileScores) -> TeachTurn:
    """Reshape display + narration without rewriting the source course file."""
    adaptations: list[str] = []
    body = slide.body
    narration = slide.narration or slide.body
    examples = list(slide.examples or [])
    # These coaching lines only exist in English. Splicing them into a
    # translated narration is what made the audio drift out of the slide's
    # language, so on a translated slide we shape the delivery without them.
    spoken = (slide.spoken_language or "en").split("-")[0].lower()
    may_coach = spoken == "en"

    if profile.fatigue >= 0.55 or profile.attention <= 0.4:
        # Shorter turns when tired / low attention — keep one example if present.
        scaffold = scaffold_for(spoken)
        body = _first_sentences(_strip_examples_block(body, scaffold), 1)
        if examples:
            # Reuse the heading verbatim (it carries its own colon) so the block
            # we re-add is the one _strip_examples_block knows how to remove.
            heading = scaffold.examples_heading if scaffold else "Examples:"
            body = f"{body}\n\n{heading}\n1. {examples[0]}"
            adaptations.append("one_example_for_fatigue")
        narration = _first_sentences(narration, 1)
        adaptations.append("shorten_for_fatigue_or_low_attention")

    if may_coach and (profile.confusion >= 0.55 or profile.literacy <= 0.4):
        narration = (
            f"Let's take this slowly. {narration} "
            "In plain terms: focus on the main idea first, then the details."
        )
        adaptations.append("simplify_for_confusion_or_literacy")

    if may_coach and profile.accessibility_need >= 0.6:
        narration = (
            f"{narration} I will also repeat the key phrase: {slide.title}."
        )
        adaptations.append("repeat_key_phrase_for_accessibility")

    if profile.pace_preference >= 0.7 and profile.fatigue < 0.4:
        adaptations.append("keep_full_pace")
    elif profile.pace_preference <= 0.35:
        if may_coach:
            narration = f"Pause with me for a beat. {narration}"
        adaptations.append("slow_pace_pref")

    if profile.engagement >= 0.75 and profile.confusion < 0.35:
        if may_coach:
            narration = f"{narration} You're tracking well — stay with this."
        adaptations.append("affirm_high_engagement")

    # Multimodal nudges — content is always present; narration points at preferred path.
    prefs = preferred_modalities(profile.model_dump())
    top = prefs[:2] if prefs else []
    if "video" in top and slide.video_url:
        if may_coach:
            narration = (
                f"{narration} If you learn by watching, tap Watch video for the motion clip."
            )
        adaptations.append("nudge_video_learners")
    if "image" in top and slide.picture_url:
        adaptations.append("nudge_image_learners")
    if "examples" in top and examples:
        adaptations.append("nudge_example_learners")
    if "quiz" in top and slide.quiz_spec:
        if may_coach:
            narration = f"{narration} When you are ready, try the multiple-choice check."
        adaptations.append("nudge_quiz_learners")
    if "game" in top and slide.game_spec:
        if may_coach:
            narration = f"{narration} Or lock it in with a short game."
        adaptations.append("nudge_game_learners")
    if "text" in top:
        adaptations.append("nudge_text_learners")

    return TeachTurn(
        slide_index=slide.index,
        title=slide.title,
        display_body=body,
        narration=narration,
        spoken_language=spoken,
        adaptations_applied=adaptations,
        profile_snapshot=profile,
    )


def _strip_examples_block(body: str, scaffold: CertScaffold | None) -> str:
    """Drop the appended examples block, whichever language labelled it."""
    headings = {"Examples:"}
    if scaffold:
        headings.add(scaffold.examples_heading)
    for heading in headings:
        body = body.split(f"\n{heading}", 1)[0]
    return body.rstrip()


# "។" (khan) ends a Khmer sentence; splitting on "." alone never shortened one.
_SENTENCE_END = re.compile(r"[.។]+")


def _first_sentences(text: str, n: int) -> str:
    flat = text.replace("\n", " ")
    parts = [p.strip() for p in _SENTENCE_END.split(flat) if p.strip()]
    if not parts:
        return text
    stop = "។" if "។" in flat else "."
    clipped = f"{stop} ".join(parts[:n]).strip()
    if not clipped.endswith(stop):
        clipped += stop
    return clipped
