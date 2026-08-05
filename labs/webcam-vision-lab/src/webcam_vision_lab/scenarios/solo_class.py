"""Solo 1:1 class with Theodore teaching — presence policy + voice persona."""

from __future__ import annotations

from dataclasses import dataclass

from webcam_vision_lab.presence.absence import AbsencePolicy
from webcam_vision_lab.voice.theodore import TheodoreMode, build_theodore_instructions


@dataclass(frozen=True)
class ClassScenario:
    name: str
    mode: TheodoreMode
    presence_policy: AbsencePolicy
    lesson_title: str
    slide_title: str
    room_id_prefix: str
    is_group: bool


SOLO_CLASS_SCENARIO = ClassScenario(
    name="solo_1on1_theodore",
    mode=TheodoreMode.SOLO_THEODORE,
    presence_policy=AbsencePolicy(
        enabled=True,
        grace_seconds=90,
        stale_seconds=20,
        require_liveness=True,
        max_faces_allowed=1,
    ),
    lesson_title="Introduction to Fractions",
    slide_title="What is a fraction?",
    room_id_prefix="solo-",
    is_group=False,
)


def solo_theodore_instructions() -> str:
    return build_theodore_instructions(
        TheodoreMode.SOLO_THEODORE,
        lesson_title=SOLO_CLASS_SCENARIO.lesson_title,
        slide_title=SOLO_CLASS_SCENARIO.slide_title,
    )
