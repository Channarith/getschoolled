#!/usr/bin/env python3
"""Translate the CURRENT audio catalog so the output can ship (pipeline v2).

  python3 scripts/translate_catalog_v2.py --check                       # what is stale, translate nothing
  python3 scripts/translate_catalog_v2.py --languages km --limit 3      # small trial
  python3 scripts/translate_catalog_v2.py                               # km,th,vi,es,zh, then sw,id,el,cs, then the rest
  python3 scripts/translate_catalog_v2.py --tier 1                      # only km,th,vi,es,zh
  python3 scripts/translate_catalog_v2.py --fallback grok --fallback-cap 40   # opt in: paid API for the leftovers

Differences from translate_courses_batch.py (v1):
  * a file is reused only when its provenance (sha256 of today's English + pipeline version)
    matches and the validator still says "ship"; skip-by-name is gone;
  * failing segments are retried on a ladder of stricter settings and never written as shippable;
  * what still fails is listed in <root>/_work/ for the opt-in Grok fallback or a person.

Run it on the Spark under the resource wrapper and the GPU lock, from a worktree of main:

  scripts/gs_run.sh --gpu -- python3 scripts/translate_catalog_v2.py --root ~/.cache/aoep/course_translations_v2

NLLB must run on CUDA there (aoep_shared.devices); the script stops with the reason if it cannot.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
for extra in (ROOT / "subrepos" / "theodore_course_studio" / "src",):
    if extra.is_dir():
        sys.path.insert(0, str(extra))

from aoep_shared import translation_v2 as v2  # noqa: E402
from aoep_shared.course_translation_library import TARGET_LANGUAGES, library_dir  # noqa: E402


def pick_languages(args: argparse.Namespace) -> list[str]:
    if args.languages:
        langs = [x.strip() for x in args.languages.split(",") if x.strip()]
    elif args.tier == 1:
        langs = list(v2.TIER1)
    elif args.tier == 2:
        langs = list(v2.TIER1) + list(v2.TIER2)
    else:
        langs = v2.priority_languages()
    bad = [x for x in langs if x not in TARGET_LANGUAGES]
    if bad:
        raise SystemExit(f"unsupported language(s): {', '.join(bad)}")
    return langs


def load_sources(args: argparse.Namespace) -> list:
    sources = v2.audio_sources()
    if args.studio:
        sources += v2.studio_sources()
    if args.course:
        wanted = tuple(args.course)
        sources = [s for s in sources if s.course_id in wanted or any(w.endswith("-") and s.course_id.startswith(w) for w in wanted)]
    if args.limit:
        sources = sources[: args.limit]
    if not sources:
        raise SystemExit("no courses selected")
    return sources


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=None, help="library folder (default AOEP_COURSE_TRANSLATION_DIR or ~/.cache/aoep/course_translations)")
    ap.add_argument("--languages", default="", help="comma list; default is priority order")
    ap.add_argument("--tier", type=int, choices=(1, 2, 3), default=3, help="1 = km,th,vi,es,zh; 2 adds sw,id,el,cs; 3 = all")
    ap.add_argument("--course", action="append", help="course id (repeatable; a trailing '-' is a prefix)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--studio", action="store_true", help="also the Course Studio catalog")
    ap.add_argument("--check", action="store_true", help="list stale files and exit; translate nothing")
    ap.add_argument("--force", action="store_true", help="translate again even when the file is current")
    ap.add_argument("--no-backfilled", action="store_true", help="do not trust files whose provenance was backfilled by the migration")
    ap.add_argument("--max-rungs", type=int, default=len(v2.RUNGS), help="retry ladder length (1 to %d)" % len(v2.RUNGS))
    ap.add_argument("--batch-size", type=int, default=0, help="sentences per generate() call (default NLLB_BATCH_SIZE or 16)")
    ap.add_argument("--fallback", choices=("off", "grok"), default="off", help="paid API for segments the ladder could not fix (default off)")
    ap.add_argument("--fallback-cap", type=int, default=50, help="most segments sent to the fallback in one run")
    ap.add_argument("--price-per-mtok", type=float, default=None, help="USD per million tokens, to print a cost estimate")
    ap.add_argument("--report-dir", type=Path, default=Path("output/translation_v2"))
    ap.add_argument("--json", action="store_true", help="machine-readable --check output")
    args = ap.parse_args()

    root = args.root or library_dir()
    langs = pick_languages(args)
    sources = load_sources(args)
    accept_backfilled = not args.no_backfilled

    if args.check:
        report = v2.check_library(sources, langs, root, accept_backfilled=accept_backfilled)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"{len(sources)} courses x {len(langs)} languages in {root}")
            for key, n in sorted(report["counts"].items(), key=lambda kv: -kv[1]):
                print(f"  {key:>16}: {n}")
            for row in report["stale"][:15]:
                print(f"  stale: {row['course_id']} {row['language']} ({row['why']})")
        return 0

    engine = v2.NllbEngine(batch_size=args.batch_size or None)
    glossary = v2.Glossary.load()
    print(f"{len(sources)} courses x {len(langs)} languages ({len(sources) * len(langs)} files) -> {root}", flush=True)
    print(f"languages in order: {' '.join(langs)}; glossary v{glossary.version} ({len(glossary.terms)} terms, unreviewed)", flush=True)

    started = time.time()

    def progress(res: v2.CourseResult, done: int, total: int) -> None:
        extra = f" retried={res.retried}" if res.retried else ""
        if res.status == "needs_fallback":
            extra += f" fallback={res.fallback} ({'; '.join(res.reasons[:1])})"
        if res.status != "reused" or done % 50 == 0:
            print(f"[{done}/{total}] {res.status:14} {res.course_id} -> {res.language}{extra}", flush=True)

    stats = v2.run_catalog(sources, langs, engine, root=root, glossary=glossary, max_rungs=args.max_rungs,
                           force=args.force, accept_backfilled=accept_backfilled, progress=progress)
    minutes = (time.time() - started) / 60
    print(f"done in {minutes:.1f} min: {json.dumps(stats)}", flush=True)

    # Segments still failing: listed for the fallback or a person. Never written as shippable.
    by_id = {s.course_id: s for s in sources}
    work = v2.fallback_work(root, langs)
    if work:
        est = v2.estimate_fallback(work, by_id, args.price_per_mtok)
        print(f"{len(work)} segments still failing after the ladder. Fallback estimate: {json.dumps(est)}", flush=True)
        if args.fallback == "grok":
            from aoep_shared.course_translation_ondemand import grok_translate

            fb = v2.run_fallback(root, by_id, langs, lambda t, s, g: grok_translate(t, s, g) or "", glossary=glossary,
                                 enabled=True, cap_segments=args.fallback_cap)
            print(f"fallback: {json.dumps(fb)}", flush=True)
        else:
            print("fallback is off (--fallback grok to enable, capped by --fallback-cap).", flush=True)

    # Final validator pass over exactly what this run was asked to produce.
    from aoep_shared.translation_validate import render_text, validate_library

    report = validate_library(Path(root), {s.course_id: s.segments for s in sources}, languages=langs)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / "summary.txt").write_text(render_text(report) + "\n", encoding="utf-8")
    (args.report_dir / "stats.json").write_text(json.dumps({"run": stats, "fallback_work": len(work)}, indent=2), encoding="utf-8")
    print(render_text(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
