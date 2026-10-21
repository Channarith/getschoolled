"""Learner-facing adaptation line."""

from aoep_shared.adaptation_line import adaptation_line, storyboard_style


def test_start_of_class_uses_the_survey_in_plain_language():
    line = adaptation_line(
        pacing="normal",
        difficulty="medium",
        survey_style="visual",
        declared_pace="moderate",
        attention=0.9,
    )
    assert line == {"key": "adapt.starting", "style": "visual", "pace": "moderate"}


def test_looked_away_outranks_other_changes():
    line = adaptation_line(
        pacing="fast",
        difficulty="easy",
        reteach=True,
        attention=0.2,
        survey_style="visual",
    )
    assert line["key"] == "adapt.lookedAway"


def test_reteach_before_an_easier_check():
    line = adaptation_line(pacing="slow", difficulty="easy", reteach=True, attention=0.8)
    assert line["key"] == "adapt.reteach"


def test_easy_difficulty_promises_an_easier_check():
    line = adaptation_line(difficulty="easy", attention=0.8)
    assert line["key"] == "adapt.easier"


def test_fast_pace_says_we_are_moving_ahead():
    line = adaptation_line(pacing="fast", difficulty="medium", attention=0.9)
    assert line["key"] == "adapt.movingAhead"


def test_live_emphasis_names_the_shift():
    line = adaptation_line(
        pacing="normal",
        difficulty="medium",
        survey_style="reading_writing",
        live_style="visual",
        attention=0.8,
    )
    assert line["key"] == "adapt.staysVisual"
    assert line["style"] == "reading"


def test_storyboard_style_maps_live_emphasis():
    assert storyboard_style("listening") == "auditory"
    assert storyboard_style("reading") == "reading_writing"
    assert storyboard_style("practice") == "hands_on"
    assert storyboard_style("") == ""
