"""Deterministic scoring for child-friendly webcam games."""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any

LETTER_ALIASES: dict[str, set[str]] = {
    "a": {"a", "ay", "eh"},
    "b": {"b", "bee", "be"},
    "c": {"c", "see", "sea"},
    "d": {"d", "dee"},
    "e": {"e", "ee"},
    "f": {"f", "ef"},
    "g": {"g", "gee"},
    "h": {"h", "aitch", "h"},
    "i": {"i", "eye"},
    "j": {"j", "jay"},
    "k": {"k", "kay"},
    "l": {"l", "el"},
    "m": {"m", "em"},
    "n": {"n", "en"},
    "o": {"o", "oh"},
    "p": {"p", "pee"},
    "q": {"q", "cue", "queue"},
    "r": {"r", "are"},
    "s": {"s", "ess"},
    "t": {"t", "tee"},
    "u": {"u", "you"},
    "v": {"v", "vee"},
    "w": {"w", "double u", "double you"},
    "x": {"x", "ex"},
    "y": {"y", "why"},
    "z": {"z", "zee", "zed"},
}

PICTURE_WORDS = {
    "a": "apple", "b": "ball", "c": "cat", "d": "dragon", "e": "elephant",
    "f": "fish", "g": "grape", "h": "heart", "i": "ice cream", "j": "jellyfish",
    "k": "kite", "l": "lion", "m": "moon", "n": "nest", "o": "octopus",
    "p": "popcorn", "q": "queen", "r": "rocket", "s": "star", "t": "teddy",
    "u": "umbrella", "v": "violin", "w": "whale", "x": "xylophone",
    "y": "yo-yo", "z": "zebra",
}

# One glyph per picture-word so Trace a picture never falls back to a sparkle
# for a letter the catalog claims to teach.
PICTURE_EMOJI = {
    "apple": "🍎", "ball": "⚽", "cat": "🐱", "dragon": "🐉", "elephant": "🐘",
    "fish": "🐟", "grape": "🍇", "heart": "💖", "ice cream": "🍦", "jellyfish": "🪼",
    "kite": "🪁", "lion": "🦁", "moon": "🌙", "nest": "🪺", "octopus": "🐙",
    "popcorn": "🍿", "queen": "👑", "rocket": "🚀", "star": "⭐", "teddy": "🧸",
    "umbrella": "☂️", "violin": "🎻", "whale": "🐋", "xylophone": "🎹",
    "yo-yo": "🪀", "zebra": "🦓",
}

# The menu the child sees, the content API, and the browser game loop must all
# name the same ids. Adding a row here without a matching branch in app.js is a
# test failure, not a silent missing game.
GAME_MENU: list[tuple[str, list[tuple[str, str]]]] = [
    ("Learn", [
        ("trace-letter", "Trace a letter"),
        ("trace-picture", "Trace a picture"),
        ("say-letter", "Say the letter"),
    ]),
    ("Face & hands", [
        ("oh-behave", "Oh behave"),
        ("heart", "Make hearts"),
        ("idea", "I have an idea"),
        ("fist-bump", "Fist bump"),
        ("wow", "Wow face"),
        ("blow-kiss", "Blow a kiss"),
        ("wink", "Wink challenge"),
        ("make-pose", "Make a hero pose"),
        ("balloon", "Pop balloons"),
        ("fish", "Catch flying fish"),
        ("popcorn", "Catch popcorn"),
    ]),
    ("Move", [
        ("fruit-cut", "Fruit cut"),
        ("air-drums", "Air drums"),
        ("bird-flap", "Flap like a bird"),
        ("head-bop", "Head bop"),
        ("face-chase", "Face chase"),
        ("stand-sit", "Stand up, sit down"),
        ("dance-freeze", "Dance freeze"),
        ("rainbow-reach", "Rainbow reach"),
    ]),
]


def all_game_ids() -> tuple[str, ...]:
    return tuple(game_id for _group, games in GAME_MENU for game_id, _title in games)

OH_BEHAVE_TIMER_MS = (8000, 6000, 4000, 2000, 1500)


