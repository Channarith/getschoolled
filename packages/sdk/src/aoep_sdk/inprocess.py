"""Curated in-process AOEP capability surface.

These exports let developers embed the same provider, retrieval, content,
teaching, homework, meeting, and training-agent engines used by the services.
Optional capability dependencies remain controlled by ``aoep-shared`` extras.
"""

from aoep_shared import (
    AppConfig,
    ComponentMode,
    DeployMode,
    ProviderFactory,
    build_factory,
    get_version,
    load_config,
)
from aoep_shared import harvest, homework, meeting, teaching, training_agents
from aoep_shared.adaptive import (
    AdaptivePolicy,
    Difficulty,
    LearnerSignals,
    Pacing,
    PacingPlan,
)
from aoep_shared.harvest import (
    GeneratedCourse,
    GeneratedSlide,
    export_course_package,
    generate_course,
    generate_lessons,
    partition_course_into_lessons,
)
from aoep_shared.rag import Document, RagIndex, Retrieved
from aoep_shared.teaching import (
    EndToEndResult,
    LessonPlan,
    LessonStep,
    run_end_to_end,
    teach_course,
)

__all__ = [
    "AdaptivePolicy",
    "AppConfig",
    "ComponentMode",
    "DeployMode",
    "Difficulty",
    "Document",
    "EndToEndResult",
    "GeneratedCourse",
    "GeneratedSlide",
    "LearnerSignals",
    "LessonPlan",
    "LessonStep",
    "Pacing",
    "PacingPlan",
    "ProviderFactory",
    "RagIndex",
    "Retrieved",
    "build_factory",
    "export_course_package",
    "generate_course",
    "generate_lessons",
    "get_version",
    "harvest",
    "homework",
    "load_config",
    "meeting",
    "partition_course_into_lessons",
    "run_end_to_end",
    "teach_course",
    "teaching",
    "training_agents",
]
