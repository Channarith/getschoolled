#!/usr/bin/env python3
"""Render every sung line into the neural-voice cache, one language at a time.

"Install all voice languages" comes down to this: the clips are rendered once
with a network connection and then replay from disk forever, so Khmer, Chinese
and the rest sing even on a device whose OS has no such voice — and even offline.

    python3 scripts/prefetch_voices.py                    # every language
    python3 scripts/prefetch_voices.py --lang km --lang zh
    python3 scripts/prefetch_voices.py --song en-travel-words-audio-v1
    python3 scripts/prefetch_voices.py --lang km --dry-run

Each clip is keyed by (voice, rate, text), the same key the player asks for, so
a warmed cache is a guaranteed hit. Already-cached clips are skipped, making
re-runs cheap and resumable after a dropped connection.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from theodore_music_lab.catalog import Catalog  # noqa: E402
from theodore_music_lab.sing import sing_plan  # noqa: E402
from theodore_music_lab.translations import (  # noqa: E402
    MEANING_LANGUAGES,
    language_name,
)
from theodore_music_lab.tts import (  # noqa: E402
    TTSUnavailable,
    cache_dir,
    clip_path,
    engine_available,
    rate_percent,
    synthesize,
    voice_candidates,
    voice_for,
)

# Microsoft quietly drops audio when a long prefetch bursts too hard. A short
# pause between clips keeps Polish / Turkish / Arabic filling instead of
# failing after a few thousand earlier languages.
_CLIP_PAUSE_SEC = 0.08
_MAX_CONSECUTIVE_FAILURES = 3


def clip_cached(text: str, language: str, rate: float) -> bool:
    """True if any candidate voice already has this line on disk."""
    percent = rate_percent(rate)
    return any(
        (path := clip_path(text, voice=voice, rate=percent)).is_file()
        and path.stat().st_size > 0
        for voice in voice_candidates(language)
    )


def wanted_lines(song, language: str) -> list[tuple[str, float]]:
    """(text, rate) for every line the player would speak in this language."""
    plan = sing_plan(song, language, allow_llm=False)
    rows: list[tuple[str, float]] = []
    for row in plan["lines"]:
        text = (row.get("speak") or "").strip()
        if text:
            rows.append((text, float(row.get("rate") or 1.0)))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lang", action="append", default=[], help="language code (repeatable)"
    )
    parser.add_argument("--song", default="", help="one song id only")
    parser.add_argument(
        "--dry-run", action="store_true", help="count what is missing, render nothing"
    )
    args = parser.parse_args()

    languages = args.lang or list(MEANING_LANGUAGES)
    unknown = [code for code in languages if code not in MEANING_LANGUAGES]
    if unknown:
        print(f"unknown language(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    songs = [s for s in Catalog().featured() if not args.song or s.song_id == args.song]
    if not songs:
        print("no featured songs matched", file=sys.stderr)
        return 2

    if not args.dry_run and not engine_available():
        print(
            "edge-tts is not installed (or MUSIC_LAB_TTS=off); "
            "install it with: pip install 'edge-tts==7.2.8'",
            file=sys.stderr,
        )
        return 2

    print(f"cache: {cache_dir()}")
    total_missing = 0
    total_rendered = 0
    failures: list[str] = []
    for language in languages:
        voice = voice_for(language)
        missing: list[tuple[str, float]] = []
        for song in songs:
            for text, rate in wanted_lines(song, language):
                if not clip_cached(text, language, rate):
                    missing.append((text, rate))
        total_missing += len(missing)
        label = f"{language_name(language)} ({voice})"
        if not missing:
            print(f"  {label}: cached")
            continue
        if args.dry_run:
            print(f"  {label}: {len(missing)} clip(s) to render")
            continue
        print(f"  {label}: rendering {len(missing)} clip(s)")
        consecutive = 0
        lang_failed = 0
        for index, (text, rate) in enumerate(missing):
            try:
                synthesize(text, language, rate=rate)
                total_rendered += 1
                consecutive = 0
            except TTSUnavailable as exc:
                lang_failed += 1
                consecutive += 1
                failures.append(f"{language}: {exc}")
                if consecutive >= _MAX_CONSECUTIVE_FAILURES:
                    print(
                        f"    stopping {language} after {consecutive} consecutive "
                        f"failures ({index + 1}/{len(missing)})",
                        file=sys.stderr,
                    )
                    break
            if index + 1 < len(missing):
                time.sleep(_CLIP_PAUSE_SEC)
        if lang_failed and consecutive < _MAX_CONSECUTIVE_FAILURES:
            print(f"    {language}: finished with {lang_failed} failed clip(s)")

    if args.dry_run:
        print(f"\n{total_missing} clip(s) missing from the cache")
        return 0
    print(f"\nrendered {total_rendered} clip(s)")
    if failures:
        print("failures:")
        for message in failures[:12]:
            print(f"  - {message}")
        if len(failures) > 12:
            print(f"  … and {len(failures) - 12} more")
        failed_langs = sorted({row.split(":", 1)[0] for row in failures})
        flags = " ".join(f"--lang {code}" for code in failed_langs)
        print(
            f"\nresume just the failed languages (cache is resumable):\n"
            f"  python3 scripts/prefetch_voices.py {flags}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
