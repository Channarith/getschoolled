#!/usr/bin/env python3
"""Stage a small, validated subset of a translation library for baking into an image.

The curriculum and identity images read AOEP_COURSE_TRANSLATION_DIR. Shipping all
~7000 files (334 MB) in both images is wasteful, so this copies only what you pick:

  python3 scripts/stage_translations.py ~/getschoolled/data/_incoming_kalel \\
      --languages km,vi,th,es,zh --courses audio --target data/_staged_audio

It runs the validator first and copies only files whose verdict is "ship" (or those
in --manifest, a shippable.json from scripts/validate_translations.py). Nothing in
the source folder is changed. The target gets the files plus manifest.json with
sizes and sha256, and a size report is printed (raw bytes, gzip estimate, and the
estimated image impact; a Docker layer is compressed, so use the gzip number).

  --courses audio   only the audio catalog courses (default)
  --courses all     every course in the library
  --courses FILE    one course id per line
  --tar OUT.tgz     also write a tar.gz of the staged folder (for rsync / Docker ADD)
  --dry-run         report only, copy nothing

Wiring a staged folder into an image is a separate, reviewed change: this script
never edits a Dockerfile.
"""
import argparse
import gzip
import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "shared" / "src"))
from aoep_shared.translation_validate import validate_library  # noqa: E402


def audio_course_ids() -> set:
    try:
        from aoep_shared.audio_courses import build_catalog

        return {c.id for c in build_catalog("en", "en") if not c.id.startswith("lang-")}
    except Exception:  # catalog needs optional data; fall back to the id convention
        return set()


def catalog_sources() -> dict:
    """English text per audio course, so counts, numbers and truncation are checked."""
    try:
        from aoep_shared.audio_courses import build_catalog

        return {
            c.id: [{"heading": s.heading, "text": s.text} for s in c.segments]
            for c in build_catalog("en", "en")
            if not c.id.startswith("lang-")
        }
    except Exception:
        return {}


def pick_courses(spec: str, library_courses: list) -> set:
    if spec == "all":
        return set(library_courses)
    if spec == "audio":
        ids = audio_course_ids()
        return {c for c in library_courses if c in ids} if ids else {c for c in library_courses if c.startswith("audio-")}
    return {line.strip() for line in Path(spec).read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return str(n)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path, help="library to read: <root>/<course_id>/<lang>.json")
    ap.add_argument("--target", type=Path, default=Path("data/_staged_translations"))
    ap.add_argument("--languages", default="", help="comma list, default all languages present")
    ap.add_argument("--courses", default="audio")
    ap.add_argument("--manifest", type=Path, help="shippable.json from validate_translations.py (skips re-validating)")
    ap.add_argument("--tar", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-mb", type=float, default=0, help="refuse to stage more than this many MB (raw)")
    args = ap.parse_args()
    root = args.root.expanduser()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    if args.manifest:
        shippable = json.loads(args.manifest.read_text(encoding="utf-8"))
        validated = None
    else:
        report = validate_library(root, sources=catalog_sources() or None)
        shippable, validated = report["shippable"], report["verdicts"]
    langs = {x for x in args.languages.split(",") if x}
    courses = pick_courses(args.courses, sorted({s["course_id"] for s in shippable}))
    chosen = [s for s in shippable if s["course_id"] in courses and (not langs or s["language"] in langs)]

    raw = gz = 0
    per_lang: dict = {}
    for item in chosen:
        data = (root / item["path"]).read_bytes()
        item["gz_bytes"] = len(gzip.compress(data, 6))
        raw += len(data)
        gz += item["gz_bytes"]
        d = per_lang.setdefault(item["language"], {"files": 0, "bytes": 0, "gz_bytes": 0})
        d["files"] += 1
        d["bytes"] += len(data)
        d["gz_bytes"] += item["gz_bytes"]

    print(f"library: {root}")
    if validated is not None:
        print(f"validator verdicts over the whole library: {validated}")
    print(f"selected {len(chosen)} files from {len({c['course_id'] for c in chosen})} courses ({args.courses}), languages: {', '.join(sorted(per_lang)) or '-'}")
    print(f"{'LANG':<5} {'FILES':>6} {'RAW':>10} {'GZIP':>10}")
    for lang, d in sorted(per_lang.items()):
        print(f"{lang:<5} {d['files']:>6} {human(d['bytes']):>10} {human(d['gz_bytes']):>10}")
    print(f"TOTAL {len(chosen):>6} {human(raw):>10} {human(gz):>10}")
    print(f"image impact: about +{human(gz)} compressed per image that bakes this in (+{human(raw)} unpacked on disk)")
    if args.max_mb and raw > args.max_mb * 1024 * 1024:
        print(f"refusing: {human(raw)} is over --max-mb {args.max_mb}", file=sys.stderr)
        return 3
    if args.dry_run or not chosen:
        return 0

    target = args.target
    target.mkdir(parents=True, exist_ok=True)
    for item in chosen:
        dest = target / item["course_id"] / f"{item['language']}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / item["path"], dest)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != item.get("sha256", hashlib.sha256(dest.read_bytes()).hexdigest()):
            print(f"checksum mismatch after copy: {dest}", file=sys.stderr)
            return 4
    manifest = {
        "source": str(root),
        "courses": args.courses,
        "languages": sorted(per_lang),
        "files": [{k: v for k, v in c.items() if k in ("course_id", "language", "bytes", "gz_bytes", "sha256", "segments", "source")} for c in chosen],
        "totals": {"files": len(chosen), "bytes": raw, "gz_bytes": gz},
        "note": "machine translations that passed the automated checks; not human reviewed",
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"staged into {target} (manifest.json written)")
    if args.tar:
        with tarfile.open(args.tar, "w:gz") as tar:
            tar.add(target, arcname=".")
        print(f"wrote {args.tar} ({human(args.tar.stat().st_size)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
