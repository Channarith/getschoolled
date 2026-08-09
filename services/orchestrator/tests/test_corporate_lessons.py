"""Corporate lesson contract for the /corporate web funnel (CD-B5..B6).

apps/web/app/corporate/page.tsx filters /api/lessons on audience ==
"corporate" and groups by track. Pin that contract and the corporate
lesson ids so a sample-curriculum regression fails loudly before an
investor demo, not on stage.
"""

from fastapi.testclient import TestClient
from orchestrator.main import app

client = TestClient(app)

EXPECTED_CORPORATE_LESSONS = {
    # AI / Data / Engineering upskilling
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
    # Workplace compliance & safety
    "sexual-harassment-prevention": "Compliance",
    "workplace-ethics": "Compliance",
    "diversity-equity-inclusion": "Compliance",
    "workplace-violence-prevention": "Compliance",
    "social-media-at-work": "Compliance",
    "anti-bribery-corruption": "Compliance",
    "fire-safety-training": "Safety",
    "osha-general-safety": "Safety",
    "osha-forklift-safety": "Safety",
    "food-handler-safety": "Safety",
    "ca-alameda-food-handler-hygiene": "Safety",
    "lab-safety-fundamentals": "Safety",
    "liquid-cooling-thermal-materials": "Safety",
    "hipaa-privacy-security": "Privacy",
    "data-privacy-workplace": "Privacy",
    "cybersecurity": "Privacy",
    "security-policies-awareness": "Privacy",
    "security-guard-certification": "Privacy",
    "trade-compliance-basics": "Trade",
    "export-control-us-regulations": "Trade",
    "ase-automotive-certification": "Automotive",
    "automotive-safety-awareness": "Automotive",
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


def test_compliance_topics_are_corporate():
    corporate = {r["lesson_id"] for r in _lessons() if r.get("audience") == "corporate"}
    for lesson_id in (
        "sexual-harassment-prevention",
        "fire-safety-training",
        "osha-general-safety",
        "food-handler-safety",
        "ca-alameda-food-handler-hygiene",
        "workplace-violence-prevention",
        "security-policies-awareness",
        "trade-compliance-basics",
        "social-media-at-work",
        "export-control-us-regulations",
        "liquid-cooling-thermal-materials",
        "data-privacy-workplace",
        "anti-bribery-corruption",
        "lab-safety-fundamentals",
        "automotive-safety-awareness",
    ):
        assert lesson_id in corporate, lesson_id
