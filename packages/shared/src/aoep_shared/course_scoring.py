"""Course scoring admin: review, manually edit, override, and tune via telemetry.

The numpy composition layer (``harvest/composition.py``) produces two numbers:
- ``composition_score()`` — the PCS *recipe fingerprint* (e.g. 128). FIXED FOREVER
  so a given node/sub-node recipe always maps to the same code. We do NOT change
  the fingerprint formula here; instead we let operators attach an adjustable
  human label/score on top and review exactly how the fingerprint was computed.
- ``quality_index()`` — a 0..100 heuristic whose *weights are tunable*.

This module adds the operator-facing layer the team asked for:

1. ScoringConfig — editable weights + quality label bands, persisted to JSON so
   the scoring system can be adjusted without code changes.
2. score_breakdown() — a full, step-by-step explanation of how a course got its
   PCS code and quality score (to review the scoring system).
3. OverrideStore — manual per-course label/score overrides with provenance.
4. TelemetryStore — collect per-course telemetry (composition_score, quality,
   engagement/happiness), compare courses, and recommend weight adjustments by
   correlating the quality components with observed happiness.

Pure (numpy + stdlib); all stores are JSON-file backed and offline-testable.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .harvest.composition import (
    CATEGORY_INDEX,
    DEFAULT_SCORE_MODULUS,
    NODE_CATEGORIES,
    QUANT_RESOLUTION,
    STRUCT_CATEGORY_COEFF,
    STRUCT_NODE_COEFF,
    CourseComposition,
    _PRIMES,
)

SCORING_CONFIG_VERSION = "1.0"

_DEFAULT_QUALITY_WEIGHTS = {
    "coverage": 0.30,
    "balance": 0.20,
    "interactivity": 0.30,
    "depth": 0.20,
}

# (min_inclusive_score, label) descending; first match wins.
_DEFAULT_QUALITY_BANDS: List[Tuple[float, str]] = [
    (85.0, "excellent"),
    (70.0, "strong"),
    (50.0, "adequate"),
    (30.0, "thin"),
    (0.0, "needs_work"),
]


def default_scoring_dir() -> Path:
    env = os.environ.get("AOEP_SCORING_DIR")
    if env:
        return Path(env)
    return Path(os.path.expanduser("~")) / ".cache" / "aoep" / "scoring"


# --------------------------------------------------------------------------- #
# Editable configuration
# --------------------------------------------------------------------------- #
@dataclass
class ScoringConfig:
    quality_weights: Dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_QUALITY_WEIGHTS))
    depth_target: float = 3.0
    quality_bands: List[Tuple[float, str]] = field(
        default_factory=lambda: list(_DEFAULT_QUALITY_BANDS))
    notes: str = ""
    updated_at: float = field(default_factory=lambda: time.time())

    def normalized_weights(self) -> Dict[str, float]:
        w = {k: max(0.0, float(v)) for k, v in self.quality_weights.items()}
        total = sum(w.values()) or 1.0
        return {k: round(v / total, 6) for k, v in w.items()}

    def quality_label(self, quality_index: float) -> str:
        for threshold, label in sorted(self.quality_bands, reverse=True):
            if quality_index >= threshold:
                return label
        return self.quality_bands[-1][1] if self.quality_bands else "unrated"

    def version(self) -> str:
        blob = json.dumps(
            {"w": self.normalized_weights(), "d": self.depth_target,
             "b": sorted(self.quality_bands)},
            sort_keys=True, separators=(",", ":"),
        )
        import hashlib

        return f"{SCORING_CONFIG_VERSION}:{hashlib.sha256(blob.encode()).hexdigest()[:8]}"

    def to_dict(self) -> dict:
        return {
            "config_version": SCORING_CONFIG_VERSION,
            "version": self.version(),
            "quality_weights": dict(self.quality_weights),
            "normalized_weights": self.normalized_weights(),
            "depth_target": self.depth_target,
            "quality_bands": [[t, l] for t, l in self.quality_bands],
            "notes": self.notes,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScoringConfig":
        bands = data.get("quality_bands")
        parsed_bands = (
            [(float(t), str(l)) for t, l in bands] if bands else list(_DEFAULT_QUALITY_BANDS)
        )
        return cls(
            quality_weights={k: float(v) for k, v in
                             (data.get("quality_weights") or _DEFAULT_QUALITY_WEIGHTS).items()},
            depth_target=float(data.get("depth_target", 3.0)),
            quality_bands=parsed_bands,
            notes=str(data.get("notes", "")),
            updated_at=float(data.get("updated_at", time.time())),
        )

    def save(self, path: Optional[Path] = None) -> None:
        path = Path(path) if path else (default_scoring_dir() / "scoring_config.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "ScoringConfig":
        path = Path(path) if path else (default_scoring_dir() / "scoring_config.json")
        if path.is_file():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                pass
        return cls()


def quality_index_with_config(comp: CourseComposition, config: ScoringConfig) -> float:
    """quality_index recomputed using the editable config weights + depth target."""
    m = comp.quality_metrics()
    w = config.normalized_weights()
    depth_norm = min(m["depth"] / max(0.1, config.depth_target), 1.0)
    score = (
        w.get("coverage", 0.0) * m["coverage"]
        + w.get("balance", 0.0) * m["balance"]
        + w.get("interactivity", 0.0) * m["interactivity"]
        + w.get("depth", 0.0) * depth_norm
    )
    return round(100.0 * score, 2)


# --------------------------------------------------------------------------- #
# Review / explain
# --------------------------------------------------------------------------- #
def score_breakdown(comp: CourseComposition, config: Optional[ScoringConfig] = None) -> dict:
    """Step-by-step explanation of the PCS fingerprint and the quality score."""
    config = config or ScoringConfig()
    quant = np.rint(comp.matrix * QUANT_RESOLUTION).astype(np.int64)
    slot_weights = np.arange(1, comp.max_subnodes + 1, dtype=np.int64)
    per_category = (quant * slot_weights[None, :]).sum(axis=1)
    prime_mix = int(np.dot(_PRIMES, per_category))
    total_nodes = comp.total_nodes()
    breadth = len(comp.present_categories())
    structural = STRUCT_NODE_COEFF * total_nodes + STRUCT_CATEGORY_COEFF * breadth
    raw = prime_mix + structural
    score = int(raw % DEFAULT_SCORE_MODULUS)
    qi = quality_index_with_config(comp, config)
    return {
        "composition_score": score,
        "composition_signature": comp.composition_signature(),
        "pcs_formula": {
            "quant_resolution": QUANT_RESOLUTION,
            "per_category_positional": {
                NODE_CATEGORIES[i]: int(per_category[i])
                for i in range(len(NODE_CATEGORIES)) if per_category[i]
            },
            "prime_mix_R": prime_mix,
            "struct_node_coeff": STRUCT_NODE_COEFF,
            "struct_category_coeff": STRUCT_CATEGORY_COEFF,
            "total_nodes_N": total_nodes,
            "breadth_K": breadth,
            "structural_term": structural,
            "raw_before_modulus": raw,
            "modulus": DEFAULT_SCORE_MODULUS,
        },
        "quality_metrics": comp.quality_metrics(),
        "quality_index": qi,
        "quality_index_default": comp.quality_index(),
        "quality_label": config.quality_label(qi),
        "present_categories": comp.present_categories(),
        "config_version": config.version(),
    }


# --------------------------------------------------------------------------- #
# Manual overrides
# --------------------------------------------------------------------------- #
@dataclass
class ManualOverride:
    course_id: str
    label: Optional[str] = None          # human label, e.g. "flagship-128"
    score: Optional[int] = None          # pinned composition code, e.g. 128
    quality_index: Optional[float] = None
    note: str = ""
    author: str = ""
    updated_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict:
        return {
            "course_id": self.course_id, "label": self.label, "score": self.score,
            "quality_index": self.quality_index, "note": self.note,
            "author": self.author, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ManualOverride":
        return cls(
            course_id=str(d["course_id"]),
            label=d.get("label"),
            score=(int(d["score"]) if d.get("score") is not None else None),
            quality_index=(float(d["quality_index"]) if d.get("quality_index") is not None else None),
            note=str(d.get("note", "")),
            author=str(d.get("author", "")),
            updated_at=float(d.get("updated_at", time.time())),
        )


class OverrideStore:
    """JSON-backed manual override registry."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else (default_scoring_dir() / "overrides.json")
        self._items: Dict[str, ManualOverride] = {}
        self._load()

    def _load(self) -> None:
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                for rec in data.get("overrides", []):
                    ov = ManualOverride.from_dict(rec)
                    self._items[ov.course_id] = ov
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                self._items = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"overrides": [o.to_dict() for o in self._items.values()]}, indent=2),
            encoding="utf-8",
        )

    def set(self, override: ManualOverride) -> ManualOverride:
        override.updated_at = time.time()
        self._items[override.course_id] = override
        self._save()
        return override

    def get(self, course_id: str) -> Optional[ManualOverride]:
        return self._items.get(course_id)

    def delete(self, course_id: str) -> bool:
        if course_id in self._items:
            del self._items[course_id]
            self._save()
            return True
        return False

    def list(self) -> List[ManualOverride]:
        return list(self._items.values())

    def effective(self, course_id: str, *, computed_score: int,
                  computed_quality: float, computed_label: str) -> dict:
        ov = self._items.get(course_id)
        return {
            "course_id": course_id,
            "score": ov.score if (ov and ov.score is not None) else computed_score,
            "quality_index": (ov.quality_index if (ov and ov.quality_index is not None)
                              else computed_quality),
            "label": (ov.label if (ov and ov.label) else computed_label),
            "overridden": bool(ov),
            "computed": {"score": computed_score, "quality_index": computed_quality,
                         "label": computed_label},
            "override": ov.to_dict() if ov else None,
        }


