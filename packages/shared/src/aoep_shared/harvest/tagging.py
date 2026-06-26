"""JSON / meta tagging for harvested courses.

Every generated course carries a structured, JSON-serializable tag set so it can
be filtered, priced, and routed downstream. Tags answer questions like:

  - Is this a FREE class or an EXPENSIVE/paid one?           -> access_tier / price
  - Is it tied to a specific LinkedIn job opening?           -> linkedin_job_id
  - Is it part of a career path (e.g. "nurse")?              -> career_path
  - Is it a basic, core-fundamental subject (e.g. algebra)?  -> core_fundamental
  - Anything else?                                           -> labels / meta

The output maps cleanly onto the catalog ``Course`` fields (access_tier,
price_usd, tags, audiences, core_skill) so the harvester can POST a course and
keep the rich metadata in ``meta``. Pure stdlib + dataclasses (offline-testable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Canonical access tiers (ordered cheap -> expensive). "expensive" maps to the
# top paid tier; callers can also set an explicit price_usd.
ACCESS_TIERS: tuple = ("free", "basic", "pro", "premium", "enterprise")
_EXPENSIVE_TIERS = {"premium", "enterprise"}


@dataclass
class CourseTags:
    """Structured, JSON-serializable course metadata."""

    access_tier: str = "free"                 # free | basic | pro | premium | enterprise
    price_usd: float = 0.0
    career_path: Optional[str] = None         # e.g. "nurse", "data-analyst"
    linkedin_job_id: Optional[str] = None     # opening this course was built for
    core_fundamental: bool = False            # basic building-block subject (algebra)
    audiences: List[str] = field(default_factory=list)   # professions this serves
    labels: List[str] = field(default_factory=list)      # free-form discovery tags
    meta: Dict[str, str] = field(default_factory=dict)    # arbitrary extra metadata

    def __post_init__(self) -> None:
        tier = (self.access_tier or "free").strip().lower()
        if tier == "expensive":
            tier = "premium"
        if tier not in ACCESS_TIERS:
            tier = "free"
        self.access_tier = tier
        self.price_usd = max(0.0, float(self.price_usd or 0.0))

    # --- derived flags ---------------------------------------------------- #
    @property
    def is_free(self) -> bool:
        return self.access_tier == "free" and self.price_usd <= 0.0

    @property
    def is_expensive(self) -> bool:
        return self.access_tier in _EXPENSIVE_TIERS or self.price_usd >= 200.0

    @property
    def is_job_linked(self) -> bool:
        return bool(self.linkedin_job_id)

    @property
    def is_career_course(self) -> bool:
        return bool(self.career_path)

    # --- serialization ---------------------------------------------------- #
    def to_dict(self) -> Dict:
        return {
            "access_tier": self.access_tier,
            "price_usd": round(self.price_usd, 2),
            "career_path": self.career_path,
            "linkedin_job_id": self.linkedin_job_id,
            "core_fundamental": self.core_fundamental,
            "audiences": list(self.audiences),
            "labels": self.label_list(),
            "meta": dict(self.meta),
            "flags": {
                "free": self.is_free,
                "expensive": self.is_expensive,
                "job_linked": self.is_job_linked,
                "career_course": self.is_career_course,
            },
        }

    def label_list(self) -> List[str]:
        """Flat list of human/search labels (derived flags + explicit labels)."""
        out: List[str] = list(self.labels)
        out.append("free" if self.is_free else "paid")
        if self.is_expensive:
            out.append("expensive")
        if self.core_fundamental:
            out.append("core-fundamental")
        if self.is_career_course:
            out.append(f"career:{self.career_path}")
        if self.is_job_linked:
            out.append(f"job:{self.linkedin_job_id}")
        # De-dup, preserve order.
        seen: set = set()
        deduped: List[str] = []
        for t in out:
            if t and t not in seen:
                seen.add(t)
                deduped.append(t)
        return deduped

    def catalog_fields(self) -> Dict:
        """Subset shaped for the curriculum catalog ``Course`` model."""
        return {
            "access_tier": self.access_tier,
            "price_usd": round(self.price_usd, 2),
            "tags": self.label_list(),
            "audiences": list(self.audiences),
            "core_skill": self.core_fundamental,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CourseTags":
        return cls(
            access_tier=data.get("access_tier", "free"),
            price_usd=float(data.get("price_usd", 0.0) or 0.0),
            career_path=data.get("career_path"),
            linkedin_job_id=data.get("linkedin_job_id"),
            core_fundamental=bool(data.get("core_fundamental", False)),
            audiences=list(data.get("audiences", []) or []),
            labels=list(data.get("labels", []) or []),
            meta=dict(data.get("meta", {}) or {}),
        )
