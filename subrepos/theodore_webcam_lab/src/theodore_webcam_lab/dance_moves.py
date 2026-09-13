"""Kid-safe dance move detection for Come get jiggy with me.

Scores each move from real webcam signals (motion, fidget, head pose, hand
gesture energy, finger-trail shape). Browser mirrors the thresholds in
monitor_page.js; tests pin the move catalog and scoring shapes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .types import WebcamSignal

JIGGY_SEQUENCE_LEN = 4
JIGGY_BEAT_MS = 2_500
JIGGY_MATCH_THRESHOLD = 0.42
SKIP_ENCOURAGE = "No problem — skip that one and keep grooving!"


@dataclass(frozen=True)
class DanceMove:
    move_id: str
    prompt: str
    encourage: str


DANCE_MOVES: dict[str, DanceMove] = {
    "shake_shake": DanceMove("shake_shake", "Shake shake!", "Awesome shakes!"),
    "dance": DanceMove("dance", "Dance dance!", "You are grooving!"),
    "spin": DanceMove("spin", "Spin around!", "Great spin energy!"),
    "twirl": DanceMove("twirl", "Twirl twirl!", "Lovely twirl!"),
    "move_hands": DanceMove("move_hands", "Move your hands!", "Hand moves on point!"),
    "bop_head": DanceMove("bop_head", "Bop your head!", "Head bop unlocked!"),
    "get_low": DanceMove("get_low", "Get low!", "Smooth get-low!"),
    "high_five": DanceMove("high_five", "High five the air!", "High five hero!"),
    "snake_hands": DanceMove("snake_hands", "Snake your hands!", "Sss-super snake hands!"),
    "side_to_side": DanceMove("side_to_side", "Side to side!", "Nice side steps!"),
    "jump_bop": DanceMove("jump_bop", "Jump and bop!", "Big jump energy!"),
    "wave_hello": DanceMove("wave_hello", "Wave hello!", "Friendly wave!"),
}

DANCE_MOVE_IDS: tuple[str, ...] = tuple(DANCE_MOVES.keys())


def random_jiggy_sequence(*, length: int = JIGGY_SEQUENCE_LEN, rng: random.Random | None = None) -> list[str]:
    pool = list(DANCE_MOVE_IDS)
    source = rng or random.Random()
    source.shuffle(pool)
    return pool[: max(1, min(length, len(pool)))]


def move_prompt(move_id: str) -> str:
    move = DANCE_MOVES.get(move_id)
    return move.prompt if move else move_id.replace("_", " ").title()


def move_encouragement(move_id: str) -> str:
    move = DANCE_MOVES.get(move_id)
    return move.encourage if move else "Great move!"


def _f(signal: WebcamSignal, name: str, default: float = 0.0) -> float:
    value = getattr(signal, name, None)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def move_confidence(move_id: str, signal: WebcamSignal, *, spell: str | None = None) -> float:
    """Return 0..1 confidence that ``signal`` shows ``move_id``."""
    motion = _f(signal, "motion_score")
    body = _f(signal, "body_motion_score", motion)
    fidget = _f(signal, "fidget_score")
    hand = _f(signal, "hand_gesture_energy")
    face_e = _f(signal, "face_motion_energy")
    pitch = abs(_f(signal, "head_pose_pitch"))
    yaw = abs(_f(signal, "head_pose_yaw"))
    roll = abs(_f(signal, "head_pose_roll"))
    excited = _f(signal, "excitement_score")

    if move_id == "shake_shake":
        return min(1.0, motion * 0.45 + fidget * 0.45 + hand * 0.2)
    if move_id == "dance":
        return min(1.0, motion * 0.35 + hand * 0.35 + face_e * 0.25 + excited * 0.15)
    if move_id == "spin":
        return min(1.0, (yaw / 22.0) * 0.55 + motion * 0.35 + body * 0.15)
    if move_id == "twirl":
        return min(1.0, (roll / 18.0) * 0.5 + (yaw / 25.0) * 0.25 + motion * 0.3)
    if move_id == "move_hands":
        return min(1.0, hand * 0.75 + motion * 0.2)
    if move_id == "bop_head":
        return min(1.0, face_e * 0.55 + motion * 0.25 + fidget * 0.15)
    if move_id == "get_low":
        return min(1.0, (pitch / 14.0) * 0.65 + motion * 0.25)
    if move_id == "high_five":
        return min(1.0, motion * 0.45 + hand * 0.45 + excited * 0.15)
    if move_id == "snake_hands":
        spell_ok = 1.0 if spell in {"swish", "loop"} else 0.0
        return min(1.0, hand * 0.45 + spell_ok * 0.45 + motion * 0.15)
    if move_id == "side_to_side":
        return min(1.0, (yaw / 16.0) * 0.6 + motion * 0.3)
    if move_id == "jump_bop":
        return min(1.0, motion * 0.5 + excited * 0.3 + fidget * 0.25)
    if move_id == "wave_hello":
        return min(1.0, hand * 0.5 + motion * 0.25 + face_e * 0.15)
    return 0.0


def sequence_progress(
    signals: list[WebcamSignal],
    expected: list[str],
    *,
    threshold: float = JIGGY_MATCH_THRESHOLD,
) -> tuple[int, list[str], list[str]]:
    """Walk expected moves in order.

    A move is complete when the camera matches it *or* the child skips it
    (unable or just not feeling that one). Skips never shame the learner.
    """
    progress = 0
    matched: list[str] = []
    skipped: list[str] = []
    for signal in signals:
        if progress >= len(expected):
            break
        move_id = expected[progress]
        if signal.dance_move_skipped == move_id:
            skipped.append(move_id)
            progress += 1
            continue
        if signal.dance_move_matched != move_id:
            continue
        conf = move_confidence(move_id, signal, spell=signal.wand_spell_label)
        if conf >= threshold:
            matched.append(move_id)
            progress += 1
    return progress, matched, skipped


def jiggy_target_duration_ms(move_count: int) -> int:
    return max(JIGGY_BEAT_MS, move_count * JIGGY_BEAT_MS)
