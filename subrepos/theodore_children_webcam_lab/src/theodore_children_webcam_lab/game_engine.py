"""Deterministic scoring for child-friendly webcam games."""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any, NamedTuple

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
        ("color-picture", "Color the picture"),
        ("connect-dots", "Connect the dots"),
        ("trace-outline", "Trace the outline"),
        ("say-letter", "Say the letter"),
    ]),
    ("Listen", [
        ("repeat-after-me", "Repeat after me"),
        ("pronounce-word", "Pronounce the word"),
        ("rhyme-time", "Say a rhyme"),
        ("listen-answer", "Answer what you hear"),
        ("missing-word", "Say the missing word"),
        ("opposites", "Say the opposite"),
        ("explain-it", "Explain it"),
        ("sum-it-up", "Sum it up"),
        ("prove-it", "Prove you understand"),
        ("story-order", "What happened first"),
        ("how-many", "How many did you hear"),
        ("same-or-different", "Same or different"),
        ("finish-the-line", "Finish the line"),
        ("spell-aloud", "Spell what you hear"),
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


class AudioRound(NamedTuple):
    round_id: str
    title: str
    prompt: str
    speak: str
    mode: str
    accept: tuple[str, ...] = ()
    require: tuple[str, ...] = ()


def _rounds(*rows: AudioRound) -> tuple[AudioRound, ...]:
    return rows


# Prompts and accepted answers stay on the server. The page only receives
# the line Theodore speaks and the on-screen instruction.
AUDIO_BANK: dict[str, tuple[AudioRound, ...]] = {
    "repeat-after-me": _rounds(
        AudioRound("cat-mat", "Repeat after me", "Say the sentence back.",
                   "Repeat after me. The cat sat on the mat.", "phrase",
                   ("the cat sat on the mat",)),
        AudioRound("red-balloons", "Repeat after me", "Say the sentence back.",
                   "Repeat after me. Red balloons float up.", "phrase",
                   ("red balloons float up",)),
    ),
    "pronounce-word": _rounds(
        AudioRound("apple", "Pronounce the word", "Say this word clearly.",
                   "Say apple.", "phrase", ("apple",)),
        AudioRound("elephant", "Pronounce the word", "Say this word clearly.",
                   "Say elephant.", "phrase", ("elephant",)),
        AudioRound("umbrella", "Pronounce the word", "Say this word clearly.",
                   "Say umbrella.", "phrase", ("umbrella",)),
    ),
    "rhyme-time": _rounds(
        AudioRound("cat", "Say a rhyme", "Say a word that rhymes with cat.",
                   "Say a word that rhymes with cat.", "any",
                   ("bat", "hat", "mat", "sat", "rat")),
        AudioRound("star", "Say a rhyme", "Say a word that rhymes with star.",
                   "Say a word that rhymes with star.", "any",
                   ("car", "far", "jar", "bar")),
    ),
    "listen-answer": _rounds(
        AudioRound("banana", "Answer what you hear", "Answer the question.",
                   "What color is a banana?", "any", ("yellow",)),
        AudioRound("meow", "Answer what you hear", "Answer the question.",
                   "Which animal says meow?", "any", ("cat", "kitten")),
        AudioRound("book", "Answer what you hear", "Answer the question.",
                   "What do you read a story in?", "any", ("book",)),
    ),
    "missing-word": _rounds(
        AudioRound("star", "Say the missing word", "Say the word that was left out.",
                   "Twinkle twinkle little blank. What word is missing?", "any", ("star",)),
        AudioRound("bus", "Say the missing word", "Say the word that was left out.",
                   "The wheels on the blank go round and round. What word is missing?", "any", ("bus",)),
    ),
    "opposites": _rounds(
        AudioRound("hot", "Say the opposite", "Say the opposite of the word you hear.",
                   "What is the opposite of hot?", "any", ("cold",)),
        AudioRound("up", "Say the opposite", "Say the opposite of the word you hear.",
                   "What is the opposite of up?", "any", ("down",)),
        AudioRound("big", "Say the opposite", "Say the opposite of the word you hear.",
                   "What is the opposite of big?", "any", ("small", "little")),
    ),
    "explain-it": _rounds(
        AudioRound("seed", "Explain it", "Explain why, using what you heard.",
                   "A seed needs water and sun to grow. Explain why a seed grows.", "all",
                   require=("water", "sun")),
        AudioRound("hands", "Explain it", "Explain why, using what you heard.",
                   "We wash our hands to wash away germs. Explain why we wash our hands.", "all",
                   require=("germs",)),
    ),
    "sum-it-up": _rounds(
        AudioRound("mia", "Sum it up", "Say the short idea, not every detail.",
                   "Mia packed a book and an apple. Then she walked to school. Sum up where Mia went.",
                   "all", require=("school",)),
        AudioRound("rain", "Sum it up", "Say the short idea, not every detail.",
                   "Clouds got dark. Then rain fell on the garden. Sum up what the garden got.",
                   "all", require=("rain",)),
    ),
    "prove-it": _rounds(
        AudioRound("ice", "Prove you understand", "Say the reason you heard.",
                   "Ice is cold water that froze. Prove you know what ice is.", "all",
                   require=("cold", "water")),
        AudioRound("triangle", "Prove you understand", "Say the reason you heard.",
                   "A triangle has three sides. Prove you know a triangle.", "all",
                   require=("three", "sides")),
    ),
    "story-order": _rounds(
        AudioRound("first", "What happened first", "Say the first thing that happened.",
                   "First the bird built a nest. Next it laid an egg. Last the egg hatched. What happened first?",
                   "any", ("nest", "built")),
        AudioRound("last", "What happened last", "Say the last thing that happened.",
                   "First we mixed the batter. Next we baked the cake. Last we ate a slice. What happened last?",
                   "any", ("ate", "slice", "eat")),
    ),
    "how-many": _rounds(
        AudioRound("sounds", "How many did you hear", "Say the number.",
                   "I hear a drum, a bell, and a flute. How many sounds?", "any",
                   ("three", "3")),
        AudioRound("socks", "How many did you hear", "Say the number.",
                   "One red sock and one blue sock. How many socks?", "any",
                   ("two", "2")),
    ),
    "same-or-different": _rounds(
        AudioRound("cats", "Same or different", "Say same or different.",
                   "Cat. Cat. Are those the same or different?", "any", ("same",)),
        AudioRound("moon", "Same or different", "Say same or different.",
                   "Moon. Spoon. Are those the same or different?", "any", ("different",)),
    ),
    "finish-the-line": _rounds(
        AudioRound("sun", "Finish the line", "Finish the sentence.",
                   "Finish this. The sun is very.", "any",
                   ("hot", "bright", "warm", "yellow")),
        AudioRound("fish", "Finish the line", "Finish the sentence.",
                   "Finish this. Fish live in the.", "any",
                   ("water", "sea", "ocean", "lake")),
    ),
    "spell-aloud": _rounds(
        AudioRound("cat", "Spell what you hear", "Say each letter.",
                   "Spell cat.", "spell", ("cat",)),
        AudioRound("sun", "Spell what you hear", "Say each letter.",
                   "Spell sun.", "spell", ("sun",)),
    ),
}


def audio_game_ids() -> tuple[str, ...]:
    return tuple(AUDIO_BANK)


def audio_round_public(game_id: str, index: int = 0) -> dict[str, Any]:
    rounds = AUDIO_BANK[game_id]
    slot = index % len(rounds)
    rnd = rounds[slot]
    return {
        "game": game_id,
        "round_id": rnd.round_id,
        "index": slot,
        "title": rnd.title,
        "prompt": rnd.prompt,
        "speak": rnd.speak,
    }


def _mentions(heard: str, word: str) -> bool:
    folded = fold_text(heard)
    target = fold_text(word)
    if not target or not folded:
        return False
    if re.search(rf"\b{re.escape(target)}\b", folded):
        return True
    return score_spoken(target, heard, kind="word")["score"] >= 84


def _spelled(heard: str, word: str) -> bool:
    letters = list(fold_text(word).replace(" ", ""))
    if not letters:
        return False
    if _mentions(heard, word):
        return True
    alias = {
        name: letter
        for letter, names in LETTER_ALIASES.items()
        for name in names
    }
    mapped = [alias.get(token, token) for token in fold_text(heard).split()]
    compact = [token for token in mapped if token]
    return compact == letters or "".join(compact) == "".join(letters)


def score_audio(game_id: str, round_id: str, heard: str) -> dict[str, Any]:
    rounds = AUDIO_BANK.get(game_id)
    rnd = next((row for row in rounds or () if row.round_id == round_id), None)
    if rnd is None:
        return {
            "target": round_id,
            "heard": (heard or "").strip(),
            "score": 0,
            "passed": False,
            "stars": 0,
            "feedback": "Pick a listening game, then try again.",
        }
    if rnd.mode == "phrase":
        best = max(
            (score_spoken(item, heard, kind="word")["score"] for item in rnd.accept),
            default=0,
        )
        passed = best >= 72
    elif rnd.mode == "all":
        passed = bool(rnd.require) and all(_mentions(heard, item) for item in rnd.require)
        best = 100 if passed else 0
    elif rnd.mode == "spell":
        passed = any(_spelled(heard, item) for item in rnd.accept)
        best = 100 if passed else 0
    else:
        passed = any(_mentions(heard, item) for item in rnd.accept)
        best = 100 if passed else 0
    retry = {
        "phrase": "Listen once more, then say it back.",
        "any": "Listen once more, then answer in your own words.",
        "all": "Say the important part of what you heard.",
        "spell": "Say each letter in the word.",
    }.get(rnd.mode, "Listen once more, then try again.")
    return {
        "target": rnd.round_id,
        "heard": (heard or "").strip(),
        "score": best if passed else min(best, 40),
        "passed": passed,
        "stars": 3 if passed and best >= 90 else 2 if passed else 0,
        "feedback": "You got it! That showed you were listening." if passed else f"Almost! {retry}",
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
