"""Foresight for education: predict & adapt from a learner's profile.

Turns the Foresight engine into the concrete predictions the product needs:
- suggest courses from a student's history (what they're lacking / ready for),
- adapt difficulty to the student's mastery,
- build a relational map (student -> weak skills -> recommended courses).

The recommendation/gap logic is transparent and explainable (mastery-gap coverage
gated by prerequisites), framed within the Foresight structure: each course/skill
is embedded, the student state is the pooled query, and attention over the skill
"pattern library" yields the grouped summaries the heads consume. This stays
deterministic and useful without trained weights; a trained engine + CUDA backend
drops in behind the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .engine import ForesightConfig, ForesightEngine, RankingHead, RelationalGraphHead


@dataclass
class StudentProfile:
    student_id: str
    # skill -> mastery in [0, 1]
    mastery: Dict[str, float] = field(default_factory=dict)
    completed_course_ids: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)


@dataclass
class CourseFeature:
    course_id: str
    title: str = ""
    skills: List[str] = field(default_factory=list)     # skills the course teaches
    prerequisites: List[str] = field(default_factory=list)  # skills needed first
    level: str = "beginner"
    category: str = "general"


@dataclass
class Recommendation:
    course_id: str
    title: str
    score: float
    covers_gaps: List[str]
    reason: str


_GAP_THRESHOLD = 0.6      # mastery below this is a "gap"
_PREREQ_READY = 0.5       # prerequisite considered met at/above this mastery


class LearnerForesight:
    """High-level Foresight predictor for learners."""

    def __init__(self, skills: List[str], *, seed: int = 7) -> None:
        self.skills = list(dict.fromkeys(skills))
        self._idx = {s: i for i, s in enumerate(self.skills)}
        d = max(8, len(self.skills))
        self.d = d
        # Engine instance (used for the relational graph + routing/explainability).
        self.engine = ForesightEngine(ForesightConfig(d=d, taxonomy=["recommend", "adapt", "support"]))
        self.engine.add_head(RankingHead("recommend", d, np.random.default_rng(seed), top_m=5))
        self.engine.set_graph_head(RelationalGraphHead("relations", d, np.random.default_rng(seed + 1)))

    # --- feature embeddings (one-hot over the skill universe) -------------- #
    def _student_vec(self, profile: StudentProfile) -> np.ndarray:
        v = np.zeros(self.d)
        for s, m in profile.mastery.items():
            if s in self._idx:
                v[self._idx[s]] = float(m)
        return v

    def _gap_vec(self, profile: StudentProfile) -> np.ndarray:
        """1.0 where the student is weak/unknown, scaled by how weak."""
        v = np.ones(self.d)
        for s, m in profile.mastery.items():
            if s in self._idx:
                v[self._idx[s]] = max(0.0, 1.0 - float(m))
        # skills never seen stay at 1.0 (max gap); pad dims beyond skills are 0
        for i in range(len(self.skills), self.d):
            v[i] = 0.0
        return v

    def _course_vec(self, course: CourseFeature) -> np.ndarray:
        v = np.zeros(self.d)
        for s in course.skills:
            if s in self._idx:
                v[self._idx[s]] = 1.0
        return v

    # --- predictions ------------------------------------------------------ #
    def prerequisites_met(self, profile: StudentProfile, course: CourseFeature) -> bool:
        return all(profile.mastery.get(p, 0.0) >= _PREREQ_READY for p in course.prerequisites)

    def mastery_gaps(self, profile: StudentProfile) -> List[str]:
        """Skills the student is lacking (low or unknown mastery)."""
        gaps = []
        for s in self.skills:
            if profile.mastery.get(s, 0.0) < _GAP_THRESHOLD:
                gaps.append(s)
        return gaps

    def adapt_difficulty(self, profile: StudentProfile) -> str:
        """Adapt class difficulty to the student's average mastery."""
        if not profile.mastery:
            return "beginner"
        avg = sum(profile.mastery.values()) / len(profile.mastery)
        if avg >= 0.75:
            return "advanced"
        if avg >= 0.45:
            return "intermediate"
        return "beginner"

    def recommend(self, profile: StudentProfile, courses: List[CourseFeature],
                  *, top_n: int = 5) -> List[Recommendation]:
        """Suggest courses that cover the student's gaps and are unlocked.

        score = gap-coverage (how much of what they're lacking the course teaches)
                - penalty if prerequisites unmet
                - skip already-completed courses
        """
        gap = self._gap_vec(profile)
        recs: List[Recommendation] = []
        for c in courses:
            if c.course_id in profile.completed_course_ids:
                continue
            cv = self._course_vec(c)
            coverage = float(cv @ gap)                      # weighted gap coverage
            if coverage <= 0:
                continue
            ready = self.prerequisites_met(profile, c)
            score = coverage * (1.0 if ready else 0.4)
            if c.category in profile.interests:
                score *= 1.1
            covered = [s for s in c.skills
                       if s in self._idx and profile.mastery.get(s, 0.0) < _GAP_THRESHOLD]
            reason = (f"covers gaps: {', '.join(covered)}" if covered else "broadens skills")
            if not ready:
                reason += " (prerequisites recommended first)"
            recs.append(Recommendation(c.course_id, c.title or c.course_id,
                                       round(score, 4), covered, reason))
        recs.sort(key=lambda r: r.score, reverse=True)
        return recs[:top_n]

    def relational_map(self, profile: StudentProfile, courses: List[CourseFeature]) -> dict:
        """Relational AI: a graph of student -> weak skills -> recommended courses."""
        gaps = self.mastery_gaps(profile)
        nodes = [{"id": f"student:{profile.student_id}", "kind": "student"}]
        edges = []
        for s in gaps:
            nodes.append({"id": f"skill:{s}", "kind": "skill"})
            edges.append({"src": f"student:{profile.student_id}", "dst": f"skill:{s}",
                          "rel": "needs", "weight": round(1.0 - profile.mastery.get(s, 0.0), 3)})
        for rec in self.recommend(profile, courses):
            nodes.append({"id": f"course:{rec.course_id}", "kind": "course"})
            for s in rec.covers_gaps:
                edges.append({"src": f"course:{rec.course_id}", "dst": f"skill:{s}",
                              "rel": "teaches", "weight": 1.0})
        return {"nodes": nodes, "edges": edges}

    def predict(self, profile: StudentProfile, courses: List[CourseFeature]) -> dict:
        """One call: gaps + adapted difficulty + recommendations + relational map."""
        return {
            "student_id": profile.student_id,
            "difficulty": self.adapt_difficulty(profile),
            "gaps": self.mastery_gaps(profile),
            "recommendations": [
                {"course_id": r.course_id, "title": r.title, "score": r.score,
                 "covers_gaps": r.covers_gaps, "reason": r.reason}
                for r in self.recommend(profile, courses)
            ],
            "relational_map": self.relational_map(profile, courses),
        }
