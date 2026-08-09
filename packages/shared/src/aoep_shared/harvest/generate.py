"""Generate reviewable course material from extracted input.

This is the step the spec calls out: "instructions on how to generate the
content when feeding in the input data so we can review." Given an
``ExtractedDoc`` (from any source) it produces a single reviewable artifact:

  1. SLIDES   - one condensed slide per input section (deterministic; no LLM, so
                it runs offline. An LLM can later rewrite slide bodies behind the
                same shape).
  2. NODES    - each section is classified into a pedagogical category and added
                to the numpy CourseComposition (the section heading is its
                sub-node / subtopic label).
  3. SCORE    - composition_score (the recipe fingerprint, e.g. 247) +
                quality_index + quality_metrics.
  4. TAGS     - JSON/meta tags (free/expensive, LinkedIn job, career path,
                core-fundamental, custom labels).

The resulting ``GeneratedCourse`` serializes to JSON for human review and maps
onto the curriculum catalog ``Course`` fields for ingestion.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .composition import CourseComposition
from .extractors import ExtractedDoc
from .pedagogy import build_teaching_slides
from .section_normalize import normalize_document
from .tagging import CourseTags

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# A single lesson should be a ~15-20 minute session. At instructional pace
# (~12 slides in ~15-18 minutes) we cap a lesson at this many slides and
# partition anything longer into Lesson 1..N. Harvested material (a scraped
# page or a big file) can yield 1000+ sections/slides — far too much for one
# lesson — so we split it into evenly-sized lessons instead of one giant deck.
MAX_SLIDES_PER_LESSON = 12
# Absolute ceiling for a single lesson regardless of caller override.
HARD_MAX_SLIDES_PER_LESSON = 24


def _condense(text: str, *, max_sentences: int = 8, max_chars: int = 1200) -> str:
    """Legacy helper — prefer ``build_teaching_slides`` for new paths."""
    sentences = _SENTENCE_RE.split(text.strip())
    body = " ".join(sentences[:max_sentences]).strip()
    return body[:max_chars].rstrip()


@dataclass
class GeneratedSlide:
    title: str
    body: str
    narration: str
    category: str          # the pedagogical node category this slide fills
    audio_path: Optional[str] = None
    media_url: Optional[str] = None
    media_kind: str = ""   # "audio" | "video" | ""

    def to_dict(self) -> Dict:
        d = {"title": self.title, "body": self.body,
             "narration": self.narration, "category": self.category}
        if self.audio_path:
            d["audio_path"] = self.audio_path
        if self.media_url:
            d["media_url"] = self.media_url
            d["media_kind"] = self.media_kind
        return d


@dataclass
class GeneratedCourse:
    course_id: str
    title: str
    subject: str
    language: str
    source: str
    fmt: str
    slides: List[GeneratedSlide] = field(default_factory=list)
    composition: Optional[CourseComposition] = None
    tags: Optional[CourseTags] = None
    presentation_mode_index: int = 0
    # Lesson partitioning: a big source is split into lesson_count lessons; this
    # course is lesson lesson_index of that set (both default to 1 = single lesson).
    lesson_index: int = 1
    lesson_count: int = 1

    @property
    def composition_score(self) -> int:
        return self.composition.composition_score() if self.composition else 0

    def to_dict(self) -> Dict:
        return {
            "course_id": self.course_id,
            "title": self.title,
            "subject": self.subject,
            "language": self.language,
            "source": self.source,
            "format": self.fmt,
            "presentation_mode_index": self.presentation_mode_index,
            "lesson_index": self.lesson_index,
            "lesson_count": self.lesson_count,
            "composition_score": self.composition_score,
            "slides": [s.to_dict() for s in self.slides],
            "composition": self.composition.to_dict() if self.composition else {},
            "tags": self.tags.to_dict() if self.tags else {},
        }

    def to_json(self, *, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), indent=indent)

    def catalog_payload(self) -> Dict:
        """Shape for POSTing to the curriculum catalog ``Course`` endpoint."""
        payload = {
            "title": self.title,
            "subject": self.subject,
            "language": self.language,
            "media_format": "video" if self.fmt == "video" else "text",
            "description": self.slides[0].body if self.slides else "",
            "source": self.source,
        }
        if self.tags:
            payload.update(self.tags.catalog_fields())
        if self.composition:
            payload["meta_composition_score"] = self.composition_score
        if self.lesson_count > 1:
            payload["meta_lesson_index"] = self.lesson_index
            payload["meta_lesson_count"] = self.lesson_count
        return payload


def generate_course(
    doc: ExtractedDoc,
    *,
    subject: str = "general",
    fmt: str = "lecture",
    tags: Optional[CourseTags] = None,
    course_id: Optional[str] = None,
    source: str = "",
    presentation_mode=None,
) -> GeneratedCourse:
    """Turn an ``ExtractedDoc`` into a scored, tagged, reviewable course."""
    from ..meeting.presentation_matrix import PresentationProfile

    cid = course_id or uuid.uuid4().hex[:12]
    doc = normalize_document(doc)
    profile = PresentationProfile.resolve(presentation_mode or fmt)
    slides = build_teaching_slides(
        doc.nonempty_sections(),
        course_title=doc.title,
        fmt=profile.arc,
        subject=subject,
        profile=profile,
    )
    comp = CourseComposition(subject=subject, course_id=cid)
    for slide in slides:
        comp.add_node(slide.category, subnode=slide.title)
    return GeneratedCourse(
        course_id=cid,
        title=doc.title,
        subject=subject,
        language=doc.language,
        source=source or doc.source_type,
        fmt=profile.arc,
        slides=slides,
        composition=comp,
        tags=tags or CourseTags(),
        presentation_mode_index=profile.mode_index,
    )


def _balanced_chunks(items: List, k: int) -> List[List]:
    """Split ``items`` into ``k`` contiguous, near-equal chunks (largest first).

    Balancing avoids a tiny trailing lesson (e.g. 20 + 20 + 3); 43 slides over
    3 lessons becomes 15/14/14 instead. Each chunk is <= ceil(len/k).
    """
    n = len(items)
    if k <= 1 or n == 0:
        return [list(items)]
    base, extra = divmod(n, k)
    chunks: List[List] = []
    start = 0
    for i in range(k):
        size = base + (1 if i < extra else 0)
        chunks.append(list(items[start:start + size]))
        start += size
    return chunks


def partition_course_into_lessons(
    course: GeneratedCourse,
    *,
    max_slides: int = MAX_SLIDES_PER_LESSON,
) -> List[GeneratedCourse]:
    """Split an oversized course deck into evenly-sized lessons.

    A lesson targets a ~15-20 minute session, so it may hold at most
    ``max_slides`` slides (clamped to ``HARD_MAX_SLIDES_PER_LESSON``). Courses at
    or under the cap are returned unchanged as a single lesson. Longer decks are
    balanced across ``ceil(n / cap)`` lessons titled "<title> — Lesson i of N",
    each with its own course_id and rebuilt composition.
    """
    cap = max(1, min(int(max_slides or MAX_SLIDES_PER_LESSON), HARD_MAX_SLIDES_PER_LESSON))
    slides = course.slides
    if len(slides) <= cap:
        # Single lesson: keep the course as-is (lesson_index/count already 1).
        return [course]

    import math

    lesson_count = math.ceil(len(slides) / cap)
    chunks = _balanced_chunks(slides, lesson_count)
    lessons: List[GeneratedCourse] = []
    for i, chunk in enumerate(chunks, start=1):
        lesson_id = f"{course.course_id}-l{i}"
        comp = CourseComposition(subject=course.subject, course_id=lesson_id)
        for slide in chunk:
            comp.add_node(slide.category, subnode=slide.title)
        lessons.append(
            GeneratedCourse(
                course_id=lesson_id,
                title=f"{course.title} — Lesson {i} of {lesson_count}",
                subject=course.subject,
                language=course.language,
                source=course.source,
                fmt=course.fmt,
                slides=chunk,
                composition=comp,
                tags=course.tags,
                presentation_mode_index=course.presentation_mode_index,
                lesson_index=i,
                lesson_count=lesson_count,
            )
        )
    return lessons


def generate_lessons(
    doc: ExtractedDoc,
    *,
    subject: str = "general",
    fmt: str = "lecture",
    tags: Optional[CourseTags] = None,
    course_id: Optional[str] = None,
    source: str = "",
    presentation_mode=None,
    max_slides: int = MAX_SLIDES_PER_LESSON,
) -> List[GeneratedCourse]:
    """Generate a course then partition it into lesson-sized decks."""
    course = generate_course(
        doc, subject=subject, fmt=fmt, tags=tags, course_id=course_id,
        source=source, presentation_mode=presentation_mode,
    )
    return partition_course_into_lessons(course, max_slides=max_slides)


# Plain-text, reviewable description of the generation recipe (surfaced by the
# harvester CLI so a reviewer sees exactly how content is produced).
GENERATION_INSTRUCTIONS = """\
HOW COURSE CONTENT IS GENERATED FROM INPUT DATA
1. INGEST   Pick a source (text/html/url/pdf/pptx/docx/database). The matching
            extractor normalizes it into a title + ordered (heading, text)
            sections. (aoep_shared.harvest.extractors)
