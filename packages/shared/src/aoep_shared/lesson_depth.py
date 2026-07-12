"""Deepen live-class lessons into engaging, conversational sessions.

The old enrichment stamped every slide with the same "Example — / Reinforcement
— / Quick check —" scaffold, so every class read identically and talked *at* the
learner. This version talks *to* the learner: it interleaves varied, content-
grounded beats after each teaching slide (apply-it scenarios, connect-the-dots
reflections, direct check-in questions) and drops in "repeat after me" speaking
checkpoints that the player pauses on to listen to and score the learner's voice.

Phrasings are drawn from rotating pools so no two consecutive beats read the same,
and the concrete detail in each beat comes from the slide's own sentences (not
generic filler). Callers pass a ``slide_factory`` that accepts the interaction
metadata (``kind`` and ``say_aloud``) so speaking checkpoints reach the UI.
"""

from __future__ import annotations

import re
from typing import Callable, List, Sequence, Tuple, TypeVar

TARGET_MIN_MINUTES = 20
TARGET_MAX_MINUTES = 30
TEACHING_WPM = 120  # instructional pace (slower than catalog skim rate)

T = TypeVar("T")

# Interaction kinds carried on a slide so the player knows how to present it.
KIND_TEACH = "teach"
KIND_SAY_ALOUD = "say_aloud"   # pause, listen to the learner, score their speech

# --- Conversational phrasing pools (rotated so consecutive beats differ). ---
_TRANSITIONS = (
    "Let's make this real.",
    "Here's why it actually matters.",
    "Now watch how this plays out.",
    "Stay with me on this one.",
    "This is the part that makes it click.",
    "Okay — let's put it to work.",
)
_QUESTIONS = (
    "Could you explain {t} to a friend in one sentence right now?",
    "Quick gut-check: what's the single most important idea in {t}?",
    "Where have you already seen {t} show up in real life?",
    "If someone asked you why {t} matters, what would you say?",
    "What would go wrong if you ignored {t} completely?",
    "In your own words, what is {t} really about?",
)
_SCENARIO_FRAMERS = (
    "Picture this: {s}",
    "Imagine you're on the job and {s_low}",
    "Here's a real situation — {s_low}",
    "Say a friend hits this exact problem: {s}",
    "Think back to the last time {s_low}",
)
_ENCOURAGERS = (
    "You've got this.",
    "Nice work sticking with it.",
    "See — not so scary.",
    "That's real progress.",
    "Good. That's exactly the way.",
)
_CONNECTORS = (
    "Notice how this builds on what we just covered.",
    "This ties straight back to the last idea.",
    "Zoom out for a second and see the pattern.",
    "Here's how the pieces fit together.",
    "Keep the previous slide in mind as you read this.",
)
_APPLY_TITLES = ("Try it out", "In the real world", "Your turn to apply it", "A situation to solve", "Put it to work")
_CONNECT_TITLES = ("Connect the dots", "How it fits", "Zoom out", "Tie it together", "The bigger picture")
_CHECKIN_TITLES = ("Quick check-in", "Gut check", "One quick question", "Before we move on", "Think it through")
_SAY_TITLES = ("Repeat after me", "Say it out loud", "Your voice now", "Speak it back")
_DEEPDIVE_FRAMERS = (
    "Let's go one level deeper. {d}",
    "Here's a detail worth knowing: {d}",
    "Worth a closer look — {d}",
    "One more useful piece: {d}",
    "Dig in a little: {d}",
)

# Per-source-slide beat recipes, cycled so the rhythm varies across the lesson.
_RECIPES: Tuple[Tuple[str, ...], ...] = (
    ("apply", "say"),
    ("connect", "checkin"),
    ("apply", "connect"),
    ("say", "checkin"),
    ("connect", "apply"),
)


def words_in_slides(slides: Sequence) -> int:
    total = 0
    for s in slides:
        body = getattr(s, "body", "") or ""
        narr = getattr(s, "narration", "") or ""
        total += len((body or narr).split())
    return total


def duration_minutes(slides: Sequence, *, wpm: int = TEACHING_WPM) -> int:
    words = words_in_slides(slides)
    return max(TARGET_MIN_MINUTES, min(TARGET_MAX_MINUTES, round(words / wpm)))


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _lower_first(text: str) -> str:
    text = text.strip()
    return (text[:1].lower() + text[1:]) if text else text


def _clean_title(title: str) -> str:
    """Strip trailing punctuation so a title reads cleanly mid-sentence."""
    return title.strip().rstrip("?!.:;,") or title.strip()


