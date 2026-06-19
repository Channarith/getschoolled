"""Course relevance taxonomy + job-description parsing."""

from aoep_shared.jobs import parse_job_description, recommend_from_description
from aoep_shared.skills_taxonomy import (
    PROFESSIONS,
    course_relevance,
    professions_catalog,
)


def _course(title, tags, subject="", category=""):
    return {"course_id": "c", "title": title, "tags": tags, "subject": subject, "category": category}


def test_algebra_is_good_for_chefs_and_accountants():
    rel = course_relevance(_course("Algebra Foundations", ["algebra"], "math", "Mathematics"))
    assert "chef" in rel["audiences"]
    assert "accountant" in rel["audiences"]
    assert "accountant" in rel["fundamental_for"]   # fundamental for accountants
    assert rel["core_skill"] is True                 # algebra is a core skill
    assert "Fundamental for Accountants" in rel["tags"]
    assert "For Chefs" in rel["tags"]


def test_calculus_is_fundamental_for_engineers():
    rel = course_relevance(_course("Calculus I", ["calculus"], "math"))
    assert "engineer" in rel["fundamental_for"]
    assert "aerospace-engineer" in rel["fundamental_for"]


def test_physics_targets_civil_and_aerospace_engineers():
    rel = course_relevance(_course("Physics 101", ["physics"], "science"))
    assert {"civil-engineer", "aerospace-engineer"} <= set(rel["audiences"])
    labels = rel["audience_labels"]
    assert any("Aerospace" in x for x in labels)


def test_anatomy_for_nurses():
    rel = course_relevance(_course("Human Anatomy", ["anatomy", "body"], "medical", "Medical"))
    assert "nurse" in rel["audiences"] and "nurse" in rel["fundamental_for"]


def test_explicit_audience_field_is_honored():
    rel = course_relevance(_course("Welding Basics", ["welding"], audiences=["engineer"])
                           if False else
                           {"course_id": "c", "title": "Welding Basics", "tags": ["welding"],
                            "audiences": ["engineer"]})
    assert "engineer" in rel["audiences"]


def test_professions_catalog_lists_feeds():
    cat = professions_catalog()
    assert len(cat) == len(PROFESSIONS)
    eng = next(c for c in cat if c["slug"] == "civil-engineer")
    assert "physics" in eng["subjects"]


def test_parse_job_description_finds_skills_and_certs():
    jd = ("We're hiring a Network Engineer. Must have CCNA; experience with Cisco UCS "
          "Manager (UCSM), networking, TCP/IP, Python and Linux. AWS certified a plus.")
    parsed = parse_job_description(jd)
    assert "Cisco UCS Manager (UCSM)" in parsed["certifications"]
    assert "Cisco CCNA" in parsed["certifications"]
    assert "AWS Certified Solutions Architect" in parsed["certifications"]
    assert "networking" in parsed["skills"] and "python" in parsed["skills"]
    assert "network-engineer" in parsed["professions"]


def test_recommend_from_description_suggests_cert_classes():
    courses = [_course("Cloud & DevOps Foundations", ["cloud", "devops", "linux"], "tech")]
    courses[0]["course_id"] = "c-cloud"
    jd = "Cloud Engineer needing Linux, Cisco UCS Manager (UCSM) and PMP certification."
    rec = recommend_from_description(jd, courses)
    titles = [s["title"] for s in rec["specialized_classes"]]
    assert any("UCSM" in t for t in titles)        # targeted cert class surfaced
    assert any("Certification Prep" in t for t in titles)
    # The Cloud course covers linux.
    assert any(m["course_id"] == "c-cloud" for m in rec["matched_courses"])
