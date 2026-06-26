"""Quantifiable course composition as a numpy node/sub-node matrix + score.

The harvester (and any authoring path) turns raw material into a *course
composition*: which pedagogical building blocks a class is made of and in what
proportion. We make that composition quantifiable so two ways of teaching the
same subject can be compared with a number instead of an opinion.

MODEL
  - A class is built from NODES. Each node has a CATEGORY (a fixed pedagogical
    type: introduction, history, example, video, q&a, ...) and an optional
    SUB-NODE label (a subtopic within that category, e.g. "music" under
    "history", or "example 2").
  - The whole class is stored in a numpy matrix ``M`` of shape
    (num_categories, max_subnodes). ``M[i, j]`` is the weight of the j-th
    sub-node slot inside category ``i``. Per-category totals (the "node
    vector") are ``M.sum(axis=1)``.

TWO NUMBERS (kept deliberately separate)
  1. composition_score(): a deterministic integer (default 0..999, so it reads
     like the "247" / "148" in the spec) computed from the matrix. It is the
     RECIPE FINGERPRINT - it *equates to* which nodes/sub-nodes were used. Same
     recipe -> same score; different recipe -> (almost always) different score.
     Use it as the key when asking "did Chemistry 101 get more survey happiness
     when taught with composition 247 vs 148?".
  2. quality_index(): a heuristic 0..100 float ("how good/bad does this recipe
     look") from coverage / balance / depth / interactivity. This is our prior;
     the real signal is survey happiness keyed by composition_score, tracked in
     CompositionOutcomeLedger.

Pure: numpy + stdlib only, fully offline-testable.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

COMPOSITION_VERSION = "1.0"

# --------------------------------------------------------------------------- #
# Canonical pedagogical node categories (ordered; index == matrix row).
# Order is part of the contract: appending is safe, reordering changes scores.
# --------------------------------------------------------------------------- #
NODE_CATEGORIES: Tuple[str, ...] = (
    "introduction",   # 0  framing / objectives / hook
    "history",        # 1  background / origins / context
    "concept",        # 2  core idea / theory
    "definition",     # 3  terminology
    "example",        # 4  worked example ("example 1", "example 2", ...)
    "demo",           # 5  live demonstration / walkthrough
    "video",          # 6  video segment ("video 1", "video 2", ...)
    "image",          # 7  diagram / visual
    "exercise",       # 8  practice / try-it
    "quiz",           # 9  formative check
    "qanda",          # 10 Q&A
    "discussion",     # 11 open discussion / debate
    "case_study",     # 12 applied case
    "summary",        # 13 wrap-up
    "recap",          # 14 spaced review
    "resources",      # 15 further reading / references
    "assessment",     # 16 graded test
    "project",        # 17 capstone / build
)

CATEGORY_INDEX: Dict[str, int] = {name: i for i, name in enumerate(NODE_CATEGORIES)}
NUM_CATEGORIES: int = len(NODE_CATEGORIES)
DEFAULT_MAX_SUBNODES: int = 16

# Categories that require the learner to act (drives the "interactivity" metric).
INTERACTIVE_CATEGORIES: Tuple[str, ...] = (
    "example", "demo", "exercise", "quiz", "qanda",
    "discussion", "case_study", "assessment", "project",
)

# Keyword cues used to auto-classify an extracted section heading/body into a
# category (best-effort; unknown text falls back to "concept").
_CLASSIFY_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("introduction", ("introduction", "intro", "overview", "objective", "welcome", "getting started")),
    ("history",      ("history", "background", "origin", "timeline", "evolution", "context")),
    ("definition",   ("definition", "glossary", "terminology", "what is", "vocabulary", "key terms")),
    ("example",      ("example", "worked", "for instance", "sample problem", "illustration")),
    ("demo",         ("demo", "demonstration", "walkthrough", "how to", "step-by-step", "tutorial")),
    ("video",        ("video", "watch", "clip", "screencast", "footage")),
    ("image",        ("diagram", "figure", "image", "illustration", "chart", "infographic")),
    ("exercise",     ("exercise", "practice", "try it", "activity", "lab", "hands-on", "drill")),
    ("quiz",         ("quiz", "check your", "knowledge check", "self-test", "pop quiz")),
    ("qanda",        ("q&a", "q and a", "questions and answers", "faq", "ask")),
    ("discussion",   ("discussion", "debate", "reflect", "forum", "talk about")),
    ("case_study",   ("case study", "case-study", "real world", "in practice", "scenario")),
    ("summary",      ("summary", "conclusion", "wrap up", "wrap-up", "takeaway", "in summary")),
    ("recap",        ("recap", "review", "remember", "flashback", "spaced")),
    ("resources",    ("resources", "further reading", "references", "bibliography", "links", "see also")),
    ("assessment",   ("assessment", "exam", "final test", "graded", "certification")),
    ("project",      ("project", "capstone", "build a", "assignment", "deliverable")),
)

# --------------------------------------------------------------------------- #
# Salareen Pedagogical Composition Score (PCS) - algorithm constants.
#
# The PCS turns the node/sub-node matrix into one deterministic integer (the
# "recipe fingerprint"). The constants below are part of the published formula
# (see README "Course Composition Score") and are FIXED FOREVER so a given
# recipe always maps to the same score across versions/services.
# --------------------------------------------------------------------------- #
PCS_VERSION = "1.0"
QUANT_RESOLUTION: float = 4.0        # rho: weights quantized to 1/4 steps
STRUCT_NODE_COEFF: int = 101         # alpha: prime coefficient on total nodes N
STRUCT_CATEGORY_COEFF: int = 103     # beta:  prime coefficient on breadth K
DEFAULT_SCORE_MODULUS: int = 1000    # mu: readable code space (0..999)

# Stable per-category coefficients p_i (the first NUM_CATEGORIES primes). Mixing
# the per-category aggregates by distinct primes is what makes the fingerprint a
# near-injective function of the composition. Fixed forever.
_PRIMES: np.ndarray = np.array(
    [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
     73, 79, 83, 89, 97][:NUM_CATEGORIES],
    dtype=np.int64,
)


def classify_section(heading: str, body: str = "") -> str:
    """Best-effort map a section's heading/body to a canonical category."""
    hay = f"{heading} {body}".lower()
    for category, cues in _CLASSIFY_RULES:
        for cue in cues:
            if cue in hay:
                return category
    # Heading that is just a topic name with no cue -> treat as a concept node.
    return "concept"


