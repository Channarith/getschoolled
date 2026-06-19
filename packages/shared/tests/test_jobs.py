"""Jobs <-> skills <-> courses matching."""

import pytest

from aoep_shared.jobs import (
    SAMPLE_JOBS,
    LinkedInJobsProvider,
    MockJobsProvider,
    get_job,
    get_jobs_provider,
    jobs_for_course,
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
