"""24/7 online harvest crawl: discover → fetch → generate → index → export."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .corpus_store import HarvestCorpusStore
from .critique import HarvestCritic
from .discovery import discover_topic
from .extractors import extract
from .fetcher import extract_links, fetch_url
from .generate import (
    MAX_SLIDES_PER_LESSON,
    generate_course,
    partition_course_into_lessons,
)
from .knowledge_bridge import default_packs_dir, facts_from_course, write_knowledge_pack
from .queue_store import PersistentHarvestQueue
from .sources import SourceSpec, is_allowed
from .themes import resolve_slide_theme
from .worker import HarvestWorker


@dataclass
class CrawlMetrics:
    discovered: int = 0
    fetched: int = 0
    generated: int = 0
    indexed_chunks: int = 0
    errors: int = 0
    skipped_license: int = 0

    def to_dict(self) -> Dict:
        return {
            "discovered": self.discovered,
            "fetched": self.fetched,
            "generated": self.generated,
            "indexed_chunks": self.indexed_chunks,
            "errors": self.errors,
            "skipped_license": self.skipped_license,
        }


@dataclass
class CrawlSession:
    corpus: HarvestCorpusStore
    queue: PersistentHarvestQueue
    out_dir: Path
    repo_root: Path
    with_media: bool = True
    expand_links: bool = True
    max_slides_per_lesson: int = MAX_SLIDES_PER_LESSON
    metrics: CrawlMetrics = field(default_factory=CrawlMetrics)

    def enqueue_topic(self, topic: str, *, include_portals: bool = True) -> int:
        specs = discover_topic(topic, include_portals=include_portals)
        n = self.queue.enqueue_many(specs)
        self.metrics.discovered += n
        return n

    def enqueue_seeds(self, specs) -> int:
        n = self.queue.enqueue_many(specs)
        self.metrics.discovered += n
        return n

    def _fetch(self, spec: SourceSpec) -> bytes:
        data, st = fetch_url(spec)
        spec.source_type = st
        return data

    def _process_record(self, spec: SourceSpec, raw: bytes) -> dict:
        title = spec.title or spec.url
        doc = extract(
            spec.source_type,
            raw,
            default_title=title,
        )
        subject = spec.subject or "general"
        base_course = generate_course(doc, subject=subject, source=spec.url)
        report = HarvestCritic().review(base_course)
        if not report.passed and report.grade in ("D", "F"):
            return {"status": "rejected", "grade": report.grade, "url": spec.url}

        # Split oversized scraped material (often 100s-1000s of slides) into
        # ~20-30 minute lessons. Small sources stay a single lesson.
        lessons = partition_course_into_lessons(
            base_course, max_slides=self.max_slides_per_lesson,
        )

        from .export import export_course_package

        # Source-level bookkeeping (once per URL, across all its lessons).
        full_text = "\n\n".join(f"{s.title}\n{s.body}" for s in base_course.slides)
        chash = hashlib.sha256(raw).hexdigest()
        self.corpus.upsert_source(
            url=spec.url,
            license=spec.license,
            subject=base_course.subject,
            title=base_course.title,
            source_type=spec.source_type,
            content_hash=chash,
            status="ingested",
            meta={
                "grade": report.grade,
                "composition_score": base_course.composition_score,
                "lesson_count": len(lessons),
            },
        )
        chunks = self.corpus.index_document(
            url=spec.url,
            title=base_course.title,
            text=full_text,
            subject=base_course.subject,
            course_id=base_course.course_id,
        )
        self.metrics.indexed_chunks += chunks

        lesson_out: list[dict] = []
        for lesson in lessons:
            theme = resolve_slide_theme(
                title=lesson.title,
                subject=lesson.subject,
                tags=lesson.tags.label_list() if lesson.tags else (),
                fmt=lesson.fmt,
            )
            course_dir = self.out_dir / "courses" / lesson.course_id
            course_dir.mkdir(parents=True, exist_ok=True)
            pkg = export_course_package(
                lesson, course_dir, write_pptx=True, with_media=self.with_media,
                repo_root=self.repo_root,
            )
            if not pkg.pptx_path or not pkg.pptx_path.is_file():
                raise RuntimeError(
                    f"harvest export missing required .pptx for {lesson.course_id} "
                    f"(expected under {course_dir})"
                )
            media_manifest = {}
            mf = course_dir / "media_manifest.json"
            if mf.is_file():
                media_manifest = json.loads(mf.read_text(encoding="utf-8"))
            lesson_text = "\n\n".join(f"{s.title}\n{s.body}" for s in lesson.slides)
            tags_dict = lesson.tags.to_dict() if lesson.tags else {}
            tags_dict = {
                **tags_dict,
                "lesson_index": lesson.lesson_index,
                "lesson_count": lesson.lesson_count,
            }
            self.corpus.save_course(
                course_id=lesson.course_id,
                url=spec.url,
                title=lesson.title,
                subject=lesson.subject,
                composition_score=lesson.composition_score,
                json_path=str(pkg.course_json_path or ""),
                pptx_path=str(pkg.pptx_path or ""),
                theme=theme.to_dict(),
                media=media_manifest,
                tags=tags_dict,
                full_text=lesson_text,
            )
            self.metrics.generated += 1
            lesson_out.append({
                "course_id": lesson.course_id,
                "title": lesson.title,
                "lesson_index": lesson.lesson_index,
                "lesson_count": lesson.lesson_count,
                "slides": len(lesson.slides),
                "output_dir": str(course_dir),
                "course_json": str(pkg.course_json_path or ""),
                "pptx": str(pkg.pptx_path or ""),
            })

        # Knowledge pack once from the full source (facts don't need per-lesson split).
        facts = facts_from_course(base_course, default_domains=(base_course.subject,))
        if facts:
            pack_dir = default_packs_dir()
            pack_dir.mkdir(parents=True, exist_ok=True)
            write_knowledge_pack(
                facts,
                pack_dir / f"harvest_{base_course.course_id}.json",
                pack_name=f"harvest_{base_course.course_id}",
            )
        base_theme = resolve_slide_theme(
            title=base_course.title, subject=base_course.subject,
            tags=base_course.tags.label_list() if base_course.tags else (),
            fmt=base_course.fmt,
        )
        first = lesson_out[0]
        return {
            "status": "ingested",
            "course_id": base_course.course_id,
            "title": base_course.title,
            "slides": len(base_course.slides),
            "grade": report.grade,
            "lesson_count": len(lessons),
            "lessons": lesson_out,
            "theme": base_theme.to_dict(),
            "output_dir": first["output_dir"],
            "course_json": first["course_json"],
            "pptx": first["pptx"],
        }

    def _extract(self, spec: SourceSpec, raw: str | bytes) -> dict:
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        return self._process_record(spec, data)

    def _sink(self, record: dict) -> None:
        pass  # side effects in _process_record

    def build_worker(self) -> HarvestWorker:
        return HarvestWorker(
            fetcher=lambda s: self._fetch(s),
            extractor=lambda s, r: self._extract(s, r),
            sink=self._sink,
        )

    def run_once(self, *, max_items: int = 1) -> CrawlMetrics:
        self.queue.load_pending()
        worker = self.build_worker()
        processed = 0
        while processed < max_items:
            spec = self.queue.dequeue()
            if spec is None:
                break
            if not is_allowed(spec.license):
                self.metrics.skipped_license += 1
                self.queue.mark_done(spec, status="skipped_license")
                processed += 1
                continue
            try:
                status = worker.process(spec)
                if status == "error":
                    self.metrics.errors += 1
                if status == "ingested":
                    self.metrics.fetched += 1
                    if self.expand_links and spec.source_type == "html":
                        try:
                            raw = self._fetch(spec)
                            html = raw.decode("utf-8", errors="replace")
                            for link in extract_links(html, base_url=spec.url, max_links=8):
                                child = SourceSpec(
                                    url=link,
                                    license=spec.license,
                                    subject=spec.subject,
                                    source_type="html",
                                    meta={"parent": spec.url},
                                )
                                self.queue.enqueue(child)
                        except Exception:
                            pass
                self.queue.mark_done(spec, status=status)
            except Exception:
                self.metrics.errors += 1
                self.queue.mark_done(spec, status="error")
            processed += 1
        return self.metrics


@dataclass
class CrawlLimits:
    """Budget for a long, paced (hourly) crawl of many pages."""
    daemon: bool = False
    interval_s: int = 60          # seconds between batches (normal pacing)
    max_total: int = 0            # stop after N pages ingested this run (0 = unlimited)
    max_seconds: float = 0.0      # stop after this wall-clock time (0 = unlimited)
    per_hour: int = 0             # cap pages ingested per rolling hour (0 = unlimited)
    keep_waiting: bool = False    # keep running after the queue drains (wait for seeds)
    hour_s: float = 3600.0        # length of the "hour" window (override for tests)


def next_crawl_action(
    *,
    pages_total: int,
    made_progress: bool,
    queue_pending: int,
    elapsed_s: float,
    hour_pages: int,
    hour_elapsed_s: float,
    limits: CrawlLimits,
) -> tuple[str, str, float]:
    """Decide what a long crawl loop should do after a batch.

    Returns ``(action, reason, seconds)`` where action is ``"stop"`` or
    ``"sleep"``. Pure + deterministic so the pacing/stop policy is unit-testable
    without any network or a running crawl.
    """
    if limits.max_total and pages_total >= limits.max_total:
        return ("stop", "max_total", 0.0)
    if limits.max_seconds and elapsed_s >= limits.max_seconds:
        return ("stop", "max_hours", 0.0)
    drained = queue_pending <= 0 and not made_progress
    if drained and not limits.keep_waiting:
        return ("stop", "drained", 0.0)
    if not limits.daemon:
        return ("stop", "single_pass", 0.0)
    if limits.per_hour and hour_pages >= limits.per_hour:
        wait = max(1.0, limits.hour_s - hour_elapsed_s)
        return ("sleep", "hourly_cap", wait)
    return ("sleep", "interval", float(max(1, limits.interval_s)))


def open_crawl_session(
    *,
    out_dir: str | Path = "output/harvest",
    corpus_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    with_media: bool = True,
    max_slides_per_lesson: int = MAX_SLIDES_PER_LESSON,
) -> CrawlSession:
    import os

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if corpus_path is None:
        env = os.environ.get("AOEP_HARVEST_CORPUS_DB", "").strip()
        corpus_path = Path(env) if env else out / "harvest_corpus.db"
    corpus = HarvestCorpusStore(corpus_path)
    root = repo_root or Path.cwd()
    return CrawlSession(
        corpus=corpus,
        queue=PersistentHarvestQueue(corpus),
        out_dir=out,
        repo_root=root,
        with_media=with_media,
        max_slides_per_lesson=max_slides_per_lesson,
    )
