"""Pedagogy + section normalization for teachable harvest output."""

from aoep_shared.harvest import extract_text, generate_course, normalize_document
from aoep_shared.harvest.section_normalize import is_junk_section, merge_learning_units


def test_filters_chapter_notes_junk():
    assert is_junk_section("Chapter notes . . .", "2Fundamentals of prediction 11")
    assert is_junk_section("Optimization", "Optimization basics . . . . Gradient descent . . . . iv")
    assert not is_junk_section(
        "Linear equations",
        "A linear equation has one variable raised to the first power only and can be graphed as a straight line.",
    )


def test_merge_learning_units_combines_same_heading_stubs():
    sections = [
        ("Intro", "Short bit that is still long enough to pass junk filter here."),
        ("Intro", "More intro content that continues the same section with extra detail."),
        ("Variables", "Variables represent unknown values in algebra and appear in expressions."),
        ("Equations", "An equation states that two expressions are equal and can be solved."),
    ]
    merged = merge_learning_units(sections)
    assert len(merged) == 3
    assert merged[0][0] == "Intro"
    assert "More intro" in merged[0][1]


def test_generate_builds_teaching_deck_not_one_liners():
    text = (
        "Introduction\nWelcome to algebra; we cover the core objectives for solving equations.\n\n"
        "Example 1\nA worked example solving for x step by step with substitution.\n\n"
        "Exercise\nPractice: solve the equation yourself using the same method.\n\n"
        "Summary\nIn summary, algebra helps us find unknown values systematically.\n"
    )
    doc = normalize_document(extract_text(text, default_title="Algebra"))
    course = generate_course(doc, subject="mathematics")
    assert len(course.slides) >= 8  # opener + concepts + try-its + recap + close
    assert any("Welcome" in s.title for s in course.slides)
    assert any(s.category == "exercise" for s in course.slides)
    assert any("Key idea:" in s.body or "Takeaway:" in s.body or "Practice:" in s.body
               for s in course.slides)
    assert all(len(s.narration) > len(s.body) * 0.5 for s in course.slides[:5])
