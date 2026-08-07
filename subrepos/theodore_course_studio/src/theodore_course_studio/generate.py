"""Build Theodore-ready courses from incorporate-labeled sources + page reviews."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from .corpus import default_data_dir, load_corpus_index
from .extract import extract_document
from .review_store import ReviewStore
from .types import CategoryId, CourseSlide, QualityLabel, StudioCourse


def _clean_block(text: str, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _narration_for(title: str, body: str) -> str:
    lead = title.strip() or "Next point"
    detail = body.strip()
    if not detail:
        return f"{lead}. Let's take a moment with this idea."
    # Keep spoken length teachable (~2 sentences).
    sentences = re.split(r"(?<=[.!?])\s+", detail)
    spoken = " ".join(sentences[:2])
    return f"{lead}. {spoken}"


class CourseBuilder:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or default_data_dir()
        self._courses_dir = self._data_dir / "courses"
        self._courses_dir.mkdir(parents=True, exist_ok=True)
        self._reviews = ReviewStore(data_dir=self._data_dir)

    def list_courses(self) -> list[StudioCourse]:
        courses: list[StudioCourse] = []
        for path in sorted(self._courses_dir.glob("*.course.json")):
            courses.append(StudioCourse.model_validate_json(path.read_text(encoding="utf-8")))
        return courses

    def get_course(self, course_id: str) -> StudioCourse | None:
        path = self._courses_dir / f"{course_id}.course.json"
        if not path.is_file():
            return None
        return StudioCourse.model_validate_json(path.read_text(encoding="utf-8"))

    def save_course(self, course: StudioCourse) -> Path:
        path = self._courses_dir / f"{course.course_id}.course.json"
        path.write_text(course.model_dump_json(indent=2), encoding="utf-8")
        return path

    def build_from_sources(
        self,
        *,
        source_ids: list[str] | None = None,
        category: CategoryId | None = None,
        title: str | None = None,
        max_slides: int = 20,
        only_incorporate: bool = True,
    ) -> StudioCourse:
        docs = load_corpus_index(self._data_dir)
        if not docs:
            raise ValueError("corpus index empty — run training scan first")
        chosen = []
        for doc in docs:
            if category and doc.category != category:
                continue
            if source_ids and doc.source_id not in source_ids:
                continue
            if only_incorporate and doc.quality_label not in {
                QualityLabel.GOOD,
                QualityLabel.BETTER,
            }:
                continue
            if doc.quality_label is QualityLabel.BAD:
                continue
            chosen.append(doc)
        if source_ids:
            # Preserve caller order when explicit ids provided.
            order = {sid: i for i, sid in enumerate(source_ids)}
            chosen.sort(key=lambda d: order.get(d.source_id, 999))
        if not chosen:
            raise ValueError("no matching incorporate sources")

        slides: list[CourseSlide] = []
        used_sources: list[str] = []
        for doc in chosen:
            used_sources.append(doc.source_id)
            extracted = extract_document(doc.path)
            page_reviews = {
                p.page_index: p for p in self._reviews.pages_for(doc.source_id)
            }
            for page in extracted.pages:
                review = page_reviews.get(page.index)
                reject = bool(
                    (review and review.marked_reject)
                    or (review is None and page.marked_reject_hint)
                )
                if reject:
                    continue
                body = _clean_block(page.text)
                if len(body) < 40:
                    continue
                title_text = (page.title or f"{doc.title_guess} · p{page.index + 1}")[:140]
                slides.append(
                    CourseSlide(
                        index=len(slides),
                        title=title_text,
                        body=body,
                        narration=_narration_for(title_text, body),
                        source_page=page.index,
                        keep=True,
                        tags=[doc.category.value, doc.quality_label.value],
                    )
                )
                if len(slides) >= max_slides:
                    break
            if len(slides) >= max_slides:
                break

        if not slides:
            raise ValueError("no keepable pages after reject filtering")

        cat = category or chosen[0].category
        course = StudioCourse(
            course_id=f"course-{uuid.uuid4().hex[:10]}",
            title=title
            or f"{cat.value.replace('_', ' ').title()} — studio lesson",
            category=cat,
            source_ids=used_sources,
            slides=slides,
            created_at_ms=int(time.time() * 1000),
            status="ready",
        )
        self.save_course(course)
        # Side-car training summary for later main-app promotion.
        summary = {
            "course_id": course.course_id,
            "sources": used_sources,
            "slide_count": len(slides),
            "policy": "filename Good/Better + page not marked reject",
        }
        (self._courses_dir / f"{course.course_id}.build.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return course
