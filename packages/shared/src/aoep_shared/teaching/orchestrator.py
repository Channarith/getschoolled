"""End-to-end orchestrator: harvest -> teach -> present.

One call runs the whole product flow:
  Part 1  harvest:  input (text/html/pdf/pptx/docx) -> GeneratedCourse (scored,
                    tagged) -> exported .pptx + .course.json
  Part 2  teach:    GeneratedCourse -> LessonPlan (offline, or via ppt_trainer)
  Part 3  present:  LessonPlan -> live meeting (Google Meet/Zoom/Teams, or mock)

Everything has an offline path (deterministic lesson + mock meeting), so the
full flow runs in tests/CI without keys, network, or ffmpeg. A manifest tying
all artifacts together is written to ``out_dir/manifest.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from ..harvest import (
    CourseTags,
    GeneratedCourse,
    export_course_package,
    extract_file,
    generate_course,
)
from ..meeting.factory import present_with_provider
from ..meeting.presenter import build_presentation_plan
from .lesson import LessonPlan, teach_course


@dataclass
class EndToEndResult:
    out_dir: Path
    course: GeneratedCourse
    lesson: LessonPlan
    provider_used: str = ""
    composition_score: int = 0
    join_url: str = ""
    presentation: Optional[object] = None   # PresentationResult
    artifacts: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "out_dir": str(self.out_dir),
            "course": {
                "course_id": self.course.course_id,
                "title": self.course.title,
                "subject": self.course.subject,
                "composition_score": self.composition_score,
                "slides": len(self.course.slides),
                "tags": self.course.tags.label_list() if self.course.tags else [],
            },
            "lesson": {
                "engine": self.lesson.engine,
                "steps": len(self.lesson.steps),
                "segments": len(self.lesson.segments),
            },
            "meeting": {
                "provider_used": self.provider_used,
                "join_url": self.join_url,
            },
            "presentation": self.presentation.to_dict() if self.presentation else None,
            "artifacts": self.artifacts,
        }


def run_end_to_end(
    *,
    source: Optional[str | Path] = None,
    text: Optional[str] = None,
    course: Optional[GeneratedCourse] = None,
    subject: str = "general",
    fmt: str = "lecture",
    tags: Optional[CourseTags] = None,
    out_dir: str | Path = "output/teaching",
    teach_engine: str = "fallback",
    audience: str = "curious beginners",
    meeting_provider: str = "mock",
    present: bool = True,
    realtime: bool = False,
    start_iso: str = "",
    duration_min: Optional[int] = None,
    elapsed_min: float = 0.0,
    smart_present: bool = True,
    write_pptx: bool = True,
    dialect: Optional[str] = None,
    language: str = "en",
    presentation_mode=None,
    persona=None,
    slide_source=None,
    with_media: bool = False,
) -> EndToEndResult:
    """Run harvest -> teach -> present and return a manifest of all artifacts."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: Dict[str, str] = {}

    # -- Part 1: harvest -> scored, tagged course ---------------------------
    if course is None:
        if source is not None:
            doc = extract_file(str(source))
        elif text is not None:
            from ..harvest import extract_text
            doc = extract_text(text, default_title=subject.title())
        else:
            raise ValueError("provide one of: course, source, or text")
        if tags is None:
            from ..harvest.auto_tags import infer_harvest_metadata, merge_tags
            inferred = infer_harvest_metadata(doc)
            subj, tags = merge_tags(
                inferred,
                subject=None if subject == "general" else subject,
            )
            subject = subj
        course = generate_course(doc, subject=subject, fmt=fmt,
                                 tags=tags or CourseTags(),
                                 source=str(source) if source else "text")

    package = export_course_package(
        course, out_dir, write_pptx=write_pptx, with_media=with_media,
        repo_root=Path(__file__).resolve().parents[5],
    )
    if package.course_json_path:
        artifacts["course_json"] = str(package.course_json_path)
    if package.pptx_path:
        artifacts["pptx"] = str(package.pptx_path)

    # -- Part 2: teach -> narrated lesson -----------------------------------
    lesson_dir = out_dir / "lesson"
    lesson_dir.mkdir(parents=True, exist_ok=True)
    lesson = teach_course(course, engine=teach_engine, pptx_path=package.pptx_path,
                          out_dir=lesson_dir, audience=audience,
                          dialect=dialect, language=language)
    lesson_json = lesson_dir / "lesson_plan.json"
    lesson_json.write_text(lesson.to_json(), encoding="utf-8")
    artifacts["lesson_plan"] = str(lesson_json)
    script_path = lesson_dir / "lesson_script.txt"
    script_path.write_text(_format_script(lesson), encoding="utf-8")
    artifacts["lesson_script"] = str(script_path)

    # -- Part 3: present live (or schedule) ---------------------------------
    if smart_present:
        from ..meeting.smart_presenter import build_smart_presentation_plan, corpus_rag_search
        from ..meeting.presentation_matrix import PresentationProfile
        profile = PresentationProfile.resolve(presentation_mode) if presentation_mode is not None else None
        plan = build_smart_presentation_plan(
            lesson,
            duration_min=duration_min,
            elapsed_min=elapsed_min,
            rag_search=corpus_rag_search,
            profile=profile,
        )
    else:
        plan = build_presentation_plan(lesson)
    plan_path = out_dir / "presentation_plan.json"
    plan_path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    artifacts["presentation_plan"] = str(plan_path)

    provider_used = ""
    join_url = ""
    presentation = None
    if present:
        provider_used, presentation = present_with_provider(
            lesson, provider=meeting_provider, topic=course.title,
            start_iso=start_iso, duration_min=duration_min,
            elapsed_min=elapsed_min, realtime=realtime, smart=smart_present,
            presentation_mode=presentation_mode,
            persona=persona,
            slide_source=slide_source,
        )
        join_url = presentation.meeting.join_url
        pres_path = out_dir / "presentation_result.json"
        pres_path.write_text(json.dumps(presentation.to_dict(), indent=2), encoding="utf-8")
        artifacts["presentation_result"] = str(pres_path)

    result = EndToEndResult(
        out_dir=out_dir, course=course, lesson=lesson,
        provider_used=provider_used,
        composition_score=course.composition_score,
        join_url=join_url, presentation=presentation, artifacts=artifacts,
    )
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    artifacts["manifest"] = str(manifest_path)
    return result


def _format_script(lesson: LessonPlan) -> str:
    lines = [lesson.title, "=" * len(lesson.title), ""]
    for step in lesson.steps:
        tag = {"intro": "WELCOME", "outro": "CLOSING"}.get(step.kind, step.title)
        lines += [f"[{tag}]", step.narration, ""]
    return "\n".join(lines)
