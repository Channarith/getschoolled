"""Durable teach-session checkpoints (Continue vs Come back later)."""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .corpus import default_data_dir
from .types import LearnerProfileScores

# Soft stop for adult / cert sessions (~15–20 min). Kids usually finish sooner.
DEFAULT_SOFT_LIMIT_MINUTES = 18
DEFAULT_SOFT_LIMIT_SLIDES = 12


class TeachCheckpoint(BaseModel):
    learner_id: str
    course_id: str
    session_id: str
    path: list[int] = Field(default_factory=list)
    path_pos: int = 0
    language: str = "en"
    profile: LearnerProfileScores = Field(default_factory=LearnerProfileScores)
    known_objective_ids: list[str] = Field(default_factory=list)
    gap_objective_ids: list[str] = Field(default_factory=list)
    completed_slide_indexes: list[int] = Field(default_factory=list)
    started_at_ms: int = 0
    updated_at_ms: int = 0
    elapsed_ms: int = 0
    soft_limit_minutes: int = DEFAULT_SOFT_LIMIT_MINUTES
    status: str = "in_progress"  # in_progress | paused | completed
    message: str = ""


class CheckpointStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        root = (data_dir or default_data_dir()) / "teach_checkpoints"
        root.mkdir(parents=True, exist_ok=True)
        self._root = root
        self._lock = threading.RLock()

    def _path(self, learner_id: str, course_id: str) -> Path:
        safe_l = re.sub(r"[^a-zA-Z0-9_-]+", "-", learner_id) or "learner"
        safe_c = re.sub(r"[^a-zA-Z0-9_-]+", "-", course_id) or "course"
        return self._root / f"{safe_l}__{safe_c}.json"

    def load(self, learner_id: str, course_id: str) -> TeachCheckpoint | None:
        path = self._path(learner_id, course_id)
        if not path.is_file():
            return None
        try:
            return TeachCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def save(self, checkpoint: TeachCheckpoint) -> TeachCheckpoint:
        with self._lock:
            checkpoint.updated_at_ms = int(time.time() * 1000)
            path = self._path(checkpoint.learner_id, checkpoint.course_id)
            path.write_text(
                checkpoint.model_dump_json(indent=2),
                encoding="utf-8",
            )
            return checkpoint

    def clear(self, learner_id: str, course_id: str) -> None:
        with self._lock:
            path = self._path(learner_id, course_id)
            if path.is_file():
                path.unlink()

    def list_for_learner(self, learner_id: str) -> list[TeachCheckpoint]:
        safe_l = re.sub(r"[^a-zA-Z0-9_-]+", "-", learner_id) or "learner"
        prefix = f"{safe_l}__"
        out: list[TeachCheckpoint] = []
        for path in sorted(self._root.glob(f"{prefix}*.json")):
            try:
                out.append(
                    TeachCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return out


def soft_checkpoint_due(
    *,
    started_at_ms: int,
    path_pos: int,
    soft_limit_minutes: int = DEFAULT_SOFT_LIMIT_MINUTES,
    soft_limit_slides: int = DEFAULT_SOFT_LIMIT_SLIDES,
    now_ms: int | None = None,
    audience: str = "general",
) -> bool:
    """Kids lessons are already short; soft-stop mainly for adult/cert sessions."""
    if audience and audience not in {"general", "adult_cert_prep", "corporate"}:
        return False
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    started = int(started_at_ms) if started_at_ms is not None else now
    elapsed_ms = max(0, now - started)
    limit_ms = max(1, int(soft_limit_minutes)) * 60_000
    if elapsed_ms >= limit_ms:
        return True
    return path_pos + 1 >= max(1, int(soft_limit_slides))


def checkpoint_prompt(elapsed_ms: int, soft_limit_minutes: int) -> dict[str, Any]:
    elapsed_min = max(1, round(elapsed_ms / 60_000))
    return {
        "due": True,
        "elapsed_minutes": elapsed_min,
        "soft_limit_minutes": soft_limit_minutes,
        "choices": [
            {"id": "continue", "label": "Continue"},
            {"id": "come_back_later", "label": "Come back later"},
        ],
        "message": (
            f"You've been in this session about {elapsed_min} minutes "
            f"(target {soft_limit_minutes}). Continue now, or save your place "
            "and come back later."
        ),
    }
