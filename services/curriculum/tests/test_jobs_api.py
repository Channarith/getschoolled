"""Jobs <-> courses matching endpoints."""

from curriculum.catalog import CatalogStore
from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _seed():
    app.state.catalog = CatalogStore()
    mk = lambda **k: client.post("/courses", json=k).json()["course_id"]  # noqa: E731
    return {
        "py": mk(title="Python Programming Bootcamp", category="Technology",
                 tags=["python", "coding"]),
        "sql": mk(title="SQL for Data Analysis", category="Data",
                  tags=["sql", "data", "analytics"]),
        "stats": mk(title="Statistics Essentials", category="Mathematics",
                    tags=["statistics"]),
        "cloud": mk(title="Cloud & DevOps Foundations", category="Technology",
                    tags=["cloud", "devops", "linux"]),
    }


def test_jobs_list():
    _seed()
    body = client.get("/jobs").json()
    assert body["count"] >= 5
    assert any(j["title"] == "Data Analyst" for j in body["jobs"])
    # each posting names its source (linkedin/indeed/sample)
    assert all("source" in j for j in body["jobs"])


def test_jobs_search_filter():
    _seed()
    body = client.get("/jobs", params={"q": "cloud"}).json()
    assert any("Cloud" in j["title"] for j in body["jobs"])


def test_job_detail_matches_courses_with_coverage():
    ids = _seed()
    m = client.get("/jobs/job-data").json()  # sql, excel, data-analysis, statistics
    matched_ids = {c["course_id"] for c in m["matched_courses"]}
    assert ids["sql"] in matched_ids and ids["stats"] in matched_ids
    assert "excel" in m["missing"]           # gap surfaced (no Excel course)
    assert 0 < m["coverage_pct"] < 100
    assert m["recommended_path"]


def test_job_full_coverage():
    _seed()
    m = client.get("/jobs/job-cloud").json()  # cloud, devops, linux, python
    assert m["coverage_pct"] == 100 and not m["missing"]


def test_course_related_jobs():
    ids = _seed()
    body = client.get(f"/courses/{ids['py']}/jobs").json()
    titles = {j["job"]["title"] for j in body["jobs"]}
    assert "Junior Software Engineer" in titles


def test_unknown_job_404():
    _seed()
    assert client.get("/jobs/nope").status_code == 404


def test_jobs_live_mode_falls_back_gracefully(monkeypatch):
    """With JOBS_LIVE=1 but no egress (as in CI), /jobs must still return a
    populated board rather than erroring."""
    _seed()
    monkeypatch.setenv("JOBS_LIVE", "1")
    # Force the live HTTP fetch to fail (simulates blocked egress).
    import aoep_shared.jobs as jobs_mod
    monkeypatch.setattr(jobs_mod, "_http_get_json",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("blocked")))
    body = client.get("/jobs").json()
    assert body["count"] >= 5
    assert body["source"] == "sample"
