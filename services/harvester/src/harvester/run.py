#!/usr/bin/env python3
"""Harvester worker entrypoint (Phase 23) - runs 24/7 on a separate agent.

Three modes (all offline-runnable for local testing):

  crawl    (default)  Seed the queue, then run the checkpoint/resumable harvest
                      loop: fetch -> extract -> license/validation gate ->
                      idempotent batch-versioned catalog upsert. Defaults to a
                      MockFetcher; production injects an httpx fetcher and posts
                      upserts to the curriculum/catalog service.

  generate --generate PATH
                      Read a local file (text/html/pdf/pptx/docx) or a sqlite DB,
                      generate a scored + tagged course, and print the reviewable
                      JSON (slides + composition matrix + composition_score +
                      quality + tags). Use --instructions to print the recipe.

  critique --critique PATH
                      Generate from PATH then run HarvestCritic and print the
                      critique report (grade, issues, suggestions).

Config is env-driven (HARVEST_*, see config + docs/secrets.txt).
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

from aoep_shared.harvest import (
    GENERATION_INSTRUCTIONS,
    CatalogUpsertStore,
    Checkpoint,
    CourseTags,
    HarvestCritic,
    HarvestPipeline,
    HarvestQueue,
    SourceSpec,
    extract,
    extract_file,
    generate_course,
    harvest_loop,
)


def mock_fetcher(spec: SourceSpec) -> str:
    return spec.meta.get("body", f"sample course material for {spec.url}")


def simple_extractor(spec: SourceSpec, raw: str) -> dict:
    return {"title": spec.title or spec.url, "text": raw, "subject": spec.subject}


def load_seeds(path: str | None) -> list[SourceSpec]:
    if not path or not Path(path).is_file():
        # Built-in OER demo seeds (permissive licenses).
        return [
            SourceSpec("https://oer.example/algebra", license="cc-by", subject="math"),
            SourceSpec("https://oer.example/biology", license="cc0", subject="biology"),
        ]
    specs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            specs.append(SourceSpec(**d))
    return specs


def _build_tags(args: argparse.Namespace) -> CourseTags:
    return CourseTags(
        access_tier=args.access_tier,
        price_usd=args.price,
        career_path=args.career_path,
        linkedin_job_id=args.linkedin_job,
        core_fundamental=args.core,
        labels=[t.strip() for t in (args.tags or "").split(",") if t.strip()],
    )


def _generate(args: argparse.Namespace):
    """Generate a scored, tagged course from a local source for review."""
    tags = _build_tags(args)
    if args.source_type == "database":
        if not args.query:
            raise SystemExit("--query is required for --source-type database")
        doc = extract("database", None, default_title=args.title or "Database course",
                      db_path=args.generate, query=args.query,
                      heading_column=args.heading_column)
    elif args.source_type:
        p = Path(args.generate)
        data = p.read_bytes() if args.source_type in ("pdf", "pptx", "docx") \
            else p.read_text(encoding="utf-8", errors="replace")
        doc = extract(args.source_type, data, default_title=args.title or p.stem)
    else:
        doc = extract_file(args.generate, default_title=args.title)
    return generate_course(doc, subject=args.subject, fmt=args.fmt, tags=tags,
                           source=str(args.generate))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default=None, help="JSONL of SourceSpec rows")
    ap.add_argument("--checkpoint", default=None, help="checkpoint JSON path")
    ap.add_argument("--max-items", type=int, default=None)
    ap.add_argument("--once", action="store_true", help="drain the queue once and exit")
    # generate / critique
    ap.add_argument("--generate", default=None, metavar="PATH",
                    help="generate a scored/tagged course from a local file/DB")
    ap.add_argument("--critique", default=None, metavar="PATH",
                    help="generate from PATH then print the critique report")
    ap.add_argument("--instructions", action="store_true",
                    help="print the content-generation recipe and exit")
    ap.add_argument("--source-type", default=None,
                    help="text|html|pdf|pptx|docx|database (else inferred)")
    ap.add_argument("--subject", default="general")
    ap.add_argument("--fmt", default="lecture",
                    help="lecture|hands_on|tutorial|video|article")
    ap.add_argument("--title", default=None)
    # database source
    ap.add_argument("--query", default=None, help="SQL for --source-type database")
    ap.add_argument("--heading-column", default=None)
    # tags
    ap.add_argument("--access-tier", default="free",
                    help="free|basic|pro|premium|enterprise|expensive")
    ap.add_argument("--price", type=float, default=0.0)
    ap.add_argument("--career-path", default=None, help="e.g. nurse")
    ap.add_argument("--linkedin-job", default=None, help="LinkedIn job id")
    ap.add_argument("--core", action="store_true",
                    help="mark as a basic core-fundamental course (e.g. algebra)")
    ap.add_argument("--tags", default=None, help="comma-separated extra labels")
    args = ap.parse_args(argv)

    if args.instructions:
        print(GENERATION_INSTRUCTIONS)
        return 0

    if args.critique:
        args.generate = args.critique
        course = _generate(args)
        report = HarvestCritic().review(course)
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    if args.generate:
        course = _generate(args)
        print(course.to_json())
        return 0

    # Default: the crawl loop.
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
        # In production this would loop forever pulling new frontier URLs.
        time.sleep(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
