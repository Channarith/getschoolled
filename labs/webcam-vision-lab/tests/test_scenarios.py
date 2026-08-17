"""Scenario fixture smoke tests."""

from webcam_vision_lab.scenarios import GROUP_CLASS_SCENARIO, SELF_TEACH_SCENARIO, SOLO_CLASS_SCENARIO
from webcam_vision_lab.scenarios.group_class import group_theodore_instructions
from webcam_vision_lab.scenarios.self_teach import self_teach_instructions
from webcam_vision_lab.scenarios.solo_class import solo_theodore_instructions
from webcam_vision_lab.voice.theodore import TheodoreMode


def test_scenario_modes():
    assert SOLO_CLASS_SCENARIO.mode == TheodoreMode.SOLO_THEODORE
    assert GROUP_CLASS_SCENARIO.is_group
    assert not SELF_TEACH_SCENARIO.is_group
    assert SELF_TEACH_SCENARIO.presence_policy.require_liveness is False


def test_instructions_include_lesson_context():
    solo = solo_theodore_instructions()
    assert "Theodore" in solo
    assert SOLO_CLASS_SCENARIO.lesson_title in solo
    group = group_theodore_instructions()
    assert "group" in group.lower() or "learners" in group.lower()
    self_t = self_teach_instructions()
    assert "coach" in self_t.lower() or "guiding" in self_t.lower()
