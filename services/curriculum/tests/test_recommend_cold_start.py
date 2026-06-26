"""Cold-start and Foresight recommend service."""

from curriculum.catalog import CatalogStore, Course
from curriculum.recommend_service import (
    is_cold_start, run_recommend, starter_payload,
)
from aoep_shared.foresight import StudentProfile


def test_cold_start_new_profile_gets_starters():
    store = CatalogStore()
    store.create_course(Course(
        course_id="a", title="Algebra Basics", tags=["algebra"],
        level="beginner", popularity=10,
    ))
    store.create_course(Course(
        course_id="b", title="Advanced ML", tags=["ml"],
        level="advanced", popularity=100,
    ))
    profile = StudentProfile(student_id="new")
    out = run_recommend(profile, store.list_courses(), top_n=3)
    assert out["cold_start"] is True
    assert out["difficulty"] == "beginner"
    assert len(out["recommendations"]) >= 1
    assert out["recommendations"][0]["title"] == "Algebra Basics"


def test_cold_start_false_when_mastery_exists():
    profile = StudentProfile(student_id="s", mastery={"algebra": 0.8})
    assert is_cold_start(profile) is False


def test_empty_foresight_result_falls_back_to_starters():
    store = CatalogStore()
    store.create_course(Course(course_id="x", title="Starter", tags=["math"], popularity=1))
    profile = StudentProfile(student_id="s", mastery={"algebra": 0.9})
    out = run_recommend(profile, store.list_courses(), top_n=2)
    assert out["recommendations"]
