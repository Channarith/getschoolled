#!/usr/bin/env python3
"""Harvester worker entrypoint — see services/harvester/RUNBOOK.txt."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

# Allow running from a clean checkout without manually setting PYTHONPATH.
_REPO = Path(__file__).resolve().parents[4]
for _p in (_REPO / "packages" / "shared" / "src", Path(__file__).resolve().parents[1]):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from aoep_shared.harvest import (  # noqa: E402
    GENERATION_INSTRUCTIONS,
    CatalogUpsertStore,
    Checkpoint,
    CourseTags,
    HarvestCritic,
    HarvestPipeline,
    HarvestQueue,
    SourceSpec,
    export_course_package,
    extract,
    extract_file,
    generate_course,
    harvest_loop,
    infer_harvest_metadata,
    merge_tags,
)

DEFAULT_OUT_DIR = _REPO / "output" / "harvest"
DEFAULT_SEEDS = _REPO / "seeds" / "harassment-training.jsonl"


def _resolve_repo_path(path: str | Path) -> Path:
    """Resolve a repo-relative path regardless of the process cwd."""
    p = Path(path).expanduser()
    if p.is_file():
        return p.resolve()
    under_repo = (_REPO / p).resolve()
    if under_repo.is_file():
        return under_repo
    return p.resolve() if p.is_absolute() else under_repo


def mock_fetcher(spec: SourceSpec) -> str:
    return spec.meta.get("body", f"sample course material for {spec.url}")


def simple_extractor(spec: SourceSpec, raw: str) -> dict:
    return {"title": spec.title or spec.url, "text": raw, "subject": spec.subject}


def load_seeds(path: str | None) -> list[SourceSpec]:
    if not path:
        return [
            SourceSpec("https://oer.example/algebra", license="cc-by", subject="math"),
            SourceSpec("https://oer.example/biology", license="cc0", subject="biology"),
        ]
    seeds_path = _resolve_repo_path(path)
    if not seeds_path.is_file():
        return [
            SourceSpec("https://oer.example/algebra", license="cc-by", subject="math"),
            SourceSpec("https://oer.example/biology", license="cc0", subject="biology"),
        ]
    specs = []
    for line in seeds_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            specs.append(SourceSpec(**d))
    return specs


def _extract_doc(args: argparse.Namespace):
    """Read and normalize input into an ExtractedDoc."""
    if args.source_type == "database":
        if not args.query:
            raise SystemExit("--query is required for --source-type database")
        return extract("database", None, default_title=args.title or "Database course",
                       db_path=args.generate, query=args.query,
                       heading_column=args.heading_column)
    if args.source_type:
        p = Path(args.generate)
        data = p.read_bytes() if args.source_type in ("pdf", "pptx", "docx") \
            else p.read_text(encoding="utf-8", errors="replace")
        return extract(args.source_type, data, default_title=args.title or p.stem)
    return extract_file(args.generate, default_title=args.title)


def _resolve_subject_and_tags(args: argparse.Namespace, doc):
    """RAG + taxonomy inference, with optional CLI overrides."""
    inferred = None
    if not args.no_auto_tags:
        inferred = infer_harvest_metadata(doc, repo_root=_REPO)
        print(json.dumps(inferred.to_dict(), indent=2), file=sys.stderr)
        print(f"\nAuto-tags: {inferred.rationale}\n", file=sys.stderr)
    extra = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    subject, tags = merge_tags(
        inferred,
        subject=args.subject,
        access_tier=args.access_tier,
        price_usd=args.price,
        career_path=args.career_path,
        linkedin_job_id=args.linkedin_job,
        core_fundamental=True if args.core else None,
        extra_labels=extra,
    )
    return subject, tags


def _generate(args: argparse.Namespace):
    """Generate a scored, tagged course from a local source for review."""
    doc = _extract_doc(args)
    subject, tags = _resolve_subject_and_tags(args, doc)
    return generate_course(doc, subject=subject, fmt=args.fmt, tags=tags,
                           source=str(args.generate))


def _emit_course(course, *, out_dir: str, with_media: bool = False) -> None:
    """Export a generated course package to disk."""
    from aoep_shared.harvest.export import ensure_pptx_available

    try:
        ensure_pptx_available()
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc

    pkg = export_course_package(
        course, out_dir, write_pptx=True, with_media=with_media, repo_root=_REPO,
    )
    if not pkg.pptx_path or not pkg.pptx_path.is_file():
        raise SystemExit(
            f"harvest export failed to write required .pptx under {out_dir}"
        )
    summary = {
        "course_id": pkg.course_id,
        "title": pkg.title,
        "subject": pkg.subject,
        "slides": len(course.slides),
        "composition_score": pkg.composition_score,
        "tags": course.tags.to_dict() if course.tags else {},
        "output_dir": str(pkg.output_dir),
        "course_json": str(pkg.course_json_path) if pkg.course_json_path else None,
        "pptx": str(pkg.pptx_path) if pkg.pptx_path else None,
    }
    if with_media:
        manifest = Path(out_dir) / "media_manifest.json"
        summary["media_manifest"] = str(manifest) if manifest.is_file() else None
        examples = sum(1 for s in course.slides if s.category == "example")
        summary["example_slides"] = examples
        summary["slides_with_audio"] = sum(1 for s in course.slides if s.audio_path)
        summary["slides_with_video"] = sum(1 for s in course.slides if s.media_url)
    print(json.dumps(summary, indent=2), file=sys.stderr)
    print(f"\nWrote {len(course.slides)}-slide course to {out_dir}", file=sys.stderr)
    if pkg.course_json_path:
        print(f"  JSON : {pkg.course_json_path}", file=sys.stderr)
    if pkg.pptx_path:
        print(f"  PPTX : {pkg.pptx_path}", file=sys.stderr)


def _list_harvest_packages(out_dir: Path, *, limit: int = 5) -> list[dict]:
    """Return recent crawl packages under ``out_dir/courses/``."""
    courses_dir = out_dir / "courses"
    if not courses_dir.is_dir():
        return []
    rows: list[dict] = []
    for course_dir in sorted(
        (p for p in courses_dir.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        jsons = sorted(course_dir.glob("*.course.json"))
        if not jsons:
            continue
        course_json = jsons[0]
        from aoep_shared.harvest.export import resolve_course_pptx

        pptx = resolve_course_pptx(course_json)
        rows.append({
            "course_id": course_dir.name,
            "course_json": str(course_json),
            "pptx": str(pptx) if pptx else None,
            "present": (
                "python3 scripts/present_course.py "
                f"\"{course_json}\" --with-media --persona davis"
            ),
        })
        if len(rows) >= limit:
            break
    return rows


def _crawl(args: argparse.Namespace) -> int:
    """Online crawl: discover → fetch → generate → RAG index (background-safe)."""
    from aoep_shared.harvest.crawl import open_crawl_session
    from aoep_shared.harvest.discovery import load_env_seeds, load_seeds_file
    from aoep_shared.harvest.export import ensure_pptx_available

    try:
        ensure_pptx_available()
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc

    session = open_crawl_session(
        out_dir=args.out_dir,
        repo_root=_REPO,
        with_media=args.with_media,
    )
    if args.topic and not args.seeds_only:
        n = session.enqueue_topic(args.topic, include_portals=not args.no_portals)
        print(f"Enqueued {n} seeds for topic {args.topic!r}", file=sys.stderr)
    elif args.topic and args.seeds_only:
        print(f"Skipping --topic discovery (--seeds-only); use --seeds or compliance seeds file", file=sys.stderr)
    if args.seeds:
        seeds_path = _resolve_repo_path(args.seeds)
        if not seeds_path.is_file():
            raise SystemExit(
                f"seeds file not found: {args.seeds!r} "
                f"(resolved: {seeds_path})\n"
                f"Bundled example: {DEFAULT_SEEDS}"
            )
        n_seeds = session.enqueue_seeds(load_seeds_file(seeds_path))
        print(f"Enqueued {n_seeds} seeds from {seeds_path}", file=sys.stderr)
    if getattr(args, "retry_errors", False):
        n_retry = session.corpus.reset_queue_state("error", new_state="pending")
        if n_retry:
            print(f"Re-queued {n_retry} previously failed URLs", file=sys.stderr)
    env_seeds = load_env_seeds()
    if env_seeds:
        session.enqueue_seeds(env_seeds)

    interval = max(5, int(args.interval))
    batch = args.max_items or 5
    while True:
        metrics = session.run_once(max_items=batch)
        summary = {**metrics.to_dict(), "corpus": session.corpus.stats()}
        packages = _list_harvest_packages(Path(args.out_dir))
        if packages:
            summary["packages"] = packages
        print(json.dumps(summary, indent=2), flush=True)
        if args.once:
            break
        if args.daemon:
            time.sleep(interval)
        else:
            break
    return 0


def _corpus_search(args: argparse.Namespace) -> int:
    from aoep_shared.harvest.corpus_store import HarvestCorpusStore

    store = HarvestCorpusStore()
    hits = store.search(args.corpus_search, top_k=args.top_k, subject=args.subject)
    print(json.dumps([
        {
            "score": h.score,
            "title": h.title,
            "heading": h.heading,
            "subject": h.subject,
            "url": h.source_url,
            "body": h.body[:400],
            "course_id": h.course_id,
        }
        for h in hits
    ], indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Harvester: crawl OER sources or generate courses from local files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--seeds", default=None,
        help=f"JSONL of SourceSpec rows (repo-relative ok; bundled: {DEFAULT_SEEDS.relative_to(_REPO)})",
    )
    ap.add_argument("--checkpoint", default=None, help="checkpoint JSON path")
    ap.add_argument("--max-items", type=int, default=None)
    ap.add_argument("--once", action="store_true", help="drain the queue once and exit")
    ap.add_argument("--generate", default=None, metavar="PATH",
                    help="generate a scored/tagged course from a local file/DB")
    ap.add_argument("--critique", default=None, metavar="PATH",
                    help="generate from PATH then print the critique report")
    ap.add_argument("--instructions", action="store_true",
                    help="print the content-generation recipe and exit")
    ap.add_argument("--source-type", default=None,
                    help="text|html|pdf|pptx|docx|database (else inferred)")
    ap.add_argument("--subject", default=None,
                    help="override inferred subject (default: RAG + taxonomy)")
    ap.add_argument("--fmt", default="lecture",
                    help="lecture|hands_on|tutorial|video|article")
    ap.add_argument("--title", default=None)
    ap.add_argument("--query", default=None, help="SQL for --source-type database")
    ap.add_argument("--heading-column", default=None)
    ap.add_argument("--no-auto-tags", action="store_true",
                    help="disable RAG/taxonomy auto-tagging")
    ap.add_argument("--access-tier", default=None,
                    help="override inferred tier (free|basic|pro|premium|enterprise)")
    ap.add_argument("--price", type=float, default=None,
                    help="override inferred price_usd")
    ap.add_argument("--career-path", default=None, help="override e.g. data-scientist")
    ap.add_argument("--linkedin-job", default=None, help="LinkedIn job id")
    ap.add_argument("--core", action="store_true",
                    help="force core-fundamental (else inferred)")
    ap.add_argument("--tags", default=None, help="comma-separated extra labels")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), metavar="DIR",
                    help=f"export .course.json + .pptx (default: {DEFAULT_OUT_DIR})")
    ap.add_argument("--with-media", action="store_true",
                    help="export per-slide narration audio + demo-video refs (media_manifest.json)")
    ap.add_argument("--crawl", action="store_true",
                    help="online crawl: discover OER/search seeds, fetch, generate, RAG index")
    ap.add_argument("--topic", default=None,
                    help="with --crawl: discover seeds for this topic (repeatable)")
    ap.add_argument("--daemon", action="store_true",
                    help="with --crawl: run forever (background harvest loop)")
    ap.add_argument("--interval", type=int, default=60,
                    help="seconds between crawl batches in --daemon mode (default 60)")
    ap.add_argument("--no-portals", action="store_true",
                    help="with --crawl --topic: skip curated OER portal seeds")
    ap.add_argument("--seeds-only", action="store_true",
                    help="with --crawl: do not enqueue --topic discovery (only --seeds)")
    ap.add_argument("--retry-errors", action="store_true",
                    help="with --crawl: re-queue URLs that previously failed with state=error")
    ap.add_argument("--corpus-search", default=None, metavar="QUERY",
                    help="search the harvest corpus (FTS/RAG) and print hits")
    ap.add_argument("--top-k", type=int, default=8, help="max hits for --corpus-search")
    args = ap.parse_args(argv)

    if args.instructions:
        print(GENERATION_INSTRUCTIONS)
        return 0

    if args.corpus_search:
        return _corpus_search(args)

    if args.crawl:
        return _crawl(args)

    if args.critique:
        args.generate = args.critique
        course = _generate(args)
        report = HarvestCritic().review(course)
        print(json.dumps(report.to_dict(), indent=2))
        _emit_course(course, out_dir=args.out_dir, with_media=args.with_media)
        return 0

    if args.generate:
        course = _generate(args)
        _emit_course(course, out_dir=args.out_dir, with_media=args.with_media)
        return 0

    queue = HarvestQueue()
    queue.enqueue_many(load_seeds(args.seeds))
    store = CatalogUpsertStore()
    pipeline = HarvestPipeline(store)
    checkpoint = Checkpoint.load(args.checkpoint)
    batch_id = uuid.uuid4().hex[:8]

    metrics = harvest_loop(
        queue, pipeline, fetcher=mock_fetcher, extractor=simple_extractor,
        batch_id=batch_id, checkpoint=checkpoint, max_items=args.max_items,
    )
    print(json.dumps({
        "batch": batch_id, "ingested": metrics.ingested, "upserted": metrics.upserted,
        "updated": metrics.updated, "dropped_license": metrics.dropped_license,
        "catalog_size": len(store.items),
    }))
    if not args.once:
        time.sleep(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
