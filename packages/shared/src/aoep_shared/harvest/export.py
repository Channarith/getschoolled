"""Export a generated course to formats the teaching layer (Part 2) consumes.

Part 1 (the harvester) produces a ``GeneratedCourse``. Part 2 (the agentic
ppt_trainer reader) natively reads ``.pptx``/``.pdf``. This module is the bridge:

  - ``export_pptx``          -> a .pptx the ppt_trainer reads with zero changes
                               (one slide per generated slide: title + bullet
                               body, with the harvester narration carried in the
                               slide's SPEAKER NOTES so Part 2 can reuse it).
  - ``export_course_json``    -> the rich course package (slides + composition
                               matrix + PCS score + tags) for the meeting layer.
  - ``export_course_package`` -> writes both into one directory and returns a
                               manifest (the hand-off contract between parts).

python-pptx is imported lazily so the rest of the harvester runs without it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .generate import GeneratedCourse


def _bullets(body: str, *, max_bullets: int = 6) -> List[str]:
    """Split a slide body into short on-screen bullet lines."""
    import re

    parts: List[str] = []
    for chunk in body.replace("\n", " ").split(". "):
        s = chunk.strip().rstrip(".")
        if s:
            parts.append(s if len(s) <= 120 else s[:117] + "...")
    return parts[:max_bullets] or [body[:120]]


def export_pptx(course: GeneratedCourse, path: str | Path) -> Path:
    """Write the course as a .pptx (title slide + one slide per generated slide).

    The spoken narration the harvester already produced is stored in each slide's
    speaker notes, so Part 2 (ppt_trainer) can read it back as ``Section.notes``.
    """
    from pptx import Presentation  # lazy
    from pptx.util import Inches, Pt

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prs = Presentation()

    # Title slide.
    title_layout = prs.slide_layouts[0]
    s0 = prs.slides.add_slide(title_layout)
    s0.shapes.title.text = course.title
    if len(s0.placeholders) > 1:
        subtitle = f"{course.subject}"
        if course.composition is not None:
            subtitle += f"  ·  composition score {course.composition_score}"
        s0.placeholders[1].text = subtitle

    # Content slides.
    content_layout = prs.slide_layouts[1]
    for slide in course.slides:
        s = prs.slides.add_slide(content_layout)
        s.shapes.title.text = slide.title
        body_tf = s.placeholders[1].text_frame
        bullets = _bullets(slide.body)
        body_tf.text = bullets[0]
        for line in bullets[1:]:
            p = body_tf.add_paragraph()
            p.text = line
            p.level = 0
        # Carry the harvester narration in the speaker notes.
        if slide.narration:
            notes = s.notes_slide.notes_text_frame
            notes.text = slide.narration

    prs.save(str(path))
    return path


def export_course_json(course: GeneratedCourse, path: str | Path) -> Path:
    """Write the rich course package JSON (slides + composition + score + tags)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(course.to_dict(), indent=2), encoding="utf-8")
    return path


@dataclass
class CoursePackage:
    """Hand-off contract from Part 1 (harvest) to Parts 2 (teach) / 3 (present)."""

    course_id: str
    title: str
    subject: str
    composition_score: int
    output_dir: Path
    pptx_path: Optional[Path] = None
    course_json_path: Optional[Path] = None

    def to_dict(self) -> Dict:
        return {
            "course_id": self.course_id,
            "title": self.title,
            "subject": self.subject,
            "composition_score": self.composition_score,
            "output_dir": str(self.output_dir),
            "pptx_path": str(self.pptx_path) if self.pptx_path else None,
            "course_json_path": str(self.course_json_path) if self.course_json_path else None,
        }


def export_course_package(
    course: GeneratedCourse,
    out_dir: str | Path,
    *,
    write_pptx: bool = True,
) -> CoursePackage:
    """Write the course package (pptx + json) into ``out_dir`` and return a manifest."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = (course.title or course.course_id or "course").strip().replace("/", "-")[:64] or "course"

    json_path = export_course_json(course, out_dir / f"{stem}.course.json")
    pptx_path: Optional[Path] = None
    if write_pptx:
        try:
            pptx_path = export_pptx(course, out_dir / f"{stem}.pptx")
        except ImportError:
            pptx_path = None  # python-pptx not installed; json package still valid

    return CoursePackage(
        course_id=course.course_id,
        title=course.title,
        subject=course.subject,
        composition_score=course.composition_score,
        output_dir=out_dir,
        pptx_path=pptx_path,
        course_json_path=json_path,
    )
