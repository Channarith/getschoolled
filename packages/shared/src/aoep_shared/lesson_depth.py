"""Deepen live-class lessons toward 20–30 minute sessions with reinforcement."""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple, TypeVar

TARGET_MIN_MINUTES = 20
TARGET_MAX_MINUTES = 30
TEACHING_WPM = 120  # instructional pace (slower than catalog skim rate)

T = TypeVar("T")


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


def enrich_slides(slides: List[T], passages: List[str], *, target_min: int = 25,
                    slide_factory=None) -> Tuple[List[T], List[str]]:
    """Expand slides with examples, reinforcement, and quiz checkpoints.

    ``slide_factory(index, title, body, narration)`` must build the slide type
    used by the caller (orchestrator Slide / learnable SampleSlide).
    """
    if not slides or slide_factory is None:
        return slides, passages

    out: List[T] = list(slides)
    extra_passages = list(passages)
    target_words = target_min * TEACHING_WPM

    def add(title: str, body: str, narr: str = "") -> None:
        out.append(slide_factory(len(out), title, body, narr or body))
        if ":" in body[:80]:
            extra_passages.append(body.split("\n", 1)[0][:200])

    # Per original slide: example + reinforcement pair.
    base = list(slides)
    for i, s in enumerate(base):
        title = getattr(s, "title", f"Topic {i + 1}")
        body = getattr(s, "body", "") or getattr(s, "narration", "")
        sentences = _split_sentences(body)
        if len(sentences) >= 2:
            example = (
                f"Example — {title}: {sentences[0]} "
                f"For instance, {sentences[1]} "
                "Try applying this idea to a problem you have seen before."
            )
        else:
            example = (
                f"Example — {title}: {body} "
                "Picture a concrete situation where this applies step by step."
            )
        add(f"Worked example: {title}", example)

        reinforce = (
            f"Reinforcement — {title}: Let's review the core idea again in different words. "
            f"{body} "
            "Key takeaway: pause and explain this concept aloud in your own words before moving on."
        )
        add(f"Review: {title}", reinforce)

        if (i + 1) % 3 == 0:
            add(
                f"Checkpoint quiz ({i + 1})",
                f"Quick check — {title}: Without looking back, name two facts you remember. "
                "If you hesitate, re-read the previous reinforcement slide.",
                narr="Pop quiz checkpoint. Pause and recall what you learned.",
            )

    # Pad with passage-derived deep dives until target word count.
    pi = 0
    while words_in_slides(out) < target_words and passages:
        p = passages[pi % len(passages)]
        pi += 1
        term = p.split(":", 1)[0].strip() if ":" in p else p[:40]
        detail = p.split(":", 1)[-1].strip() if ":" in p else p
        add(
            f"Deep dive: {term}",
            f"{detail} Consider how this connects to earlier slides. "
            "Write one sentence linking this fact to something you already know.",
        )

    # Final synthesis slide.
    add(
        "Lesson synthesis",
        "You have covered the full lesson with examples, reviews, and checkpoints. "
        "Summarize the three most important ideas in your own words before finishing.",
    )

    return out, extra_passages
