"""Build Theodore-ready courses from incorporate-labeled sources + page reviews."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from dataclasses import dataclass

from .content_quality import analyze_document, similarity
from .corpus import default_data_dir, load_corpus_index
from .extract import extract_document
from .quality_model import QualityModel, default_model_path, load_model
from .review_store import ReviewStore
from .studio_languages import normalize_language
from .types import CategoryId, CourseSlide, QualityLabel, StudioCourse


@dataclass
class _Candidate:
    score: float
    source_id: str
    page_index: int
    title: str
    body: str
    category: str
    quality: str


def _dedupe_candidates(
    candidates: list[_Candidate], threshold: float = 0.85
) -> list[_Candidate]:
    kept: list[_Candidate] = []
    for cand in candidates:
        if any(similarity(cand.body, other.body) >= threshold for other in kept):
            continue
        kept.append(cand)
    return kept


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
    # The title is often also the body's first line (slide headings); saying it
    # twice sounds broken when spoken aloud.
    lowered_lead = lead.lower().rstrip(" .:;,-")
    lines = [ln.strip() for ln in detail.splitlines() if ln.strip()]
    if lines and lines[0].lower().rstrip(" .:;,-") == lowered_lead:
        detail = "\n".join(lines[1:]).strip() or detail
    elif detail.lower().startswith(lowered_lead) and len(lowered_lead) > 8:
        detail = detail[len(lead) :].lstrip(" .:;,-\n") or detail
    # Keep spoken length teachable (~2 sentences).
    sentences = re.split(r"(?<=[.!?])\s+", detail.replace("\n", " ").strip())
    spoken = " ".join(sentences[:2]).strip()
    return f"{lead}. {spoken}" if spoken else f"{lead}."


class CourseBuilder:
    def __init__(
        self,
        data_dir: Path | None = None,
        quality_model: QualityModel | None = None,
    ) -> None:
        self._data_dir = data_dir or default_data_dir()
        self._courses_dir = self._data_dir / "courses"
        self._courses_dir.mkdir(parents=True, exist_ok=True)
        self._reviews = ReviewStore(data_dir=self._data_dir)
        self._quality_model = quality_model
        if self._quality_model is None:
            self._quality_model = load_model(default_model_path(self._data_dir))

    @property
    def data_dir(self) -> Path:
        """Root the builder persists under; collaborators share it for isolation."""
        return self._data_dir

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
        language: str = "en",
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

        # Clean + classify pages, then rank the teachable ones.
        candidates: list[_Candidate] = []
        filtered: dict[str, int] = {}
        doc_order = {doc.source_id: i for i, doc in enumerate(chosen)}
        for doc in chosen:
            extracted = extract_document(doc.path)
            page_reviews = {
                p.page_index: p for p in self._reviews.pages_for(doc.source_id)
            }
            analysis = analyze_document(
                [(p.index, p.title, p.text) for p in extracted.pages]
            )
            raw_hints = {p.index: p.marked_reject_hint for p in extracted.pages}
            for page in analysis.pages:
                review = page_reviews.get(page.index)
                reject = bool(
                    (review and review.marked_reject)
                    or (review is None and raw_hints.get(page.index))
                )
                if reject:
                    filtered["human_reject"] = filtered.get("human_reject", 0) + 1
                    continue
                if not page.teachable:
                    filtered[page.kind.value] = filtered.get(page.kind.value, 0) + 1
                    continue
                body = _clean_block(page.body)
                if len(body) < 40:
                    filtered["too_short"] = filtered.get("too_short", 0) + 1
                    continue
                title_text = (page.title or f"{doc.title_guess} · p{page.index + 1}")[:140]
                score = 0.5
                if self._quality_model is not None:
                    score = self._quality_model.score_text(title_text, body)
                if doc.quality_label is QualityLabel.BETTER:
                    score += 0.08
                elif doc.quality_label is QualityLabel.GOOD:
                    score += 0.04
                candidates.append(
                    _Candidate(
                        score=score,
                        source_id=doc.source_id,
                        page_index=page.index,
                        title=title_text,
                        body=body,
                        category=doc.category.value,
                        quality=doc.quality_label.value,
                    )
                )

        # Drop near-duplicate policy blocks that recur across documents.
        before_dedupe = len(candidates)
        candidates = _dedupe_candidates(candidates)
        if before_dedupe - len(candidates):
            filtered["duplicate"] = before_dedupe - len(candidates)

        # Select best pages, but cap any single source so one document cannot
        # become the whole lesson.
        candidates.sort(key=lambda c: c.score, reverse=True)
        per_source_cap = max(3, -(-max_slides // max(len(chosen), 1)) * 2)
        picked: list[_Candidate] = []
        per_source: dict[str, int] = {}
        for cand in candidates:
            if len(picked) >= max_slides:
                break
            if per_source.get(cand.source_id, 0) >= per_source_cap:
                continue
            picked.append(cand)
            per_source[cand.source_id] = per_source.get(cand.source_id, 0) + 1
        # Backfill if the cap left room.
        if len(picked) < max_slides:
            chosen_keys = {(c.source_id, c.page_index) for c in picked}
            for cand in candidates:
                if len(picked) >= max_slides:
                    break
                if (cand.source_id, cand.page_index) not in chosen_keys:
                    picked.append(cand)

        # Teach in source/page order so the lesson reads as a narrative rather
        # than a ranking.
        picked.sort(key=lambda c: (doc_order.get(c.source_id, 999), c.page_index))

        slides: list[CourseSlide] = []
        used_sources: list[str] = []
        for cand in picked:
            slides.append(
                CourseSlide(
                    index=len(slides),
                    title=cand.title,
                    body=cand.body,
                    narration=_narration_for(cand.title, cand.body),
                    source_page=cand.page_index,
                    keep=True,
                    tags=[cand.category, cand.quality, f"q={cand.score:.3f}"],
                )
            )
            if cand.source_id not in used_sources:
                used_sources.append(cand.source_id)

        if not slides:
            raise ValueError(
                "no teachable pages after cleaning "
                f"(filtered: {filtered or 'nothing extracted'})"
            )

        cat = category or chosen[0].category
        lang = normalize_language(language)
        course = StudioCourse(
            course_id=f"course-{uuid.uuid4().hex[:10]}",
            title=title
            or f"{cat.value.replace('_', ' ').title()} — studio lesson",
            category=cat,
            language=lang,
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
            "language": lang,
            "filtered_pages": filtered,
            "policy": (
                "filename Good/Better + page not marked reject + content-quality "
                "filter (cover/toc/references/boilerplate) + dedupe + quality model rank"
            ),
        }
        (self._courses_dir / f"{course.course_id}.build.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return course
