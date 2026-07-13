"""Default corporate program seeding (CD-B1..B4, CD-B7).

The /corporate page's Programs section is populated by startup seeding
(corporate_programs.seed_default_programs). These tests pin that behaviour
so the investor-demo funnel cannot silently regress to an empty state.
"""

import os

from curriculum.catalog import CatalogStore, Program
from curriculum.corporate_programs import (
    CORPORATE_AUDIENCE,
    DEFAULT_CORPORATE_PROGRAMS,
    seed_default_programs,
    seeding_enabled,
)
from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Lesson ids in sample-curriculum tagged AUDIENCE: corporate. The web
# programme cards resolve program course_ids against these lessons.
EXPECTED_CORPORATE_LESSON_IDS = {
    "ai-fluency-essentials",
    "ai-powered-productivity",
    "ai-solutions-builder",
    "ai-product-engineering",
    "ai-ml-fellowship",
    "ai-transformation-architect",
    "applied-data-engineering",
    "data-insights-business-decisions",
    "data-fellowship",
    "devops-engineering-upskiller",
    "java-software-engineering",
}


def _repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", ".."))


def test_seed_populates_empty_store():  # CD-B1
    store = CatalogStore()
    created = seed_default_programs(store)
    assert created == len(DEFAULT_CORPORATE_PROGRAMS) > 0
    programs = store.list_programs()
    assert {p.audience for p in programs} == {CORPORATE_AUDIENCE}
    assert all(p.title and p.description and p.course_ids for p in programs)


def test_seed_is_idempotent():  # CD-B2
    store = CatalogStore()
    assert seed_default_programs(store) > 0
    before = {p.program_id for p in store.list_programs()}
    assert seed_default_programs(store) == 0
    assert {p.program_id for p in store.list_programs()} == before


def test_seed_respects_existing_programs():  # CD-B2b
    store = CatalogStore()
    store.create_program(Program(title="Operator authored", audience="corporate"))
    assert seed_default_programs(store) == 0
    assert len(store.list_programs()) == 1


def test_programs_api_returns_seeded_corporate_tracks():  # CD-B3
    # Other suites swap app.state.catalog, so recreate the startup state
    # (fresh store + seeding) rather than relying on import-time seeding.
    app.state.catalog = CatalogStore()
    seed_default_programs(app.state.catalog)
    r = client.get("/programs", params={"audience": "corporate"})
    assert r.status_code == 200
    rows = r.json()
    got_ids = {p["program_id"] for p in rows}
    expected_ids = {p.program_id for p in DEFAULT_CORPORATE_PROGRAMS}
    assert expected_ids <= got_ids
    for p in rows:
        if p["program_id"] in expected_ids:
            assert p["course_ids"], p["program_id"]


def test_every_seeded_course_id_is_a_corporate_lesson():  # CD-B4
    # Programme cards join course_ids against corporate live lessons; a
    # typo'd id renders as a dead muted string on /corporate.
    seeded_ids = {cid for p in DEFAULT_CORPORATE_PROGRAMS for cid in p.course_ids}
    assert seeded_ids <= EXPECTED_CORPORATE_LESSON_IDS
    for cid in seeded_ids:
        lesson_txt = os.path.join(_repo_root(), "sample-curriculum", cid, "lesson.txt")
        assert os.path.isfile(lesson_txt), f"missing sample-curriculum for {cid}"


def test_seeded_course_ids_cover_all_corporate_lessons():  # CD-B4b
    seeded_ids = {cid for p in DEFAULT_CORPORATE_PROGRAMS for cid in p.course_ids}
    assert seeded_ids == EXPECTED_CORPORATE_LESSON_IDS


def test_seeded_lessons_resolve_via_courses_search():  # CD-B4c
    # The web page resolves titles through /courses/search (unified
    # learnable index); every seeded id must resolve to a searchable course.
    r = client.get("/courses/search", params={"limit": 500})
    assert r.status_code == 200
    by_id = {c["course_id"] for c in r.json()}
    seeded_ids = {cid for p in DEFAULT_CORPORATE_PROGRAMS for cid in p.course_ids}
    missing = seeded_ids - by_id
    assert not missing, f"seeded course_ids absent from /courses/search: {missing}"


def test_seeding_flag_disables(monkeypatch):  # CD-B7
    monkeypatch.setenv("SEED_CORPORATE_PROGRAMS", "0")
    assert seeding_enabled() is False
    monkeypatch.setenv("SEED_CORPORATE_PROGRAMS", "1")
    assert seeding_enabled() is True
