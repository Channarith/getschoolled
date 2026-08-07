"""Media assets + simple learning games for Theodore course sessions."""

from __future__ import annotations

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
    """Placeholder media hooks — wire real URLs/files as corpus media is added."""
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
    return GameAttemptResult(
        game_id=challenge.game_id,
        score=0.0,
        passed=False,
        feedback="Unsupported game kind.",
        objective_id=challenge.objective_id,
    )
