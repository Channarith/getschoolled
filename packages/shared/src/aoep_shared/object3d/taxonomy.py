"""Map a detector label onto animal / food / sign / person / thing."""

from __future__ import annotations

ANIMALS = frozenset({
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear",
    "zebra", "giraffe",
})
FOOD = frozenset({
    "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake",
})
SIGNS = frozenset({"stop sign", "traffic light", "parking meter"})
PERSONS = frozenset({"person"})


def kind_for(label: str) -> str:
    """Return animal, food, sign, person, or thing."""
    key = " ".join((label or "").casefold().split())
    if key in ANIMALS:
        return "animal"
    if key in FOOD:
        return "food"
    if key in SIGNS or "sign" in key:
        return "sign"
    if key in PERSONS:
        return "person"
    return "thing"
