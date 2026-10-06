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
from typing import Dict, List, Optional, Tuple

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


# Visual timeline carried on harvested slides. Sentence ranges stay on the cues;
# a player compiles them to seconds once audio duration is known. This is a
# plain dict so the shared package does not import Course Studio models.
VISUAL_TIMELINE_VERSION = 1
_TIMELINE_SOURCES = ("curated", "inferred", "explicit")

# Text/diagram fallbacks for harvested slides, which have no authored media.
# Names match the presentation-style registry; selection here stays local.
_STYLE_BY_CATEGORY: Dict[str, str] = {
    "introduction": "question_hook",
    "history": "timeline",
    "concept": "sentence_highlight",
    "definition": "definition_reveal",
    "example": "process_build",
    "demo": "diagram_build",
    "video": "diagram_build",
    "exercise": "sentence_highlight",
    "quiz": "sentence_highlight",
    "qanda": "question_hook",
    "discussion": "pros_cons",
    "case_study": "story_sequence",
    "summary": "recap_layout",
    "recap": "recap_layout",
    "project": "decision_path",
    "assessment": "sentence_highlight",
    "resources": "sentence_highlight",
}
_TEXT_DIAGRAM_STYLES: Tuple[str, ...] = (
    "question_hook",
    "story_sequence",
    "before_after",
    "timeline",
    "cause_effect",
    "process_build",
    "decision_path",
    "diagram_build",
    "kinetic_keywords",
    "type_on",
    "sentence_highlight",
    "quote_card",
    "definition_reveal",
    "pros_cons",
    "recap_layout",
)
_DIAGRAM_STYLE_IDS = frozenset({
    "diagram_build",
    "process_build",
    "timeline",
    "cause_effect",
    "decision_path",
    "before_after",
})
_SECTION_CHECKPOINT_ACTIVITY = {
    "exercise": "try_it",
    "quiz": "quiz",
    "assessment": "quiz",
    "recap": "recap",
}


