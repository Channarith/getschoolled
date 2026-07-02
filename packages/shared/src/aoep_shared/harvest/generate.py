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
