"""Deterministic memory aids for facts, sequences, vocabulary, and data."""

from __future__ import annotations

import re
from typing import Dict, List

MEMORY_STRATEGIES = (
    {"id": "acronym", "name": "Acronym", "icon": "🔠"},
    {"id": "acrostic", "name": "Acrostic sentence", "icon": "📝"},
    {"id": "chunking", "name": "Chunking", "icon": "🧱"},
    {"id": "story_chain", "name": "Story chain", "icon": "📖"},
    {"id": "memory_palace", "name": "Memory palace", "icon": "🏛️"},
    {"id": "analogy", "name": "Visual analogy", "icon": "💡"},
    {"id": "rhyme", "name": "Rhythm and rhyme", "icon": "🎵"},
    {"id": "retrieval_brainteaser", "name": "Retrieval brainteaser", "icon": "🧠"},
)
_RECALL_TERMS = frozenset({
    "remember", "memorize", "memory", "recall", "list", "steps", "sequence",
    "vocabulary", "terms", "dates", "formula", "facts", "data",
})

_ACROSTIC_WORDS = {
    "A": "Always", "B": "Brave", "C": "Curious", "D": "Dreamers",
    "E": "Explore", "F": "Fresh", "G": "Great", "H": "Horizons",
    "I": "Ideas", "J": "Joyfully", "K": "Keep", "L": "Learning",
    "M": "Making", "N": "New", "O": "Observations", "P": "Practice",
    "Q": "Questions", "R": "Reveal", "S": "Strong", "T": "Thinking",
    "U": "Unlocks", "V": "Valuable", "W": "Wisdom", "X": "eXtra",
    "Y": "Yearly", "Z": "Zeal",
}


def extract_items(content: str) -> List[str]:
    """Extract memorable units while preserving their original order."""
    text = " ".join((content or "").strip().split())
    if not text:
        return []
    parts = re.split(r"\s*(?:,|;|\||→|->|\n|\.\s+)\s*", text)
    items = [part.strip(" .:-") for part in parts if part.strip(" .:-")]
    if len(items) == 1:
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", text)
        return words if 2 <= len(words) <= 12 else [text]
    return items[:20]


def requires_memory_support(question: str, content: str = "") -> bool:
    text = f"{question} {content}".lower()
    if any(term in text for term in _RECALL_TERMS):
        return True
    return text.count(",") >= 2 or bool(re.search(r"\b(?:step|phase|stage)\s+\d", text))


def build_memory_aid(
    content: str,
    *,
    topic: str = "this lesson",
    preferred: str = "auto",
) -> Dict[str, object]:
    items = extract_items(content)
    if not items:
        raise ValueError("content is required")
    initials = "".join(item[0].upper() for item in items if item)[:12]
    chunks = [items[i:i + 3] for i in range(0, len(items), 3)]
    strategy = _choose_strategy(items, preferred)
    aids = {
        "acronym": initials,
        "acrostic": " ".join(_ACROSTIC_WORDS.get(ch, ch) for ch in initials),
        "chunking": [" · ".join(chunk) for chunk in chunks],
        "story_chain": _story_chain(items, topic),
        "memory_palace": _memory_palace(items),
        "analogy": (
            f"Picture {topic} as a toolbox: each fact is a different tool, "
            "and its shape reminds you when to use it."
        ),
        "rhyme": "Group it, picture it, solve the clue—then teach the idea back in your own view.",
        "retrieval_brainteaser": _brainteaser(items, topic),
    }
    return {
        "topic": topic.strip() or "this lesson",
        "items": items,
        "recommended_strategy": strategy,
        "recommended": aids[strategy],
        "aids": aids,
        "check": {
            "prompt": f"Without looking, reconstruct the {len(items)} key part(s) of {topic}.",
            "answer": items,
            "hint": f"The initials are {initials}." if len(items) > 1 else "Picture the toolbox.",
        },
        "teaching_sequence": [
            "Connect each item to meaning or a vivid image.",
            f"Use the {strategy.replace('_', ' ')} memory aid.",
            "Solve the brainteaser without viewing the answer.",
            "Explain the content in your own words.",
            "Retrieve it again later with increasingly spaced checks.",
        ],
    }


def _choose_strategy(items: List[str], preferred: str) -> str:
    valid = {row["id"] for row in MEMORY_STRATEGIES}
    if preferred in valid:
        return preferred
    if 3 <= len(items) <= 9:
        return "acrostic"
    if len(items) > 9:
        return "chunking"
    return "story_chain"


def _story_chain(items: List[str], topic: str) -> str:
    chain = " → ".join(items[:6])
    return f"Imagine walking through {topic}: each scene transforms into the next: {chain}."


def _memory_palace(items: List[str]) -> List[str]:
    places = ("front door", "hallway", "kitchen", "sofa", "window", "desk")
    return [
        f"At the {places[i % len(places)]}, picture {item} in an exaggerated action."
        for i, item in enumerate(items[:12])
    ]


def _brainteaser(items: List[str], topic: str) -> str:
    if len(items) > 1:
        return (
            f"The initials are {''.join(item[0].upper() for item in items)}. "
            f"What {len(items)} connected parts of {topic} do they unlock?"
        )
    return f"What idea from {topic} fits this clue: {len(items[0])} characters and essential here?"
