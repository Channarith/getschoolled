"""Course relevance/audience endpoints + job-description parsing."""

from curriculum.catalog import CatalogStore
from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _seed():
    app.state.catalog = CatalogStore()
    mk = lambda **k: client.post("/courses", json=k).json()["course_id"]  # noqa: E731
    return {
        "alg": mk(title="Algebra Foundations", category="Mathematics", subject="math", tags=["algebra"]),
        "phys": mk(title="Physics 101", category="Science", subject="science", tags=["physics"]),
        "anat": mk(title="Human Anatomy", category="Medical", subject="medical", tags=["anatomy", "body"]),
        "cloud": mk(title="Cloud & DevOps Foundations", category="Technology", tags=["cloud", "devops", "linux"]),
    }


def test_professions_catalog():
    body = client.get("/skills/professions").json()["professions"]
    slugs = {p["slug"] for p in body}
    assert {"engineer", "civil-engineer", "aerospace-engineer", "nurse", "chef", "accountant"} <= slugs


def test_course_relevance_algebra_for_chefs_accountants():
    ids = _seed()
    rel = client.get(f"/courses/{ids['alg']}/relevance").json()
    assert "chef" in rel["audiences"] and "accountant" in rel["audiences"]
    assert rel["core_skill"] is True
    assert any("Fundamental for Accountants" == t for t in rel["tags"])


def test_physics_relevance_for_engineers():
    ids = _seed()
    rel = client.get(f"/courses/{ids['phys']}/relevance").json()
    assert {"civil-engineer", "aerospace-engineer"} <= set(rel["audiences"])


def test_search_audience_and_core_skill_filters():
    _seed()
    nurses = client.get("/courses/search", params={"audience": "nurse"}).json()
    titles = {c["title"] for c in nurses}
    assert "Human Anatomy" in titles
    core = client.get("/courses/search", params={"core_skill": "true"}).json()
    assert any(c["title"] == "Algebra Foundations" for c in core)


def test_facets_include_audiences():
    _seed()
    f = client.get("/courses/facets").json()
    slugs = {a["slug"] for a in f["audiences"]}
    assert "nurse" in slugs or "chef" in slugs


def test_parse_job_description_endpoint_targets_cert_classes():
    ids = _seed()
    jd = ("Network/Cloud Engineer: Linux, Cisco UCS Manager (UCSM), CCNA, Python. "
          "AWS certified preferred. PMP a plus.")
    rec = client.post("/jobs/parse", json={"description": jd}).json()
    assert "Cisco UCS Manager (UCSM)" in rec["parsed"]["certifications"]
    titles = [s["title"] for s in rec["specialized_classes"]]
    assert any("UCSM" in t for t in titles)
    # Cloud course covers linux from the JD.
    assert any(m["course_id"] == ids["cloud"] for m in rec["matched_courses"])
