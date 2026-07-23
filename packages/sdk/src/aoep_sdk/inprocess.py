"""Curated in-process AOEP capability surface for local extension.

Exposes the provider factory, adaptive learning, RAG, teaching loop, and
content-pack loaders used by the services. Prefer importing
``aoep_sdk.local.local_factory`` when you only need the local provider factory
(lighter import graph).

Heavier surfaces remain available from ``aoep_shared`` when extras are installed::

    from aoep_shared import harvest, homework, meeting, training_agents
"""

from __future__ import annotations

from aoep_shared import (
    AppConfig,
    ComponentMode,
    DeployMode,
    ProviderFactory,
    build_factory,
    content_packs,
    get_version,
    load_config,
    teaching,
)
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

from .local import local_factory

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