# --------------------------------------------------------------------------- #
# Telemetry: collect, compare, and recommend tuning
# --------------------------------------------------------------------------- #
@dataclass
class TelemetrySample:
    course_id: str
    composition_score: int
    quality_index: float
    subject: str = "general"
    happiness: Optional[float] = None       # 0..1 or 1..5 survey signal
    completion_rate: Optional[float] = None  # 0..1
    metrics: Dict[str, float] = field(default_factory=dict)  # coverage/balance/...
    config_version: str = ""
    at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict:
        return {
            "course_id": self.course_id, "composition_score": self.composition_score,
            "quality_index": self.quality_index, "subject": self.subject,
            "happiness": self.happiness, "completion_rate": self.completion_rate,
            "metrics": dict(self.metrics), "config_version": self.config_version, "at": self.at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TelemetrySample":
        return cls(
            course_id=str(d["course_id"]),
            composition_score=int(d["composition_score"]),
            quality_index=float(d["quality_index"]),
            subject=str(d.get("subject", "general")),
            happiness=(float(d["happiness"]) if d.get("happiness") is not None else None),
            completion_rate=(float(d["completion_rate"]) if d.get("completion_rate") is not None else None),
            metrics={k: float(v) for k, v in (d.get("metrics") or {}).items()},
            config_version=str(d.get("config_version", "")),
            at=float(d.get("at", time.time())),
        )


class TelemetryStore:
    """JSON-backed course-scoring telemetry with comparison + tuning hints."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else (default_scoring_dir() / "telemetry.jsonl")
        self._samples: List[TelemetrySample] = []
        self._load()

    def _load(self) -> None:
        if self.path.is_file():
            try:
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        self._samples.append(TelemetrySample.from_dict(json.loads(line)))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                self._samples = []

    def record(self, sample: TelemetrySample) -> None:
        self._samples.append(sample)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(sample.to_dict()) + "\n")

    def all(self) -> List[TelemetrySample]:
        return list(self._samples)

    def course_summary(self, course_id: str) -> dict:
        rows = [s for s in self._samples if s.course_id == course_id]
        if not rows:
            return {"course_id": course_id, "samples": 0}
        happ = [s.happiness for s in rows if s.happiness is not None]
        comp = [s.completion_rate for s in rows if s.completion_rate is not None]
        return {
            "course_id": course_id,
            "samples": len(rows),
            "composition_score": rows[-1].composition_score,
            "quality_index": rows[-1].quality_index,
            "avg_happiness": round(sum(happ) / len(happ), 4) if happ else None,
            "avg_completion": round(sum(comp) / len(comp), 4) if comp else None,
        }

    def compare_courses(self, course_a: str, course_b: str) -> dict:
        a = self.course_summary(course_a)
        b = self.course_summary(course_b)

        def _key(s: dict) -> float:
            return (s.get("avg_happiness") or 0.0) * 100 + (s.get("quality_index") or 0.0)

        winner = None
        if a.get("samples") and b.get("samples"):
            winner = course_a if _key(a) >= _key(b) else course_b
        return {"a": a, "b": b, "winner": winner}

    def leaderboard(self, *, subject: Optional[str] = None, min_samples: int = 1,
                    top_n: int = 10) -> List[dict]:
        ids = sorted({s.course_id for s in self._samples
                      if subject is None or s.subject == subject})
        rows = [self.course_summary(cid) for cid in ids]
        rows = [r for r in rows if r.get("samples", 0) >= min_samples]
        rows.sort(key=lambda r: ((r.get("avg_happiness") or 0.0), (r.get("quality_index") or 0.0)),
                  reverse=True)
        return rows[:top_n]

    def recommend_weight_adjustments(self, config: ScoringConfig) -> dict:
        """Correlate each quality metric with happiness and nudge weights.

        Uses recorded per-course metric vectors against happiness; the metric
        most positively correlated with happiness gets a small weight increase,
        negatively-correlated metrics get decreased. Returns suggested (not
        applied) normalized weights plus the correlations and rationale.
        """
        keys = ["coverage", "balance", "interactivity", "depth"]
        usable = [s for s in self._samples
                  if s.happiness is not None and all(k in s.metrics for k in keys)]
        current = config.normalized_weights()
        if len(usable) < 3:
            return {
                "status": "insufficient_data",
                "needed": 3, "have": len(usable),
                "current_weights": current,
                "suggested_weights": current,
                "correlations": {},
            }
        happ = np.array([float(s.happiness) for s in usable], dtype=np.float64)
        correlations: Dict[str, float] = {}
        for k in keys:
            col = np.array([float(s.metrics[k]) for s in usable], dtype=np.float64)
            if np.std(col) < 1e-9 or np.std(happ) < 1e-9:
                correlations[k] = 0.0
            else:
                correlations[k] = float(round(np.corrcoef(col, happ)[0, 1], 4))
        # Nudge weights proportionally to correlation, then renormalize.
        step = 0.10
        suggested = {k: max(0.0, current.get(k, 0.0) + step * correlations[k]) for k in keys}
        total = sum(suggested.values()) or 1.0
        suggested = {k: round(v / total, 6) for k, v in suggested.items()}
        best = max(correlations, key=correlations.get)
        return {
            "status": "ok",
            "samples_used": len(usable),
            "current_weights": current,
            "suggested_weights": suggested,
            "correlations": correlations,
            "rationale": f"'{best}' correlates most with happiness "
                         f"(r={correlations[best]}); weights nudged toward it.",
        }
