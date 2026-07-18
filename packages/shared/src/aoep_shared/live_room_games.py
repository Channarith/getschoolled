"""Synchronized educational mini-games for Salareen group classes."""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict

GAME_LIBRARY = (
    {"id": "quiz_race", "name": "First Answer Race", "icon": "⚡",
     "description": "The first learner with the correct answer wins."},
    {"id": "tic_tac_toe", "name": "Learning Tic-Tac-Toe", "icon": "⭕",
     "description": "Answer correctly before claiming a board square."},
    {"id": "hangman", "name": "Learning Hangman", "icon": "🔤",
     "description": "Reveal a course word one letter at a time."},
    {"id": "multiple_choice", "name": "Multiple Choice Dash", "icon": "🔢",
     "description": "Race to submit the correct choice."},
    {"id": "true_false", "name": "True or False", "icon": "✅",
     "description": "Judge a course statement as true or false."},
    {"id": "word_scramble", "name": "Word Scramble", "icon": "🔀",
     "description": "Unscramble an important course term."},
    {"id": "fill_blank", "name": "Fill the Blank", "icon": "✍️",
     "description": "Complete a key sentence or definition."},
    {"id": "emoji_decode", "name": "Emoji Decode", "icon": "🧩",
     "description": "Decode a concept represented by emoji clues."},
    {"id": "lightning_round", "name": "Lightning Round", "icon": "🌩️",
     "description": "A fast, high-energy knowledge check."},
    {"id": "team_buzzer", "name": "Team Buzzer", "icon": "🔔",
     "description": "Buzz in and answer for the group."},
    {"id": "hot_seat", "name": "Hot Seat", "icon": "🔥",
     "description": "One focused learner answers a challenge."},
    {"id": "jeopardy", "name": "Jeopardy Challenge", "icon": "💎",
     "description": "Respond to a clue with the matching concept."},
)
GAME_TYPES = tuple(row["id"] for row in GAME_LIBRARY)
ANSWER_RACE_TYPES = frozenset(GAME_TYPES) - {"tic_tac_toe", "hangman"}


class GroupGameError(ValueError):
    pass


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _digest(value: str) -> str:
    return hashlib.sha256(_norm(value).encode()).hexdigest()


def start_game(
    game_type: str,
    *,
    prompt: str,
    answer: str,
    points: int = 25,
) -> Dict[str, Any]:
    kind = _norm(game_type).replace(" ", "_")
    if kind not in GAME_TYPES:
        raise GroupGameError(f"unknown game type {game_type!r}")
    if not prompt.strip() or not answer.strip():
        raise GroupGameError("prompt and answer are required")
    state: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "type": kind,
        "prompt": prompt.strip()[:500],
        "answer_hash": _digest(answer),
        "_answer": _norm(answer),
        "points": max(1, min(500, int(points))),
        "status": "active",
        "winner_participant_id": "",
        "winner_name": "",
        "scores": {},
        "started_at": time.time(),
        "updated_at": time.time(),
    }
    if kind == "tic_tac_toe":
        state.update({"board": [""] * 9, "turn": "X", "moves": []})
    elif kind == "hangman":
        state.update({"guessed": [], "wrong": 0, "max_wrong": 6})
    else:
        state["answers"] = []
    if kind == "word_scramble":
        # Deterministic rotation is readable, testable, and avoids leaking the answer.
        compact = "".join(ch for ch in _norm(answer) if ch.isalnum())
        state["scrambled"] = compact[1::2] + compact[::2]
    return state


def public_game(state: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not state:
        return None
    out = {k: v for k, v in state.items() if k not in ("_answer", "answer_hash")}
    if state.get("type") == "hangman":
        answer = str(state.get("_answer") or "")
        guessed = set(state.get("guessed") or [])
        out["masked"] = " ".join(ch if ch == " " or ch in guessed else "_" for ch in answer)
    return out


def apply_action(
    state: Dict[str, Any],
    *,
    participant_id: str,
    participant_name: str,
    answer: str = "",
    cell: int = -1,
    letter: str = "",
) -> Dict[str, Any]:
    if state.get("status") != "active":
        raise GroupGameError("game is not active")
    kind = state.get("type")
    correct = _digest(answer) == state.get("answer_hash")
    event: Dict[str, Any] = {"correct": correct, "finished": False, "points": 0}

    if kind in ANSWER_RACE_TYPES:
        state.setdefault("answers", []).append({
            "participant_id": participant_id,
            "name": participant_name,
            "correct": correct,
        })
        if correct and not state.get("winner_participant_id"):
            _win(state, participant_id, participant_name)
            event.update({"finished": True, "points": int(state["points"])})
    elif kind == "tic_tac_toe":
        if not correct:
            return event
        if cell < 0 or cell > 8 or state["board"][cell]:
            raise GroupGameError("choose an empty tic-tac-toe cell")
        mark = state["turn"]
        state["board"][cell] = mark
        state.setdefault("moves", []).append({
            "participant_id": participant_id, "name": participant_name,
            "cell": cell, "mark": mark,
        })
        state["turn"] = "O" if mark == "X" else "X"
        if _board_won(state["board"], mark):
            _win(state, participant_id, participant_name)
            event.update({"finished": True, "points": int(state["points"])})
        elif all(state["board"]):
            state["status"] = "draw"
            event["finished"] = True
    elif kind == "hangman":
        guess = _norm(letter)[:1]
        if not guess or not guess.isalnum():
            raise GroupGameError("enter one letter")
        guessed = state.setdefault("guessed", [])
        if guess not in guessed:
            guessed.append(guess)
            if guess not in state["_answer"]:
                state["wrong"] = int(state.get("wrong", 0)) + 1
        solved = all(ch == " " or ch in guessed for ch in state["_answer"])
        if solved:
            _win(state, participant_id, participant_name)
            event.update({"correct": True, "finished": True, "points": int(state["points"])})
        elif state["wrong"] >= state["max_wrong"]:
            state["status"] = "ended"
            event["finished"] = True
    else:
        raise GroupGameError("unknown game")
    state["updated_at"] = time.time()
    return event


def _win(state: Dict[str, Any], participant_id: str, name: str) -> None:
    state["winner_participant_id"] = participant_id
    state["winner_name"] = name
    state["status"] = "won"
    scores = state.setdefault("scores", {})
    scores[participant_id] = int(scores.get(participant_id, 0)) + int(state["points"])


def _board_won(board: list[str], mark: str) -> bool:
    lines = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7),
             (2, 5, 8), (0, 4, 8), (2, 4, 6))
    return any(all(board[i] == mark for i in line) for line in lines)
