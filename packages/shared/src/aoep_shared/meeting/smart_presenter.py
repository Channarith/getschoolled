"""Smart AI presenter: realistic delivery, summarization, and time-aware pacing.

Goes beyond reading slide text verbatim:
  - Digresses with examples, real-world links, and optional RAG asides
  - Summarizes dense slides instead of reading every bullet
  - Tracks class time remaining and skips / compresses when behind schedule
"""

from __future__ import annotations

import re
from typing import Callable, List, Optional, Sequence

from ..presentation_skills import apply_technique
from .base import PresentationPlan, PresentationStep
from .presenter import DEFAULT_WPM, build_presentation_plan, estimate_seconds

_MAX_WORDS_BEFORE_SUMMARY = 110
_SUMMARY_TARGET_WORDS = 52
_SKIP_ANNOUNCE_SECONDS = 4.0
_TIME_CRUNCH_WORDS = 28  # minimum words for a spoken time-warning

_CATEGORY_FROM_TITLE = (
    ("try it", "exercise"),
    ("example", "example"),
    ("recap", "recap"),
    ("welcome", "introduction"),
    ("quick recap", "recap"),
    ("you did it", "summary"),
)


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _guess_category(heading: str, kind: str) -> str:
    h = (heading or "").lower()
    for needle, cat in _CATEGORY_FROM_TITLE:
        if needle in h:
            return cat
    if kind == "intro":
        return "introduction"
    if kind == "outro":
        return "summary"
    return "concept"


def summarize_narration(text: str, *, target_words: int = _SUMMARY_TARGET_WORDS) -> str:
    """Compress long narration for spoken delivery."""
    text = (text or "").strip()
    if _word_count(text) <= target_words:
        return text
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    kept: List[str] = []
    count = 0
    for s in sentences[:5]:
        w = _word_count(s)
        if count + w > target_words and kept:
            break
        kept.append(s)
        count += w
    if not kept:
        words = text.split()
        body = " ".join(words[:target_words])
    else:
        body = " ".join(kept)
    if _word_count(body) >= _word_count(text):
        body = " ".join((text or "").split()[:target_words])
    return (
        f"{body} "
        f"I'll keep the extra detail on the slide — scan it when you review."
    ).strip()


def _is_script_final(kind: str, category: str, heading: str) -> bool:
    """Harvest/teach already wrote the spoken script — do not stack techniques again."""
    if kind in ("intro", "outro"):
        return True
    if category in ("summary", "recap"):
        return True
    h = (heading or "").lower()
    return "you did it" in h or h.startswith("welcome")


def _digression_prefix(*, topic: str, heading: str, category: str, narration: str = "") -> str:
    if category in ("summary", "recap"):
        return ""
    point = heading or topic
    combined = f"{heading} {narration}"
    if category == "example":
        if re.search(r"\d\s*[+\-=*/]|=\s*\d|[A-Za-z]\s*[+\-]\s*[A-Za-z]", combined):
            return ""
        return apply_technique("chunking", topic=topic, point=point)
    if category in ("exercise", "quiz"):
        return apply_technique("check_understanding", topic=topic, point=point)
    if category in ("introduction", "history"):
        return apply_technique("hook_story", topic=topic, point=point)
    if category == "recap":
        return apply_technique("recap", topic=topic, point=point)
    # Light digression — not every slide
    return apply_technique("real_world_link", topic=topic, point=point)


def _rag_aside(topic: str, heading: str, search_fn: Optional[Callable[[str], Sequence]]) -> str:
    if not search_fn:
        return ""
    try:
        hits = search_fn(f"{topic} {heading}")
        if hits:
            body = getattr(hits[0], "body", None) or hits[0].get("body", "")
            if body:
                return f"Related idea worth connecting: {str(body)[:180].rstrip()}."
    except Exception:
        pass
    return ""


