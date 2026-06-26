"""Who may take which content — maturity gates with disability/accommodation override."""

from __future__ import annotations

from typing import Dict, Tuple

# Notes mentioning these terms suggest simplified / child-rated content may help.
ACCOMMODATION_HINTS = (
    "disability", "disorder", "adhd", "dyslexia", "autism", "dyscalculia",
    "learning disorder", "learning disability", "accommodation", "iep", "504",
    "cognitive", "processing",
)


def needs_simplified_content(
    *,
    age_band: str = "adult",
    reading_level: str = "intermediate",
    accessibility: Dict[str, bool] | None = None,
    accommodations_notes: str = "",
    learner_category: str = "",
) -> bool:
    """True when the learner benefits from simpler, child-rated material."""
    if learner_category == "accessibility_supported":
        return True
    if (reading_level or "").lower() == "beginner":
        return True
    if accessibility and any(accessibility.values()):
        return True
    notes = (accommodations_notes or "").lower()
    if any(hint in notes for hint in ACCOMMODATION_HINTS):
        return True
    return False


def may_access_course(
    *,
    age_band: str,
    maturity_rating: str,
    needs_simplified: bool,
) -> Tuple[bool, str]:
    """Return (allowed, reason_code).

  Adults may take child-rated courses when ``needs_simplified`` is true
  (disabilities, learning disorders, accessibility accommodations).
    """
    mat = (maturity_rating or "all").lower()
    band = (age_band or "adult").lower()

    if mat in ("all", ""):
        return True, "open_to_all"
    if mat == "teen":
        if band == "child":
            return False, "teen_content_child_blocked"
        return True, "allowed"
    if mat == "kids":
        if band == "child":
            return True, "age_appropriate"
        if band == "teen":
            return True, "teen_on_kids_content_ok"
        if band == "adult" and needs_simplified:
            return True, "adult_accessibility_child_content"
        if band == "adult":
            return False, "adult_on_kids_content_blocked"
    if mat == "mature" and band == "child":
        return False, "mature_content_child_blocked"
    return True, "allowed"


def student_profile_for_access(prof) -> dict:
    """Extract access-relevant fields from a StudentProfile-like object."""
    return {
        "age_band": getattr(prof, "age_band", "adult"),
        "reading_level": getattr(prof, "reading_level", "intermediate"),
        "accessibility": dict(getattr(prof, "accessibility", None) or {}),
        "accommodations_notes": getattr(prof, "accommodations_notes", "") or "",
        "learner_category": getattr(prof, "learner_category", "") or "",
    }