2. NORMALIZE Filter TOC junk / dot leaders; merge small sections into learning
            units sized for teaching. (aoep_shared.harvest.section_normalize)
3. SLIDE    Build a teachable deck: welcome hook, concept slides, worked examples,
            try-it checkpoints, demo-video beats, recaps, closing CTA. Speaker
            notes use presentation-skills enrichment.
            (aoep_shared.harvest.pedagogy)
4. CLASSIFY Each slide maps to a pedagogical NODE category (introduction,
            history, concept, example, video, quiz, q&a, summary, ...) by
            keyword cues; the slide title is recorded as that node's SUB-NODE
            (subtopic) label.
5. SCORE    All nodes/sub-nodes are stored in a numpy matrix. We compute:
              - composition_score : the recipe fingerprint (e.g. 247) you key
                survey happiness on;
              - quality_index/metrics : coverage, balance, depth, interactivity.
6. TAG      RAG over the course catalog + skills taxonomy infer subject,
            access_tier, price, career_path, core_fundamental, and labels.
            Manual flags override inferred values. (aoep_shared.harvest.auto_tags)
7. REVIEW   The whole artifact serializes to JSON (slides + composition + score
            + tags) so a human can review before it is published to the catalog.
8. MEDIA    Optional (--with-media): per-slide narration audio (macOS say /
            espeak) + demo-video references in media_manifest.json.
            (aoep_shared.harvest.media)
"""