def enrich_spoken_narration(
    narration: str,
    *,
    topic: str,
    heading: str,
    kind: str,
    category: Optional[str] = None,
    allow_digression: bool = True,
    rag_search: Optional[Callable[[str], Sequence]] = None,
    profile=None,
) -> str:
    """Build realistic spoken script: optional digression/RAG on top of lesson narration."""
    text = (narration or "").strip()
    if not text:
        return ""
    cat = category or _guess_category(heading, kind)
    if _is_script_final(kind, cat, heading):
        return text

    if profile is not None and getattr(profile, "arc", "") == "lewin":
        if cat in ("demo", "example", "introduction") or kind == "intro":
            from ..harvest.lewin_pedagogy import enrich_lewin_narration
            phase = "opening" if kind == "intro" else ("climax" if cat == "demo" else "build")
            base = enrich_lewin_narration(
                text,
                topic=topic,
                heading=heading,
                category=cat,
                phase=phase,
            )
        else:
            base = text
    else:
        # Lesson narration is already presentation-skilled at harvest time.
        base = text
    parts: List[str] = []
    if allow_digression and kind == "segment" and cat in (
        "concept", "example", "demo", "introduction", "history",
    ):
        dig = _digression_prefix(topic=topic, heading=heading, category=cat, narration=text)
        if dig and dig not in base:
            parts.append(dig)
    parts.append(base)
    aside = _rag_aside(topic, heading, rag_search)
    if aside and aside not in base:
        parts.append(aside)
    spoken = " ".join(p for p in parts if p).strip()
    if _word_count(spoken) > _MAX_WORDS_BEFORE_SUMMARY:
        spoken = summarize_narration(spoken)
    return spoken


def _time_warning(remaining_min: float, slides_left: int) -> str:
    m = max(1, int(round(remaining_min)))
    return (
        f"Quick time check — we have about {m} minute{'s' if m != 1 else ''} left "
        f"and {slides_left} slide{'s' if slides_left != 1 else ''} to go. "
        f"I'll hit the highlights now; you can revisit skipped parts in the deck anytime."
    )


def _apply_time_budget(
    steps: List[PresentationStep],
    *,
    budget_seconds: float,
    topic: str,
    profile=None,
) -> None:
    """Mutate steps in place to fit ``budget_seconds`` (skip / summarize / fast)."""
    from .presentation_matrix import PresentationProfile

    prof = profile or PresentationProfile.resolve()
    total = sum(s.est_seconds for s in steps)
    if total <= budget_seconds:
        return

    # Pass 1: skip low-priority beats (try-it, recap) with a spoken note.
    skip_markers = ("try it", "quick recap", "practice:")
    if prof.arc == "lewin":
        skip_markers = ("quick recap",)  # protect demos and try-it predict beats
    if prof.skip_try_it_live:
        skip_markers = ("try it", "quick recap", "practice:", "exercise", "quiz")
    if prof.aggressive_time_skip:
        skip_markers = skip_markers + ("example", "demo", "resources")
    for step in steps:
        if total <= budget_seconds:
            break
        h = step.heading.lower()
        if step.kind in ("intro", "outro"):
            continue
        if not any(m in h for m in skip_markers):
            continue
        saved = step.est_seconds
        step.action = "skip"
        step.spoken_narration = (
            f"I'm going to skip '{step.heading}' so we finish on time — "
            f"it's great practice material when you review the slides later."
        )
        step.est_seconds = _SKIP_ANNOUNCE_SECONDS
        step.presenter_meta = "time_skip"
        total -= max(0, saved - step.est_seconds)

    # Pass 2: summarize remaining long segments.
    for step in steps:
        if total <= budget_seconds:
            break
        if step.action == "skip":
            continue
        spoken = step.spoken_narration or step.narration
        if _word_count(spoken) <= 45:
            continue
        old = step.est_seconds
        step.spoken_narration = summarize_narration(spoken, target_words=38)
        step.action = "summarize"
        step.est_seconds = estimate_seconds(step.spoken_narration)
        step.presenter_meta = "time_summarize"
        total -= max(0, old - step.est_seconds)

    # Pass 3: accelerate remaining segments + offer resume later.
    if total > budget_seconds:
        remaining = [s for s in steps if s.action not in ("skip",)]
        slides_left = len(remaining)
        remaining_min = budget_seconds / 60.0
        warn = _time_warning(remaining_min, slides_left)
        # Attach warning to first not-yet-spoken segment after intro.
        for step in steps:
            if step.kind == "intro":
                continue
            if step.action != "skip":
                step.spoken_narration = f"{warn} {step.spoken_narration or step.narration}"
                step.presenter_meta = "time_crunch_warning"
                break
        pace = min(2.2, max(1.25, total / max(budget_seconds, 30)))
        for step in steps:
            if step.action == "skip" or step.kind == "outro":
                continue
            step.pace_multiplier = pace
            step.action = "fast" if step.action == "speak" else step.action
            if pace >= 1.6 and "pick up" not in (step.spoken_narration or ""):
                step.spoken_narration = (
                    f"{step.spoken_narration or step.narration} "
                    f"We can continue the rest whenever it's convenient for you."
                ).strip()
            step.est_seconds = max(
                _SKIP_ANNOUNCE_SECONDS,
                estimate_seconds(step.spoken_narration or step.narration) / pace,
            )


