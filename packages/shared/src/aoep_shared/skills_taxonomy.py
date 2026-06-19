"""Course relevance taxonomy: core skills, fundamentals, and profession audiences.

Beyond "related jobs", courses carry relevance tags that connect a subject to the
professions it supports - e.g. algebra is a fundamental for accountants and useful
for chefs; calculus is a fundamental for engineers; physics underpins civil and
aerospace engineering. These derived tags ("For Engineers", "Core skill",
"Fundamental for Nurses") help learners and the matcher find the skills a job
needs.

Pure/offline + stdlib. Relevance is derived from a course's subject/tags via the
maps below, and can be augmented by explicit course fields.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence, Set

# Profession slug -> plural display label.
PROFESSIONS: Dict[str, str] = {
    "engineer": "Engineers",
    "civil-engineer": "Civil Engineers",
    "aerospace-engineer": "Aerospace / NASA Engineers",
    "mechanical-engineer": "Mechanical Engineers",
    "electrical-engineer": "Electrical Engineers",
    "software-engineer": "Software Engineers",
    "network-engineer": "Network Engineers",
    "data-analyst": "Data Analysts",
    "data-scientist": "Data Scientists",
    "accountant": "Accountants",
    "financial-analyst": "Financial Analysts",
    "nurse": "Nurses",
    "doctor": "Doctors",
    "pharmacist": "Pharmacists",
    "farmer": "Farmers",
    "chef": "Chefs",
    "baker": "Bakers",
    "marketer": "Marketers",
    "designer": "Designers",
    "project-manager": "Project Managers",
    "teacher": "Teachers",
    "pilot": "Pilots",
    "scientist": "Scientists",
    "electrician": "Electricians",
}

# subject/skill keyword -> professions it is RELEVANT (useful) for.
RELEVANCE: Dict[str, Set[str]] = {
    "algebra": {"chef", "baker", "accountant", "financial-analyst", "engineer",
                "data-analyst", "nurse", "electrician"},
    "geometry": {"chef", "civil-engineer", "engineer", "designer"},
    "trigonometry": {"civil-engineer", "engineer", "pilot", "electrician"},
    "calculus": {"engineer", "civil-engineer", "aerospace-engineer", "mechanical-engineer",
                 "electrical-engineer", "data-scientist", "scientist"},
    "statistics": {"data-analyst", "data-scientist", "accountant", "nurse", "scientist",
                   "financial-analyst", "marketer"},
    "math": {"engineer", "accountant", "data-analyst", "chef", "scientist"},
    "physics": {"civil-engineer", "aerospace-engineer", "mechanical-engineer",
                "electrical-engineer", "engineer", "pilot", "scientist"},
    "chemistry": {"chef", "baker", "nurse", "pharmacist", "farmer", "scientist", "doctor"},
    "biology": {"nurse", "doctor", "pharmacist", "farmer", "scientist"},
    "anatomy": {"nurse", "doctor", "pharmacist"},
    "nutrition": {"chef", "baker", "nurse", "farmer"},
    "culinary": {"chef", "baker"},
    "cooking": {"chef", "baker"},
    "agriculture": {"farmer"},
    "soil": {"farmer"},
    "python": {"software-engineer", "data-analyst", "data-scientist", "engineer"},
    "programming": {"software-engineer", "data-analyst", "data-scientist"},
    "coding": {"software-engineer", "data-analyst"},
    "machine-learning": {"data-scientist", "software-engineer", "engineer"},
    "cloud": {"software-engineer", "network-engineer"},
    "devops": {"software-engineer", "network-engineer"},
    "networking": {"network-engineer", "software-engineer"},
    "sql": {"data-analyst", "software-engineer", "accountant"},
    "data": {"data-analyst", "data-scientist"},
    "accounting": {"accountant", "financial-analyst"},
    "finance": {"accountant", "financial-analyst"},
    "marketing": {"marketer"},
    "design": {"designer"},
    "communication": set(PROFESSIONS.keys()),   # core for everyone
    "writing": set(PROFESSIONS.keys()),
    "spanish": {"nurse", "teacher", "marketer", "chef"},
}

# subject keyword -> professions it is a FUNDAMENTAL / core requirement for.
FUNDAMENTAL: Dict[str, Set[str]] = {
    "algebra": {"accountant", "engineer", "data-analyst", "financial-analyst"},
    "calculus": {"engineer", "aerospace-engineer", "mechanical-engineer", "electrical-engineer"},
    "physics": {"civil-engineer", "aerospace-engineer", "mechanical-engineer"},
    "statistics": {"data-analyst", "data-scientist"},
    "anatomy": {"nurse", "doctor"},
    "chemistry": {"pharmacist", "nurse"},
    "biology": {"nurse", "doctor"},
    "python": {"software-engineer", "data-scientist"},
    "accounting": {"accountant"},
    "networking": {"network-engineer"},
}

# Broadly foundational "core skills".
CORE_SKILL_KEYWORDS = {
    "algebra", "math", "statistics", "communication", "writing", "reading",
    "critical-thinking", "problem-solving", "logic",
}

_STOP = {"the", "a", "an", "to", "of", "for", "and", "with", "in", "on", "intro",
         "introduction", "basics", "essentials", "101", "audio", "fundamentals",
         "foundations", "your", "how", "what"}


def _tokens(text: str) -> Set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if w and w not in _STOP}


def _course_keywords(course: dict) -> Set[str]:
    toks: Set[str] = set()
    for t in course.get("tags", []) or []:
        toks.add(str(t).lower())
        toks |= _tokens(str(t))
    toks |= _tokens(course.get("title", ""))
    toks |= _tokens(course.get("subject", ""))
    toks |= _tokens(course.get("category", ""))
    return toks


def course_relevance(course: dict) -> dict:
    """Derive profession audiences + fundamentals + core-skill flag for a course."""
    kws = _course_keywords(course)
    audiences: Set[str] = set(course.get("audiences", []) or [])
    fundamental_for: Set[str] = set()
    matched: Set[str] = set()
    for kw in kws:
        if kw in RELEVANCE:
            audiences |= RELEVANCE[kw]
            matched.add(kw)
        if kw in FUNDAMENTAL:
            fundamental_for |= FUNDAMENTAL[kw]
    core = bool(course.get("core_skill")) or bool(kws & CORE_SKILL_KEYWORDS)
    return {
        "audiences": sorted(audiences),
        "fundamental_for": sorted(fundamental_for),
        "core_skill": core,
        "matched_subjects": sorted(matched),
        "audience_labels": [PROFESSIONS.get(p, p.title()) for p in sorted(audiences)],
        "tags": relevance_tags(sorted(audiences), sorted(fundamental_for), core),
    }


def relevance_tags(audiences: Sequence[str], fundamental_for: Sequence[str],
                   core: bool) -> List[str]:
    tags: List[str] = []
    if core:
        tags.append("Core skill")
    for p in fundamental_for:
        tags.append(f"Fundamental for {PROFESSIONS.get(p, p.title())}")
    for p in audiences:
        if p not in fundamental_for:
            tags.append(f"For {PROFESSIONS.get(p, p.title())}")
    return tags


def course_audiences(course: dict) -> List[str]:
    return course_relevance(course)["audiences"]


def professions_catalog() -> List[dict]:
    """Professions + the subjects that feed them (for discovery/facets)."""
    feeds: Dict[str, Set[str]] = {}
    for subj, profs in RELEVANCE.items():
        for p in profs:
            feeds.setdefault(p, set()).add(subj)
    return [
        {"slug": slug, "label": label, "subjects": sorted(feeds.get(slug, set()))}
        for slug, label in sorted(PROFESSIONS.items(), key=lambda kv: kv[1])
    ]
