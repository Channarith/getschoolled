"""User self-teaching with Theodore as coach — lighter presence holds."""

from __future__ import annotations

from webcam_vision_lab.presence.absence import AbsencePolicy
from webcam_vision_lab.scenarios.solo_class import ClassScenario
from webcam_vision_lab.voice.theodore import TheodoreMode, build_theodore_instructions

SELF_TEACH_SCENARIO = ClassScenario(
    name="self_teach_coach",
    mode=TheodoreMode.SELF_TEACH,
    presence_policy=AbsencePolicy(
        enabled=True,
        grace_seconds=120,
        stale_seconds=30,
        require_liveness=False,
        max_faces_allowed=1,
    ),
    lesson_title="Self-paced Algebra Review",
    slide_title="Solving linear equations",
    room_id_prefix="self-",
    is_group=False,
)


def self_teach_instructions() -> str:
    return build_theodore_instructions(
        TheodoreMode.SELF_TEACH,
        lesson_title=SELF_TEACH_SCENARIO.lesson_title,
        slide_title=SELF_TEACH_SCENARIO.slide_title,
    )
