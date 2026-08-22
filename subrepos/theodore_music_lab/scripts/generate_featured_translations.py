#!/usr/bin/env python3
"""Generate and verify committed full-line translations for featured songs."""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from theodore_music_lab.catalog import Catalog, MEANING_LANGUAGES  # noqa: E402
from theodore_music_lab.curated_lines import normalize  # noqa: E402
from theodore_music_lab.translations import _xai_translate  # noqa: E402

PACK_PATH = ROOT / "data" / "curated_lines_extra.json"
CHUNK_SIZE = 48


def chunks(rows: list[str]) -> list[list[str]]:
    return [rows[index : index + CHUNK_SIZE] for index in range(0, len(rows), CHUNK_SIZE)]


def translate_chunk(lines: list[str], language: str) -> dict[str, str]:
    pending = list(lines)
    translated: dict[str, str] = {}
    for attempt in range(3):
        if not pending:
            break
        translated.update(_xai_translate(pending, language))
        pending = [line for line in pending if normalize(line) not in translated]
        if pending:
            time.sleep(1.5 * (attempt + 1))
    return translated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--song", action="append", default=[], help="song id (repeatable)")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    catalog = Catalog()
    selected = [
        song
        for song in catalog.featured()
        if not args.song or song.song_id in set(args.song)
    ]
    if not selected:
        print("no featured songs matched", file=sys.stderr)
        return 2

    payload = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pack_lines = payload.setdefault("lines", {})
    source_by_key: dict[str, str] = {}
    for song in selected:
        for line in song.lines:
            source_by_key.setdefault(normalize(line.text), line.text)

    languages = [code for code in MEANING_LANGUAGES if code != "en"]
    jobs: list[tuple[str, list[str]]] = []
    for language in languages:
        missing = [
            source
            for key, source in source_by_key.items()
            if not str(pack_lines.get(key, {}).get(language, "")).strip()
        ]
        jobs.extend((language, batch) for batch in chunks(missing))
        print(f"{language}: {len(missing)} missing line(s)")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(translate_chunk, batch, language): (language, batch)
            for language, batch in jobs
        }
        for future in as_completed(futures):
            language, batch = futures[future]
            result = future.result()
            for key, text in result.items():
                pack_lines.setdefault(key, {})[language] = text
            print(f"  {language}: translated {len(result)}/{len(batch)}")

    failures: list[str] = []
    for key in source_by_key:
        for language in languages:
            if not str(pack_lines.get(key, {}).get(language, "")).strip():
                failures.append(f"{language}:{key}")

    PACK_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    if failures:
        print(f"{len(failures)} translations still missing:", file=sys.stderr)
        for failure in failures[:30]:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"complete: {len(source_by_key)} unique lines x {len(languages)} languages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
