"""Media assets + learning games for Theodore course sessions.

Visual challenges grade author-supplied labels and the vetted A–Z picture
catalog. They do not infer what an unlabeled image depicts.
"""

from __future__ import annotations

import difflib
import random
import re
import unicodedata
import uuid
from enum import Enum

from pydantic import BaseModel, Field

from .types import CourseSlide


class MediaKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    ANIMATION = "animation"


class MediaAsset(BaseModel):
    asset_id: str
    kind: MediaKind
    title: str
    url: str = ""
    local_path: str = ""
    duration_sec: float | None = None
    slide_index: int | None = None
    autoplay: bool = False
    caption: str = ""


class GameKind(str, Enum):
    MATCH_TERM = "match_term"
    ORDER_STEPS = "order_steps"
    SPOT_GAP = "spot_gap"
    IMAGE_TO_WORD = "image_to_word"
    WORD_TO_IMAGE = "word_to_image"
    HOTSPOT = "hotspot"
    CLASSIFY = "classify"
    SORT = "sort"
    LABEL_PLACEMENT = "label_placement"
    PICTURE_ORDER = "picture_order"
    SPOT_DIFFERENCE = "spot_difference"
    MEMORY_PAIRS = "memory_pairs"


class GameChallenge(BaseModel):
    game_id: str
    kind: GameKind
    title: str
    prompt: str
    payload: dict = Field(default_factory=dict)
    objective_id: str = ""
    pass_score: float = 0.7


class GameAttemptResult(BaseModel):
    game_id: str
    score: float
    passed: bool
    feedback: str
    objective_id: str = ""
    explanation: str = ""


def media_suggestions_for_slide(slide: CourseSlide) -> list[MediaAsset]:
    """Return real slide media first, with placeholders only for generic courses."""
    assets: list[MediaAsset] = []
    if slide.picture_url:
        assets.append(
            MediaAsset(
                asset_id=str(uuid.uuid4()),
                kind=MediaKind.IMAGE,
                title=slide.picture_alt or slide.title,
                url=slide.picture_url,
                slide_index=slide.index,
                caption=slide.picture_alt,
            )
        )
    if slide.video_url:
        assets.append(
            MediaAsset(
                asset_id=str(uuid.uuid4()),
                kind=MediaKind.VIDEO,
                title=f"Watch: {slide.title}",
                url=slide.video_url,
                slide_index=slide.index,
                caption=slide.video_caption,
            )
        )
    if assets:
        return assets

    # Generic corpus courses do not always have source media yet.
    base = f"studio://course-media/slide-{slide.index}"
    return [
        MediaAsset(
            asset_id=str(uuid.uuid4()),
            kind=MediaKind.ANIMATION,
            title=f"Animate: {slide.title}",
            url=f"{base}/animation.json",
            slide_index=slide.index,
            caption="Slide entrance + highlight key phrase",
            autoplay=True,
        ),
        MediaAsset(
            asset_id=str(uuid.uuid4()),
            kind=MediaKind.AUDIO,
            title=f"Narration bed: {slide.title}",
            url=f"{base}/narration.mp3",
            slide_index=slide.index,
            caption="Optional bed under Theodore TTS",
        ),
    ]


def build_match_term_game(
    slide: CourseSlide,
    objective_id: str = "",
) -> GameChallenge:
    title = slide.title.strip() or f"Slide {slide.index + 1}"
    term = title.split(" ")[0][:24] if title else "Concept"
    body = (slide.body or "").strip()
    correct = body[:120] if body else f"Key idea for {title}"
    options = [
        correct,
        "A distraction unrelated to this class objective.",
        "Skip — I already know everything.",
    ]
    return GameChallenge(
        game_id=str(uuid.uuid4()),
        kind=GameKind.MATCH_TERM,
        title="Match the learning point",
        prompt=f"Which definition matches “{term}” in this lesson?",
        payload={"term": term, "options": options, "correct_index": 0},
        objective_id=objective_id,
    )


def build_order_steps_game(
    slide: CourseSlide,
    objective_id: str = "",
) -> GameChallenge:
    parts = [(p or "").strip() for p in (slide.body or "").split(".") if (p or "").strip()]
    titled = (slide.title or "").strip()
    # Drop empties before the fallback check — [""] is truthy, so an empty
    # title + empty body used to ship a game whose only step was "".
    steps = [s for s in (parts[:3] if len(parts) >= 3 else ([titled] + parts)[:3]) if s]
    if not steps:
        steps = [titled or "Practice"]
    scrambled = list(reversed(steps))
    return GameChallenge(
        game_id=str(uuid.uuid4()),
        kind=GameKind.ORDER_STEPS,
        title="Check understanding",
        prompt="Put the learning steps in order",
        payload={"steps_correct": steps, "steps_shown": scrambled},
        objective_id=objective_id,
    )


def build_spot_gap_game(
    slide: CourseSlide,
    objective_id: str = "",
    options: int = 3,
) -> GameChallenge:
    """Blank a key phrase from the slide body and offer multiple choices.

    The learner picks the word/phrase that fills the gap. Distractors are drawn
    from other salient words on the same slide (falling back to honest generic
    options) so the game stays grounded in the real lesson text.
    """
    body = re.sub(r"\s+", " ", (slide.body or "").strip())
    title = (slide.title or "").strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    sentence = sentences[0] if sentences else (body or title or "Key idea")

    # Salient words = longer alphabetic tokens; prefer the longest as the answer.
    candidates = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", sentence)
    if not candidates:
        candidates = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", f"{title} {body}")
    key_phrase = max(candidates, key=len) if candidates else (title.split(" ")[0] if title else "concept")

    gapped = re.sub(
        re.escape(key_phrase), "_____", sentence, count=1
    ) if key_phrase in sentence else f"{sentence} (fill the blank: _____)"

    distractor_pool = [w for w in candidates if w.casefold() != key_phrase.casefold()]
    # De-duplicate case-insensitively, preserve order.
    seen: set[str] = set()
    distractors: list[str] = []
    for word in distractor_pool:
        if word.casefold() not in seen:
            seen.add(word.casefold())
            distractors.append(word)

    want = max(2, int(options) - 1)
    # A fill-the-blank answer is one word, so "all of the above" is never valid.
    generic = ["none of these", "skip this", "not covered here", "guesswork"]
    gi = 0
    while len(distractors) < want:
        distractors.append(generic[gi % len(generic)])
        gi += 1

    choices = [key_phrase] + distractors[:want]
    # Rotate so the answer is not always first; deterministic per slide.
    rot = slide.index % len(choices)
    choices = choices[rot:] + choices[:rot]
    correct_index = choices.index(key_phrase)

    return GameChallenge(
        game_id=str(uuid.uuid4()),
        kind=GameKind.SPOT_GAP,
        title="Spot the missing word",
        prompt=f"Fill the blank: “{gapped}”",
        payload={
            "sentence_with_gap": gapped,
            "answer": key_phrase,
            "options": choices,
            "correct_index": correct_index,
        },
        objective_id=objective_id,
    )


_GAME_ROTATION = (
    GameKind.MATCH_TERM,
    GameKind.ORDER_STEPS,
    GameKind.SPOT_GAP,
)


def pick_game_for_slide(
    slide: CourseSlide,
    objective_id: str = "",
    rotate_index: int = 0,
) -> GameChallenge:
    """Prefer curated cert game specs; else cycle match/order/spot_gap."""
    try:
        from .cert_multimodal import game_from_slide

        curated = game_from_slide(slide, objective_id=objective_id)
        if curated is not None:
            return curated
    except Exception:
        pass
    kind = _GAME_ROTATION[int(rotate_index) % len(_GAME_ROTATION)]
    if kind is GameKind.ORDER_STEPS:
        return build_order_steps_game(slide, objective_id)
    if kind is GameKind.SPOT_GAP:
        return build_spot_gap_game(slide, objective_id)
    return build_match_term_game(slide, objective_id)


