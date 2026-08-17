"""Course-agnostic storyboard generation for every curriculum slide.

Hand-authored catalogs remain the highest-quality tier.  This module supplies a
deterministic semantic scene for everything else so no corporate or solo lesson
falls back to a text-only experience.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .types import Cast, ObjectCallout, Scene, SegmentStoryboard


@dataclass(frozen=True)
class StoryboardExperience:
    segment: SegmentStoryboard
    examples: tuple[str, ...]
    activity_prompt: str
    modalities: tuple[str, ...]
    profile_mode: str
    source_language: str = "en"
    translation_ready: bool = True


_DOMAIN_RULES: tuple[tuple[tuple[str, ...], str, tuple[str, ...]], ...] = (
    (
        ("drive", "road", "vehicle", "traffic", "dmv", "parking", "motor"),
        "intersection",
        ("car-blue", "car-red", "sign-warning", "pedestrian"),
    ),
    (
        ("food", "kitchen", "cook", "hygiene", "temperature", "allergen"),
        "kitchen",
        ("adult", "sink", "plate", "thermometer-41"),
    ),
    (
        ("safety", "hazard", "emergency", "fire", "first aid", "injury"),
        "work-zone",
        ("adult", "ambulance", "sign-warning", "cone"),
    ),
    (
        ("work", "business", "leader", "team", "customer", "corporate"),
        "office",
        ("adult", "teen", "chart", "document"),
    ),
    (
        ("data", "ai", "software", "code", "cyber", "cloud", "computer"),
        "office",
        ("adult", "teen", "laptop", "chart"),
    ),
    (
        ("environment", "climate", "water", "earth", "biology", "science"),
        "lab",
        ("adult", "teen", "chart", "document"),
    ),
    (
        ("math", "algebra", "calculus", "number", "equation", "geometry"),
        "classroom",
        ("adult", "teen", "chart", "document"),
    ),
    (
        ("health", "medical", "care", "patient", "pharmacy", "nurse"),
        "lab",
        ("adult", "glove", "document", "thermometer-41"),
    ),
)

_DEFAULT_BACKDROPS = (
    "residential",
    "school-zone",
    "prep-station",
    "intersection",
    "freeway",
    "night-road",
)
_DEFAULT_CAST = ("adult", "teen", "sign-guide", "sign-warning")
_CAMERAS = (
    "ken-burns",
    "push-in",
    "pull-out",
    "pan-right",
    "pan-left",
    "tilt-up",
)
_MOTIONS = ("bob", "sway", "pulse", "walk")


def _sentences(text: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", " ".join((text or "").split()))
        if len(part.strip()) >= 12
    ]


def _profile_mode(profile: dict[str, str] | None) -> str:
    style = (profile or {}).get("primary_style", "").strip().lower()
    aliases = {
        "visual": "visual",
        "auditory": "auditory",
        "reading_writing": "reading",
        "read_write": "reading",
        "hands_on": "hands_on",
        "kinesthetic": "hands_on",
    }
    return aliases.get(style, "mixed")


def _domain(text: str, seed: int) -> tuple[str, tuple[str, ...]]:
    lowered = text.lower()
    for terms, backdrop, cast in _DOMAIN_RULES:
        if any(term in lowered for term in terms):
            return backdrop, cast
    return _DEFAULT_BACKDROPS[seed % len(_DEFAULT_BACKDROPS)], _DEFAULT_CAST


def _cast(kind_rows: Iterable[str], seed: int, mode: str) -> tuple[Cast, ...]:
    rows = list(kind_rows)
    # Visual/hands-on learners get the richest scene. Auditory and reading
    # profiles retain enough visible context without crowding the captions.
    count = 4 if mode in {"visual", "hands_on", "mixed"} else 3
    positions = ((220, 330), (430, 300), (620, 340), (760, 230))
    out: list[Cast] = []
    for i, kind in enumerate(rows[:count]):
        x, y = positions[i]
        out.append(
            Cast(
                kind=kind,
                x=x,
                y=y,
                scale=1.0 if i < 2 else 0.85,
                motion=_MOTIONS[(seed + i) % len(_MOTIONS)],
                flip=bool((seed + i) % 2 and kind.startswith(("car", "bike"))),
                delay=i * 0.18,
            )
        )
    return tuple(out)


def build_generic_storyboard(
    *,
    lesson_id: str,
    slide_index: int,
    title: str,
    body: str,
    narration: str,
    language: str = "en",
    profile: dict[str, str] | None = None,
) -> StoryboardExperience:
    """Create a deterministic multimodal scene from one curriculum slide."""
    key = f"{lesson_id}:{slide_index}:{title}"
    seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
    mode = _profile_mode(profile)
    combined = f"{lesson_id} {title} {body} {narration}"
    backdrop, cast_kinds = _domain(combined, seed)
    sentences = _sentences(body or narration)
    concept = sentences[0] if sentences else (narration or title)
    examples = tuple(sentences[1:3])
    if not examples:
        examples = (
            f"Example: apply “{title}” to a realistic decision.",
            f"Contrast: identify what would go wrong if “{title}” were ignored.",
        )

    callouts = [
        ObjectCallout(label=title[:54], x=34, y=82),
        ObjectCallout(label=examples[0][:54], x=700, y=105),
    ]
    if mode in {"visual", "hands_on", "mixed"}:
        callouts.append(
            ObjectCallout(label="Notice → decide → act", x=360, y=440)
        )

    camera = _CAMERAS[(seed + (0 if mode == "visual" else 2)) % len(_CAMERAS)]
    scene = Scene(
        scene_id=f"auto-{lesson_id}-{slide_index:03d}",
        title=title,
        backdrop=backdrop,
        camera=camera,
        narration=narration or body or title,
        cast=_cast(cast_kinds, seed, mode),
        objects=tuple(callouts),
        concept=concept[:180],
        duration_hint_s=16.0 if mode == "auditory" else 12.0,
    )
    segment = SegmentStoryboard(
        lesson_id=lesson_id,
        slide_index=slide_index,
        verse_label=title,
        learning_goal=concept[:180],
        scene=scene,
    )
    prompt = (
        f"Act it out: choose the safest next step in a scenario about {title}."
        if mode == "hands_on"
        else f"Pause and explain how {title} changes a real decision."
    )
    return StoryboardExperience(
        segment=segment,
        examples=examples,
        activity_prompt=prompt,
        modalities=("scene", "narration", "captions", "examples", "activity"),
        profile_mode=mode,
        source_language=language or "en",
    )


def experience_dict(experience: StoryboardExperience) -> dict[str, Any]:
    out = experience.segment.to_dict(include_svg=True)
    out.update(
        {
            "examples": list(experience.examples),
            "activity_prompt": experience.activity_prompt,
            "modalities": list(experience.modalities),
            "profile_mode": experience.profile_mode,
            "source_language": experience.source_language,
            "translation_ready": experience.translation_ready,
        }
    )
    return out
