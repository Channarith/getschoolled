"""JSON/meta course tagging: pricing, job-linked, career, core-fundamental."""

from aoep_shared.harvest import CourseTags


def test_free_vs_expensive():
    free = CourseTags()
    assert free.is_free and not free.is_expensive
    assert "free" in free.label_list()

    pricey = CourseTags(access_tier="expensive", price_usd=499.0)
    assert pricey.access_tier == "premium"  # "expensive" normalizes to premium
    assert pricey.is_expensive and not pricey.is_free
    assert "expensive" in pricey.label_list()


def test_job_and_career_tags():
    tags = CourseTags(career_path="nurse", linkedin_job_id="li-12345",
                      audiences=["nurse"])
    labels = tags.label_list()
    assert "career:nurse" in labels
    assert "job:li-12345" in labels
    assert tags.is_job_linked and tags.is_career_course
    d = tags.to_dict()
    assert d["flags"]["career_course"] is True
    assert d["flags"]["job_linked"] is True


def test_core_fundamental_and_catalog_fields():
    tags = CourseTags(core_fundamental=True, labels=["algebra"])
    assert "core-fundamental" in tags.label_list()
    cf = tags.catalog_fields()
    assert cf["core_skill"] is True
    assert "algebra" in cf["tags"]


def test_roundtrip():
    tags = CourseTags(access_tier="pro", price_usd=29.0, career_path="data-analyst",
                      meta={"provider": "oer"})
    again = CourseTags.from_dict(tags.to_dict())
    assert again.access_tier == "pro"
    assert again.career_path == "data-analyst"
    assert again.meta["provider"] == "oer"
