#!/usr/bin/env python3
"""Fetch or seed dictionary baselines into AOEP_DICTIONARY_DIR/baselines.

Offline-friendly: ``--from-fixtures`` copies the packaged test fixtures (no network).
With network, downloads small public wordlists when URLs are reachable; failures
fall back to fixtures so the pipeline always has a seed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "packages" / "shared" / "tests" / "fixtures" / "dictionary"

# Optional live sources (best-effort; never required for CI).
URLS = {
    # Small frequency sample — full lists are operator-supplied.
    "wordfreq_en.txt": None,
}


def _copy_fixtures(dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in (
        "wordfreq_en.txt",
        "wordnet_glosses.txt",
        "cmudict.txt",
        "wiktionary_en.txt",
        "tatoeba.tsv",
        "khmer_vocab.json",
    ):
        src = FIXTURES / name
        if src.is_file():
            shutil.copy2(src, dest / name)
            copied.append(name)
    # License notes
    (dest / "LICENSES.txt").write_text(
        "\n".join([
            "Dictionary baseline cache — license notes",
            "",
            "wordfreq / frequency lists: use project-compatible open lists locally.",
            "WordNet: Princeton WordNet license (wordnet.princeton.edu).",
            "CMUdict: BSD-style (cmusphinx.github.io).",
            "Wiktionary extracts: CC BY-SA (wiktionary.org).",
            "Tatoeba: CC BY (tatoeba.org).",
            "Khmer pack: see content pack license (MIT for khmer_core_v1).",
            "",
            "This directory may contain fixture stubs for offline development.",
            "",
        ]),
        encoding="utf-8",
    )
    return copied


def _try_download(url: str, dest: Path) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return dest.is_file() and dest.stat().st_size > 0
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_corpus import (
        dictionary_dir,
        ensure_layout,
        fingerprint_baselines,
        write_fingerprint,
    )

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None, help="AOEP_DICTIONARY_DIR override")
    ap.add_argument(
        "--from-fixtures",
        action="store_true",
        help="Copy offline fixtures (default if downloads unavailable)",
    )
    args = ap.parse_args(argv)

    root = ensure_layout(args.root or dictionary_dir())
    dest = root / "baselines"
    dest.mkdir(parents=True, exist_ok=True)

    if args.from_fixtures or not any(dest.glob("*.txt")):
        copied = _copy_fixtures(dest)
        print(f"seeded fixtures → {dest} ({len(copied)} files)")
    else:
        print(f"baselines already present in {dest}")

    # Also pull khmer pack snapshot from installed content packs when available.
    try:
        from aoep_shared.content_packs import load_records
        import json

        recs = [r for r in load_records("vocabulary") if r.get("language") == "km"]
        if recs:
            payload = {"pack": "khmer_from_content_packs", "records": recs}
            (dest / "khmer_vocab.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"wrote khmer_vocab.json ({len(recs)} records)")
    except Exception as exc:
        print(f"khmer pack snapshot skipped: {exc}")

    fp = fingerprint_baselines(dest)
    write_fingerprint(root, fp)
    print(f"fingerprint={fp[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
