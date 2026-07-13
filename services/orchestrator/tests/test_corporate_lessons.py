"""Corporate lesson contract for the /corporate web funnel (CD-B5..B6).

apps/web/app/corporate/page.tsx filters /api/lessons on audience ==
"corporate" and groups by track. Pin that contract and the exact set of
corporate lesson ids so a sample-curriculum regression fails loudly before
an investor demo, not on stage.
"""

from fastapi.testclient import TestClient
from orchestrator.main import app

client = TestClient(app)

EXPECTED_CORPORATE_LESSONS = {
    # lesson_id: track
    "ai-fluency-essentials": "AI",
    "ai-powered-productivity": "AI",
    "ai-solutions-builder": "AI",
    "ai-ml-fellowship": "AI",
    "ai-transformation-architect": "AI",
    "applied-data-engineering": "Data",
    "data-insights-business-decisions": "Data",
    "data-fellowship": "Data",
    "ai-product-engineering": "Engineering",
    "devops-engineering-upskiller": "Engineering",
    "java-software-engineering": "Engineering",
}


def _lessons() -> list[dict]:
    r = client.get("/api/lessons")
    assert r.status_code == 200
    return r.json()


def test_lessons_expose_audience_field():  # CD-B5
    rows = _lessons()
    assert rows
    assert all("audience" in row for row in rows)


def test_corporate_lesson_set_is_pinned():  # CD-B6
    corporate = {r["lesson_id"] for r in _lessons() if r.get("audience") == "corporate"}
    assert corporate == set(EXPECTED_CORPORATE_LESSONS)


def test_corporate_lessons_have_demo_ready_metadata():  # CD-B6b
    rows = {r["lesson_id"]: r for r in _lessons() if r.get("audience") == "corporate"}
    for lesson_id, track in EXPECTED_CORPORATE_LESSONS.items():
        row = rows[lesson_id]
        assert row.get("track") == track, lesson_id
        assert row.get("title"), lesson_id
        assert row.get("slides"), lesson_id
