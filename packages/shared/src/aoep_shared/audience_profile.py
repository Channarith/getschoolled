"""Audience readiness aggregation for Theodore / admin (privacy-safe).

Builds composite readiness + dimensional summaries without putting learner names
or accommodations into LLM prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .learning_experience import LX_TARGET, LXComponents, compute_lx_score


READINESS_BANDS = (
    ("needs_support", 0.0, 55.0),
    ("developing", 55.0, 75.0),
    ("ready", 75.0, 101.0),
)


@dataclass
class LearnerReadinessSnapshot:
    student_id: str = ""
    account_id: str = ""
    readiness_score: float = 0.0
    dimensions: Dict[str, float] = field(default_factory=dict)
    physical_skill: float = 0.5
    band: str = "developing"
    course_history_summary: Dict[str, Any] = field(default_factory=dict)
    preferred_language: str = ""
    primary_style: str = "mixed"

    def to_host_private(self) -> dict:
        """Host/admin view — may include student_id but not accommodations."""
        return {
            "student_id": self.student_id,
            "readiness_score": self.readiness_score,
            "dimensions": dict(self.dimensions),
            "physical_skill": self.physical_skill,
            "band": self.band,
            "course_history_summary": dict(self.course_history_summary),
            "preferred_language": self.preferred_language,
            "primary_style": self.primary_style,
        }

    def to_prompt_safe(self) -> dict:
        """No identifiers — safe for LLM context."""
        return {
            "band": self.band,
            "readiness_score": self.readiness_score,
            "dimensions": dict(self.dimensions),
            "physical_skill": self.physical_skill,
            "primary_style": self.primary_style,
            "language": self.preferred_language or "en",
            "prior_courses": {
                "passed": int((self.course_history_summary or {}).get("passed", 0)),
                "failed": int((self.course_history_summary or {}).get("failed", 0)),
                "needs_work": int((self.course_history_summary or {}).get("needs_work", 0)),
                "recent_titles": list(
                    (self.course_history_summary or {}).get("recent_titles") or []
                )[:5],
            },
        }


@dataclass
class AudienceProfile:
    learner_count: int = 0
    mean_readiness: float = 0.0
    median_readiness: float = 0.0
    band_counts: Dict[str, int] = field(default_factory=dict)
    mean_dimensions: Dict[str, float] = field(default_factory=dict)
    dominant_styles: List[str] = field(default_factory=list)
    language_counts: Dict[str, int] = field(default_factory=dict)
    course_struggle_titles: List[str] = field(default_factory=list)
    lx_target: float = LX_TARGET

    def to_prompt_safe(self) -> dict:
        return {
            "learner_count": self.learner_count,
            "mean_readiness": self.mean_readiness,
            "median_readiness": self.median_readiness,
            "band_counts": dict(self.band_counts),
            "mean_dimensions": dict(self.mean_dimensions),
            "dominant_styles": list(self.dominant_styles)[:3],
            "language_counts": dict(self.language_counts),
            "course_struggle_titles": list(self.course_struggle_titles)[:5],
            "lx_target": self.lx_target,
            "adaptation_hints": _adaptation_hints(self),
        }


def readiness_band(score: float) -> str:
    s = float(score)
    for name, lo, hi in READINESS_BANDS:
        if lo <= s < hi:
            return name
    return "developing"


def snapshot_from_adaptation(
    *,
    student_id: str = "",
    account_id: str = "",
    adaptation: Optional[dict] = None,
    primary_style: str = "mixed",
    preferred_language: str = "",
    enrollments: Optional[Sequence[dict]] = None,
    physical_skill: Optional[float] = None,
) -> LearnerReadinessSnapshot:
    raw = dict(adaptation or {})
    dims = _dimensions_from_adaptation(raw)
    phys = physical_skill
    if phys is None:
        phys = float(raw.get("physical_skill", dims.get("physical_skill", 0.5)))
    comps = LXComponents(
        engagement=float(dims.get("engagement", 0.7)),
        mastery=float(dims.get("mastery", 0.5)),
        clarity=float(dims.get("clarity", 0.9)),
        pace_fit=float(dims.get("pace_fit", 0.7)),
        completion=float(dims.get("completion", 0.0)),
        wellness=float(dims.get("wellness", 1.0)),
    )
    ema = raw.get("lx_score_ema")
    if ema is None:
        # Blend LX with physical skill lightly for readiness.
        base = compute_lx_score(comps)
        score = round(0.85 * base + 0.15 * (float(phys) * 100.0), 1)
    else:
        score = round(0.85 * float(ema) + 0.15 * (float(phys) * 100.0), 1)
    history = summarize_course_history(enrollments or [])
    dim_out = comps.as_dict()
    dim_out["physical_skill"] = round(float(phys), 3)
    return LearnerReadinessSnapshot(
        student_id=student_id,
        account_id=account_id,
        readiness_score=score,
        dimensions=dim_out,
        physical_skill=round(float(phys), 3),
        band=readiness_band(score),
        course_history_summary=history,
        preferred_language=(preferred_language or "").strip().lower()[:12],
        primary_style=(primary_style or "mixed").strip().lower() or "mixed",
    )


def summarize_course_history(enrollments: Sequence[dict]) -> Dict[str, Any]:
    passed = failed = needs_work = in_progress = 0
    recent_titles: List[str] = []
    struggle: List[str] = []
    rows = sorted(
        list(enrollments),
        key=lambda e: float(e.get("updated_at") or e.get("enrolled_at") or 0),
        reverse=True,
    )
    for e in rows:
        status = str(e.get("status") or "").lower()
        title = (e.get("title") or e.get("course_id") or "").strip()
        if status == "passed":
            passed += 1
            if title and len(recent_titles) < 5:
                recent_titles.append(title)
        elif status == "failed":
            failed += 1
            if title and title not in struggle:
                struggle.append(title)
        elif status in ("needs_work", "needs-work"):
            needs_work += 1
            if title and title not in struggle:
                struggle.append(title)
        elif status in ("in_progress", "enrolled"):
            in_progress += 1
    return {
        "passed": passed,
        "failed": failed,
        "needs_work": needs_work,
        "in_progress": in_progress,
        "recent_titles": recent_titles,
        "struggle_titles": struggle[:5],
    }


def aggregate_audience(snapshots: Sequence[LearnerReadinessSnapshot]) -> AudienceProfile:
    snaps = list(snapshots)
    if not snaps:
        return AudienceProfile()
    scores = sorted(s.readiness_score for s in snaps)
    n = len(scores)
    median = scores[n // 2] if n % 2 else (scores[n // 2 - 1] + scores[n // 2]) / 2.0
    band_counts: Dict[str, int] = {}
    lang_counts: Dict[str, int] = {}
    style_counts: Dict[str, int] = {}
    dim_sums: Dict[str, float] = {}
    struggle: List[str] = []
    for s in snaps:
        band_counts[s.band] = band_counts.get(s.band, 0) + 1
        lang = s.preferred_language or "en"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        style_counts[s.primary_style] = style_counts.get(s.primary_style, 0) + 1
        for k, v in (s.dimensions or {}).items():
            dim_sums[k] = dim_sums.get(k, 0.0) + float(v)
        for t in (s.course_history_summary or {}).get("struggle_titles") or []:
            if t not in struggle:
                struggle.append(t)
    mean_dims = {k: round(v / n, 3) for k, v in dim_sums.items()}
    dominant = sorted(style_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return AudienceProfile(
        learner_count=n,
        mean_readiness=round(sum(scores) / n, 1),
        median_readiness=round(float(median), 1),
        band_counts=band_counts,
        mean_dimensions=mean_dims,
        dominant_styles=[name for name, _ in dominant],
        language_counts=lang_counts,
        course_struggle_titles=struggle[:5],
    )


def _dimensions_from_adaptation(raw: dict) -> Dict[str, float]:
    stored = raw.get("readiness_dimensions") or raw.get("lx_components") or {}
    out = {
        "engagement": float(stored.get("engagement", 0.7)),
        "mastery": float(stored.get("mastery", 0.5)),
        "clarity": float(stored.get("clarity", 0.9)),
        "pace_fit": float(stored.get("pace_fit", 0.7)),
        "completion": float(stored.get("completion", 0.0)),
        "wellness": float(stored.get("wellness", 1.0)),
    }
    if "physical_skill" in stored:
        out["physical_skill"] = float(stored["physical_skill"])
    return out


def _adaptation_hints(aud: AudienceProfile) -> List[str]:
    hints: List[str] = []
    if aud.band_counts.get("needs_support", 0) >= max(1, aud.learner_count // 3):
        hints.append("slow_pace_and_recap")
    if aud.mean_readiness >= LX_TARGET:
        hints.append("increase_challenge")
    styles = aud.dominant_styles
    if styles:
        hints.append(f"prefer_style:{styles[0]}")
    if aud.course_struggle_titles:
        hints.append("scaffold_prior_struggle_topics")
    if len(aud.language_counts) > 1:
        hints.append("multilingual_audience")
    return hints
