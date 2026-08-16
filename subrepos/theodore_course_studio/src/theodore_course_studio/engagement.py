"""Media assets + simple learning games for Theodore course sessions."""

from __future__ import annotations

import re
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
    steps = parts[:3] if len(parts) >= 3 else ([slide.title] + parts)[:3]
    if not steps:
        steps = [slide.title or "Practice"]
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
    generic = ["none of these", "skip this", "not covered here", "all of the above"]
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
    return GameAttemptResult(
        game_id=challenge.game_id,
        score=0.0,
        passed=False,
        feedback="Unsupported game kind.",
        objective_id=challenge.objective_id,
    )
