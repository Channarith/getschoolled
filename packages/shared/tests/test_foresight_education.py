"""Foresight education predictor: gaps, adaptation, recommendations, relations."""

from aoep_shared.foresight import CourseFeature, LearnerForesight, StudentProfile

SKILLS = ["fractions", "algebra", "geometry", "calculus", "cells", "dna"]

COURSES = [
    CourseFeature("c_frac", "Fractions 101", skills=["fractions"], level="beginner", category="math"),
    CourseFeature("c_alg", "Algebra", skills=["algebra"], prerequisites=["fractions"],
                  level="intermediate", category="math"),
    CourseFeature("c_calc", "Calculus", skills=["calculus"], prerequisites=["algebra"],
                  level="advanced", category="math"),
    CourseFeature("c_bio", "Biology", skills=["cells", "dna"], level="beginner", category="biology"),
]


def _lf():
    return LearnerForesight(SKILLS)


def test_gaps_identifies_weak_skills():
    p = StudentProfile("s1", mastery={"fractions": 0.9, "algebra": 0.2})
    gaps = _lf().mastery_gaps(p)
    assert "algebra" in gaps          # low mastery
    assert "calculus" in gaps         # unknown -> gap
    assert "fractions" not in gaps    # mastered


def test_adapt_difficulty():
    lf = _lf()
    assert lf.adapt_difficulty(StudentProfile("a", mastery={"x": 0.9, "y": 0.8})) == "advanced"
    assert lf.adapt_difficulty(StudentProfile("b", mastery={"x": 0.5})) == "intermediate"
    assert lf.adapt_difficulty(StudentProfile("c", mastery={"x": 0.1})) == "beginner"
    assert lf.adapt_difficulty(StudentProfile("d")) == "beginner"


def test_recommend_targets_gaps_and_respects_prereqs():
    # Mastered fractions; weak algebra -> Algebra is unlocked & recommended high.
    p = StudentProfile("s2", mastery={"fractions": 0.9, "algebra": 0.2})
    recs = _lf().recommend(p, COURSES)
    ids = [r.course_id for r in recs]
    assert "c_alg" in ids
    # Algebra (prereq met) ranks above Calculus (prereq NOT met) -> gating works.
    assert ids.index("c_alg") < ids.index("c_calc")
    # The Algebra recommendation explicitly targets the algebra gap.
    alg = next(r for r in recs if r.course_id == "c_alg")
    assert "algebra" in alg.covers_gaps


def test_recommend_skips_completed():
    p = StudentProfile("s3", mastery={"fractions": 0.1}, completed_course_ids=["c_frac"])
    recs = _lf().recommend(p, COURSES)
    assert "c_frac" not in [r.course_id for r in recs]


def test_relational_map_links_student_skills_courses():
    p = StudentProfile("s4", mastery={"algebra": 0.2})
    g = _lf().relational_map(p, COURSES)
    kinds = {n["kind"] for n in g["nodes"]}
    assert {"student", "skill", "course"} <= kinds
    assert any(e["rel"] == "needs" for e in g["edges"])
    assert any(e["rel"] == "teaches" for e in g["edges"])


def test_predict_bundle():
    p = StudentProfile("s5", mastery={"fractions": 0.9, "algebra": 0.3})
    out = _lf().predict(p, COURSES)
    assert out["difficulty"] in ("beginner", "intermediate", "advanced")
    assert "recommendations" in out and "gaps" in out and "relational_map" in out