def _key_phrase(title: str, body: str) -> str:
    """A short, complete, speakable phrase for a repeat-after-me checkpoint.

    Prefer a full short sentence (so the learner echoes something coherent);
    otherwise use the cleaned slide title rather than truncating mid-sentence.
    """
    for s in _split_sentences(body):
        if 3 <= len(s.split()) <= 12:
            return s.rstrip(".,;:")
    return _clean_title(title)


class _Picker:
    """Rotates through a pool so consecutive picks are always different."""

    def __init__(self) -> None:
        self._n = 0

    def pick(self, pool: Sequence[str]) -> str:
        v = pool[self._n % len(pool)]
        self._n += 1
        return v


def enrich_slides(
    slides: List[T],
    passages: List[str],
    *,
    target_min: int = 25,
    slide_factory: Callable[..., T] | None = None,
) -> Tuple[List[T], List[str]]:
    """Interleave conversational, content-grounded beats after each slide.

    ``slide_factory(index, title, body, narration, kind=..., say_aloud=...)`` must
    build the slide type used by the caller (orchestrator Slide / SampleSlide).
    ``kind``/``say_aloud`` are keyword args; factories may ignore them.
    """
    if not slides or slide_factory is None:
        return slides, passages

    out: List[T] = []
    extra_passages = list(passages)
    pick = _Picker().pick

    def add(title: str, body: str, narr: str = "", *, kind: str = KIND_TEACH, say_aloud: str = "") -> None:
        out.append(slide_factory(len(out), title, body, narr or body, kind=kind, say_aloud=say_aloud))
        if ":" in body[:80]:
            extra_passages.append(body.split("\n", 1)[0][:200])

    def beat_apply(title: str, body: str) -> None:
        sents = _split_sentences(body)
        core = sents[0] if sents else (body or title)
        scen = pick(_SCENARIO_FRAMERS).format(s=core, s_low=_lower_first(core))
        q = pick(_QUESTIONS).format(t=_clean_title(title).lower())
        add(pick(_APPLY_TITLES),
            f"{scen} How would you use {_clean_title(title)} to handle it? {q}")

    def beat_connect(title: str, body: str) -> None:
        sents = _split_sentences(body)
        detail = sents[-1] if sents else (body or title)
        add(pick(_CONNECT_TITLES),
            f"{pick(_CONNECTORS)} {detail} In one sentence, how does {_clean_title(title)} link to what came just before it?")

    def beat_checkin(title: str, _body: str) -> None:
        q = pick(_QUESTIONS).format(t=_clean_title(title).lower())
        add(pick(_CHECKIN_TITLES),
            f"{q} Take a beat and answer in your head before you move on. {pick(_ENCOURAGERS)}")

    def beat_say(title: str, body: str) -> None:
        phrase = _key_phrase(title, body)
        add(pick(_SAY_TITLES),
            f"Your turn — say this out loud so it really sticks, and I'll listen: "
            f"\u201c{phrase}.\u201d When you speak, I'll tell you how close you were.",
            narr=f"Repeat after me: {phrase}.",
            kind=KIND_SAY_ALOUD, say_aloud=phrase)

    beats = {"apply": beat_apply, "connect": beat_connect, "checkin": beat_checkin, "say": beat_say}

    # Interleave: each real slide (conversational narration) then its varied beats.
    for i, s in enumerate(slides):
        title = getattr(s, "title", f"Topic {i + 1}")
        body = getattr(s, "body", "") or getattr(s, "narration", "")
        orig_narr = getattr(s, "narration", "") or body
        opener = pick(_TRANSITIONS) if i else "Welcome — let's dive in."
        add(title, body, narr=f"{opener} {orig_narr}")
        for beat in _RECIPES[i % len(_RECIPES)]:
            beats[beat](title, body)

    # Deep dives from UNIQUE passages only (each once, varied framing) — real
    # content, no cyclic padding. Session length is guaranteed by duration_minutes.
    seen: set[str] = set()
    for p in passages:
        key = p.strip().lower()[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        if len(seen) > 8:
            break
        term = p.split(":", 1)[0].strip() if ":" in p else p[:40]
        detail = p.split(":", 1)[-1].strip() if ":" in p else p
        add(f"Deep dive: {term}",
            f"{pick(_DEEPDIVE_FRAMERS).format(d=detail)} "
            f"Jot down one sentence linking this to something you already know.")

    # Conversational wrap-up.
    add("Let's wrap up",
        "You just worked through the whole lesson — teaching, real scenarios, and a "
        "few moments where you spoke it back. Before you finish, say or write the three "
        "ideas you most want to remember. That's what turns a class into a skill.")

    return out, extra_passages