def fold_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9\s-]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def score_spoken(target: str, heard: str, *, kind: str = "word") -> dict[str, Any]:
    expected = fold_text(target)
    actual = fold_text(heard)
    accepted = {expected}
    if kind == "letter" and expected in LETTER_ALIASES:
        accepted |= LETTER_ALIASES[expected]
    if kind == "noun":
        accepted |= {expected.removesuffix("s"), f"{expected}s"}
    ratio = max(
        (difflib.SequenceMatcher(a=value, b=actual).ratio() for value in accepted),
        default=0.0,
    )
    score = round(ratio * 100)
    threshold = 64 if kind == "letter" else 72
    return {
        "target": target,
        "heard": heard.strip(),
        "score": score,
        "passed": score >= threshold,
        "stars": 3 if score >= 90 else 2 if score >= threshold else 1 if score else 0,
        "feedback": (
            "You got it! That sounded great."
            if score >= threshold
            else f"Almost! Listen once, then try {target} again."
        ),
    }


def fun_score(
    *,
    completed: bool,
    attempts: int = 1,
    duration_ms: int = 0,
    target_ms: int = 8000,
    combo: int = 0,
    celebration: bool = False,
    smile: float = 0.0,
    kept_going: bool = False,
    mobility_regions: int = 0,
    skipped: bool = False,
) -> dict[str, Any]:
    play = 40.0 if completed else 8.0 if attempts else 0.0
    pace = max(0.0, min(1.0, 1 - duration_ms / max(1, target_ms)))
    spark = (18.0 if completed and attempts == 1 else 8.0 if completed else 0.0)
    spark += min(8.0, combo * 2.0) + (4.0 if celebration else 0.0) + pace * 4.0
    giggle = max(0.0, min(1.0, smile)) * 12.0
    persistence = (8.0 if kept_going or attempts > 1 else 2.0) + min(8.0, mobility_regions * 2.0)
    penalty = 18.0 if skipped else 0.0
    total = round(max(0.0, min(100.0, play + spark + giggle + persistence - penalty)))
    return {
        "fun_score": total,
        "components": {
            "play": round(play),
            "spark": round(spark),
            "giggle": round(giggle),
            "keep_going": round(persistence),
            "drop_off": round(penalty),
        },
    }


def next_oh_behave_timer(current_ms: int, *, hit: bool, age_band: str) -> int:
    ladder = OH_BEHAVE_TIMER_MS if age_band == "7-10" else OH_BEHAVE_TIMER_MS[:3]
    try:
        index = ladder.index(current_ms)
    except ValueError:
        index = 0
    index = min(len(ladder) - 1, index + 1) if hit else max(0, index - 1)
    return ladder[index]


# Matches static/vision_math.js FIST_MAX_PALMS. tip_to_wrist is in the same
# units as palm_span (wrist to middle knuckle), not a fraction of the frame.
FIST_MAX_PALMS = 1.6


def is_closed_fist(
    *,
    finger_count: int,
    tip_to_wrist: float,
    palm_span: float = 1.0,
) -> bool:
    """A rest pose is not a fist; fingertips must be near the wrist, in palms."""
    scale = max(1e-4, float(palm_span))
    return int(finger_count) == 0 and (float(tip_to_wrist) / scale) < FIST_MAX_PALMS


def trace_pass(
    points: list[tuple[float, float]],
    *,
    age_band: str,
) -> bool:
    """Require the stroke to stay on the centered glyph, not wave at the edges."""
    if len(points) < 40:
        return False
    cells: set[tuple[int, int]] = set()
    inside = 0
    for x, y in points:
        if 0.22 <= x <= 0.78 and 0.18 <= y <= 0.82:
            inside += 1
            cells.add((round(x * 8), round(y * 8)))
    # A letter is a narrow path. 16/22 cells made a clean A/B/C fail even when
    # the child visibly followed the guide; keep these in lockstep with app.js.
    need = 10 if age_band == "4-6" else 14
    return inside >= len(points) * 0.55 and len(cells) >= need


def oh_behave_hit(
    *,
    expected_expression: str,
    actual_expression: str,
    target_region: str,
    actual_region: str,
    confidence: float,
) -> bool:
    return (
        expected_expression == actual_expression
        and target_region == actual_region
        and confidence >= 0.55
    )
