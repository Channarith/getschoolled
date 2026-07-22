"""Default corporate training programs.

The in-memory CatalogStore starts with no programs, so the /corporate page's
"Programs" section renders empty out of the box (the same gap the audio
catalog bridge fills for courses). Seed a curated set of corporate tracks at
startup so the corporate funnel is populated without an operator having to
POST /programs by hand.

course_ids reference live-lesson ids from sample-curriculum (AUDIENCE:
corporate); the unified learnable index exposes those lessons through
/courses/search under the same ids, so the web programme cards resolve
titles without seeding Course records.
"""

from __future__ import annotations

import os

from curriculum.catalog import CatalogStore, Program

CORPORATE_AUDIENCE = "corporate"

DEFAULT_CORPORATE_PROGRAMS = [
    Program(
        program_id="corp-workplace-safety",
        title="Workplace Safety & OSHA",
        audience=CORPORATE_AUDIENCE,
        description=(
            "Required safety training for facilities and operations: OSHA "
            "general industry, fire prevention, forklifts, lab safety, and "
            "liquid-cooling / thermal materials handling."
        ),
        course_ids=[
            "osha-general-safety",
            "fire-safety-training",
            "osha-forklift-safety",
            "lab-safety-fundamentals",
            "liquid-cooling-thermal-materials",
        ],
    ),
    Program(
        program_id="corp-hr-compliance",
        title="HR & Workplace Conduct",
        audience=CORPORATE_AUDIENCE,
        description=(
            "People-risk essentials: sexual harassment prevention, workplace "
            "violence, ethics, anti-bribery, DEI, and social media at work."
        ),
        course_ids=[
            "sexual-harassment-prevention",
            "workplace-violence-prevention",
            "workplace-ethics",
            "anti-bribery-corruption",
            "diversity-equity-inclusion",
            "social-media-at-work",
        ],
    ),
    Program(
        program_id="corp-privacy-security",
        title="Privacy, Security & Data Protection",
        audience=CORPORATE_AUDIENCE,
        description=(
            "Protect people and information: HIPAA, workplace data privacy, "
            "cybersecurity fundamentals, and day-to-day security policies."
        ),
        course_ids=[
            "hipaa-privacy-security",
            "data-privacy-workplace",
            "cybersecurity",
            "security-policies-awareness",
            "security-guard-certification",
        ],
    ),
    Program(
        program_id="corp-food-health",
        title="Food Handler Certification",
        audience=CORPORATE_AUDIENCE,
        description=(
            "ServSafe-aligned food safety for hospitality and cafeteria teams: "
            "hazards, temperatures, hygiene, and cross-contamination control."
        ),
        course_ids=["food-handler-safety"],
    ),
    Program(
        program_id="corp-trade-export",
        title="Trade Compliance & Export Control",
        audience=CORPORATE_AUDIENCE,
        description=(
            "Cross-border risk for product, sales, and logistics teams: trade "
            "compliance essentials and US EAR/ITAR export-control awareness."
        ),
        course_ids=[
            "trade-compliance-basics",
            "export-control-us-regulations",
        ],
    ),
    Program(
        program_id="corp-automotive-safety",
        title="Automotive Safety & ASE",
        audience=CORPORATE_AUDIENCE,
        description=(
            "Shop and fleet safety awareness plus ASE certification prep for "
            "automotive service teams."
        ),
        course_ids=[
            "automotive-safety-awareness",
            "ase-automotive-certification",
        ],
    ),
    Program(
        program_id="corp-ai-fluency",
        title="AI Fluency for Teams",
        audience=CORPORATE_AUDIENCE,
        description=(
            "Everyday AI confidence for every employee: practical GenAI "
            "skills, responsible use, and productivity workflows."
        ),
        course_ids=["ai-fluency-essentials", "ai-powered-productivity"],
    ),
    Program(
        program_id="corp-ai-engineering",
        title="AI Engineering Upskilling",
        audience=CORPORATE_AUDIENCE,
        description=(
            "From builder to shipping AI products: solution design, product "
            "engineering, DevOps practice, and core software craft."
        ),
        course_ids=[
            "ai-solutions-builder",
            "ai-product-engineering",
            "devops-engineering-upskiller",
            "java-software-engineering",
        ],
    ),
    Program(
        program_id="corp-data-decisions",
        title="Data & Decisions",
        audience=CORPORATE_AUDIENCE,
        description=(
            "Turn data into business outcomes: applied data engineering, "
            "analytics for decision makers, and a hands-on data fellowship."
        ),
        course_ids=[
            "applied-data-engineering",
            "data-insights-business-decisions",
            "data-fellowship",
        ],
    ),
    Program(
        program_id="corp-ai-leadership",
        title="AI Leadership",
        audience=CORPORATE_AUDIENCE,
        description=(
            "For leaders driving adoption: architect the AI transformation "
            "and go deep through the AI & ML fellowship."
        ),
        course_ids=["ai-transformation-architect", "ai-ml-fellowship"],
    ),
]


def seeding_enabled() -> bool:
    return os.environ.get("SEED_CORPORATE_PROGRAMS", "1").lower() in ("1", "true", "yes")


def seed_default_programs(store: CatalogStore) -> int:
    """Idempotently seed the default corporate programs.

    No-ops when the store already has any programs (operator-authored
    catalogs, or a persisted CATALOG_PATH from a prior run, win).
    Returns the number of programs created.
    """
    if store.list_programs():
        return 0
    created = 0
    for program in DEFAULT_CORPORATE_PROGRAMS:
        store.create_program(program.model_copy(deep=True))
        created += 1
    return created
