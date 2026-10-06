"""Deterministic presentation styles for Theodore course slides.

Forty-eight explicit styles, twelve in each family (narrative, picture, text,
challenge). Assignment scores the slide's words and assets, breaks remaining
ties with a stable hash of the slide key, and can step off the previous
slide's style so neighbors do not repeat.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .types import CourseSlide, ReducedMotionPolicy, StyleFamily, VisualMotion

STYLE_FAMILIES: tuple[StyleFamily, ...] = ("narrative", "picture", "text", "challenge")

# Scores within this band share a tie. Zero means only an exact top score is
# hashed; a one-point lead is already decisive.
_NEAR_TIE = 0
_PREFER_WEIGHTS = {"multi_media": 18}


@dataclass(frozen=True)
class StyleSpec:
    """One content-aware layout the director can assign."""

    style_id: str
    family: StyleFamily
    label: str
    summary: str
    keywords: tuple[str, ...] = ()
    requires: frozenset[str] = frozenset()
    prefers: frozenset[str] = frozenset()
    avoids: frozenset[str] = frozenset()
    motion: VisualMotion = "fade"
    reduced_motion: ReducedMotionPolicy = "static"
    layout: str = "stack"
    priority: int = 0


def _style(
    style_id: str,
    family: StyleFamily,
    label: str,
    summary: str,
    *,
    keywords: tuple[str, ...] = (),
    requires: frozenset[str] = frozenset(),
    prefers: frozenset[str] = frozenset(),
    avoids: frozenset[str] = frozenset(),
    motion: VisualMotion = "fade",
    reduced_motion: ReducedMotionPolicy = "static",
    layout: str = "stack",
    priority: int = 0,
) -> StyleSpec:
    return StyleSpec(
        style_id=style_id,
        family=family,
        label=label,
        summary=summary,
        keywords=keywords,
        requires=requires,
        prefers=prefers,
        avoids=avoids,
        motion=motion,
        reduced_motion=reduced_motion,
        layout=layout,
        priority=priority,
    )


_NARRATIVE: tuple[StyleSpec, ...] = (
    _style(
        "narrative-title-card",
        "narrative",
        "Title card",
        "A quiet opening card for one or two spoken lines.",
        prefers=frozenset({"short_text"}),
        motion="fade",
        layout="card",
        priority=2,
    ),
    _style(
        "narrative-story-arc",
        "narrative",
        "Story arc",
        "A longer narration that unfolds across several sentences.",
        prefers=frozenset({"long_text"}),
        avoids=frozenset({"short_text"}),
        motion="fade",
        reduced_motion="instant",
        layout="stack",
        priority=2,
    ),
    _style(
        "narrative-quote-pull",
        "narrative",
        "Quote pull",
        "A spoken line built around a quotation.",
        prefers=frozenset({"quote"}),
        motion="type-on",
        layout="quote",
        priority=3,
    ),
    _style(
        "narrative-scene-set",
        "narrative",
        "Scene set",
        "An opening that places the learner in a moment.",
        keywords=("once", "one day", "when you"),
        motion="fade",
        reduced_motion="instant",
        layout="stack",
        priority=4,
    ),
    _style(
        "narrative-dialogue",
        "narrative",
        "Dialogue",
        "A line where someone speaks, asks, or answers.",
        keywords=("said", "asked", "replied", "whispered"),
        motion="fade",
        layout="quote",
        priority=5,
    ),
    _style(
        "narrative-cause-effect",
        "narrative",
        "Cause and effect",
        "A reason followed by what it changes.",
        keywords=("because", "therefore", "as a result"),
        motion="slide",
        layout="split",
        priority=4,
    ),
    _style(
        "narrative-timeline",
        "narrative",
        "Timeline",
        "A sequence of events told in order.",
        keywords=("first", "finally"),
        prefers=frozenset({"steps"}),
        motion="draw",
        layout="steps",
        priority=3,
    ),
    _style(
        "narrative-contrast",
        "narrative",
        "Contrast",
        "Two ideas held apart in the same narration.",
        keywords=("however", "although", "on the other hand"),
        motion="slide",
        layout="compare",
        priority=4,
    ),
    _style(
        "narrative-reflection",
        "narrative",
        "Reflection",
        "A beat that asks the learner to notice or consider.",
        keywords=("think about", "notice", "consider", "wonder"),
        motion="fade",
        layout="card",
        priority=4,
    ),
    _style(
        "narrative-recap",
        "narrative",
        "Recap",
        "A short look back at what was just taught.",
        keywords=("recap", "in summary", "remember", "review"),
        motion="fade",
        layout="stack",
        priority=4,
    ),
    _style(
        "narrative-hook",
        "narrative",
        "Hook",
        "A question that opens the slide.",
        prefers=frozenset({"hook"}),
        motion="fade",
        reduced_motion="instant",
        layout="card",
        priority=4,
    ),
    _style(
        "narrative-closing",
        "narrative",
        "Closing",
        "A handoff into the next study beat.",
        keywords=("study next", "up next", "coming up", "finish"),
        motion="fade",
        layout="card",
        priority=3,
    ),
)

_PICTURE: tuple[StyleSpec, ...] = (
    _style(
        "picture-hero-still",
        "picture",
        "Hero still",
        "One picture held still beside a short line.",
        requires=frozenset({"picture"}),
        prefers=frozenset({"picture", "short_text"}),
        avoids=frozenset({"long_text"}),
        motion="none",
        layout="hero",
        priority=4,
    ),
    _style(
        "picture-ken-burns",
        "picture",
        "Ken Burns",
        "A slow move across one picture during a longer narration.",
        requires=frozenset({"picture"}),
        prefers=frozenset({"picture", "long_text"}),
        motion="ken-burns",
        layout="hero",
        priority=3,
    ),
    _style(
        "picture-captioned",
        "picture",
        "Captioned still",
        "A picture with a short caption line.",
        requires=frozenset({"picture"}),
        prefers=frozenset({"picture", "short_text"}),
        motion="fade",
        layout="caption",
        priority=1,
    ),
    _style(
        "picture-split-copy",
        "picture",
        "Split copy",
        "A picture beside a longer block of words.",
        requires=frozenset({"picture"}),
        prefers=frozenset({"picture", "long_text"}),
        motion="slide",
        layout="split",
        priority=1,
    ),
    _style(
        "picture-video-lead",
        "picture",
        "Video lead",
        "A motion clip carrying a longer explanation.",
        requires=frozenset({"video"}),
        prefers=frozenset({"video", "long_text"}),
        motion="fade",
        layout="hero",
        priority=3,
    ),
    _style(
        "picture-motion-card",
        "picture",
        "Motion card",
        "A short motion clip on a card.",
        requires=frozenset({"video"}),
        prefers=frozenset({"video", "short_text"}),
        avoids=frozenset({"long_text"}),
        motion="pulse",
        layout="card",
        priority=3,
    ),
    _style(
        "picture-storyboard",
        "picture",
        "Storyboard",
        "An inline storyboard illustrating the beat.",
        requires=frozenset({"storyboard"}),
        prefers=frozenset({"storyboard"}),
        avoids=frozenset({"steps"}),
        motion="draw",
        layout="hero",
        priority=3,
    ),
    _style(
        "picture-storyboard-steps",
        "picture",
        "Storyboard steps",
        "A storyboard walked in step with an ordered narration.",
        requires=frozenset({"storyboard", "steps"}),
        prefers=frozenset({"storyboard", "steps"}),
        motion="draw",
        layout="steps",
        priority=3,
    ),
    _style(
        "picture-compare",
        "picture",
        "Picture compare",
        "A picture used to hold two ideas apart.",
        requires=frozenset({"picture", "compare"}),
        prefers=frozenset({"picture", "compare"}),
        motion="slide",
        layout="compare",
        priority=5,
    ),
    _style(
        "picture-example-callouts",
        "picture",
        "Example callouts",
        "A picture with example callouts revealed over the narration.",
        requires=frozenset({"picture", "examples"}),
        prefers=frozenset({"picture", "examples"}),
        motion="fade",
        layout="gallery",
        priority=5,
    ),
    _style(
        "picture-detail-focus",
        "picture",
        "Detail focus",
        "A closer look when the picture description is specific.",
        requires=frozenset({"picture", "detail"}),
        prefers=frozenset({"picture", "detail"}),
        motion="ken-burns",
        layout="focus",
        priority=5,
    ),
    _style(
        "picture-media-stack",
        "picture",
        "Media stack",
        "Picture, video, and storyboard layered on one beat.",
        prefers=frozenset({"multi_media"}),
        motion="fade",
        layout="stack",
        priority=0,
    ),
)

_TEXT: tuple[StyleSpec, ...] = (
    _style(
        "text-definition",
        "text",
        "Definition",
        "A term followed by what it means.",
        keywords=("means", "defined as", "refers to"),
        prefers=frozenset({"definition"}),
        motion="type-on",
        layout="card",
        priority=4,
    ),
    _style(
        "text-key-term",
        "text",
        "Key term",
        "A short defined term held on its own card.",
        prefers=frozenset({"definition", "short_text"}),
        motion="type-on",
        layout="focus",
        priority=1,
    ),
    _style(
        "text-big-number",
        "text",
        "Big number",
        "A figure the learner needs to remember.",
        prefers=frozenset({"number"}),
        motion="fade",
        layout="focus",
        priority=4,
    ),
    _style(
        "text-comparison",
        "text",
        "Comparison",
        "Two written ideas set side by side.",
        prefers=frozenset({"compare"}),
        motion="slide",
        layout="compare",
        priority=4,
    ),
    _style(
        "text-steps",
        "text",
        "Steps",
        "A short ordered procedure.",
        requires=frozenset({"steps"}),
        prefers=frozenset({"steps"}),
        keywords=("first", "finally"),
        motion="draw",
        layout="steps",
        priority=4,
    ),
    _style(
        "text-warning",
        "text",
        "Warning",
        "A rule the learner must not miss.",
        keywords=("never", "danger", "warning", "hazard"),
        prefers=frozenset({"warning"}),
        motion="pulse",
        layout="card",
        priority=4,
    ),
    _style(
        "text-bullets",
        "text",
        "Bullets",
        "Examples revealed as separate callouts.",
        prefers=frozenset({"examples"}),
        motion="fade",
        layout="stack",
        priority=3,
    ),
    _style(
        "text-checklist",
        "text",
        "Checklist",
        "A written list of checks.",
        prefers=frozenset({"bullets"}),
        motion="fade",
        layout="steps",
        priority=3,
    ),
    _style(
        "text-quote-card",
        "text",
        "Quote card",
        "A quotation set as text rather than a scene.",
        prefers=frozenset({"quote"}),
        motion="type-on",
        layout="quote",
        priority=4,
    ),
    _style(
        "text-two-column",
        "text",
        "Two column",
        "A longer passage split into two reading columns.",
        prefers=frozenset({"long_text"}),
        motion="fade",
        layout="split",
        priority=2,
    ),
    _style(
        "text-passage",
        "text",
        "Passage",
        "A longer reading with no figure to anchor it.",
        prefers=frozenset({"long_text"}),
        avoids=frozenset({"number"}),
        motion="type-on",
        reduced_motion="instant",
        layout="stack",
        priority=0,
    ),
    _style(
        "text-callout",
        "text",
        "Callout",
        "A short text card when nothing more specific fits.",
        prefers=frozenset({"short_text"}),
        motion="fade",
        layout="card",
        priority=0,
    ),
)

_CHALLENGE: tuple[StyleSpec, ...] = (
    _style(
        "challenge-choice-grid",
        "challenge",
        "Choice grid",
        "A quiz whose answers sit in a grid.",
        requires=frozenset({"choices"}),
        prefers=frozenset({"choices"}),
        motion="fade",
        layout="gallery",
        priority=4,
    ),
    _style(
        "challenge-question-card",
        "challenge",
        "Question card",
        "A quiz prompt before choices are attached.",
        prefers=frozenset({"quiz"}),
        avoids=frozenset({"choices"}),
        motion="fade",
        layout="card",
        priority=2,
    ),
    _style(
        "challenge-explain-why",
        "challenge",
        "Explain why",
        "A quiz that asks the learner to say why.",
        requires=frozenset({"why", "quiz"}),
        prefers=frozenset({"why", "quiz"}),
        motion="fade",
        layout="split",
        priority=5,
    ),
    _style(
        "challenge-spot-gap",
        "challenge",
        "Spot the gap",
        "A game that asks the learner to find what is missing.",
        requires=frozenset({"gap"}),
        prefers=frozenset({"gap"}),
        motion="fade",
        layout="focus",
        priority=5,
    ),
    _style(
        "challenge-match",
        "challenge",
        "Match",
        "A game that pairs terms with meanings.",
        requires=frozenset({"match"}),
        prefers=frozenset({"match"}),
        motion="slide",
        layout="compare",
        priority=5,
    ),
    _style(
        "challenge-sequence",
        "challenge",
        "Sequence",
        "An ordered challenge the learner arranges.",
        requires=frozenset({"ordered"}),
        prefers=frozenset({"ordered"}),
        motion="draw",
        layout="steps",
        priority=5,
    ),
    _style(
        "challenge-activity",
        "challenge",
        "Activity",
        "A spoken prompt the learner answers out loud.",
        prefers=frozenset({"activity"}),
        avoids=frozenset({"quiz", "game"}),
        motion="fade",
        layout="card",
        priority=3,
    ),
    _style(
        "challenge-reflect",
        "challenge",
        "Reflect",
        "An activity that asks the learner to think before moving on.",
        requires=frozenset({"reflection"}),
        prefers=frozenset({"activity", "reflection"}),
        avoids=frozenset({"quiz"}),
        motion="fade",
        layout="card",
        priority=4,
    ),
    _style(
        "challenge-checkpoint",
        "challenge",
        "Checkpoint",
        "A hard pause so the learner can mark their place.",
        prefers=frozenset({"checkpoint"}),
        motion="none",
        layout="card",
        priority=6,
    ),
    _style(
        "challenge-try-it",
        "challenge",
        "Try it",
        "Practice built from worked examples.",
        prefers=frozenset({"practice", "examples"}),
        motion="fade",
        layout="gallery",
        priority=3,
    ),
    _style(
        "challenge-practice",
        "challenge",
        "Practice",
        "A practice beat with no separate example list.",
        prefers=frozenset({"practice"}),
        motion="fade",
        layout="card",
        priority=4,
    ),
    _style(
        "challenge-pause",
        "challenge",
        "Pause",
        "A question held on screen until the learner continues.",
        prefers=frozenset({"question"}),
        motion="none",
        layout="card",
        priority=1,
    ),
)

_ALL_STYLES: tuple[StyleSpec, ...] = _NARRATIVE + _PICTURE + _TEXT + _CHALLENGE

PRESENTATION_STYLES: dict[str, StyleSpec] = {style.style_id: style for style in _ALL_STYLES}

if len(PRESENTATION_STYLES) != len(_ALL_STYLES):
    raise RuntimeError("duplicate presentation style id")


_STEP_STYLE_IDS = frozenset(
    {
        "narrative-timeline",
        "text-steps",
        "picture-storyboard-steps",
        "challenge-sequence",
    }
)


def step_style(style_id: str) -> bool:
    """True when the style reveals narration one sentence at a time."""
    return style_id in _STEP_STYLE_IDS


def styles_in_family(family: StyleFamily) -> tuple[StyleSpec, ...]:
    return tuple(style for style in _ALL_STYLES if style.family == family)


def split_sentences(text: str) -> list[str]:
    """Split narration on sentence punctuation, keeping decimal numbers intact."""
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return []
    protected = re.sub(r"(\d)\.(\d)", r"\1<dot>\2", raw)
    chunks = re.split(r"(?<=[.!?。！？])\s+", protected)
    sentences: list[str] = []
    for chunk in chunks:
        sentence = chunk.replace("<dot>", ".").strip()
        if sentence:
            sentences.append(sentence)
    return sentences


def sentences_for(slide: CourseSlide, narration: str | None = None) -> list[str]:
    """Sentences the style picker and the timeline compiler both use."""
    chosen = slide.narration if narration is None else narration
    spoken = (chosen or slide.body or slide.title or "").strip()
    parsed = split_sentences(spoken)
    if parsed:
        return parsed
    fallback = (slide.title or "Slide").strip() or "Slide"
    return [fallback]


def spoken_text(slide: CourseSlide, narration: str | None = None) -> str:
    return " ".join(sentences_for(slide, narration))


def _keyword_in(text: str, keyword: str) -> bool:
    needle = keyword.casefold()
    if " " in needle:
        return needle in text
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])", text) is not None


def _any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_keyword_in(text, keyword) for keyword in keywords)


def _step_signal(blob: str) -> bool:
    """Ordered language needs two markers so a single 'then' is not a procedure."""
    markers = ("first", "then", "next", "finally", "step")
    return sum(1 for marker in markers if _keyword_in(blob, marker)) >= 2


def content_blob(slide: CourseSlide, spoken: str) -> str:
    quiz = slide.quiz_spec if isinstance(slide.quiz_spec, dict) else {}
    game = slide.game_spec if isinstance(slide.game_spec, dict) else {}
    parts = [
        slide.title,
        slide.body,
        spoken,
        slide.activity_prompt,
        slide.picture_alt,
        slide.video_caption,
        slide.storyboard_concept,
        " ".join(slide.examples),
        " ".join(slide.tags),
        str(quiz.get("prompt") or ""),
        str(quiz.get("explanation") or ""),
        str(game.get("prompt") or ""),
        str(game.get("kind") or ""),
    ]
    return " ".join(part for part in parts if part).casefold()


def slide_signals(
    slide: CourseSlide,
    sentences: list[str],
    blob: str,
) -> dict[str, bool]:
    """Boolean content and asset flags used to score styles."""
    quiz = slide.quiz_spec if isinstance(slide.quiz_spec, dict) else {}
    game = slide.game_spec if isinstance(slide.game_spec, dict) else {}
    choices = quiz.get("choices") if isinstance(quiz.get("choices"), list) else []
    kind = str(game.get("kind") or "").casefold()
    picture = bool((slide.picture_url or "").strip())
    video = bool((slide.video_url or "").strip())
    storyboard = bool((slide.storyboard_svg or "").strip())
    alt = (slide.picture_alt or "").strip()
    spoken = " ".join(sentences)
    prose = slide.body or slide.narration or ""
    quiz_bits = f"{quiz.get('prompt') or ''} {quiz.get('explanation') or ''}".casefold()
    long_text = len(sentences) >= 4
    checkpoint = "checkpoint" in blob or any(
        tag.casefold() == "checkpoint" for tag in slide.tags
    )
    return {
        "picture": picture,
        "video": video,
        "storyboard": storyboard,
        "multi_media": sum((picture, video, storyboard)) >= 2,
        "quiz": bool(quiz),
        "choices": len(choices) >= 2,
        "game": bool(game),
        "match": "match" in kind,
        "gap": "gap" in kind,
        "ordered": "order" in kind or "sequence" in kind,
        "why": _keyword_in(quiz_bits, "why") or _keyword_in(blob, "why"),
        "activity": bool((slide.activity_prompt or "").strip()),
        "checkpoint": checkpoint,
        "practice": _any_keyword(blob, ("practice", "try this", "your turn")),
        "examples": len(slide.examples) >= 2,
        "bullets": bool(re.search(r"(?:^|\n)\s*(?:\d+[.)]|[-•])\s+\S", slide.body or "")),
        "long_text": long_text,
        "short_text": (not long_text) and len(sentences) <= 2 and len(prose) < 160,
        "warning": _any_keyword(blob, ("warning", "danger", "never", "hazard")),
        "compare": _any_keyword(blob, ("versus", "compare", "difference", "before and after")),
        "steps": _step_signal(blob),
        "quote": bool(re.search(r"[\"“”]", f"{slide.title} {slide.body} {spoken}")),
        "number": bool(re.search(r"\d", f"{slide.title} {slide.body}")),
        "definition": _any_keyword(blob, ("means", "defined as", "refers to")),
        "hook": spoken.strip().endswith("?") or (slide.title or "").strip().endswith("?"),
        "question": "?" in f"{slide.title} {spoken} {slide.activity_prompt}",
        "detail": len(alt) >= 40,
        "reflection": _any_keyword(blob, ("think about", "notice", "consider", "wonder")),
    }


def infer_family(signals: dict[str, bool]) -> StyleFamily:
    """Pick the style family from assets and the kind of work on the slide."""
    if any(signals[name] for name in ("quiz", "game", "activity", "checkpoint", "practice")):
        return "challenge"
    if signals["picture"] or signals["video"] or signals["storyboard"]:
        return "picture"
    if any(
        signals[name]
        for name in ("definition", "warning", "bullets", "number", "compare", "examples")
    ):
        return "text"
    if signals["steps"] and not signals["long_text"]:
        return "text"
    return "narrative"


def _prefer_weight(name: str) -> int:
    return _PREFER_WEIGHTS.get(name, 6)


def score_style(style: StyleSpec, signals: dict[str, bool], blob: str) -> int | None:
    """Return a score, or None when a required signal is missing."""
    if any(not signals.get(name) for name in style.requires):
        return None
    score = 10 + style.priority
    for name in style.prefers:
        if signals.get(name):
            score += _prefer_weight(name)
    for name in style.avoids:
        if signals.get(name):
            score -= 8
    hits = 0
    for keyword in style.keywords:
        if _keyword_in(blob, keyword):
            hits += 1
            if hits >= 3:
                break
    return score + 5 * hits


def rank_presentation_styles(
    slide: CourseSlide,
    *,
    narration: str | None = None,
) -> list[tuple[int, StyleSpec]]:
    """Eligible styles in the inferred family, best score first."""
    sentences = sentences_for(slide, narration)
    blob = content_blob(slide, " ".join(sentences))
    signals = slide_signals(slide, sentences, blob)
    family = infer_family(signals)
    ranked: list[tuple[int, StyleSpec]] = []
    for style in styles_in_family(family):
        score = score_style(style, signals, blob)
        if score is None:
            continue
        ranked.append((score, style))
    ranked.sort(key=lambda row: (-row[0], row[1].style_id))
    return ranked


def assignment_key(slide: CourseSlide, narration: str | None = None) -> str:
    """Stable tie-break material: slide key, spoken content, and assets."""
    sentences = sentences_for(slide, narration)
    blob = content_blob(slide, " ".join(sentences))
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]
    base = (slide.slide_key or slide.title or "slide").strip() or "slide"
    assets = "".join(
        (
            "p" if (slide.picture_url or "").strip() else "-",
            "v" if (slide.video_url or "").strip() else "-",
            "s" if (slide.storyboard_svg or "").strip() else "-",
        )
    )
    return f"{base}|{digest}|{assets}"


def stable_pick(key: str, count: int) -> int:
    if count <= 1:
        return 0
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % count


def select_ranked_style(
    ranked: list[tuple[int, StyleSpec]],
    *,
    slide_key: str,
    previous_style_id: str | None = None,
    pinned: bool = False,
) -> StyleSpec:
    """Pick the top band, then step past ``previous_style_id`` when asked."""
    if not ranked:
        raise ValueError("no presentation style matches this slide")
    best = ranked[0][0]
    band = [style for score, style in ranked if best - score <= _NEAR_TIE]
    chosen = band[stable_pick(slide_key or "slide", len(band))]
    if pinned or not previous_style_id or chosen.style_id != previous_style_id or len(ranked) == 1:
        return chosen
    ids = [style.style_id for _, style in ranked]
    start = ids.index(chosen.style_id)
    for step in range(1, len(ids)):
        candidate = ranked[(start + step) % len(ids)][1]
        if candidate.style_id != previous_style_id:
            return candidate
    return chosen


def assign_presentation_style(
    slide: CourseSlide,
    *,
    previous_style_id: str | None = None,
    narration: str | None = None,
) -> StyleSpec:
    """Choose one registry style for ``slide``.

    An explicit ``presentation_style`` wins, including when it repeats the
    previous slide. Automatic picks are a pure function of the slide key,
    spoken content, and assets, and will move to the next eligible style when
    ``previous_style_id`` would otherwise repeat.
    """
    pinned = (slide.presentation_style or "").strip()
    if pinned:
        style = PRESENTATION_STYLES.get(pinned)
        if style is None:
            raise ValueError(f"unknown presentation style {pinned!r}")
        return style
    ranked = rank_presentation_styles(slide, narration=narration)
    if not ranked:
        raise ValueError("no presentation style matches this slide")
    return select_ranked_style(
        ranked,
        slide_key=assignment_key(slide, narration),
        previous_style_id=previous_style_id,
        pinned=False,
    )
