"""Walter Lewin pedagogical tactics."""

from aoep_shared.harvest import extract_text, generate_course
from aoep_shared.harvest.lewin_pedagogy import (
    LEWIN_REFERENCE_URL,
    analyze_lewin_lecture,
    apply_lewin_tactic,
    lewin_demo_slide,
    lewin_opening,
)
from aoep_shared.meeting.presentation_matrix import PresentationProfile, resolve_mode_index


def test_lewin_tactic_catalog():
    tactics = analyze_lewin_lecture()
    assert len(tactics) >= 8
    assert tactics[0]["reference"] == LEWIN_REFERENCE_URL
    assert "predict_before_reveal" in {t["id"] for t in tactics}


def test_lewin_opening_is_theatrical():
    body = lewin_opening("Physics", ["Blue sky", "Red sunsets"])
    assert "story" in body.lower() or "foundation" in body.lower()
    assert "Blue sky" in body


def test_lewin_demo_slide_has_predict_and_data():
    title, body, narr = lewin_demo_slide("Light and color", subject="physics")
    assert "PREDICT" in body
    assert "Rayleigh" in body or "scatters" in body.lower()
    assert "predict" in narr.lower()
    assert apply_lewin_tactic("predict_before_reveal")


def test_lewin_preset_profile():
    p = PresentationProfile.resolve("lewin")
    assert p.arc == "lewin"
    assert p.socratic_prompts is True
    assert p.aggressive_time_skip is False


def test_generate_course_with_lewin_arc():
    text = (
        "Introduction\nWhy is the sky blue?\n\n"
        "Rayleigh scattering\nShorter wavelengths scatter more in air.\n\n"
        "Summary\nSunsets look red when the path through air is long.\n"
    )
    course = generate_course(
        extract_text(text, default_title="For the Love of Physics"),
        subject="physics",
        presentation_mode="lewin",
    )
    assert any(s.category == "demo" for s in course.slides)
    assert any("PREDICT" in s.body for s in course.slides)
    demo = [s for s in course.slides if s.category == "demo"][0]
    assert "blue" in demo.body.lower() or "Rayleigh" in demo.body


def test_lewin_mode_index_in_catalog():
    idx = resolve_mode_index("lewin")
    arc, voice, time_p, engage, media = __import__(
        "aoep_shared.meeting.presentation_matrix", fromlist=["decode_presentation_mode"],
    ).decode_presentation_mode(idx)
    assert arc == "lewin"
