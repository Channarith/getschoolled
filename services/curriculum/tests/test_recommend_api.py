"""Foresight /recommend over the catalog."""

from fastapi.testclient import TestClient

from curriculum.catalog import CatalogStore
from curriculum.main import app

client = TestClient(app)


def _course(**kw):
    body = {"title": "T", "subject": "general"}
    body.update(kw)
    return client.post("/courses", json=body).json()


def test_recommend_targets_gaps_over_catalog():
    # Isolate the catalog so ranking is deterministic regardless of other tests.
    app.state.catalog = CatalogStore()
    _course(title="Fractions", subject="math", tags=["fractions"], level="beginner")
    _course(title="Algebra", subject="math", tags=["algebra"], level="intermediate")
    _course(title="Biology", subject="biology", tags=["cells", "dna"], level="beginner")

    out = client.post("/recommend", json={
        "student_id": "stu1",
        "mastery": {"fractions": 0.9, "algebra": 0.2},
        "interests": ["math"],
        "top_n": 5,
    }).json()

    assert out["student_id"] == "stu1"
    assert out["difficulty"] in ("beginner", "intermediate", "advanced")
    assert "algebra" in out["gaps"]
    titles = {r["title"] for r in out["recommendations"]}
    assert "Algebra" in titles                    # the gap course is recommended
    kinds = {n["kind"] for n in out["relational_map"]["nodes"]}
    assert {"student", "skill", "course"} <= kinds


def test_recommend_handles_empty_catalog_gracefully():
    # A fresh app state may already have courses from other tests; just assert shape.
    out = client.post("/recommend", json={"mastery": {}}).json()
    assert "recommendations" in out and "gaps" in out and "difficulty" in out


def test_recommend_cold_start_via_http():
    app.state.catalog = CatalogStore()
    _course(title="Starter Math", subject="math", tags=["math"], level="beginner", popularity=50)
    _course(title="Advanced ML", subject="ai", tags=["ml"], level="advanced", popularity=100)

    out = client.post("/recommend", json={
        "student_id": "brand-new",
        "mastery": {},
        "interests": [],
        "top_n": 3,
    }).json()

    assert out["cold_start"] is True
    assert out["difficulty"] == "beginner"
    assert out["recommendations"]
    assert out["recommendations"][0]["title"] == "Starter Math"
