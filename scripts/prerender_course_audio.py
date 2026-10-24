#!/usr/bin/env python3
"""Render On the Go course narration with CosyVoice and store it by content hash.

Run on the DGX Spark with CosyVoice healthy (scripts/run_cosyvoice_local.sh):

  export COSYVOICE_URL=http://127.0.0.1:9880
  python3 scripts/prerender_course_audio.py --dry-run
  python3 scripts/prerender_course_audio.py --limit 3 --out output/prerender

Files land in --out as <hash>.wav, plus manifest.jsonl. Re-running skips what is
already there, so it can be stopped and resumed. Point the speech gateway at the
folder with AOEP_PRERENDER_AUDIO_DIR. Never arms a timer; run it by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from aoep_shared import audio_courses, cosyvoice_tts, prerender_audio  # noqa: E402

WORDS_PER_MINUTE = 150.0


def plan(locale: str, training_locale: str, course_ids: list[str] | None, out: Path):
    """Yield one job per unique narration line."""
    seen: set[str] = set()
    for row in audio_courses.build_catalog(locale, training_locale):
        if course_ids and row.id not in course_ids:
            continue
        course = audio_courses.get_course(row.id, locale, training_locale)
        if not course:
            continue
        language = course.body_locale or training_locale
        for index, seg in enumerate(course.segments):
            line = prerender_audio.narration_line(seg.heading, seg.text)
            key = prerender_audio.audio_key(line, language)
            if key in seen:
                continue
            seen.add(key)
            yield {"key": key, "line": line, "language": language, "course": course.id, "index": index,
                   "done": prerender_audio.find(line, language, out) is not None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.environ.get(prerender_audio.ENV_DIR, "output/prerender"))
    ap.add_argument("--locale", default="en", help="UI locale for the catalog")
    ap.add_argument("--training-locale", default="", help="course language (default: same as --locale)")
    ap.add_argument("--course", action="append", help="only this course id (repeatable)")
    ap.add_argument("--limit", type=int, default=0, help="render at most N new files (0 = all)")
    ap.add_argument("--speaker", default=os.environ.get("COSYVOICE_DEFAULT_SPK", ""))
    ap.add_argument("--dry-run", action="store_true", help="count work and estimate GPU time; render nothing")
    ap.add_argument("--assume-rtf", type=float, default=0.5, help="real-time factor for the estimate")
    args = ap.parse_args(argv)

    out = Path(args.out)
    training = args.training_locale or args.locale
    jobs = list(plan(args.locale, training, args.course, out))
    todo = [j for j in jobs if not j["done"]]
    words = sum(len(j["line"].split()) for j in todo)
    audio_hours = words / WORDS_PER_MINUTE / 60
    print(f"unique passages {len(jobs)}, already rendered {len(jobs) - len(todo)}, to render {len(todo)}")
    print(f"~{words} words = ~{audio_hours:.1f} h of audio; at RTF {args.assume_rtf} about {audio_hours * args.assume_rtf:.1f} GPU-hours")
    if args.dry_run:
        return 0

    base_url = os.environ.get("COSYVOICE_URL", "")
    if not cosyvoice_tts.cosyvoice_configured(base_url):
        print("COSYVOICE_URL is not set", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    rendered = failed = 0
    with (out / "manifest.jsonl").open("a", encoding="utf-8") as manifest:
        for job in todo:
            if args.limit and rendered >= args.limit:
                break
            started = time.monotonic()
            try:
                audio, ctype = cosyvoice_tts.synthesize(
                    job["line"], base_url=base_url, language=job["language"], speaker=args.speaker, timeout=180.0)
            except Exception as exc:  # keep going; the next run retries it
                failed += 1
                print(f"FAIL {job['course']}#{job['index']}: {exc}", file=sys.stderr)
                continue
            elapsed = time.monotonic() - started
            ext = ".mp3" if "mpeg" in ctype else ".wav"
            tmp = out / f"{job['key']}.part"
            tmp.write_bytes(audio)
            tmp.replace(out / f"{job['key']}{ext}")
            rendered += 1
            manifest.write(json.dumps({
                "key": job["key"], "course": job["course"], "index": job["index"], "language": job["language"],
                "words": len(job["line"].split()), "bytes": len(audio), "seconds": round(elapsed, 2),
                "speaker": args.speaker, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }) + "\n")
            manifest.flush()
            print(f"ok {job['course']}#{job['index']} {elapsed:.1f}s")
    print(f"rendered {rendered}, failed {failed}")
    return 1 if failed and not rendered else 0


if __name__ == "__main__":
    raise SystemExit(main())
