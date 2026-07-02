"""24/7 online harvest crawl: discover → fetch → generate → index → export."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

from .corpus_store import HarvestCorpusStore
from .critique import HarvestCritic
from .discovery import discover_topic, load_env_seeds, load_seeds_file
from .extractors import extract
from .fetcher import extract_links, fetch_url
from .generate import generate_course
from .knowledge_bridge import default_packs_dir, facts_from_course, write_knowledge_pack
from .queue_store import PersistentHarvestQueue
from .sources import SourceSpec, is_allowed
from .themes import resolve_slide_theme
from .worker import HarvestStats, HarvestWorker


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
        course = generate_course(doc, subject=subject, source=spec.url)
        report = HarvestCritic().review(course)
        if not report.passed and report.grade in ("D", "F"):
            return {"status": "rejected", "grade": report.grade, "url": spec.url}

        theme = resolve_slide_theme(
            title=course.title,
            subject=course.subject,
            tags=course.tags.label_list() if course.tags else (),
            fmt=course.fmt,
        )
        from .export import export_course_package

        course_dir = self.out_dir / "courses" / course.course_id
        course_dir.mkdir(parents=True, exist_ok=True)
        pkg = export_course_package(
            course, course_dir, write_pptx=True, with_media=self.with_media,
            repo_root=self.repo_root,
        )
        if not pkg.pptx_path or not pkg.pptx_path.is_file():
            raise RuntimeError(
                f"harvest export missing required .pptx for {course.course_id} "
                f"(expected under {course_dir})"
            )
        media_manifest = {}
        mf = course_dir / "media_manifest.json"
        if mf.is_file():
            media_manifest = json.loads(mf.read_text(encoding="utf-8"))

        full_text = "\n\n".join(
            f"{s.title}\n{s.body}" for s in course.slides
        )
        chash = hashlib.sha256(raw).hexdigest()
        self.corpus.upsert_source(
            url=spec.url,
            license=spec.license,
            subject=course.subject,
            title=course.title,
            source_type=spec.source_type,
            content_hash=chash,
            status="ingested",
            meta={"grade": report.grade, "composition_score": course.composition_score},
        )
        chunks = self.corpus.index_document(
            url=spec.url,
            title=course.title,
            text=full_text,
            subject=course.subject,
            course_id=course.course_id,
        )
        self.metrics.indexed_chunks += chunks
        self.corpus.save_course(
            course_id=course.course_id,
            url=spec.url,
            title=course.title,
            subject=course.subject,
            composition_score=course.composition_score,
            json_path=str(pkg.course_json_path or ""),
            pptx_path=str(pkg.pptx_path or ""),
            theme=theme.to_dict(),
            media=media_manifest,
            tags=course.tags.to_dict() if course.tags else {},
            full_text=full_text,
        )
        facts = facts_from_course(course, default_domains=(course.subject,))
        if facts:
            pack_dir = default_packs_dir()
            pack_dir.mkdir(parents=True, exist_ok=True)
            write_knowledge_pack(
                facts,
                pack_dir / f"harvest_{course.course_id}.json",
                pack_name=f"harvest_{course.course_id}",
            )
        self.metrics.generated += 1
        return {
            "status": "ingested",
            "course_id": course.course_id,
            "title": course.title,
            "slides": len(course.slides),
            "grade": report.grade,
            "theme": theme.to_dict(),
            "output_dir": str(course_dir),
            "course_json": str(pkg.course_json_path or ""),
            "pptx": str(pkg.pptx_path or ""),
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


def open_crawl_session(
    *,
    out_dir: str | Path = "output/harvest",
    corpus_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    with_media: bool = True,
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
    )
