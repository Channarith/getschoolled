"""End-of-class survey store + multi-dimensional data-mining rollups."""

import pytest

from aoep_shared.survey import (
    SurveyResponse,
    SurveyStore,
    mine_suggestions,
    template,
)


def test_template_has_required_overall_rating():
    t = template()
    overall = next(q for q in t["questions"] if q["id"] == "overall")
    assert overall["type"] == "rating" and overall["required"] is True


def test_submit_validates_rating_range():
    s = SurveyStore()
    with pytest.raises(ValueError):
        s.submit(SurveyResponse(course_id="c1", overall=6))
    s.submit(SurveyResponse(course_id="c1", overall=5))
    assert s.count() == 1


def test_course_summary_metrics():
    s = SurveyStore()
    for o in (5, 5, 4, 2):
        s.submit(SurveyResponse(course_id="bio", overall=o,
                                would_recommend=(o >= 4)))
    summ = s.course_summary("bio")
    assert summ["responses"] == 4
    assert summ["avg_overall"] == 4.0
    # promoters(3: o>=4) - detractors(1: o<=2) = 2 / 4 -> 50.0
    assert summ["nps_like"] == 50.0
    assert summ["recommend_rate"] == 75.0


def test_suggestion_mining_ranks_themes_ignoring_stopwords():
    themes = mine_suggestions([
        "more examples please", "more examples and more practice",
        "examples were great",
    ])
    terms = [t["term"] for t in themes]
    assert "examples" in terms
    assert "the" not in terms and "more" not in terms  # stopwords removed
    top = themes[0]
    assert top["term"] == "examples" and top["count"] == 3


def test_datamart_is_multidimensional():
    s = SurveyStore()
    s.submit(SurveyResponse(course_id="bio", class_type="live", overall=5))
    s.submit(SurveyResponse(course_id="bio", class_type="live", overall=4))
    s.submit(SurveyResponse(course_id="bio", class_type="self_paced", overall=2,
                            suggestion="too fast slow down"))
    s.submit(SurveyResponse(course_id="math", class_type="live", overall=3))
    mart = s.datamart()
    assert mart["total_responses"] == 4
    assert mart["dimensions"]["course"]["bio"] == 3
    assert mart["dimensions"]["class_type"]["live"] == 3
    assert set(mart["dimensions"]["rating_bucket"]) <= {"promoter", "passive", "detractor"}
    # A specific cube cell exists: bio / live / promoter with 2 responses avg 4.5
    cell = next(c for c in mart["cells"]
                if c["course_id"] == "bio" and c["class_type"] == "live"
                and c["rating_bucket"] == "promoter")
    assert cell["responses"] == 2 and cell["avg_overall"] == 4.5
    assert any(t["term"] == "fast" for t in mart["top_suggestions"])


def test_empty_course_summary():
    s = SurveyStore()
    assert s.course_summary("nope")["responses"] == 0