def build_smart_presentation_plan(
    lesson,
    *,
    duration_min: Optional[int] = None,
    elapsed_min: float = 0.0,
    wpm: int = DEFAULT_WPM,
    rag_search: Optional[Callable[[str], Sequence]] = None,
    enable_time_budget: bool = True,
    profile=None,
) -> PresentationPlan:
    """Build a time-aware, realistically narrated presentation plan."""
    from .presentation_matrix import PresentationProfile

    prof = profile or PresentationProfile.resolve()
    if prof.voice == "verbatim":
        return build_presentation_plan(lesson, wpm=int(wpm * prof.wpm_factor))

    effective_wpm = max(80, int(wpm * prof.wpm_factor))
    base = build_presentation_plan(lesson, wpm=effective_wpm)
    topic = getattr(lesson, "title", "Lesson")
    smart_steps: List[PresentationStep] = []

    for step in base.steps:
        cat = _guess_category(step.heading, step.kind)
        treatment = prof.treatment_for(cat)
        allow_dig = prof.allow_digression and treatment in ("digress", "interact", "speak")
        spoken = enrich_spoken_narration(
            step.narration,
            topic=topic,
            heading=step.heading,
            kind=step.kind,
            category=cat,
            allow_digression=allow_dig and step.kind == "segment",
            rag_search=rag_search if prof.media_first or treatment == "media" else None,
            profile=prof,
        )
        action = "speak"
        meta = ""
        if prof.auto_summarize or treatment == "summarize":
            skip_sum = prof.arc == "lewin" and cat in ("demo", "example")
            if not skip_sum and _word_count(spoken) > 45:
                spoken = summarize_narration(spoken)
                action = "summarize"
                meta = "matrix_summarize"
        if treatment == "skip" and step.kind not in ("intro", "outro"):
            action = "skip"
            spoken = (
                f"I'll skip '{step.heading}' in this session — "
                f"it's in the deck for when you review on your own."
            )
            meta = "matrix_skip"
        elif prof.socratic_prompts and treatment == "interact":
            spoken = f"{spoken} What's your first instinct here — take ten seconds.".strip()
        est = _SKIP_ANNOUNCE_SECONDS if action == "skip" else estimate_seconds(spoken, wpm=effective_wpm)
        smart_steps.append(PresentationStep(
            order=step.order,
            kind=step.kind,
            heading=step.heading,
            narration=step.narration,
            on_screen_points=list(step.on_screen_points),
            est_seconds=est,
            slide_index=step.slide_index,
            spoken_narration=spoken,
            action=action,
            pace_multiplier=1.0,
            presenter_meta=meta,
        ))

    time_on = enable_time_budget and prof.enable_time_budget
    if time_on and duration_min is not None and duration_min > 0:
        budget = max(30.0, duration_min * 60.0 - elapsed_min * 60.0)
        _apply_time_budget(smart_steps, budget_seconds=budget, topic=topic, profile=prof)

    return PresentationPlan(title=base.title, steps=smart_steps)


def corpus_rag_search(query: str, *, top_k: int = 2):
    """Optional RAG hook: search the harvest corpus for presenter asides."""
    try:
        from ..harvest.corpus_store import HarvestCorpusStore
        return HarvestCorpusStore().search(query, top_k=top_k)
    except Exception:
        return []
