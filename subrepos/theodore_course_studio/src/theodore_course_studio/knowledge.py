"""Learning objectives + mastery model for knowledge-gap teaching."""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

from pydantic import BaseModel, Field

from .corpus import default_data_dir


class LearningObjective(BaseModel):
    objective_id: str
    course_id: str
    title: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    slide_indexes: list[int] = Field(default_factory=list)
    required_mastery: float = 0.7


class ObjectiveMastery(BaseModel):
    objective_id: str
    score: float = 0.0
    attempts: int = 0
    last_result: str = ""
    updated_at_ms: int = 0


class LearnerKnowledgeState(BaseModel):
    learner_id: str
    course_id: str
    mastery: dict[str, ObjectiveMastery] = Field(default_factory=dict)
    known_objective_ids: list[str] = Field(default_factory=list)
    gap_objective_ids: list[str] = Field(default_factory=list)
    focus_objective_ids: list[str] = Field(default_factory=list)
    updated_at_ms: int = 0


def objectives_from_slides(course_id: str, slides) -> list[LearningObjective]:
    """Derive coarse learning points from slide titles/bodies."""
    out: list[LearningObjective] = []
    stop = frozenset(
        {
            "your",
            "will",
            "could",
            "which",
            "about",
            "from",
            "there",
            "have",
            "into",
            "when",
            "should",
            "what",
            "that",
            "this",
            "with",
            "their",
            "would",
        }
    )
    for slide in slides:
        title = (getattr(slide, "title", None) or "").strip()
        if not title:
            title = f"Point {slide.index + 1}"
        body = getattr(slide, "body", None) or ""
        words = [
            w.lower()
            for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", f"{title} {body}")
            if w.lower() not in stop
        ]
        # unique preserve order
        seen: set[str] = set()
        keywords: list[str] = []
        for w in words:
            if w not in seen:
                seen.add(w)
                keywords.append(w)
            if len(keywords) >= 8:
                break
        oid = f"{course_id}::obj-{slide.index:03d}"
        out.append(
            LearningObjective(
                objective_id=oid,
                course_id=course_id,
                title=title,
                description=(body[:280] if body else title),
                keywords=keywords,
                slide_indexes=[slide.index],
            )
        )
    return out


class KnowledgeStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        root = (data_dir or default_data_dir()) / "knowledge"
        root.mkdir(parents=True, exist_ok=True)
        self._root = root
        self._lock = threading.RLock()

    def _path(self, learner_id: str, course_id: str) -> Path:
        safe_l = re.sub(r"[^a-zA-Z0-9_-]+", "-", learner_id)
        safe_c = re.sub(r"[^a-zA-Z0-9_-]+", "-", course_id)
        return self._root / f"{safe_l}__{safe_c}.json"

    def load(self, learner_id: str, course_id: str) -> LearnerKnowledgeState:
        path = self._path(learner_id, course_id)
        if path.is_file():
            return LearnerKnowledgeState.model_validate_json(path.read_text(encoding="utf-8"))
        return LearnerKnowledgeState(learner_id=learner_id, course_id=course_id)

    def save(self, state: LearnerKnowledgeState) -> None:
        with self._lock:
            state.updated_at_ms = int(time.time() * 1000)
            path = self._path(state.learner_id, state.course_id)
            path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def assess_prior_knowledge(
        self,
        *,
        learner_id: str,
        course_id: str,
        objectives: list[LearningObjective],
        self_reported_known: list[str] | None = None,
        pretest_scores: dict[str, float] | None = None,
    ) -> LearnerKnowledgeState:
        """Identify known vs gap objectives; focus path = gaps first."""
        state = self.load(learner_id, course_id)
        known = set(self_reported_known or [])
        pretest_scores = pretest_scores or {}
        for obj in objectives:
            prior = pretest_scores.get(obj.objective_id)
            if prior is None and obj.objective_id in known:
                prior = 0.85
            if prior is None:
                prior = state.mastery.get(
                    obj.objective_id, ObjectiveMastery(objective_id=obj.objective_id)
                ).score
            mastery = ObjectiveMastery(
                objective_id=obj.objective_id,
                score=max(0.0, min(1.0, float(prior))),
                attempts=state.mastery.get(
                    obj.objective_id, ObjectiveMastery(objective_id=obj.objective_id)
                ).attempts,
                last_result="pretest" if obj.objective_id in pretest_scores else "init",
                updated_at_ms=int(time.time() * 1000),
            )
            state.mastery[obj.objective_id] = mastery

        state.known_objective_ids = [
            o.objective_id
            for o in objectives
            if state.mastery.get(o.objective_id, ObjectiveMastery(objective_id=o.objective_id)).score
            >= o.required_mastery
        ]
        state.gap_objective_ids = [
            o.objective_id
            for o in objectives
            if o.objective_id not in state.known_objective_ids
        ]
        state.focus_objective_ids = list(state.gap_objective_ids) or [
            o.objective_id for o in objectives
        ]
        self.save(state)
        return state

    def record_outcome(
        self,
        *,
        learner_id: str,
        course_id: str,
        objective_id: str,
        correct: bool,
        weight: float = 0.15,
    ) -> LearnerKnowledgeState:
        state = self.load(learner_id, course_id)
        cur = state.mastery.get(objective_id, ObjectiveMastery(objective_id=objective_id))
        delta = weight if correct else -(weight * 0.8)
        cur.score = max(0.0, min(1.0, cur.score + delta))
        cur.attempts += 1
        cur.last_result = "correct" if correct else "incorrect"
        cur.updated_at_ms = int(time.time() * 1000)
        state.mastery[objective_id] = cur

        known: list[str] = []
        gaps: list[str] = []
        for oid, m in state.mastery.items():
            if m.score >= 0.7:
                known.append(oid)
            else:
                gaps.append(oid)
        state.known_objective_ids = known
        state.gap_objective_ids = gaps
        state.focus_objective_ids = list(gaps) or list(known)
        self.save(state)
        return state


def next_slide_indexes(
    objectives: list[LearningObjective],
    state: LearnerKnowledgeState,
    include_known_refresh: bool = False,
) -> list[int]:
    """Ordered slide indexes focusing on knowledge gaps."""
    by_id = {o.objective_id: o for o in objectives}
    ordered: list[int] = []
    for oid in state.focus_objective_ids:
        obj = by_id.get(oid)
        if not obj:
            continue
        for idx in obj.slide_indexes:
            if idx not in ordered:
                ordered.append(idx)
    if include_known_refresh:
        for oid in state.known_objective_ids:
            obj = by_id.get(oid)
            if not obj:
                continue
            for idx in obj.slide_indexes:
                if idx not in ordered:
                    ordered.append(idx)
    if not ordered:
        for obj in objectives:
            for idx in obj.slide_indexes:
                if idx not in ordered:
                    ordered.append(idx)
    return ordered
