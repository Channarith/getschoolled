"""Group class with Theodore host — multi-face policy + Q&A floor."""

from __future__ import annotations

from webcam_vision_lab.presence.absence import AbsencePolicy
from webcam_vision_lab.scenarios.solo_class import ClassScenario
from webcam_vision_lab.voice.theodore import TheodoreMode, build_theodore_instructions

GROUP_CLASS_SCENARIO = ClassScenario(
    name="group_theodore_host",
    mode=TheodoreMode.GROUP_THEODORE,
    presence_policy=AbsencePolicy(
        enabled=True,
        grace_seconds=90,
        stale_seconds=20,
        require_liveness=True,
        max_faces_allowed=1,
    ),
    lesson_title="World History: The Silk Road",
    slide_title="Trade routes across Asia",
    room_id_prefix="gc-",
    is_group=True,
)


def group_theodore_instructions() -> str:
    return build_theodore_instructions(
        TheodoreMode.GROUP_THEODORE,
        lesson_title=GROUP_CLASS_SCENARIO.lesson_title,
        slide_title=GROUP_CLASS_SCENARIO.slide_title,
        audience_note="Multiple learners may be on camera; respect the speaking queue.",
    )
