#!/usr/bin/env python3
"""Export approved staging rows to vocabulary/slang content-pack JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_corpus import (
        approved_entries,
        dictionary_dir,
        ensure_layout,
        load_staging,
        to_slang_pack_record,
        to_vocabulary_pack_record,
    )

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Pack root (default: AOEP_DICTIONARY_DIR/export or AOEP_CONTENT_PACKS)",
    )
    ap.add_argument(
        "--ship",
        action="store_true",
        help="Also write a curated EN core pack under packages/shared data/content_packs",
    )
    args = ap.parse_args(argv)

    root = ensure_layout(args.root or dictionary_dir())
    out_root = args.out or (root / "export")
    vocab_dir = out_root / "vocabulary"
    slang_dir = out_root / "slang"
    vocab_dir.mkdir(parents=True, exist_ok=True)
    slang_dir.mkdir(parents=True, exist_ok=True)

    en_entries = approved_entries(load_staging(root, "en"))
    km_entries = approved_entries(load_staging(root, "km"))

    en_vocab = []
    for e in en_entries:
        # English study pack (target=lemma)
        rec = to_vocabulary_pack_record(e, target_lang="en")
        if rec:
            en_vocab.append(rec)
        # KM translation pack rows when translation present
        km_rec = to_vocabulary_pack_record(e, target_lang="km")
        if km_rec:
            en_vocab.append(km_rec)

    for e in km_entries:
        rec = to_vocabulary_pack_record(e, target_lang="km")
        if rec:
            en_vocab.append(rec)

    # Dedup by id
    seen = set()
    vocab_records = []
    for r in en_vocab:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        vocab_records.append(r)

    slang_records = []
    for e in en_entries:
        s = to_slang_pack_record(e)
        if s:
            slang_records.append(s)

    vocab_path = vocab_dir / "dictionary_export_v1.json"
    slang_path = slang_dir / "dictionary_export_slang_v1.json"
    vocab_path.write_text(
        json.dumps(
            {
                "pack": "dictionary_export_v1",
                "description": "Approved dictionary corpus export (EN + KM).",
                "license": "mixed-open-baselines",
                "records": vocab_records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    slang_path.write_text(
        json.dumps(
            {
                "pack": "dictionary_export_slang_v1",
                "description": "Approved slang/idiom rows from dictionary corpus.",
                "records": slang_records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"vocabulary={len(vocab_records)} → {vocab_path}")
    print(f"slang={len(slang_records)} → {slang_path}")

    if args.ship:
        # Ship a small EN core seed into the packaged content packs (top frequent literals).
        from aoep_shared.dictionary_corpus import CLOSED_CLASS

        ship_dir = (
            ROOT
            / "packages"
            / "shared"
            / "src"
            / "aoep_shared"
            / "data"
            / "content_packs"
            / "vocabulary"
        )
        ship_dir.mkdir(parents=True, exist_ok=True)
        core = []
        for r in vocab_records:
            if r.get("language") != "en":
                continue
            lemma = str(r.get("en") or r.get("target") or "").strip().lower()
            if not lemma or lemma in CLOSED_CLASS or " " in lemma:
                continue
            # Prefer content words that have a gloss, IPA, or non-core category.
            if not (r.get("gloss_en") or r.get("ipa") or r.get("category") != "core"):
                if int(r.get("freq_rank") or 999999) > 3000:
                    continue
            core.append(r)
        core = sorted(core, key=lambda r: int(r.get("freq_rank") or 999999))[:200]
        ship_path = ship_dir / "en_core_dictionary_v1.json"
        ship_path.write_text(
            json.dumps(
                {
                    "pack": "en_core_dictionary_v1",
                    "description": "Curated English core vocabulary from the dictionary corpus.",
                    "license": "MIT",
                    "records": core,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"shipped={len(core)} → {ship_path}")

    print(f"Tip: export AOEP_CONTENT_PACKS={out_root} to load without shipping.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
