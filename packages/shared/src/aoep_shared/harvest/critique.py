"""Continuous review / critique / optimization of the harvester output.

As the learning algorithm and teaching behavior improve, we want to keep
re-grading what the harvester produces and steer it toward better course
compositions. ``HarvestCritic`` inspects a generated course (or a raw
``CourseComposition``), grades it against pedagogical heuristics, and emits
concrete issues + suggestions. ``optimize_with_ledger`` records each critique
pass as a revertible checkpoint in the shared ``OptimizationLedger`` so a
regression in harvested quality can be detected and rolled back - the runtime
analog of the per-PR git revert used elsewhere in the platform.

Pure stdlib + numpy (via composition); offline-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .composition import CourseComposition

# Default review thresholds (tunable as the learning algorithm evolves).
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "min_slides": 3,
    "min_coverage": 0.30,        # >=30% of pedagogical categories present
    "min_interactivity": 0.15,   # >=15% of nodes require the learner to act
    "min_quality_index": 50.0,
    "min_balance": 0.25,         # avoid one category dominating everything
}


@dataclass
class CritiqueReport:
    course_id: str
    subject: str
    composition_score: int
    quality_index: float
    metrics: Dict[str, float]
    grade: str
    passed: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "course_id": self.course_id,
            "subject": self.subject,
            "composition_score": self.composition_score,
            "quality_index": self.quality_index,
            "metrics": self.metrics,
            "grade": self.grade,
            "passed": self.passed,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


def _grade(quality_index: float) -> str:
    if quality_index >= 85:
        return "A"
    if quality_index >= 70:
        return "B"
    if quality_index >= 55:
        return "C"
    if quality_index >= 40:
        return "D"
    return "F"


class HarvestCritic:
    """Grades harvested/generated courses and suggests improvements."""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    # --- single course ---------------------------------------------------- #
    def review_composition(self, comp: CourseComposition, *, num_slides: int = 0,
                           course_id: str = "", subject: str = "") -> CritiqueReport:
        metrics = comp.quality_metrics()
        qi = comp.quality_index()
        present = set(comp.present_categories())
        issues: List[str] = []
        suggestions: List[str] = []

        if num_slides and num_slides < self.thresholds["min_slides"]:
            issues.append(f"too few slides ({num_slides})")
            suggestions.append("ingest a richer source or split sections further")
        if metrics["coverage"] < self.thresholds["min_coverage"]:
            issues.append(f"low pedagogical coverage ({metrics['coverage']:.0%})")
            suggestions.append("add missing block types (e.g. example, summary, q&a)")
        if "introduction" not in present:
            issues.append("missing an introduction node")
            suggestions.append("add an introduction that frames objectives")
        if not ({"summary", "recap"} & present):
            issues.append("missing a summary/recap node")
            suggestions.append("add a closing summary or spaced recap")
        if metrics["interactivity"] < self.thresholds["min_interactivity"]:
            issues.append(f"low interactivity ({metrics['interactivity']:.0%})")
            suggestions.append("add exercises, a quiz, or a Q&A block")
        if metrics["balance"] and metrics["balance"] < self.thresholds["min_balance"]:
            issues.append(f"unbalanced composition (balance {metrics['balance']:.2f})")
            suggestions.append("spread material across more node categories")
        if qi < self.thresholds["min_quality_index"]:
            issues.append(f"quality index below bar ({qi:.1f})")

        passed = not issues
        return CritiqueReport(
            course_id=course_id or comp.course_id,
            subject=subject or comp.subject,
            composition_score=comp.composition_score(),
            quality_index=qi,
            metrics=metrics,
            grade=_grade(qi),
            passed=passed,
            issues=issues,
            suggestions=suggestions,
        )

    def review(self, generated) -> CritiqueReport:
        """Review a ``GeneratedCourse`` (duck-typed: needs .composition/.slides)."""
        comp = generated.composition
        if comp is None:
            raise ValueError("generated course has no composition to critique")
        return self.review_composition(
            comp,
            num_slides=len(getattr(generated, "slides", []) or []),
            course_id=getattr(generated, "course_id", ""),
            subject=getattr(generated, "subject", ""),
        )

    # --- batch ------------------------------------------------------------ #
    def review_batch(self, generated_courses: Sequence) -> Dict:
        reports = [self.review(g) for g in generated_courses]
        return summarize_reports(reports)


def summarize_reports(reports: Sequence[CritiqueReport]) -> Dict:
    n = len(reports)
    if not n:
        return {"count": 0, "pass_rate": 0.0, "avg_quality_index": 0.0,
                "reports": [], "top_issues": []}
    passed = sum(1 for r in reports if r.passed)
    avg_qi = round(sum(r.quality_index for r in reports) / n, 2)
    issue_counts: Dict[str, int] = {}
    for r in reports:
        for issue in r.issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    top_issues = sorted(issue_counts.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "count": n,
        "pass_rate": round(passed / n, 4),
        "avg_quality_index": avg_qi,
        "top_issues": [{"issue": k, "count": v} for k, v in top_issues],
        "reports": [r.to_dict() for r in reports],
    }


def optimize_with_ledger(ledger, reports: Sequence[CritiqueReport], *,
                         stage: str = "harvester_quality", params: Optional[Dict] = None):
    """Commit a critique pass as a revertible OptimizationStep and promote it iff
    it does not regress average quality. Returns (step, promoted)."""
    summary = summarize_reports(reports)
    step = ledger.commit(
        stage,
        {**(params or {}), "n_reviewed": summary["count"]},
        {"accuracy": summary["avg_quality_index"] / 100.0,
         "pass_rate": summary["pass_rate"],
         "avg_quality_index": summary["avg_quality_index"]},
    )
    promoted = ledger.promote_if_better(step)
    return step, promoted