def grade_game(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    if challenge.kind is GameKind.MATCH_TERM:
        selected = int(response.get("selected_index", -1))
        correct = int(challenge.payload.get("correct_index", 0))
        ok = selected == correct
        return GameAttemptResult(
            game_id=challenge.game_id,
            score=1.0 if ok else 0.0,
            passed=ok,
            feedback="Nice match." if ok else "Not quite — revisit the slide definition.",
            objective_id=challenge.objective_id,
        )
    if challenge.kind is GameKind.ORDER_STEPS:
        shown = list(response.get("ordered_steps") or [])
        correct = list(challenge.payload.get("steps_correct") or [])
        if not correct:
            return GameAttemptResult(
                game_id=challenge.game_id,
                score=0.0,
                passed=False,
                feedback="No steps.",
                objective_id=challenge.objective_id,
            )
        hits = sum(1 for a, b in zip(shown, correct) if a == b)
        score = hits / max(len(correct), 1)
        passed = score >= challenge.pass_score
        return GameAttemptResult(
            game_id=challenge.game_id,
            score=score,
            passed=passed,
            feedback="Order looks solid." if passed else "Reorder using the lesson sequence.",
            objective_id=challenge.objective_id,
        )
    if challenge.kind is GameKind.SPOT_GAP:
        correct = int(challenge.payload.get("correct_index", 0))
        selected = response.get("selected_index", None)
        if selected is None:
            # Allow answering by text as well as by index.
            answer = str(response.get("selected_text", "")).strip().casefold()
            expected = str(challenge.payload.get("answer", "")).strip().casefold()
            ok = bool(answer) and answer == expected
        else:
            ok = int(selected) == correct
        return GameAttemptResult(
            game_id=challenge.game_id,
            score=1.0 if ok else 0.0,
            passed=ok,
            feedback="You spotted it." if ok else "Re-read the sentence and try the blank again.",
            objective_id=challenge.objective_id,
        )
    visual = _grade_visual(challenge, response)
    if visual is not None:
        return visual
    return GameAttemptResult(
        game_id=challenge.game_id,
        score=0.0,
        passed=False,
        feedback="Unsupported game kind.",
        objective_id=challenge.objective_id,
    )


# Picture words and glyphs are copied from the children webcam lab catalog.
# Named regions are that lab's 3x3 grid. Course studio does not import the lab.
# A hotspot hit is the named region itself: a neighbor does not count. The lab's
# speech score is not copied as a pass threshold; a typed near-miss stays wrong
# and is explained. Only these catalog pairs have a meaning we will state
# without an author-supplied label.
PICTURE_WORDS: dict[str, str] = {
    "a": "apple",
    "b": "ball",
    "c": "cat",
    "d": "dragon",
    "e": "elephant",
    "f": "fish",
    "g": "grape",
    "h": "heart",
    "i": "ice cream",
    "j": "jellyfish",
    "k": "kite",
    "l": "lion",
    "m": "moon",
    "n": "nest",
    "o": "octopus",
    "p": "popcorn",
    "q": "queen",
    "r": "rocket",
    "s": "star",
    "t": "teddy",
    "u": "umbrella",
    "v": "violin",
    "w": "whale",
    "x": "xylophone",
    "y": "yo-yo",
    "z": "zebra",
}
PICTURE_EMOJI: dict[str, str] = {
    "apple": "🍎",
    "ball": "⚽",
    "cat": "🐱",
    "dragon": "🐉",
    "elephant": "🐘",
    "fish": "🐟",
    "grape": "🍇",
    "heart": "💖",
    "ice cream": "🍦",
    "jellyfish": "🪼",
    "kite": "🪁",
    "lion": "🦁",
    "moon": "🌙",
    "nest": "🪺",
    "octopus": "🐙",
    "popcorn": "🍿",
    "queen": "👑",
    "rocket": "🚀",
    "star": "⭐",
    "teddy": "🧸",
    "umbrella": "☂️",
    "violin": "🎻",
    "whale": "🐋",
    "xylophone": "🎹",
    "yo-yo": "🪀",
    "zebra": "🦓",
}
NAMED_REGIONS: tuple[str, ...] = (
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
)
VISUAL_GAME_KINDS: tuple[GameKind, ...] = (
    GameKind.IMAGE_TO_WORD,
    GameKind.WORD_TO_IMAGE,
    GameKind.HOTSPOT,
    GameKind.CLASSIFY,
    GameKind.SORT,
    GameKind.LABEL_PLACEMENT,
    GameKind.PICTURE_ORDER,
    GameKind.SPOT_DIFFERENCE,
    GameKind.MEMORY_PAIRS,
)
# Children-lab word threshold, used only to say "Almost" — never to mark a pass.
_WORD_NEAR_MISS_RATIO = 0.72
_GLYPH_TO_WORD = {glyph: word for word, glyph in PICTURE_EMOJI.items()}


class VisualChallengeError(ValueError):
    """A visual challenge is missing labels or contradicts a known picture."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems) or "invalid visual challenge")


def _assert_picture_catalog() -> None:
    words = list(PICTURE_WORDS.values())
    if list(PICTURE_WORDS) != list("abcdefghijklmnopqrstuvwxyz"):
        raise RuntimeError("picture catalog must be the letters a through z")
    if len(set(words)) != 26 or set(PICTURE_EMOJI) != set(words):
        raise RuntimeError("every catalog word needs one glyph")
    if len(set(PICTURE_EMOJI.values())) != 26:
        raise RuntimeError("catalog glyphs must be unique")
    if len(NAMED_REGIONS) != 9 or len(set(NAMED_REGIONS)) != 9:
        raise RuntimeError("named regions must be the 3x3 grid")


_assert_picture_catalog()


def fold_label(text: str) -> str:
    """Fold a label the way the children lab folds spoken text."""
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(char for char in raw if not unicodedata.combining(char))
    raw = re.sub(r"[^a-z0-9\s-]", " ", raw.lower())
    return re.sub(r"\s+", " ", raw).strip()


_CATALOG_FOLDED = frozenset(fold_label(word) for word in PICTURE_EMOJI)


def _noun_forms(word: str) -> set[str]:
    """apple/apples match. A catalog word is not chopped into a different word."""
    folded = fold_label(word)
    if not folded:
        return set()
    forms = {folded}
    if len(folded) >= 3 and not folded.endswith("s"):
        forms.add(folded + "s")
    if (
        len(folded) >= 4
        and folded.endswith("s")
        and not folded.endswith("ss")
        and folded not in _CATALOG_FOLDED
    ):
        forms.add(folded[:-1])
    return forms


def labels_match(expected: str, actual: str) -> bool:
    actual_folded = fold_label(actual)
    return bool(actual_folded) and actual_folded in _noun_forms(expected)


def _near_miss(expected: str, actual: str) -> bool:
    expected_folded = fold_label(expected)
    actual_folded = fold_label(actual)
    if not expected_folded or not actual_folded or labels_match(expected, actual):
        return False
    ratio = difflib.SequenceMatcher(a=expected_folded, b=actual_folded).ratio()
    return ratio >= _WORD_NEAR_MISS_RATIO


def _same(left: str, right: str) -> bool:
    folded = fold_label(left)
    return bool(folded) and folded == fold_label(right)


def _lookup(mapping: dict[str, str], key: str, default: str = "") -> str:
    for ident, value in mapping.items():
        if _same(ident, key):
            return value
    return default


def _q(text: str) -> str:
    return f"“{text}”"


def _slug(label: str) -> str:
    return fold_label(label).replace(" ", "-")


def catalog_glyph(label: str) -> str:
    folded = fold_label(label)
    for word, glyph in PICTURE_EMOJI.items():
        if fold_label(word) == folded:
            return glyph
    return ""


def catalog_words_in_text(text: str) -> list[str]:
    """Catalog words that actually appear, in text order. No extra meanings."""
    folded = fold_label(text)
    found: list[tuple[int, str]] = []
    for word in PICTURE_WORDS.values():
        positions = []
        for form in _noun_forms(word):
            match = re.search(
                rf"(?<![a-z0-9]){re.escape(form)}(?![a-z0-9])",
                folded,
            )
            if match:
                positions.append(match.start())
        if positions:
            found.append((min(positions), word))
    found.sort(key=lambda row: row[0])
    return [word for _, word in found]


def _short_label(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned or len(cleaned) > 48 or re.search(r"[.!?]", cleaned):
        return ""
    words = cleaned.split(" ")
    if not 1 <= len(words) <= 4:
        return ""
    return cleaned


def _normalize_card(raw: dict | None, fallback_id: str) -> dict[str, str]:
    data = raw if isinstance(raw, dict) else {}
    label = str(data.get("label") or "").strip()
    alt = str(data.get("alt") or label).strip()
    if not label and alt:
        label = alt
    card_id = str(data.get("id") or "").strip() or _slug(label) or fallback_id
    return {
        "id": card_id,
        "label": label,
        "alt": alt or label,
        "glyph": str(data.get("glyph") or "").strip(),
        "image_url": str(data.get("image_url") or data.get("url") or "").strip(),
    }


def _attach_catalog_glyph(card: dict[str, str]) -> dict[str, str]:
    """Attach a glyph only when the label is exactly a catalog word."""
    if card.get("glyph") or card.get("image_url"):
        return card
    glyph = catalog_glyph(card.get("label") or "")
    if not glyph:
        return card
    return {**card, "glyph": glyph}


def _slide_picture(slide: CourseSlide | None) -> dict[str, str] | None:
    """Use the slide picture only when the author already named it."""
    if slide is None:
        return None
    label = _short_label(slide.picture_alt)
    if not label:
        return None
    card = _normalize_card(
        {"id": "slide-picture", "label": label, "alt": label, "image_url": slide.picture_url},
        "slide-picture",
    )
    if card["image_url"]:
        return card
    card = _attach_catalog_glyph(card)
    if not card["glyph"]:
        return None
    return card


def _check_picture(
    card: dict,
    problems: list[str],
    where: str,
    *,
    require_picture: bool,
) -> None:
    if not isinstance(card, dict):
        problems.append(f"{where} is missing")
        return
    label = str(card.get("label") or "").strip()
    glyph = str(card.get("glyph") or "").strip()
    url = str(card.get("image_url") or "").strip()
    if not label and (glyph or url):
        problems.append(
            f"{where} has a picture without a label; image meaning is not inferred"
        )
    elif require_picture and not label:
        problems.append(f"{where} needs a label; image meaning is not inferred")
    elif require_picture and not glyph and not url:
        problems.append(
            f"{where} needs a picture (catalog glyph or image url) and a label"
        )
    catalog_word = _GLYPH_TO_WORD.get(glyph, "")
    if glyph and catalog_word and label and not labels_match(catalog_word, label):
        problems.append(
            f"{where} glyph {glyph} is the catalog picture for "
            f"{_q(catalog_word)}, not {_q(label)}"
        )


def _conflicts(candidate: str, answer: str) -> bool:
    if labels_match(answer, candidate) or labels_match(candidate, answer):
        return True
    cand = fold_label(candidate)
    ans = fold_label(answer)
    if not cand or not ans:
        return True
    return cand in ans or ans in cand


def _distractor_words(answer: str, slide: CourseSlide | None, count: int) -> list[str]:
    pool: list[str] = []
    if slide is not None:
        text = f"{slide.title} {slide.body}"
        pool.extend(re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text))
    pool.extend(PICTURE_WORDS.values())
    chosen: list[str] = []
    seen: set[str] = set()
    for word in pool:
        key = fold_label(word)
        if not key or key in seen or _conflicts(word, answer):
            continue
        seen.add(key)
        chosen.append(word)
        if len(chosen) >= count:
            break
    return chosen


def _rotated(items: list, seed: str) -> list:
    if len(items) < 2:
        return list(items)
    rot = sum(ord(char) for char in seed) % len(items)
    return list(items[rot:]) + list(items[:rot])


def _shuffled(items: list, seed: str) -> list:
    copy = list(items)
    random.Random(seed).shuffle(copy)
    return copy


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _normalize_regions(regions: list) -> tuple[list[dict[str, str]], list[str]]:
    problems: list[str] = []
    out: list[dict[str, str]] = []
    if not isinstance(regions, list):
        return [], ["regions must be a list of ids"]
    for index, raw in enumerate(regions, start=1):
        if isinstance(raw, str):
            ident = raw.strip()
            name = ident
        elif isinstance(raw, dict):
            ident = str(raw.get("id") or "").strip()
            name = str(raw.get("name") or ident).strip()
            if not ident and ({"x", "y"} & set(raw)):
                problems.append(
                    "hotspot regions need an id; x/y coordinates are not graded"
                )
                continue
        else:
            problems.append(f"region {index} is not an id")
            continue
        if not ident:
            problems.append(f"region {index} is missing an id")
            continue
        out.append({"id": ident, "name": name or ident})
    folded = [fold_label(row["id"]) for row in out]
    if len(set(folded)) != len(folded):
        problems.append("duplicate region ids")
    return out, problems


def _item_rows(raw_items: list) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, raw in enumerate(raw_items, start=1):
        if isinstance(raw, str):
            raw = {"label": raw}
        rows.append(_attach_catalog_glyph(_normalize_card(raw, f"item-{index}")))
    return rows


def _check_items(items: list, problems: list[str], *, require_picture: bool) -> None:
    if len(items) < 2:
        problems.append("needs at least two items")
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            problems.append(f"item {index} is missing")
            continue
        _check_picture(item, problems, f"item {index}", require_picture=require_picture)
        if not require_picture and not str(item.get("label") or "").strip():
            problems.append(f"item {index} needs a label")
        ident = str(item.get("id") or "")
        key = fold_label(ident)
        if not key:
            problems.append(f"item {index} is missing an id")
        elif key in seen:
            problems.append("duplicate item ids")
        else:
            seen.add(key)


def _check_image_to_word(payload: dict, problems: list[str]) -> None:
    image = payload.get("image")
    _check_picture(
        image if isinstance(image, dict) else {},
        problems,
        "image",
        require_picture=True,
    )
    options = payload.get("options")
    if not isinstance(options, list) or len(options) < 2:
        problems.append("image_to_word needs at least two word choices")
        return
    labels = [str(option) for option in options]
    if any(not label.strip() for label in labels):
        problems.append("empty word choice")
    forms: list[set[str]] = []
    for label in labels:
        current = _noun_forms(label)
        if any(current & previous for previous in forms):
            problems.append("duplicate word choices")
            break
        forms.append(current)
    answer = str(payload.get("answer") or "")
    index = payload.get("correct_index")
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(labels):
        problems.append("correct_index out of range")
    elif not labels_match(answer, labels[index]):
        problems.append("correct_index does not point at the answer")
    image_label = str((image or {}).get("label") or "") if isinstance(image, dict) else ""
    if answer and image_label and not labels_match(answer, image_label):
        problems.append("answer does not match the picture label")


def _check_word_to_image(payload: dict, problems: list[str]) -> None:
    word = str(payload.get("word") or "").strip()
    if not word:
        problems.append("word_to_image needs a word")
    images = payload.get("images")
    if not isinstance(images, list) or len(images) < 2:
        problems.append("word_to_image needs at least two pictures")
        return
    matched = []
    for index, image in enumerate(images, start=1):
        _check_picture(
            image if isinstance(image, dict) else {},
            problems,
            f"picture {index}",
            require_picture=True,
        )
        if isinstance(image, dict) and word and labels_match(word, str(image.get("label") or "")):
            matched.append(image)
    if word and len(matched) != 1:
        problems.append(
            "word_to_image needs exactly one picture whose label matches the word"
        )
    elif matched and not _same(
        str(matched[0].get("id") or ""),
        str(payload.get("correct_id") or ""),
    ):
        problems.append("correct_id is not the picture labeled with the word")


def _check_hotspot(payload: dict, problems: list[str]) -> None:
    regions = payload.get("regions")
    if not isinstance(regions, list) or len(regions) < 2:
        problems.append("hotspot needs at least two regions")
        regions = regions if isinstance(regions, list) else []
    ids = []
    for index, region in enumerate(regions, start=1):
        if not isinstance(region, dict) or not str(region.get("id") or "").strip():
            problems.append(f"region {index} is missing an id")
            continue
        ids.append(str(region["id"]))
    if len({fold_label(ident) for ident in ids}) != len(ids):
        problems.append("duplicate region ids")
    correct = str(payload.get("correct_region") or "").strip()
    if not correct or not any(_same(correct, ident) for ident in ids):
        problems.append("correct_region is not one of the regions")
    if "image" in payload:
        _check_picture(payload.get("image"), problems, "image", require_picture=True)


def _check_classify(payload: dict, problems: list[str]) -> None:
    categories = payload.get("categories")
    if not isinstance(categories, list) or len([c for c in categories if str(c).strip()]) < 2:
        problems.append("classify needs at least two groups")
        categories = []
    names = [str(category).strip() for category in categories if str(category).strip()]
    if len({fold_label(name) for name in names}) != len(names):
        problems.append("duplicate groups")
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    _check_items(items, problems, require_picture=False)
    answer = payload.get("answer") if isinstance(payload.get("answer"), dict) else None
    if answer is None:
        problems.append("classify needs an answer for every item")
        return
    item_ids = [str(item.get("id") or "") for item in items if isinstance(item, dict)]
    if {fold_label(key) for key in answer} != {fold_label(ident) for ident in item_ids if ident}:
        problems.append("answer must classify every item once")
    for raw_category in answer.values():
        if not any(_same(str(raw_category), name) for name in names):
            problems.append(f"{_q(str(raw_category))} is not one of the groups")


def _check_sort(payload: dict, problems: list[str]) -> None:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    _check_items(items, problems, require_picture=False)
    order = payload.get("order_correct")
    ids = [str(item.get("id") or "") for item in items if isinstance(item, dict)]
    if not isinstance(order, list) or [fold_label(str(x)) for x in order] != [
        fold_label(ident) for ident in ids
    ]:
        # order_correct must be a permutation of the item ids, not a copy of
        # the list position. Compare as sets plus length, then require each id.
        order_ids = [str(x) for x in order] if isinstance(order, list) else []
        if len(order_ids) != len(ids) or {fold_label(x) for x in order_ids} != {
            fold_label(ident) for ident in ids if ident
        }:
            problems.append("sort order must include each item once")
    shown = payload.get("order_shown")
    if isinstance(shown, list):
        shown_ids = [str(x) for x in shown]
        if {fold_label(x) for x in shown_ids} != {fold_label(ident) for ident in ids if ident}:
            problems.append("order_shown must be the same items")


def _check_label_placement(payload: dict, problems: list[str]) -> None:
    targets = payload.get("targets") if isinstance(payload.get("targets"), list) else []
    labels = payload.get("labels") if isinstance(payload.get("labels"), list) else []
    answer = payload.get("answer") if isinstance(payload.get("answer"), dict) else None
    if len(targets) < 1:
        problems.append("label placement needs a spot")
    target_ids = []
    for index, target in enumerate(targets, start=1):
        if not isinstance(target, dict) or not str(target.get("id") or "").strip():
            problems.append(f"spot {index} is missing an id")
            continue
        target_ids.append(str(target["id"]))
    if len({fold_label(ident) for ident in target_ids}) != len(target_ids):
        problems.append("duplicate spots")
    if answer is None:
        problems.append("label placement needs a label for every spot")
        return
    if {fold_label(str(key)) for key in answer} != {fold_label(ident) for ident in target_ids}:
        problems.append("answer must label every spot once")
    answer_labels = [str(value) for value in answer.values()]
    if len({fold_label(label) for label in answer_labels}) != len(answer_labels):
        problems.append("the same label is placed on two spots")
    choice_labels = [str(label) for label in labels]
    if len(choice_labels) < len(answer_labels):
        problems.append("labels must include every placed label")
    for label in answer_labels:
        if not any(labels_match(label, choice) for choice in choice_labels):
            problems.append(f"{_q(label)} is not one of the labels")
    forms: list[set[str]] = []
    for label in choice_labels:
        current = _noun_forms(label)
        if any(current & previous for previous in forms):
            problems.append("duplicate labels")
            break
        forms.append(current)
    if len(targets) < 2 and len(choice_labels) <= len(target_ids):
        problems.append("label placement needs another label or another spot")
    if "image" in payload:
        _check_picture(payload.get("image"), problems, "image", require_picture=True)


def _check_picture_order(payload: dict, problems: list[str]) -> None:
    cards = payload.get("cards_correct")
    if not isinstance(cards, list):
        problems.append("picture order needs pictures")
        return
    _check_items(cards, problems, require_picture=True)
    shown = payload.get("cards_shown")
    if isinstance(shown, list):
        correct_ids = {
            fold_label(str(card.get("id") or ""))
            for card in cards
            if isinstance(card, dict)
        }
        shown_ids = {
            fold_label(str(card.get("id") or "")) for card in shown if isinstance(card, dict)
        }
        if shown_ids != correct_ids:
            problems.append("cards_shown must be the same pictures")


def _check_spot_difference(payload: dict, problems: list[str]) -> None:
    for side in ("left", "right"):
        _check_picture(payload.get(side), problems, side, require_picture=True)
    differences = payload.get("differences")
    if not isinstance(differences, list) or not differences:
        problems.append("spot the difference needs an authored difference")
        differences = []
    seen: set[str] = set()
    for index, raw in enumerate(differences, start=1):
        if not isinstance(raw, dict):
            problems.append(f"difference {index} is missing")
            continue
        if {"x", "y"} & set(raw) and not str(raw.get("region") or "").strip():
            problems.append("differences need a region id; x/y coordinates are not graded")
        ident = str(raw.get("id") or "").strip()
        region = str(raw.get("region") or "").strip()
        note = str(raw.get("note") or "").strip()
        if not ident:
            problems.append(f"difference {index} is missing an id")
        elif fold_label(ident) in seen:
            problems.append("duplicate difference ids")
        else:
            seen.add(fold_label(ident))
        if not region:
            problems.append(f"difference {index} needs a region id")
        if not note:
            problems.append(
                f"difference {index} needs a note; pictures are not compared as pixels"
            )
    decoys = payload.get("decoys") if isinstance(payload.get("decoys"), list) else []
    for index, raw in enumerate(decoys, start=1):
        if not isinstance(raw, dict) or not str(raw.get("id") or "").strip():
            problems.append(f"decoy {index} is missing an id")
            continue
        if fold_label(str(raw["id"])) in seen:
            problems.append("a decoy uses a difference id")
        seen.add(fold_label(str(raw["id"])))
        if not str(raw.get("region") or "").strip():
            problems.append(f"decoy {index} needs a region id")


def _check_memory_pairs(payload: dict, problems: list[str]) -> None:
    pairs = payload.get("pairs")
    if not isinstance(pairs, list) or len(pairs) < 2:
        problems.append("memory pairs needs at least two pairs")
        return
    seen_cards: set[str] = set()
    seen_pairs: set[str] = set()
    for index, pair in enumerate(pairs, start=1):
        if not isinstance(pair, dict):
            problems.append(f"pair {index} is missing")
            continue
        pair_id = str(pair.get("id") or "").strip()
        if not pair_id:
            problems.append(f"pair {index} is missing an id")
        elif fold_label(pair_id) in seen_pairs:
            problems.append("duplicate pair ids")
        else:
            seen_pairs.add(fold_label(pair_id))
        for side in ("left", "right"):
            card = pair.get(side)
            _check_picture(
                card if isinstance(card, dict) else {},
                problems,
                f"pair {index} {side}",
                require_picture=False,
            )
            if isinstance(card, dict) and not str(card.get("label") or "").strip():
                problems.append(f"pair {index} {side} needs a label")
            ident = str((card or {}).get("id") or "") if isinstance(card, dict) else ""
            key = fold_label(ident)
            if not key:
                problems.append(f"pair {index} {side} is missing an id")
            elif key in seen_cards:
                problems.append("duplicate memory cards")
            else:
                seen_cards.add(key)
        left = pair.get("left") if isinstance(pair.get("left"), dict) else {}
        right = pair.get("right") if isinstance(pair.get("right"), dict) else {}
        left_visual = bool(left.get("glyph") or left.get("image_url"))
        right_visual = bool(right.get("glyph") or right.get("image_url"))
        if not left_visual and not right_visual:
            problems.append(f"pair {index} needs a picture on one side")


_VISUAL_CHECKS = {
    GameKind.IMAGE_TO_WORD: _check_image_to_word,
    GameKind.WORD_TO_IMAGE: _check_word_to_image,
    GameKind.HOTSPOT: _check_hotspot,
    GameKind.CLASSIFY: _check_classify,
    GameKind.SORT: _check_sort,
    GameKind.LABEL_PLACEMENT: _check_label_placement,
    GameKind.PICTURE_ORDER: _check_picture_order,
    GameKind.SPOT_DIFFERENCE: _check_spot_difference,
    GameKind.MEMORY_PAIRS: _check_memory_pairs,
}


def visual_challenge_problems(challenge: GameChallenge) -> list[str]:
    """Structural checks for visual challenges. The original three kinds pass."""
    if challenge.kind not in VISUAL_GAME_KINDS:
        return []
    problems: list[str] = []
    if not challenge.prompt.strip():
        problems.append("missing prompt")
    payload = challenge.payload if isinstance(challenge.payload, dict) else {}
    if not str(payload.get("explanation") or "").strip():
        problems.append("missing explanation")
    checker = _VISUAL_CHECKS.get(challenge.kind)
    if checker is not None:
        checker(payload, problems)
    return problems


def _attempt(
    challenge: GameChallenge,
    score: float,
    feedback: str,
    explanation: str = "",
) -> GameAttemptResult:
    bounded = max(0.0, min(1.0, float(score)))
    why = explanation or str(challenge.payload.get("explanation") or "")
    return GameAttemptResult(
        game_id=challenge.game_id,
        score=bounded,
        passed=bounded >= float(challenge.pass_score),
        feedback=feedback,
        objective_id=challenge.objective_id,
        explanation=why,
    )


def _grade_image_to_word(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    payload = challenge.payload
    label = str(payload["image"]["label"])
    options = [str(option) for option in payload["options"]]
    selected = response.get("selected_index", None)
    typed = str(response.get("selected_text") or "").strip()
    if selected is not None:
        index = _as_int(selected)
        if index is None or not 0 <= index < len(options):
            return _attempt(
                challenge,
                0.0,
                f"That choice is not one of the options. This picture is labeled {_q(label)}.",
            )
        chosen = options[index]
        ok = index == int(payload["correct_index"])
    elif typed:
        chosen = typed
        ok = labels_match(label, typed)
    else:
        return _attempt(
            challenge,
            0.0,
            f"Choose the word for this picture. It is labeled {_q(label)}.",
        )
    if ok:
        return _attempt(challenge, 1.0, f"Yes. This picture is {_q(label)}.")
    prefix = "Almost. " if _near_miss(label, chosen) else "Not quite. "
    return _attempt(
        challenge,
        0.0,
        f"{prefix}You chose {_q(chosen)}. This picture is labeled {_q(label)}.",
    )


def _grade_word_to_image(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    payload = challenge.payload
    images = list(payload["images"])
    word = str(payload["word"])
    correct = next(image for image in images if _same(str(image["id"]), str(payload["correct_id"])))
    picked = None
    if response.get("selected_id") is not None:
        selected_id = str(response.get("selected_id"))
        picked = next((image for image in images if _same(str(image["id"]), selected_id)), None)
    elif response.get("selected_index", None) is not None:
        index = _as_int(response.get("selected_index"))
        if index is not None and 0 <= index < len(images):
            picked = images[index]
    if picked is None:
        return _attempt(
            challenge,
            0.0,
            f"Choose the picture for {_q(word)}. It matches {_q(correct['label'])}.",
        )
    if _same(str(picked["id"]), str(correct["id"])):
        return _attempt(
            challenge,
            1.0,
            f"Yes. {_q(word)} matches the picture labeled {_q(correct['label'])}.",
        )
    return _attempt(
        challenge,
        0.0,
        (
            f"Not quite. You picked the picture labeled {_q(picked['label'])}. "
            f"{_q(word)} matches {_q(correct['label'])}."
        ),
    )


def _region_name(regions: list[dict], ident: str) -> str:
    for region in regions:
        if _same(str(region.get("id") or ""), ident) or _same(str(region.get("name") or ""), ident):
            return str(region.get("name") or region.get("id"))
    return ident


def _grade_hotspot(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    payload = challenge.payload
    regions = list(payload["regions"])
    correct_id = str(payload["correct_region"])
    correct_name = _region_name(regions, correct_id)
    note = str(payload.get("note") or "").strip()
    note_bit = f" {note}" if note else ""
    picked = str(
        response.get("region")
        or response.get("selected_region")
        or response.get("selected_id")
        or ""
    ).strip()
    if not picked:
        return _attempt(
            challenge,
            0.0,
            f"Choose a marked region. The marked spot is {_q(correct_name)}.{note_bit}",
        )
    match = next(
        (
            region
            for region in regions
            if _same(str(region.get("id") or ""), picked)
            or _same(str(region.get("name") or ""), picked)
        ),
        None,
    )
    if match is None:
        return _attempt(
            challenge,
            0.0,
            (
                f"{_q(picked)} is not one of the marked spots. "
                f"The marked spot is {_q(correct_name)}.{note_bit}"
            ),
        )
    if _same(str(match["id"]), correct_id):
        return _attempt(
            challenge,
            1.0,
            f"Yes. The marked spot is {_q(correct_name)}.{note_bit}",
        )
    picked_name = str(match.get("name") or match.get("id"))
    return _attempt(
        challenge,
        0.0,
        f"You chose {_q(picked_name)}. The marked spot is {_q(correct_name)}.{note_bit}",
    )


def _by_id(rows: list[dict], ident: str) -> dict | None:
    return next((row for row in rows if _same(str(row.get("id") or ""), ident)), None)


def _grade_classify(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    payload = challenge.payload
    items = list(payload["items"])
    answer = {str(key): str(value) for key, value in payload["answer"].items()}
    raw = response.get("assignments") if isinstance(response.get("assignments"), dict) else {}
    hits = 0
    notes: list[str] = []
    for item in items:
        expected = ""
        for key, category in answer.items():
            if _same(key, str(item["id"])):
                expected = category
                break
        got = ""
        for key, category in raw.items():
            if _same(str(key), str(item["id"])):
                got = str(category).strip()
                break
        label = str(item.get("label") or item["id"])
        if got and _same(got, expected):
            hits += 1
        else:
            shown = got or "nothing"
            notes.append(f"{_q(label)} belongs in {_q(expected)}, not {_q(shown)}.")
    total = len(items) or 1
    if hits == len(items) and items:
        feedback = f"Yes. All {hits} items are in the right group."
    else:
        feedback = f"{hits} of {len(items)} are in the right group. " + " ".join(notes)
    return _attempt(challenge, hits / total, feedback.strip())


def _sequence_feedback(
    challenge: GameChallenge,
    response: dict,
    rows: list[dict],
) -> GameAttemptResult:
    correct_ids = [str(row["id"]) for row in rows]
    labels = [str(row.get("label") or row["id"]) for row in rows]
    order_text = " → ".join(labels)
    shown_ids: list[str] | None = None
    if response.get("ordered_ids") is not None:
        shown_ids = [str(item) for item in response.get("ordered_ids") or []]
    elif response.get("ordered_labels") is not None or response.get("ordered_steps") is not None:
        raw_labels = response.get("ordered_labels")
        if raw_labels is None:
            raw_labels = response.get("ordered_steps") or []
        shown_ids = []
        for label in raw_labels:
            match = next(
                (
                    row for row in rows
                    if labels_match(str(row.get("label") or ""), str(label))
                ),
                None,
            )
            shown_ids.append(str(match["id"]) if match else f"missing:{label}")
    else:
        return _attempt(
            challenge,
            0.0,
            f"Put the items in order. The order is {order_text}.",
        )
    hits = sum(
        1
        for index, ident in enumerate(correct_ids)
        if index < len(shown_ids) and _same(shown_ids[index], ident)
    )
    notes: list[str] = []
    for index, (ident, label) in enumerate(zip(correct_ids, labels), start=1):
        got_id = shown_ids[index - 1] if index - 1 < len(shown_ids) else ""
        if _same(got_id, ident):
            continue
        got = _by_id(rows, got_id)
        got_label = str(got.get("label")) if got else (got_id or "nothing")
        notes.append(f"Place {index} should be {_q(label)}, not {_q(got_label)}.")
    total = len(rows) or 1
    if hits == len(rows) and rows:
        feedback = f"Yes. The order is {order_text}."
    else:
        feedback = f"{hits} of {len(rows)} are in the right place. " + " ".join(notes)
        feedback = f"{feedback} The order is {order_text}."
    return _attempt(challenge, hits / total, feedback.strip())


def _grade_sort(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    payload = challenge.payload
    by_id = {str(item["id"]): item for item in payload["items"]}
    rows = []
    for ident in payload["order_correct"]:
        item = _by_id(list(by_id.values()), str(ident))
        if item is not None:
            rows.append(item)
    return _sequence_feedback(challenge, response, rows)


def _grade_picture_order(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    return _sequence_feedback(challenge, response, list(challenge.payload["cards_correct"]))


def _grade_label_placement(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    payload = challenge.payload
    targets = list(payload["targets"])
    answer = {str(key): str(value) for key, value in payload["answer"].items()}
    raw = response.get("placements")
    if not isinstance(raw, dict):
        raw = response.get("assignments") if isinstance(response.get("assignments"), dict) else {}
    hits = 0
    notes: list[str] = []
    for target in targets:
        expected = ""
        for key, label in answer.items():
            if _same(key, str(target["id"])):
                expected = label
                break
        got = ""
        for key, label in raw.items():
            if _same(str(key), str(target["id"])):
                got = str(label).strip()
                break
        name = str(target.get("name") or target["id"])
        if got and labels_match(expected, got):
            hits += 1
        else:
            shown = got or "nothing"
            notes.append(f"{_q(name)} is labeled {_q(expected)}. You placed {_q(shown)} there.")
    total = len(targets) or 1
    if hits == len(targets) and targets:
        feedback = f"Yes. All {hits} labels are on the right spots."
    else:
        feedback = f"{hits} of {len(targets)} labels are on the right spots. " + " ".join(notes)
    return _attempt(challenge, hits / total, feedback.strip())


def _id_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = [str(item) for item in value]
    else:
        return []
    seen: list[str] = []
    for item in raw:
        ident = item.strip()
        if ident and not any(_same(ident, previous) for previous in seen):
            seen.append(ident)
    return seen


def _grade_spot_difference(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    payload = challenge.payload
    differences = list(payload["differences"])
    decoys = list(payload.get("decoys") or [])
    true_ids = [str(item["id"]) for item in differences]
    picked = _id_list(response.get("selected_ids", response.get("differences")))
    hits = [ident for ident in picked if any(_same(ident, true) for true in true_ids)]
    false_ids = [ident for ident in picked if ident not in hits]
    missed = [item for item in differences if not any(_same(str(item["id"]), hit) for hit in hits)]
    denom = len(true_ids) + len(false_ids)
    score = (len(hits) / denom) if denom else 0.0
    missed_bits = [f"{item['region']} — {item['note']}" for item in missed]
    all_bits = [f"{item['region']} — {item['note']}" for item in differences]
    false_bits = []
    for ident in false_ids:
        decoy = next((item for item in decoys if _same(str(item.get("id") or ""), ident)), None)
        region = str(decoy.get("region")) if decoy else ident
        false_bits.append(f"{_q(region)} is not a difference")
    if len(hits) == len(true_ids) and not false_ids:
        feedback = f"Yes. You found all {len(hits)} differences."
    else:
        feedback = f"You found {len(hits)} of {len(true_ids)} differences."
        if missed_bits:
            feedback += " Still to find: " + "; ".join(missed_bits) + "."
        elif all_bits:
            feedback += " Differences: " + "; ".join(all_bits) + "."
        if false_bits:
            feedback += " " + ". ".join(false_bits) + "."
    return _attempt(challenge, score, feedback)


def _memory_links(response: dict) -> list[tuple[str, str]]:
    raw = response.get("matches")
    links: list[tuple[str, str]] = []
    if isinstance(raw, dict):
        pairs = raw.items()
    elif isinstance(raw, list):
        pairs = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                pairs.append((item[0], item[1]))
            elif isinstance(item, dict):
                pairs.append(
                    (item.get("left") or item.get("a"), item.get("right") or item.get("b"))
                )
    else:
        return []
    for left, right in pairs:
        a = str(left or "").strip()
        b = str(right or "").strip()
        if a and b:
            links.append((a, b))
    return links


def _grade_memory_pairs(challenge: GameChallenge, response: dict) -> GameAttemptResult:
    pairs = list(challenge.payload["pairs"])
    card_pair: dict[str, str] = {}
    card_label: dict[str, str] = {}
    for pair in pairs:
        for side in ("left", "right"):
            card = pair[side]
            card_pair[str(card["id"])] = str(pair["id"])
            card_label[str(card["id"])] = str(card.get("label") or card["id"])
    correct: set[str] = set()
    false_links = 0
    wrong_notes: list[str] = []
    for left_id, right_id in _memory_links(response):
        left_pair = _lookup(card_pair, left_id)
        right_pair = _lookup(card_pair, right_id)
        if left_pair and left_pair == right_pair and not _same(left_id, right_id):
            correct.add(left_pair)
            continue
        false_links += 1
        left_label = _lookup(card_label, left_id, left_id)
        right_label = _lookup(card_label, right_id, right_id)
        wrong_notes.append(f"{_q(left_label)} does not pair with {_q(right_label)}.")
    missed = []
    for pair in pairs:
        if any(_same(str(pair["id"]), found) for found in correct):
            continue
        left_label = str(pair["left"].get("label") or "")
        right_label = str(pair["right"].get("label") or "")
        missed.append(f"{_q(left_label)} pairs with {_q(right_label)}.")
    total = len(pairs) or 1
    score = max(0, len(correct) - false_links) / total
    if len(correct) == len(pairs) and false_links == 0:
        feedback = f"Yes. You matched all {len(pairs)} pairs."
    else:
        feedback = f"You matched {len(correct)} of {len(pairs)} pairs."
        if missed:
            feedback += " " + " ".join(missed)
        if wrong_notes:
            feedback += " " + " ".join(wrong_notes)
    return _attempt(challenge, score, feedback.strip())


_VISUAL_GRADERS = {
    GameKind.IMAGE_TO_WORD: _grade_image_to_word,
    GameKind.WORD_TO_IMAGE: _grade_word_to_image,
    GameKind.HOTSPOT: _grade_hotspot,
    GameKind.CLASSIFY: _grade_classify,
    GameKind.SORT: _grade_sort,
    GameKind.LABEL_PLACEMENT: _grade_label_placement,
    GameKind.PICTURE_ORDER: _grade_picture_order,
    GameKind.SPOT_DIFFERENCE: _grade_spot_difference,
    GameKind.MEMORY_PAIRS: _grade_memory_pairs,
}


def _grade_visual(challenge: GameChallenge, response: dict | None) -> GameAttemptResult | None:
    if challenge.kind not in VISUAL_GAME_KINDS:
        return None
    if not isinstance(response, dict):
        return _attempt(challenge, 0.0, "Send the answer as a response object.")
    problems = visual_challenge_problems(challenge)
    if problems:
        return _attempt(
            challenge,
            0.0,
            "This challenge cannot be graded: " + "; ".join(problems),
        )
    return _VISUAL_GRADERS[challenge.kind](challenge, response)


def _make_challenge(
    kind: GameKind,
    title: str,
    prompt: str,
    payload: dict,
    objective_id: str,
    pass_score: float,
) -> GameChallenge:
    return GameChallenge(
        game_id=str(uuid.uuid4()),
        kind=kind,
        title=title,
        prompt=prompt,
        payload=payload,
        objective_id=objective_id,
        pass_score=pass_score,
    )


def _publish(game: GameChallenge) -> GameChallenge:
    problems = visual_challenge_problems(game)
    if problems:
        raise VisualChallengeError(problems)
    return game


def _refuse(explicit: bool, message: str) -> None:
    if explicit:
        raise VisualChallengeError([message])


def build_image_to_word_game(
    slide: CourseSlide | None = None,
    objective_id: str = "",
    *,
    image: dict | None = None,
    options: list[str] | None = None,
    answer: str = "",
    option_count: int = 3,
    prompt: str = "",
    pass_score: float = 0.7,
    explicit: bool = False,
) -> GameChallenge | None:
    """Name a labeled picture. An unlabeled url is not given a meaning."""
    if image is not None:
        card = _normalize_card(image, "picture")
        # A url or glyph with no label is not named by the answer key. The
        # picture itself has to say what it is.
        if (
            answer.strip()
            and not card["label"]
            and not card["image_url"]
            and not card["glyph"]
        ):
            card["label"] = answer.strip()
            card["alt"] = card["label"]
        card = _attach_catalog_glyph(card)
        resolved = answer.strip() or card["label"]
    elif answer.strip():
        photo = _slide_picture(slide)
        if photo is not None and labels_match(photo["label"], answer):
            card = photo
            resolved = photo["label"]
        elif catalog_glyph(answer):
            key = next(
                word for word in PICTURE_EMOJI if fold_label(word) == fold_label(answer)
            )
            card = _normalize_card(
                {"label": key, "glyph": PICTURE_EMOJI[key], "alt": key},
                _slug(key),
            )
            resolved = key
        else:
            card = _normalize_card({"label": answer.strip(), "alt": answer.strip()}, "picture")
            resolved = answer.strip()
    else:
        card = _slide_picture(slide)
        resolved = card["label"] if card else ""
        if card is None and slide is not None:
            words = catalog_words_in_text(f"{slide.title} {slide.body}")
            if words:
                word = words[0]
                card = _normalize_card(
                    {"label": word, "glyph": PICTURE_EMOJI[word], "alt": word},
                    _slug(word),
                )
                resolved = word
    if card is None or not resolved:
        _refuse(explicit or image is not None or options is not None or bool(answer.strip()),
                "image_to_word needs a labeled picture")
        return None
    want = max(2, int(option_count))
    if options is not None:
        choices = [str(option).strip() for option in options if str(option).strip()]
    else:
        choices = [resolved, *_distractor_words(resolved, slide, want - 1)]
        choices = _rotated(choices, f"image-to-word|{resolved}|{objective_id}")
    correct_index = next(
        (index for index, choice in enumerate(choices) if labels_match(resolved, choice)),
        -1,
    )
    explanation = f"This picture is labeled {_q(card['label'])}."
    game = _make_challenge(
        GameKind.IMAGE_TO_WORD,
        "Name the picture",
        prompt or "Which word names this picture?",
        {
            "image": card,
            "options": choices,
            "correct_index": correct_index,
            "answer": card["label"],
            "explanation": explanation,
        },
        objective_id,
        pass_score,
    )
    return _publish(game)


def build_word_to_image_game(
    slide: CourseSlide | None = None,
    objective_id: str = "",
    *,
    word: str = "",
    images: list[dict] | None = None,
    option_count: int = 3,
    prompt: str = "",
    pass_score: float = 0.7,
    explicit: bool = False,
) -> GameChallenge | None:
    """Pick the picture whose label is the word. Other pictures keep their own labels."""
    photo = _slide_picture(slide)
    resolved = word.strip()
    if not resolved and photo is not None:
        resolved = photo["label"]
    if not resolved and slide is not None:
        found = catalog_words_in_text(f"{slide.title} {slide.body}")
        resolved = found[0] if found else ""
    if not resolved:
        _refuse(explicit or images is not None or bool(word.strip()), "word_to_image needs a word")
        return None
    if images is not None:
        cards = [
            _attach_catalog_glyph(_normalize_card(raw, f"picture-{index}"))
            for index, raw in enumerate(images, start=1)
        ]
    else:
        correct: dict[str, str] | None = None
        if photo is not None and labels_match(photo["label"], resolved):
            correct = photo
        elif catalog_glyph(resolved):
            key = next(item for item in PICTURE_EMOJI if fold_label(item) == fold_label(resolved))
            correct = _normalize_card(
                {"label": key, "glyph": PICTURE_EMOJI[key], "alt": key},
                _slug(key),
            )
        if correct is None:
            _refuse(
                explicit or bool(word.strip()),
                "word_to_image needs a labeled picture for that word",
            )
            return None
        extras: list[dict[str, str]] = []
        if photo is not None and not labels_match(photo["label"], resolved):
            extras.append(photo)
        for catalog_word in PICTURE_WORDS.values():
            if labels_match(catalog_word, resolved) or labels_match(catalog_word, correct["label"]):
                continue
            extras.append(
                _normalize_card(
                    {
                        "label": catalog_word,
                        "glyph": PICTURE_EMOJI[catalog_word],
                        "alt": catalog_word,
                    },
                    _slug(catalog_word),
                )
            )
        room = max(1, int(option_count) - 1)
        cards = _rotated(
            [correct, *extras[:room]],
            f"word-to-image|{resolved}|{objective_id}",
        )
    match = next((card for card in cards if labels_match(resolved, card["label"])), None)
    explanation = (
        f"{_q(resolved)} matches the picture labeled {_q(match['label'])}."
        if match
        else f"{_q(resolved)} has no matching picture."
    )
    game = _make_challenge(
        GameKind.WORD_TO_IMAGE,
        "Find the picture",
        prompt or f"Which picture matches {_q(resolved)}?",
        {
            "word": resolved,
            "images": cards,
            "correct_id": match["id"] if match else "",
            "explanation": explanation,
        },
        objective_id,
        pass_score,
    )
    return _publish(game)


def build_hotspot_game(
    slide: CourseSlide | None = None,
    objective_id: str = "",
    *,
    regions: list | None = None,
    correct_region: str = "",
    note: str = "",
    image: dict | None = None,
    prompt: str = "",
    pass_score: float = 0.7,
    explicit: bool = False,
) -> GameChallenge | None:
    """Pick an authored region. Coordinates are not turned into a meaning."""
    if regions is None and not correct_region and image is None and not explicit:
        return None
    normalized, region_problems = _normalize_regions(list(regions or []))
    if region_problems:
        raise VisualChallengeError(region_problems)
    if len(normalized) < 2 or not correct_region.strip():
        _refuse(True, "hotspot needs at least two regions and a correct_region")
        return None
    match = next(
        (
            region
            for region in normalized
            if _same(region["id"], correct_region) or _same(region["name"], correct_region)
        ),
        None,
    )
    if match is None:
        raise VisualChallengeError(["correct_region is not one of the regions"])
    card = None
    if image is not None:
        card = _attach_catalog_glyph(_normalize_card(image, "hotspot-image"))
    elif slide is not None:
        card = _slide_picture(slide)
    note_text = note.strip()
    explanation = f"The marked spot is {_q(match['name'])}."
    if note_text:
        explanation = f"{explanation} {note_text}"
    payload: dict = {
        "regions": normalized,
        "correct_region": match["id"],
        "note": note_text,
        "explanation": explanation,
    }
    if card is not None:
        payload["image"] = card
    return _publish(
        _make_challenge(
            GameKind.HOTSPOT,
            "Find the spot",
            prompt or "Choose the marked region.",
            payload,
            objective_id,
            pass_score,
        )
    )


def build_classify_game(
    slide: CourseSlide | None = None,
    objective_id: str = "",
    *,
    categories: list[str] | None = None,
    items: list | None = None,
    answer: dict | None = None,
    prompt: str = "",
    pass_score: float = 0.7,
    explicit: bool = False,
) -> GameChallenge | None:
    """Put items in authored groups. Groups are not inferred from pictures."""
    del slide
    if categories is None and items is None and answer is None and not explicit:
        return None
    rows = _item_rows(list(items or []))
    names = [str(category).strip() for category in (categories or []) if str(category).strip()]
    mapping = {str(key): str(value) for key, value in (answer or {}).items()}
    parts = [
        (
            f"{_q(row['label'])} belongs in "
            f"{_q(mapping.get(row['id'], mapping.get(row['label'], '')))}."
        )
        for row in rows
    ]
    return _publish(
        _make_challenge(
            GameKind.CLASSIFY,
            "Classify",
            prompt or "Put each item in the right group.",
            {
                "categories": names,
                "items": rows,
                "answer": mapping,
                "explanation": " ".join(part for part in parts if not part.endswith("“”.")),
            },
            objective_id,
            pass_score,
        )
    )


def build_sort_game(
    slide: CourseSlide | None = None,
    objective_id: str = "",
    *,
    items: list | None = None,
    order_correct: list[str] | None = None,
    prompt: str = "",
    pass_score: float = 0.7,
    explicit: bool = False,
) -> GameChallenge | None:
    """Order authored items. The list order is the answer unless ids are given."""
    del slide
    if items is None and order_correct is None and not explicit:
        return None
    rows = _item_rows(list(items or []))
    if order_correct is not None:
        ordered = []
        for ident in order_correct:
            match = _by_id(rows, str(ident))
            if match is None:
                raise VisualChallengeError([f"{_q(str(ident))} is not one of the items"])
            ordered.append(match)
        if len(ordered) != len(rows):
            raise VisualChallengeError(["sort order must include each item once"])
        rows = ordered
    labels = [row["label"] for row in rows]
    shown = list(reversed([row["id"] for row in rows]))
    return _publish(
        _make_challenge(
            GameKind.SORT,
            "Sort into order",
            prompt or "Put these items in order.",
            {
                "items": rows,
                "order_correct": [row["id"] for row in rows],
                "order_shown": shown,
                "explanation": "The order is " + " → ".join(labels) + ".",
            },
            objective_id,
            pass_score,
        )
    )


def build_label_placement_game(
    slide: CourseSlide | None = None,
    objective_id: str = "",
    *,
    targets: list | None = None,
    labels: list[str] | None = None,
    answer: dict | None = None,
    image: dict | None = None,
    prompt: str = "",
    pass_score: float = 0.7,
    explicit: bool = False,
) -> GameChallenge | None:
    """Place authored labels on authored spots."""
    if targets is None and answer is None and not explicit:
        return None
    spots: list[dict[str, str]] = []
    for index, raw in enumerate(list(targets or []), start=1):
        if isinstance(raw, str):
            spots.append({"id": raw.strip(), "name": raw.strip()})
        elif isinstance(raw, dict):
            ident = str(raw.get("id") or "").strip()
            name = str(raw.get("name") or ident).strip()
            if not ident and ({"x", "y"} & set(raw)):
                raise VisualChallengeError(
                    ["label spots need an id; x/y coordinates are not graded"]
                )
            spots.append({"id": ident, "name": name or ident})
    mapping = {str(key): str(value).strip() for key, value in (answer or {}).items()}
    raw_labels = labels if labels is not None else mapping.values()
    choice_labels = [str(label).strip() for label in raw_labels]
    choice_labels = [label for label in choice_labels if label]
    card = None
    if image is not None:
        card = _attach_catalog_glyph(_normalize_card(image, "diagram"))
    elif slide is not None:
        card = _slide_picture(slide)
    parts = []
    for spot in spots:
        label = ""
        for key, value in mapping.items():
            if _same(key, spot["id"]):
                label = value
                break
        if label:
            parts.append(f"{_q(spot['name'])} is labeled {_q(label)}.")
    payload: dict = {
        "targets": spots,
        "labels": choice_labels,
        "answer": mapping,
        "explanation": " ".join(parts),
    }
    if card is not None:
        payload["image"] = card
    return _publish(
        _make_challenge(
            GameKind.LABEL_PLACEMENT,
            "Place the labels",
            prompt or "Place each label on the right spot.",
            payload,
            objective_id,
            pass_score,
        )
    )


def build_picture_order_game(
    slide: CourseSlide | None = None,
    objective_id: str = "",
    *,
    cards: list | None = None,
    prompt: str = "",
    pass_score: float = 0.7,
    explicit: bool = False,
) -> GameChallenge | None:
    """Order labeled pictures. Text-only steps stay on the order_steps game."""
    del slide
    if cards is None and not explicit:
        return None
    rows = _item_rows(list(cards or []))
    shown = list(reversed(rows))
    labels = [row["label"] for row in rows]
    return _publish(
        _make_challenge(
            GameKind.PICTURE_ORDER,
            "Order the pictures",
            prompt or "Put the pictures in order.",
            {
                "cards_correct": rows,
                "cards_shown": shown,
                "explanation": "The order is " + " → ".join(labels) + ".",
            },
            objective_id,
            pass_score,
        )
    )


def build_spot_difference_game(
    slide: CourseSlide | None = None,
    objective_id: str = "",
    *,
    left: dict | None = None,
    right: dict | None = None,
    differences: list | None = None,
    decoys: list | None = None,
    prompt: str = "",
    pass_score: float = 0.7,
    explicit: bool = False,
) -> GameChallenge | None:
    """Grade authored differences. The pictures are not opened or pixel-compared."""
    del slide
    if left is None and right is None and differences is None and not explicit:
        return None
    left_card = _attach_catalog_glyph(_normalize_card(left, "left"))
    right_card = _attach_catalog_glyph(_normalize_card(right, "right"))
    cleaned = []
    for index, raw in enumerate(list(differences or []), start=1):
        if not isinstance(raw, dict):
            cleaned.append(raw)
            continue
        cleaned.append(
            {
                "id": str(raw.get("id") or "").strip(),
                "region": str(raw.get("region") or "").strip(),
                "note": str(raw.get("note") or "").strip(),
            }
        )
    cleaned_decoys = []
    for raw in list(decoys or []):
        if not isinstance(raw, dict):
            continue
        cleaned_decoys.append(
            {
                "id": str(raw.get("id") or "").strip(),
                "region": str(raw.get("region") or "").strip(),
                "note": str(raw.get("note") or "").strip(),
            }
        )
    notes = [f"{item['region']} — {item['note']}" for item in cleaned if isinstance(item, dict)]
    return _publish(
        _make_challenge(
            GameKind.SPOT_DIFFERENCE,
            "Spot the differences",
            prompt or "Find the differences that are marked.",
            {
                "left": left_card,
                "right": right_card,
                "differences": cleaned,
                "decoys": cleaned_decoys,
                "explanation": "Differences: " + "; ".join(notes) + ".",
            },
            objective_id,
            pass_score,
        )
    )


def _memory_pair_from_word(word: str) -> dict:
    slug = _slug(word)
    picture = _normalize_card(
        {"id": f"{slug}-picture", "label": word, "glyph": PICTURE_EMOJI[word], "alt": word},
        f"{slug}-picture",
    )
    text = _normalize_card(
        {"id": f"{slug}-word", "label": word, "alt": word},
        f"{slug}-word",
    )
    return {"id": slug, "left": picture, "right": text}


def build_memory_pairs_game(
    slide: CourseSlide | None = None,
    objective_id: str = "",
    *,
    pairs: list[dict] | None = None,
    words: list[str] | None = None,
    pair_count: int = 4,
    prompt: str = "",
    pass_score: float = 0.7,
    explicit: bool = False,
) -> GameChallenge | None:
    """Match authored pairs. Catalog words use their vetted glyph, not a new one."""
    built: list[dict] = []
    if pairs is not None:
        for index, raw in enumerate(pairs, start=1):
            left = _attach_catalog_glyph(_normalize_card(raw.get("left"), f"left-{index}"))
            right = _attach_catalog_glyph(_normalize_card(raw.get("right"), f"right-{index}"))
            pair_id = str(raw.get("id") or "").strip() or _slug(left["label"] or f"pair-{index}")
            built.append({"id": pair_id, "left": left, "right": right})
    elif words is not None:
        unknown = [word for word in words if not catalog_glyph(word)]
        if unknown:
            quoted = ", ".join(_q(word) for word in unknown)
            raise VisualChallengeError(
                [f"{quoted} is not a catalog picture word and has no picture"]
            )
        for word in words:
            key = next(item for item in PICTURE_EMOJI if fold_label(item) == fold_label(word))
            built.append(_memory_pair_from_word(key))
    else:
        found = catalog_words_in_text(f"{slide.title} {slide.body}") if slide is not None else []
        limit = max(2, int(pair_count))
        if len(found) < 2:
            _refuse(explicit, "memory pairs needs at least two labeled pictures")
            return None
        built = [_memory_pair_from_word(word) for word in found[:limit]]
    faces = [card for pair in built for card in (pair["left"], pair["right"])]
    parts = [
        f"{_q(pair['left']['label'])} pairs with {_q(pair['right']['label'])}."
        for pair in built
    ]
    return _publish(
        _make_challenge(
            GameKind.MEMORY_PAIRS,
            "Match the pairs",
            prompt or "Match each picture with its word.",
            {
                "pairs": built,
                "cards_shown": _shuffled(faces, f"memory|{objective_id}|{len(built)}"),
                "explanation": " ".join(parts),
            },
            objective_id,
            pass_score,
        )
    )


_SLIDE_VISUAL_ROTATION = (
    GameKind.IMAGE_TO_WORD,
    GameKind.WORD_TO_IMAGE,
    GameKind.MEMORY_PAIRS,
)


def pick_visual_game_for_slide(
    slide: CourseSlide,
    objective_id: str = "",
    rotate_index: int = 0,
) -> GameChallenge | None:
    """Build a visual game only from a labeled picture or a catalog word.

    Hotspot, classify, sort, label placement, picture order, and spot the
    difference need an authored answer key, so they are never guessed.
    """
    builders = {
        GameKind.IMAGE_TO_WORD: build_image_to_word_game,
        GameKind.WORD_TO_IMAGE: build_word_to_image_game,
        GameKind.MEMORY_PAIRS: build_memory_pairs_game,
    }
    count = len(_SLIDE_VISUAL_ROTATION)
    for offset in range(count):
        kind = _SLIDE_VISUAL_ROTATION[(int(rotate_index) + offset) % count]
        game = builders[kind](slide, objective_id)
        if game is not None:
            return game
    return None


def visual_game_from_spec(
    spec: dict | None,
    slide: CourseSlide | None = None,
    objective_id: str = "",
) -> GameChallenge | None:
    """Build an authored visual spec. Incomplete specs raise instead of guessing."""
    if not isinstance(spec, dict) or not spec:
        return None
    try:
        kind = GameKind(str(spec.get("kind") or ""))
    except ValueError:
        return None
    if kind not in VISUAL_GAME_KINDS:
        return None
    prompt = str(spec.get("prompt") or "")
    if kind is GameKind.IMAGE_TO_WORD:
        return build_image_to_word_game(
            slide,
            objective_id,
            image=spec.get("image"),
            options=spec.get("options"),
            answer=str(spec.get("answer") or ""),
            prompt=prompt,
            explicit=True,
        )
    if kind is GameKind.WORD_TO_IMAGE:
        return build_word_to_image_game(
            slide,
            objective_id,
            word=str(spec.get("word") or ""),
            images=spec.get("images"),
            prompt=prompt,
            explicit=True,
        )
    if kind is GameKind.HOTSPOT:
        return build_hotspot_game(
            slide,
            objective_id,
            regions=spec.get("regions"),
            correct_region=str(spec.get("correct_region") or ""),
            note=str(spec.get("note") or ""),
            image=spec.get("image"),
            prompt=prompt,
            explicit=True,
        )
    if kind is GameKind.CLASSIFY:
        return build_classify_game(
            slide,
            objective_id,
            categories=spec.get("categories"),
            items=spec.get("items"),
            answer=spec.get("answer"),
            prompt=prompt,
            explicit=True,
        )
    if kind is GameKind.SORT:
        return build_sort_game(
            slide,
            objective_id,
            items=spec.get("items"),
            order_correct=spec.get("order_correct"),
            prompt=prompt,
            explicit=True,
        )
    if kind is GameKind.LABEL_PLACEMENT:
        return build_label_placement_game(
            slide,
            objective_id,
            targets=spec.get("targets"),
            labels=spec.get("labels"),
            answer=spec.get("answer"),
            image=spec.get("image"),
            prompt=prompt,
            explicit=True,
        )
    if kind is GameKind.PICTURE_ORDER:
        return build_picture_order_game(
            slide,
            objective_id,
            cards=spec.get("cards"),
            prompt=prompt,
            explicit=True,
        )
    if kind is GameKind.SPOT_DIFFERENCE:
        return build_spot_difference_game(
            slide,
            objective_id,
            left=spec.get("left"),
            right=spec.get("right"),
            differences=spec.get("differences"),
            decoys=spec.get("decoys"),
            prompt=prompt,
            explicit=True,
        )
    return build_memory_pairs_game(
        slide,
        objective_id,
        pairs=spec.get("pairs"),
        words=spec.get("words"),
        prompt=prompt,
        explicit=True,
    )

