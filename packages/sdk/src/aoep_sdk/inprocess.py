"""Curated, lazy-loaded in-process AOEP capability surface for local extension.

These exports let developers embed the same provider, retrieval, content,
teaching, homework, meeting, and training-agent engines used by the services.
Capabilities load only when accessed, so lightweight retrieval does not import
optional harvesting, numerical, vision, or presentation stacks.

Use ``aoep_sdk.local.local_factory`` when only the lightweight local provider
factory is needed.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str | None]] = {
    "AppConfig": ("aoep_shared", "AppConfig"),
    "ComponentMode": ("aoep_shared", "ComponentMode"),
    "DeployMode": ("aoep_shared", "DeployMode"),
    "ProviderFactory": ("aoep_shared", "ProviderFactory"),
    "build_factory": ("aoep_shared", "build_factory"),
    "get_version": ("aoep_shared", "get_version"),
    "load_config": ("aoep_shared", "load_config"),
    "content_packs": ("aoep_shared.content_packs", None),
    "local_factory": ("aoep_sdk.local", "local_factory"),
    "AdaptivePolicy": ("aoep_shared.adaptive", "AdaptivePolicy"),
    "Difficulty": ("aoep_shared.adaptive", "Difficulty"),
    "LearnerSignals": ("aoep_shared.adaptive", "LearnerSignals"),
    "Pacing": ("aoep_shared.adaptive", "Pacing"),
    "PacingPlan": ("aoep_shared.adaptive", "PacingPlan"),
    "Document": ("aoep_shared.rag", "Document"),
    "RagIndex": ("aoep_shared.rag", "RagIndex"),
    "Retrieved": ("aoep_shared.rag", "Retrieved"),
    "GeneratedCourse": ("aoep_shared.harvest", "GeneratedCourse"),
    "GeneratedSlide": ("aoep_shared.harvest", "GeneratedSlide"),
    "export_course_package": ("aoep_shared.harvest", "export_course_package"),
    "generate_course": ("aoep_shared.harvest", "generate_course"),
    "generate_lessons": ("aoep_shared.harvest", "generate_lessons"),
    "partition_course_into_lessons": (
        "aoep_shared.harvest",
        "partition_course_into_lessons",
    ),
    "EndToEndResult": ("aoep_shared.teaching", "EndToEndResult"),
    "LessonPlan": ("aoep_shared.teaching", "LessonPlan"),
    "LessonStep": ("aoep_shared.teaching", "LessonStep"),
    "run_end_to_end": ("aoep_shared.teaching", "run_end_to_end"),
    "teach_course": ("aoep_shared.teaching", "teach_course"),
    "harvest": ("aoep_shared.harvest", None),
    "homework": ("aoep_shared.homework", None),
    "meeting": ("aoep_shared.meeting", None),
    "teaching": ("aoep_shared.teaching", None),
    "training_agents": ("aoep_shared.training_agents", None),
}


def __getattr__(name: str) -> Any:
    """Load a capability on first access and cache it in this module."""

    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name)
    value = module if attribute is None else getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))


__all__ = sorted(_EXPORTS)
