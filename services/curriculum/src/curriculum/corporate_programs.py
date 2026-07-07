"""Default corporate training programs.

The in-memory CatalogStore starts with no programs, so the /corporate page's
"Programs" section renders empty out of the box (the same gap the audio
catalog bridge fills for courses). Seed a small set of curated corporate
tracks at startup so the corporate funnel is populated without an operator
having to POST /programs by hand.

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