@dataclass
class CourseComposition:
    """A class expressed as a numpy node/sub-node matrix.

    ``matrix[i, j]`` = weight of sub-node slot ``j`` within category ``i``.
    ``subnode_labels[i]`` = ordered labels for the occupied slots in row ``i``
    (kept alongside the matrix purely for human interpretability).
    """

    subject: str = "general"
    course_id: str = ""
    max_subnodes: int = DEFAULT_MAX_SUBNODES
    matrix: np.ndarray = field(default=None)  # type: ignore[assignment]
    subnode_labels: List[List[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.matrix is None:
            self.matrix = np.zeros((NUM_CATEGORIES, self.max_subnodes), dtype=np.float64)
        if not self.subnode_labels:
            self.subnode_labels = [[] for _ in range(NUM_CATEGORIES)]

    # --- building --------------------------------------------------------- #
    def add_node(self, category: str, subnode: str = "", weight: float = 1.0) -> "CourseComposition":
        """Add one teaching node. A repeated category (e.g. a 2nd example) lands
        in the next free sub-node slot; a repeated *labelled* sub-node accrues
        weight in its existing slot (e.g. more material on the "music" subtopic).
        """
        if category not in CATEGORY_INDEX:
            raise ValueError(f"unknown category {category!r}; one of {NODE_CATEGORIES}")
        i = CATEGORY_INDEX[category]
        label = (subnode or "").strip()
        labels = self.subnode_labels[i]
        if label and label.lower() in (l.lower() for l in labels):
            j = next(k for k, l in enumerate(labels) if l.lower() == label.lower())
            self.matrix[i, j] += weight
            return self
        j = len(labels)
        if j >= self.max_subnodes:
            # Saturated: fold overflow into the last slot so weight is preserved.
            self.matrix[i, self.max_subnodes - 1] += weight
            return self
        self.subnode_labels[i].append(label or f"{category}-{j + 1}")
        self.matrix[i, j] += weight
        return self

    def add_sections(self, sections: Sequence[Tuple[str, str]]) -> "CourseComposition":
        """Classify and add a sequence of (heading, body) sections."""
        for heading, body in sections:
            self.add_node(classify_section(heading, body), subnode=heading)
        return self

    # --- numpy views ------------------------------------------------------ #
    def node_vector(self) -> np.ndarray:
        """Per-category total weight (length NUM_CATEGORIES)."""
        return self.matrix.sum(axis=1)

    def total_nodes(self) -> int:
        return int(round(float(self.matrix.sum())))

    def present_categories(self) -> List[str]:
        return [NODE_CATEGORIES[i] for i in np.flatnonzero(self.node_vector() > 0)]

    def subnode_counts(self) -> np.ndarray:
        """Number of distinct occupied sub-node slots per category."""
        return (self.matrix > 0).sum(axis=1)

    # --- the two numbers -------------------------------------------------- #
    def composition_score(self, modulus: int = DEFAULT_SCORE_MODULUS) -> int:
        """Salareen Pedagogical Composition Score (PCS) - the recipe fingerprint.

        Deterministic integer in ``0..modulus-1`` (default 0..999, e.g. 247).
        Same node/sub-node recipe -> same score; this is the number you key
        survey outcomes on. The published formula (README "Course Composition
        Score"):

            Q[i,j] = round(rho * M[i,j])                 # 1. quantize (rho=4)
            a[i]   = sum_j (j+1) * Q[i,j]                 # 2. positional sub-node
            R      = sum_i p[i] * a[i]                    # 3. prime category mix
            R     += alpha*N + beta*K                     # 4. structural terms
            PCS    = R mod mu                             # 5. readable code space

        where p[i] is the i-th prime, N = total nodes, K = present categories,
        and (rho, alpha, beta, mu) = (QUANT_RESOLUTION, STRUCT_NODE_COEFF,
        STRUCT_CATEGORY_COEFF, DEFAULT_SCORE_MODULUS). ``modulus <= 0`` returns
        the full uncompressed raw R' (use composition_signature for exact id).
        """
        # 1. Quantize weights to a fixed resolution -> integer matrix Q.
        quant = np.rint(self.matrix * QUANT_RESOLUTION).astype(np.int64)
        # 2. Positional sub-node weighting: slot j (0-indexed) contributes (j+1)x.
        slot_weights = np.arange(1, self.max_subnodes + 1, dtype=np.int64)
        per_category = (quant * slot_weights[None, :]).sum(axis=1)
        # 3. Prime category mixing -> the raw recipe number R.
        raw = int(np.dot(_PRIMES, per_category))
        # 4. Structural terms (size + breadth) reduce cross-shape collisions.
        raw += (STRUCT_NODE_COEFF * self.total_nodes()
                + STRUCT_CATEGORY_COEFF * len(self.present_categories()))
        # 5. Fold into the readable code space (default 0..999).
        if modulus <= 0:
            return raw
        return int(raw % modulus)

    def composition_signature(self) -> str:
        """Full hex fingerprint for *exact* identity (no modulus collisions)."""
        payload = {
            "v": COMPOSITION_VERSION,
            "m": np.rint(self.matrix * 4.0).astype(np.int64).tolist(),
        }
        blob = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def quality_metrics(self) -> Dict[str, float]:
        """Quantitative, numpy-derived descriptors of the composition."""
        vec = self.node_vector()
        total = float(vec.sum())
        present = vec > 0
        n_present = int(present.sum())
        coverage = n_present / NUM_CATEGORIES if NUM_CATEGORIES else 0.0
        # Balance = normalized Shannon entropy of category weights (1.0 == even).
        if total > 0 and n_present > 1:
            p = vec[present] / total
            entropy = float(-(p * np.log(p)).sum())
            balance = entropy / math.log(n_present)
        else:
            balance = 0.0
        subnode_counts = self.subnode_counts()
        depth = float(subnode_counts[present].mean()) if n_present else 0.0
        inter_idx = [CATEGORY_INDEX[c] for c in INTERACTIVE_CATEGORIES]
        interactivity = float(vec[inter_idx].sum() / total) if total > 0 else 0.0
        return {
            "coverage": round(coverage, 4),
            "balance": round(balance, 4),
            "depth": round(depth, 4),
            "interactivity": round(interactivity, 4),
            "richness": round(total, 4),
        }

    def quality_index(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Single 0..100 heuristic 'how good does this recipe look' score."""
        m = self.quality_metrics()
        w = {"coverage": 0.30, "balance": 0.20, "interactivity": 0.30, "depth": 0.20}
        if weights:
            w.update(weights)
        depth_norm = min(m["depth"] / 3.0, 1.0)  # ~3 subtopics/category is "deep"
        score = (
            w["coverage"] * m["coverage"]
            + w["balance"] * m["balance"]
            + w["interactivity"] * m["interactivity"]
            + w["depth"] * depth_norm
        )
        return round(100.0 * score, 2)

    # --- serialization ---------------------------------------------------- #
    def to_dict(self) -> Dict:
        return {
            "version": COMPOSITION_VERSION,
            "subject": self.subject,
            "course_id": self.course_id,
            "max_subnodes": self.max_subnodes,
            "composition_score": self.composition_score(),
            "composition_signature": self.composition_signature(),
            "quality_index": self.quality_index(),
            "quality_metrics": self.quality_metrics(),
            "node_vector": {
                NODE_CATEGORIES[i]: round(float(v), 4)
                for i, v in enumerate(self.node_vector()) if v > 0
            },
            "subnodes": {
                NODE_CATEGORIES[i]: list(labels)
                for i, labels in enumerate(self.subnode_labels) if labels
            },
            "matrix": self.matrix.tolist(),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict) -> "CourseComposition":
        max_subnodes = int(data.get("max_subnodes", DEFAULT_MAX_SUBNODES))
        matrix = np.array(data.get("matrix") or
                          np.zeros((NUM_CATEGORIES, max_subnodes)), dtype=np.float64)
        labels = [[] for _ in range(NUM_CATEGORIES)]
        for cat, vals in (data.get("subnodes") or {}).items():
            if cat in CATEGORY_INDEX:
                labels[CATEGORY_INDEX[cat]] = list(vals)
        return cls(
            subject=data.get("subject", "general"),
            course_id=data.get("course_id", ""),
            max_subnodes=max_subnodes,
            matrix=matrix,
            subnode_labels=labels,
        )


# --------------------------------------------------------------------------- #
# Outcome ledger: correlate a composition_score with real survey happiness so we
# can answer "is recipe 247 happier than recipe 148 for this subject?".
# --------------------------------------------------------------------------- #
@dataclass
class _ScoreStat:
    score: int
    n: int = 0
    happiness_sum: float = 0.0
    courses: set = field(default_factory=set)

    @property
    def avg_happiness(self) -> float:
        return round(self.happiness_sum / self.n, 4) if self.n else 0.0


class CompositionOutcomeLedger:
    """Aggregates survey happiness (1..5 or 0..1) per composition_score.

    Keyed by (subject, composition_score) so the same recipe can be compared
    across subjects. ``compare`` answers the spec's headline question directly.
    """

    def __init__(self) -> None:
        self._stats: Dict[Tuple[str, int], _ScoreStat] = {}

    def record(self, *, composition_score: int, happiness: float,
               subject: str = "general", course_id: str = "") -> None:
        key = (subject, int(composition_score))
        stat = self._stats.get(key)
        if stat is None:
            stat = _ScoreStat(score=int(composition_score))
            self._stats[key] = stat
        stat.n += 1
        stat.happiness_sum += float(happiness)
        if course_id:
            stat.courses.add(course_id)

    def stats_for(self, composition_score: int, subject: str = "general") -> Dict:
        stat = self._stats.get((subject, int(composition_score)))
        if stat is None:
            return {"subject": subject, "composition_score": int(composition_score),
                    "responses": 0, "avg_happiness": 0.0, "courses": []}
        return {
            "subject": subject,
            "composition_score": stat.score,
            "responses": stat.n,
            "avg_happiness": stat.avg_happiness,
            "courses": sorted(stat.courses),
        }

    def compare(self, score_a: int, score_b: int, subject: str = "general") -> Dict:
        a = self.stats_for(score_a, subject)
        b = self.stats_for(score_b, subject)
        winner = None
        if a["responses"] and b["responses"]:
            winner = score_a if a["avg_happiness"] >= b["avg_happiness"] else score_b
        elif a["responses"]:
            winner = score_a
        elif b["responses"]:
            winner = score_b
        return {
            "subject": subject,
            "a": a,
            "b": b,
            "winner": winner,
            "delta": round(a["avg_happiness"] - b["avg_happiness"], 4),
        }

    def best_scores(self, subject: str = "general", *, min_responses: int = 1,
                    top_n: int = 5) -> List[Dict]:
        rows = [
            self.stats_for(score, subj)
            for (subj, score), stat in self._stats.items()
            if subj == subject and stat.n >= min_responses
        ]
        rows.sort(key=lambda r: r["avg_happiness"], reverse=True)
        return rows[:top_n]
