"""Storyboard domain types for certification course segments."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class Cast:
    """One character or prop placed on the 960×540 scene (pixel coords)."""

    kind: str
    x: float
    y: float
    scale: float = 1.0
    motion: str = "bob"
    flip: bool = False
    rot: float = 0.0
    label: str = ""
    delay: float = 0.0


@dataclass(frozen=True)
class ObjectCallout:
    """Labeled teaching callout overlaid on the scene."""

    label: str
    x: float = 40.0
    y: float = 80.0
    kind: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Scene:
    """One animated visual scenario for a course slide/segment."""

    scene_id: str
    title: str
    backdrop: str
    camera: str
    narration: str
    cast: Tuple[Cast, ...] = field(default_factory=tuple)
    objects: Tuple[ObjectCallout, ...] = field(default_factory=tuple)
    concept: str = ""
    duration_hint_s: float = 12.0

    @property
    def caption(self) -> str:
        return self.concept or self.narration[:120]


@dataclass
class SegmentStoryboard:
    """Payload for one curriculum slide — ready for API / frontend."""

    lesson_id: str
    slide_index: int
    scene: Scene
    verse_label: str = ""
    learning_goal: str = ""

    def to_dict(self, *, include_svg: bool = True) -> dict[str, Any]:
        from .render import scene_data_url

        scene = self.scene
        out: dict[str, Any] = {
            "lesson_id": self.lesson_id,
            "slide_index": self.slide_index,
            "verse_label": self.verse_label or scene.title,
            "learning_goal": self.learning_goal or scene.concept,
            "scene_id": scene.scene_id,
            "title": scene.title,
            "backdrop": scene.backdrop,
            "camera": scene.camera,
            "narration": scene.narration,
            "concept": scene.concept,
            "caption": scene.caption,
            "duration_hint_s": scene.duration_hint_s,
            "cast": [asdict(c) for c in scene.cast],
            "objects": [asdict(o) for o in scene.objects],
            "examples": [],
            "activity_prompt": "",
            "modalities": ["scene", "narration", "captions"],
            "profile_mode": "mixed",
            "source_language": "en",
            "translation_ready": True,
        }
        if include_svg:
            from .render import render_scene_html, render_scene_svg, scene_data_url

            out["svg"] = render_scene_svg(scene)
            out["svg_data_url"] = scene_data_url(scene)
            out["html"] = render_scene_html(scene)
        return out
