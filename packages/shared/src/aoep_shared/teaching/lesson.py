"""Part 2 - build a narrated LessonPlan from a harvested course.

Two engines, same ``LessonPlan`` output shape:

  - "fallback" (default, offline, no keys): a deterministic teaching script built
    from the narration the harvester already produced for every slide, plus an
    auto-written welcome and closing. Runs anywhere; used in tests/CI.
  - "ppt_trainer": delegate to the external agentic reader (the separate
    ``ppt_trainer`` project) by exporting a .pptx and invoking its CLI
    (``ppt-trainer teach``), then reading back its ``lesson.json``. Used when the
    richer, LLM-written, human-sounding script + audio/video is wanted.

Keeping one ``LessonPlan`` shape means the meeting presenter (Part 3) does not
care which engine produced the lesson.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class LessonStep:
    """One spoken unit of the lesson (aligned 1:1 with a presentation slide)."""

    order: int
    kind: str               # "intro" | "segment" | "outro"
    title: str
    narration: str
    on_screen_points: List[str] = field(default_factory=list)
    section_index: Optional[int] = None
    category: str = ""

    def to_dict(self) -> Dict:
        return {
            "order": self.order,
            "kind": self.kind,
            "title": self.title,
            "narration": self.narration,
            "on_screen_points": list(self.on_screen_points),
            "section_index": self.section_index,
            "category": self.category,
        }


@dataclass
class LessonPlan:
    """A complete narrated lesson, engine-agnostic."""

    title: str
    subject: str = "general"
    engine: str = "fallback"
    steps: List[LessonStep] = field(default_factory=list)

    @property
    def segments(self) -> List[LessonStep]:
        return [s for s in self.steps if s.kind == "segment"]

    @property
    def full_narration(self) -> str:
        return "\n\n".join(s.narration for s in self.steps if s.narration.strip())

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "subject": self.subject,
            "engine": self.engine,
            "steps": [s.to_dict() for s in self.steps],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def _bullets(body: str, *, max_bullets: int = 6) -> List[str]:
    parts: List[str] = []
    for chunk in body.replace("\n", " ").split(". "):
        s = chunk.strip().rstrip(".")
        if s:
            parts.append(s if len(s) <= 120 else s[:117] + "...")
    return parts[:max_bullets] or ([body[:120]] if body else [])


# --------------------------------------------------------------------------- #
# Engine 1: deterministic offline lesson (reuses the harvester's narration)
# --------------------------------------------------------------------------- #
def _auto_intro(title: str, headings: List[str]) -> str:
    preview = ", ".join(h for h in headings[:4] if h)
    tail = "" if len(headings) <= 4 else ", and more"
    body = f"Welcome! Today we're learning {title}."
    if preview:
        body += f" We'll walk through {preview}{tail}."
    body += " Take your time, and let's get into it."
    return body


def _auto_outro(title: str) -> str:
    return (
        f"That's a wrap on {title}. Nice work getting through it. "
        "The best way to make this stick is to try it yourself - so go practice, "
        "and come back any time you want a refresher."
    )


def lesson_from_generated_course(course) -> LessonPlan:
    """Build a LessonPlan directly from a harvester ``GeneratedCourse`` (offline)."""
    headings = [s.title for s in course.slides]
    steps: List[LessonStep] = [
        LessonStep(order=0, kind="intro", title=f"Welcome to {course.title}",
                   narration=_auto_intro(course.title, headings),
                   on_screen_points=headings[:6])
    ]
    for i, slide in enumerate(course.slides, start=1):
        narration = (slide.narration or slide.body or slide.title).strip()
        steps.append(LessonStep(
            order=i, kind="segment", title=slide.title, narration=narration,
            on_screen_points=_bullets(slide.body), section_index=i - 1,
            category=getattr(slide, "category", ""),
        ))
    steps.append(LessonStep(order=len(steps), kind="outro",
                            title="Closing", narration=_auto_outro(course.title)))
    return LessonPlan(title=course.title, subject=course.subject,
                      engine="fallback", steps=steps)


# --------------------------------------------------------------------------- #
# Engine 2: delegate to the external ppt_trainer agent (LLM script + media)
# --------------------------------------------------------------------------- #
def ppt_trainer_available() -> bool:
    """True if the ppt_trainer CLI is importable or on PATH."""
    if shutil.which(os.environ.get("PPT_TRAINER_BIN", "ppt-trainer")):
        return True
    try:
        import ppt_trainer  # noqa: F401
        return True
    except Exception:
        return False


def _lesson_from_ppt_trainer_json(data: Dict, *, subject: str = "general") -> LessonPlan:
    """Map ppt_trainer's lesson.json (intro/segments/outro) into a LessonPlan."""
    steps: List[LessonStep] = []
    title = data.get("title", "Lesson")
    if data.get("intro"):
        steps.append(LessonStep(order=0, kind="intro", title=f"Welcome to {title}",
                                narration=data["intro"]))
    for i, seg in enumerate(data.get("segments", []), start=1):
        steps.append(LessonStep(
            order=len(steps), kind="segment",
            title=seg.get("section_title") or seg.get("heading") or f"Part {i}",
            narration=seg.get("narration", ""),
            on_screen_points=[str(p) for p in seg.get("on_screen_points", [])][:6],
            section_index=seg.get("section_index"),
        ))
    if data.get("outro"):
        steps.append(LessonStep(order=len(steps), kind="outro", title="Closing",
                                narration=data["outro"]))
    return LessonPlan(title=title, subject=subject, engine="ppt_trainer", steps=steps)


