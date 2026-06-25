"""Teaching layer: turn a harvested course into a narrated lesson, then present
it live in a meeting.

This package ties the three parts of the product together:
  Part 1  aoep_shared.harvest   -> a scored, tagged GeneratedCourse
  Part 2  aoep_shared.teaching  -> a LessonPlan (narrated teaching script); can
                                   delegate to the external ppt_trainer agent or
                                   build a deterministic offline lesson
  Part 3  aoep_shared.meeting   -> present the lesson live (Google Meet/Zoom/
                                   Teams, with an offline mock)

``run_end_to_end`` (orchestrator) runs all three.
"""

from .lesson import (
    LessonPlan,
    LessonStep,
    ppt_trainer_available,
    teach_course,
)
from .orchestrator import EndToEndResult, run_end_to_end

__all__ = [
    "LessonPlan",
    "LessonStep",
    "teach_course",
    "ppt_trainer_available",
    "run_end_to_end",
    "EndToEndResult",
]
