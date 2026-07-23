"""Import host-uploaded PDF/PPTX decks as orchestrator curriculum lessons."""

from __future__ import annotations

import os
import re
import uuid
from typing import Tuple

from aoep_shared.harvest.extractors import extract_pdf, extract_pptx

from .curriculum import CurriculumStore, Lesson, _parse_lesson


def _lesson_id_for(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "host-deck").lower()).strip("-")[:40]
    return f"host-{slug or 'deck'}-{uuid.uuid4().hex[:8]}"


def sections_to_lesson_text(title: str, language: str, sections: list[tuple[str, str]]) -> str:
    lines = [f"LESSON: {title}", f"LANGUAGE: {language}", ""]
    for i, (heading, body) in enumerate(sections, start=1):
        lines.append(f"SLIDE {i} | {heading or f'Slide {i}'}")
        if body:
            lines.append(body)
        narration = (body or heading or title).strip()
        lines.append(f"NARRATION: {narration[:500]}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def import_presentation_bytes(
    data: bytes,
    *,
    filename: str,
    title: str = "",
    language: str = "en",
    store: CurriculumStore,
) -> Tuple[str, Lesson, str]:
    """Parse PDF/PPTX bytes, persist under ``host-uploads/``, register lesson."""
    lower = (filename or "").lower()
    default_title = (
        title.strip()
        or os.path.splitext(os.path.basename(filename or "presentation"))[0]
        or "Host class"
    )
    if lower.endswith(".pdf"):
        try:
            doc = extract_pdf(data, default_title=default_title)
        except ImportError:
            raise ValueError(
                "PDF parsing library (pypdf) is not installed on this server. "
                "Please select a catalog lesson instead of uploading a PDF, "
                "or contact support to enable file uploads."
            )
    elif lower.endswith(".pptx"):
        try:
            doc = extract_pptx(data, default_title=default_title)
        except ImportError:
            raise ValueError(
                "PowerPoint parsing library (python-pptx) is not installed on this server. "
                "Please select a catalog lesson instead of uploading a PPTX, "
                "or contact support to enable file uploads."
            )
    else:
        raise ValueError("supported presentation formats: .pdf, .pptx")
    if not doc.sections:
        raise ValueError("no slides found in presentation")
    lesson_title = doc.title or default_title
    lesson_id = _lesson_id_for(lesson_title)
    text = sections_to_lesson_text(lesson_title, language, doc.sections)
    lesson, passages = _parse_lesson(lesson_id, text)
    host_dir = os.path.join(store.root, "host-uploads", lesson_id)
    os.makedirs(host_dir, exist_ok=True)
    with open(os.path.join(host_dir, "lesson.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)
    store.register_lesson(lesson_id, lesson, passages)
    return lesson_id, lesson, os.path.basename(filename or "presentation")
