"""Jobs <-> skills <-> courses matching."""

import pytest

from aoep_shared.jobs import (
    SAMPLE_JOBS,
    AdzunaJobsProvider,
    ArbeitnowJobsProvider,
    CompositeJobsProvider,
    JSearchJobsProvider,
    LinkedInJobsProvider,
    MockJobsProvider,
    RemotiveJobsProvider,
    filter_jobs_by_location,
    get_job,
    get_jobs_provider,
    jobs_for_course,
    location_matches,
    match_courses_to_job,
)

# A small fake catalog with skill-bearing tags.
COURSES = [
    {"course_id": "c-py", "title": "Python Programming Bootcamp", "subject": "technology",
     "category": "Technology", "tags": ["python", "coding"]},
    {"course_id": "c-sql", "title": "SQL for Data Analysis", "subject": "data",
     "category": "Data", "tags": ["sql", "data", "analytics"]},
    {"course_id": "c-stats", "title": "Statistics Essentials", "subject": "math",
     "category": "Mathematics", "tags": ["statistics", "probability"]},
    {"course_id": "c-cloud", "title": "Cloud & DevOps Foundations", "subject": "technology",
     "category": "Technology", "tags": ["cloud", "devops", "linux"]},
    {"course_id": "c-es", "title": "Spanish: Essential phrases", "subject": "spanish",
     "category": "Languages", "tags": ["spanish", "language"]},
    {"course_id": "c-cook", "title": "Italian Cooking", "subject": "culinary",
     "category": "Culinary", "tags": ["pasta"]},
]


def test_provider_defaults_to_mock_and_keyed_to_linkedin():
    assert isinstance(get_jobs_provider({}), MockJobsProvider)
    assert isinstance(get_jobs_provider({"LINKEDIN_API_KEY": "x"}), LinkedInJobsProvider)


def test_mock_search_filters_by_query_and_location():
    p = MockJobsProvider()
    assert any(j.title == "Data Analyst" for j in p.search(query="data"))
    assert all("miami" in j.location.lower() for j in p.search(location="Miami"))


def test_match_data_analyst_to_courses_with_coverage_and_path():
    job = get_job("job-data")  # skills: sql, excel, data-analysis, statistics
    m = match_courses_to_job(job, COURSES)
    ids = {c.course_id for c in m.matched_courses}
    assert "c-sql" in ids and "c-stats" in ids
    assert "c-cook" not in ids                 # irrelevant course excluded
    assert "sql" in m.covered and "statistics" in m.covered
    assert "excel" in m.missing                # no excel course -> gap
    assert 0 < m.coverage_pct < 100
    assert m.recommended_path                   # a learning path is suggested


def test_full_coverage_reaches_100():
    job = get_job("job-cloud")  # cloud, devops, linux, python
    m = match_courses_to_job(job, COURSES)
    assert m.coverage_pct == 100 and not m.missing


def test_jobs_for_course_reverse_lookup():
    py = next(c for c in COURSES if c["course_id"] == "c-py")
    rel = jobs_for_course(py, SAMPLE_JOBS)
    titles = {r["job"].title for r in rel}
    assert "Junior Software Engineer" in titles  # python role
    assert all(r["relevant_skills"] for r in rel)


def test_real_provider_needs_network():
    with pytest.raises(NotImplementedError):
        LinkedInJobsProvider("k").search(query="python")


def test_unknown_job_none():
    assert get_job("nope") is None


# --------------------------------------------------------------------------- #
# Live providers: parse real-shaped payloads (no network) + offline fallback +
# env-based selection.
# --------------------------------------------------------------------------- #
def test_remotive_parses_real_shaped_payload():
    rows = [{
        "id": 123, "url": "https://remotive.com/remote-jobs/123",
        "title": "Senior Python Engineer", "company_name": "Acme Remote",
        "candidate_required_location": "Worldwide", "salary": "$120k-$150k",
        "job_type": "full_time", "category": "Software Development",
        "tags": ["python", "sql", "aws"],
        "description": "<p>Build APIs in <b>Python</b> with SQL and AWS.</p>",
        "publication_date": "2026-06-20T00:00:00",
    }]
    [job] = RemotiveJobsProvider()._parse(rows)
    assert job.id == "remotive-123"
    assert job.title == "Senior Python Engineer" and job.company == "Acme Remote"
    assert job.source == "remotive"
    assert job.url == "https://remotive.com/remote-jobs/123"
    assert "<" not in job.description           # HTML stripped
    assert "python" in job.skills and "sql" in job.skills   # skills derived
    assert job.category == "Engineering"


