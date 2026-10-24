#!/usr/bin/env python3
"""Sort an existing translation library into keep / stale / unverifiable. Never edits the source folder.

  python3 scripts/translation_migrate.py ~/getschoolled/data/_incoming_kalel --out data/_migrated/kalel
  python3 scripts/translation_migrate.py DIR --out OUT --studio        # also verify Course Studio courses
  python3 scripts/translation_migrate.py DIR --out OUT --dry-run       # counts only

  keep          the file matches today's English. Either it already has provenance, or it is backfilled:
                same segment count, every number from the English present, validator says ship.
                Written to OUT/<course>/<lang>.json with provenance.backfilled = true.
  stale         the course is in the current catalog but the file does not match it (made from the
                old padded English, wrong script, loops...). Copied to OUT/_stale/ with a reason, never shipped.
  unverifiable  no current English exists for this course (not in the audio catalog), so nothing can be
                checked. Copied to OUT/_unverified/. Do not ship these without a source to check against.

The source folder is only read. OUT is created if needed; existing files in OUT are overwritten.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
for extra in (ROOT / "subrepos" / "theodore_course_studio" / "src",):
    if extra.is_dir():
        sys.path.insert(0, str(extra))

from aoep_shared import translation_v2 as v2  # noqa: E402
from aoep_shared.translation_validate import scan_library  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--languages", default="", help="comma list; default every language found")
    ap.add_argument("--studio", action="store_true", help="also verify Course Studio courses against their current narration")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sources = {s.course_id: s for s in v2.audio_sources()}
    if args.studio:
        for s in v2.studio_sources():
            sources.setdefault(s.course_id, s)
    wanted = {x.strip() for x in args.languages.split(",") if x.strip()}
    files, stray = scan_library(args.root)

    counts: dict = defaultdict(Counter)
    reasons: dict = defaultdict(Counter)
    rows = []
    for path, lang in files:
        if lang == "en" or (wanted and lang not in wanted):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            record = None
        course = path.parent.name
        verdict, upgraded, why = v2.migrate_record(record, sources.get(course), lang)
        counts[lang][verdict] += 1
        reasons[verdict][why.split(";")[0][:70]] += 1
        rows.append({"course_id": course, "language": lang, "verdict": verdict, "why": why})
        if args.dry_run:
            continue
        if verdict == "keep" and upgraded is not None:
            dest = args.out / course / f"{lang}.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(upgraded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            folder = "_stale" if verdict == "stale" else "_unverified"
            dest = args.out / folder / course / f"{lang}.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

    total = Counter()
    print(f"{'LANG':<5} {'KEEP':>6} {'STALE':>7} {'UNVERIFIED':>11}")
    for lang, c in sorted(counts.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"{lang:<5} {c['keep']:>6} {c['stale']:>7} {c['unverifiable']:>11}")
        total.update(c)
    print(f"{'ALL':<5} {total['keep']:>6} {total['stale']:>7} {total['unverifiable']:>11}   ({sum(total.values())} files, {len(sources)} current courses)")
    for verdict in ("stale", "unverifiable"):
        print(f"\ntop reasons ({verdict}):")
        for why, n in reasons[verdict].most_common(6):
            print(f"  {n:>5}  {why}")
    if stray:
        print(f"\n{len(stray)} stray files ignored (partial/lock/odd names)")
    if not args.dry_run:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "migration.json").write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwrote {args.out}/ (kept files, _stale/, _unverified/, migration.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