def teach_with_ppt_trainer(pptx_path: str | Path, *, out_dir: str | Path,
                           subject: str = "general", audience: str = "curious beginners",
                           timeout: int = 1800) -> LessonPlan:
    """Invoke the external ppt_trainer CLI on a .pptx and read back its lesson.

    Raises RuntimeError if the CLI is unavailable or fails. The orchestrator
    catches this and falls back to the offline engine.
    """
    pptx_path = Path(pptx_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    binary = os.environ.get("PPT_TRAINER_BIN", "ppt-trainer")
    if not shutil.which(binary):
        raise RuntimeError(f"ppt_trainer CLI {binary!r} not found on PATH")
    cmd = [binary, "teach", str(pptx_path), "--output", "script",
           "--audience", audience, "--output-dir", str(out_dir)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"ppt_trainer failed: {exc}") from exc
    # ppt_trainer writes <out_dir>/<stem>/lesson.json
    candidates = list(out_dir.glob("**/lesson.json"))
    if not candidates:
        raise RuntimeError("ppt_trainer produced no lesson.json")
    data = json.loads(candidates[0].read_text(encoding="utf-8"))
    return _lesson_from_ppt_trainer_json(data, subject=subject)


def teach_course(course, *, engine: str = "fallback", pptx_path: Optional[str | Path] = None,
                 out_dir: Optional[str | Path] = None, audience: str = "curious beginners",
                 fallback_on_error: bool = True) -> LessonPlan:
    """Build a LessonPlan for a harvested course.

    engine="fallback" -> deterministic offline lesson (default).
    engine="ppt_trainer" -> delegate to the external agent (needs pptx_path +
    out_dir); on any failure, falls back to the offline engine when
    ``fallback_on_error`` is set.
    """
    if engine == "ppt_trainer":
        if not pptx_path or not out_dir:
            if not fallback_on_error:
                raise ValueError("ppt_trainer engine needs pptx_path and out_dir")
        else:
            try:
                return teach_with_ppt_trainer(pptx_path, out_dir=out_dir,
                                              subject=course.subject, audience=audience)
            except RuntimeError:
                if not fallback_on_error:
                    raise
    return lesson_from_generated_course(course)