def test_jsearch_parses_and_labels_publisher_source():
    rows = [{
        "job_id": "abc", "job_title": "Data Analyst", "employer_name": "Globex",
        "job_city": "Austin", "job_country": "US", "job_publisher": "LinkedIn",
        "job_apply_link": "https://www.linkedin.com/jobs/view/abc",
        "job_employment_type": "FULLTIME", "job_min_salary": 70000, "job_max_salary": 95000,
        "job_description": "Analyze data with SQL and Excel.",
        "job_posted_at_timestamp": 1781990000,
    }]
    [job] = JSearchJobsProvider("k")._parse(rows)
    assert job.id == "jsearch-abc"
    assert job.source == "linkedin"            # carries the real publisher
    assert "linkedin.com" in job.url
    assert job.salary_range == "$70k-$95k"
    assert "sql" in job.skills


def test_arbeitnow_and_adzuna_parse():
    [a] = ArbeitnowJobsProvider()._parse([{
        "slug": "x1", "title": "Frontend Developer", "company_name": "Berlin Co",
        "description": "React and JavaScript.", "remote": True, "url": "https://arbeitnow.com/x1",
        "tags": ["javascript"], "job_types": ["full_time"], "created_at": 1781990000}])
    assert a.id == "arbeitnow-x1" and a.source == "arbeitnow" and a.location

    [d] = AdzunaJobsProvider("id", "key")._parse([{
        "id": "9", "title": "DevOps Engineer", "company": {"display_name": "Cloud Inc"},
        "location": {"display_name": "Remote"}, "salary_min": 120000, "salary_max": 150000,
        "redirect_url": "https://adzuna.com/9", "created": "2026-06-18T00:00:00",
        "category": {"label": "IT Jobs"}, "description": "Run cloud infra."}])
    assert d.id == "adzuna-9" and d.salary_range == "$120k-$150k"


def test_live_provider_falls_back_to_sample_offline(monkeypatch):
    p = RemotiveJobsProvider()
    monkeypatch.setattr(p, "_fetch", lambda *a, **k: (_ for _ in ()).throw(OSError("blocked")))
    rows = p.search(limit=5)
    assert len(rows) >= 5                       # served the curated board
    assert p.source == "sample"                 # and reported as sample, not remotive


def test_live_provider_caches_for_get_job(monkeypatch):
    p = RemotiveJobsProvider()
    monkeypatch.setattr(p, "_fetch", lambda *a, **k: [{
        "id": 777, "url": "u", "title": "ML Engineer", "company_name": "C",
        "tags": ["python"], "description": "ML in python", "publication_date": ""}])
    rows = p.search(limit=5)
    assert rows and rows[0].source == "remotive"
    assert get_job("remotive-777") is not None  # resolvable by /jobs/{id}


def test_composite_merges_dedups_and_falls_back():
    class _Fake(MockJobsProvider):
        source = "remotive"
        def __init__(self, jobs): self._jobs = jobs
        def search(self, *, query="", location="", limit=50): return self._jobs

    j = SAMPLE_JOBS[0]
    comp = CompositeJobsProvider([_Fake([j]), _Fake([j])])  # same job twice
    out = comp.search(limit=10)
    assert len([x for x in out if x.id == j.id]) == 1        # de-duplicated

    empty = CompositeJobsProvider([])
    assert len(empty.search(limit=5)) >= 5                   # falls back to sample
    assert empty.source == "sample"


def test_get_jobs_provider_selection():
    assert isinstance(get_jobs_provider({}), MockJobsProvider)
    assert isinstance(get_jobs_provider({"JOBS_LIVE": "1"}), CompositeJobsProvider)
    assert isinstance(get_jobs_provider({"JOBS_PROVIDER": "remotive"}), RemotiveJobsProvider)
    assert isinstance(get_jobs_provider({"JOBS_PROVIDER": "arbeitnow"}), ArbeitnowJobsProvider)
    assert isinstance(get_jobs_provider({"RAPIDAPI_KEY": "k"}), JSearchJobsProvider)
    assert isinstance(
        get_jobs_provider({"ADZUNA_APP_ID": "a", "ADZUNA_APP_KEY": "b"}), AdzunaJobsProvider)
    # keyed aggregator wins over the generic live flag
    assert isinstance(
        get_jobs_provider({"JOBS_LIVE": "1", "RAPIDAPI_KEY": "k"}), JSearchJobsProvider)


def test_location_matches_usa_filters_brazil():
    assert location_matches("usa", "Remote (US)")
    assert location_matches("us", "Austin, TX")
    assert not location_matches("usa", "São Paulo, Brazil")
    assert not location_matches("usa", "Florianópolis, Brazil")
    filtered = filter_jobs_by_location(SAMPLE_JOBS, "usa")
    assert all(location_matches("usa", j.location) for j in filtered)
