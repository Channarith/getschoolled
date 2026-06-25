"""Narration voice style resolution."""

from aoep_shared.voice_profiles import (
    prosody_for_style,
    resolve_voice_style,
    suggest_voice_style_from_profile,
    voice_name_style_bonus,
)


def test_child_profile_suggests_child_voice():
    assert suggest_voice_style_from_profile({"age_band": "child"}) == "child"


def test_accessibility_suggests_accessible_voice():
    prof = {
        "age_band": "adult",
        "accessibility": {"needs_extra_time": True},
        "learning_pace": "moderate",
    }
    assert suggest_voice_style_from_profile(prof) == "accessible"


def test_auto_resolves_from_profile():
    assert resolve_voice_style("auto", {"age_band": "child"}) == "child"
    assert resolve_voice_style("calm", {"age_band": "child"}) == "calm"


def test_prosody_accessible_slower_than_standard():
    assert prosody_for_style("accessible").rate < prosody_for_style("standard").rate


def test_child_voice_name_bonus():
    assert voice_name_style_bonus("child", "Nicky (Enhanced)") > 0