def narration_sentences(text: str) -> List[str]:
    """Split narration into the sentence ranges visual cues attach to."""
    parts = _SENTENCE_RE.split((text or "").strip())
    return [part.strip() for part in parts if part.strip()]


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _json_safe(value):
    """Copy a presentation payload into JSON-safe builtins."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def infer_presentation_style_id(category: str, *, media_url: str = "") -> str:
    """Deterministic text/diagram style. Media slides prefer an image style."""
    cat = (category or "").strip().lower()
    if media_url:
        if cat in ("demo", "video"):
            return "diagram_build"
        return "annotated_image"
    return _STYLE_BY_CATEGORY.get(cat, "sentence_highlight")


def _avoid_adjacent_style(style_id: str, previous: str) -> str:
    if not previous or style_id != previous:
        return style_id
    for candidate in _TEXT_DIAGRAM_STYLES:
        if candidate != previous:
            return candidate
    return style_id


def static_presentation_frame(
    *,
    title: str,
    body: str,
    style_id: str,
    media_url: str = "",
) -> Dict:
    """Representative still frame. PPTX cannot store the animated timeline."""
    lines = [line.strip() for line in (body or "").splitlines() if line.strip()]
    primary = lines[0][:180] if lines else (title or "")[:180]
    if media_url:
        kind = "media"
    elif style_id in _DIAGRAM_STYLE_IDS:
        kind = "diagram"
    else:
        kind = "text"
    frame: Dict = {
        "kind": kind,
        "title": title,
        "primary_text": primary,
        "style_id": style_id,
    }
    if media_url:
        frame["media_url"] = media_url
    return frame


def cue_summary_text(cues: List[Dict]) -> str:
    """One-line summary of sentence-ranged cues."""
    bits: List[str] = []
    for cue in cues:
        if not isinstance(cue, dict):
            continue
        start = cue.get("sentence_start", 0)
        end = cue.get("sentence_end", start)
        span = str(start) if start == end else f"{start}-{end}"
        action = str(cue.get("action") or "show")
        summary = str(cue.get("summary") or "").strip()
        bits.append(f"{span} {action}: {summary}" if summary else f"{span} {action}")
    text = "; ".join(bits)
    if len(text) > 1000:
        return text[:997] + "..."
    return text


def _clamp_cue(
    raw: Dict,
    *,
    sentence_count: int,
    style_id: str,
    sentences: List[str],
) -> Dict:
    start = max(0, _as_int(raw.get("sentence_start", 0), 0))
    end = max(start, _as_int(raw.get("sentence_end", start), start))
    if sentence_count:
        start = min(start, sentence_count - 1)
        end = min(max(start, end), sentence_count - 1)
    layer = str(raw.get("layer") or ("diagram" if style_id in _DIAGRAM_STYLE_IDS else "text"))
    summary = str(raw.get("summary") or "").strip()[:160]
    if not summary and sentences and start < len(sentences):
        summary = sentences[start][:160]
    cue: Dict = {
        "sentence_start": start,
        "sentence_end": end,
        "layer": layer,
        "action": str(raw.get("action") or "show"),
        "summary": summary,
    }
    start_s = _as_float(raw.get("start_s")) if "start_s" in raw else None
    if start_s is not None and start_s >= 0:
        cue["start_s"] = start_s
    duration_s = _as_float(raw.get("duration_s")) if "duration_s" in raw else None
    if duration_s is not None and duration_s > 0:
        cue["duration_s"] = duration_s
    return cue


def build_visual_timeline(
    narration: str,
    *,
    style_id: str,
    title: str = "",
    body: str = "",
    media_url: str = "",
    source: str = "inferred",
    cues: Optional[List[Dict]] = None,
    static_frame: Optional[Dict] = None,
    duration_s: Optional[float] = None,
) -> Dict:
    """Serializable VisualTimeline v1. Cues keep inclusive sentence ranges."""
    sentences = narration_sentences(narration)
    if not sentences:
        seed = (title or body or "").strip()
        if seed:
            sentences = [seed[:160]]
    if cues is None:
        raw_cues = []
        for index, sentence in enumerate(sentences):
            raw_cues.append({
                "sentence_start": index,
                "sentence_end": index,
                "layer": "diagram" if style_id in _DIAGRAM_STYLE_IDS else "text",
                "action": "enter" if index == 0 else "emphasis",
                "summary": sentence[:160],
            })
    else:
        raw_cues = [cue for cue in cues if isinstance(cue, dict)]
    built = [
        _clamp_cue(cue, sentence_count=len(sentences), style_id=style_id, sentences=sentences)
        for cue in raw_cues
    ]
    if isinstance(static_frame, dict) and static_frame.get("kind"):
        frame = _json_safe(static_frame)
        frame.setdefault("style_id", style_id)
    else:
        frame = static_presentation_frame(
            title=title, body=body, style_id=style_id, media_url=media_url,
        )
    timeline: Dict = {
        "version": VISUAL_TIMELINE_VERSION,
        "source": source if source in _TIMELINE_SOURCES else "inferred",
        "style_id": style_id,
        "static_frame": frame,
        "cues": built,
    }
    measured = _as_float(duration_s) if duration_s is not None else None
    if measured is not None and measured > 0:
        timeline["duration_s"] = measured
    summary = cue_summary_text(built)
    if summary:
        timeline["cue_summary"] = summary
    return timeline


def normalize_visual_timeline(
    timeline: Dict,
    *,
    narration: str,
    style_id: str,
    title: str,
    body: str,
    media_url: str = "",
) -> Dict:
    """Clamp cue bounds and fill the v1 fields a player expects."""
    raw = timeline if isinstance(timeline, dict) else {}
    style = style_id or str(raw.get("style_id") or "") or "sentence_highlight"
    cues = raw.get("cues")
    duration = raw.get("duration_s")
    return build_visual_timeline(
        narration,
        style_id=style,
        title=title,
        body=body,
        media_url=media_url,
        source=str(raw.get("source") or "inferred"),
        cues=list(cues) if isinstance(cues, list) else None,
        static_frame=raw.get("static_frame") if isinstance(raw.get("static_frame"), dict) else None,
        duration_s=duration if duration is not None else None,
    )


def default_checkpoints(category: str, *, lesson_end: bool = False) -> List[Dict]:
    """Section markers on activity slides; a lesson marker at the close."""
    cat = (category or "").strip().lower()
    rows: List[Dict] = []
    activity = _SECTION_CHECKPOINT_ACTIVITY.get(cat)
    if activity:
        rows.append({"placement": "section", "activity": activity, "category": cat})
    if lesson_end or cat == "summary":
        rows.append({
            "placement": "lesson",
            "activity": "close",
            "category": cat or "summary",
        })
    return rows


def apply_harvest_presentation(slides: List["GeneratedSlide"]) -> None:
    """Fill empty presentation fields. Explicit style, timeline, or checkpoints stay."""
    previous = ""
    last = len(slides) - 1
    for index, slide in enumerate(slides):
        timeline = slide.visual_timeline if isinstance(slide.visual_timeline, dict) else None
        if not slide.presentation_style_id:
            authored = str((timeline or {}).get("style_id") or "")
            if authored:
                slide.presentation_style_id = authored
            else:
                inferred = infer_presentation_style_id(
                    slide.category, media_url=slide.media_url or "",
                )
                slide.presentation_style_id = _avoid_adjacent_style(inferred, previous)
        if timeline:
            slide.visual_timeline = normalize_visual_timeline(
                timeline,
                narration=slide.narration,
                style_id=slide.presentation_style_id,
                title=slide.title,
                body=slide.body,
                media_url=slide.media_url or "",
            )
        else:
            slide.visual_timeline = build_visual_timeline(
                slide.narration,
                style_id=slide.presentation_style_id,
                title=slide.title,
                body=slide.body,
                media_url=slide.media_url or "",
            )
        if slide.checkpoints is None:
            slide.checkpoints = default_checkpoints(
                slide.category, lesson_end=(index == last),
            )
        previous = slide.presentation_style_id


@dataclass
class GeneratedSlide:
    title: str
    body: str
    narration: str
    category: str          # the pedagogical node category this slide fills
    audio_path: Optional[str] = None
    media_url: Optional[str] = None
    media_kind: str = ""   # "audio" | "video" | ""
    # Optional presentation plan. Empty values are omitted from JSON so older
    # consumers and older exports keep the previous slide shape.
    presentation_style_id: str = ""
    visual_timeline: Optional[Dict] = None
    checkpoints: Optional[List[Dict]] = None

    def to_dict(self) -> Dict:
        d = {"title": self.title, "body": self.body,
             "narration": self.narration, "category": self.category}
        if self.audio_path:
            d["audio_path"] = self.audio_path
        if self.media_url:
            d["media_url"] = self.media_url
            d["media_kind"] = self.media_kind
        style_id = self.presentation_style_id
        if not style_id and isinstance(self.visual_timeline, dict):
            style_id = str(self.visual_timeline.get("style_id") or "")
        if style_id:
            d["presentation_style_id"] = style_id
        if isinstance(self.visual_timeline, dict) and self.visual_timeline:
            timeline = normalize_visual_timeline(
                self.visual_timeline,
                narration=self.narration,
                style_id=style_id,
                title=self.title,
                body=self.body,
                media_url=self.media_url or "",
            )
            d["visual_timeline"] = timeline
            if timeline.get("cue_summary"):
                d["cue_summary"] = timeline["cue_summary"]
        if self.checkpoints:
            d["checkpoints"] = [
                _json_safe(item) if isinstance(item, dict) else {"marker": str(item)}
                for item in self.checkpoints
            ]
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "GeneratedSlide":
        """Load a slide. Missing presentation keys stay empty (older JSON)."""
        raw = data or {}
        timeline = raw.get("visual_timeline")
        if not isinstance(timeline, dict):
            timeline = None
        elif raw.get("cue_summary") and not timeline.get("cue_summary"):
            timeline = dict(timeline)
            timeline["cue_summary"] = raw["cue_summary"]
        checkpoints = raw.get("checkpoints")
        if not isinstance(checkpoints, list):
            checkpoints = None
        return cls(
            title=str(raw.get("title") or ""),
            body=str(raw.get("body") or ""),
            narration=str(raw.get("narration") or ""),
            category=str(raw.get("category") or ""),
            audio_path=raw.get("audio_path") or None,
            media_url=raw.get("media_url") or None,
            media_kind=str(raw.get("media_kind") or ""),
            presentation_style_id=str(raw.get("presentation_style_id") or ""),
            visual_timeline=timeline,
            checkpoints=checkpoints,
        )


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
    apply_harvest_presentation(slides)
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
    each with its own course_id and rebuilt composition. Slide objects are reused,
    so presentation style, visual timeline, and checkpoint metadata stay put.
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
            Each slide may also carry presentation_style_id, a visual timeline
            v1 (sentence-ranged cues, cue summary, static frame), and checkpoint
            markers. Text and diagram styles are the fallback without media.
            (aoep_shared.harvest.generate)
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
