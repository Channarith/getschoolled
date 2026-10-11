#!/usr/bin/env python3
"""Async CosyVoice synthesis for approved dictionary lemmas (raw only, never gold)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


async def _run(entries, language: str, root: Path, concurrency: int, speaker: str) -> dict:
    from aoep_shared.dictionary_audio import synthesize_entry_cosyvoice
    from aoep_shared.dictionary_corpus import save_staging
    from aoep_shared.cosyvoice_tts import cosyvoice_configured

    if not cosyvoice_configured():
        return {"ok": False, "error": "COSYVOICE_URL not set", "written": 0}

    sem = asyncio.Semaphore(max(1, concurrency))
    out = []
    written = 0

    async def one(e):
        nonlocal written
        async with sem:
            row = await asyncio.to_thread(
                synthesize_entry_cosyvoice,
                e,
                language=language,
                text=e.lemma,
                root=root,
                speaker=speaker,
            )
            slot = row.audio.get(language)
            if slot and getattr(slot, "quality", None) == "raw":
                written += 1
            out.append(row)

    await asyncio.gather(*(one(e) for e in entries))
    # Preserve order by id map
    by_id = {e.id: e for e in out}
    merged = [by_id.get(e.id, e) for e in entries]
    save_staging(merged, root, language)
    return {"ok": True, "written": written, "total": len(entries)}


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_corpus import (
        approved_entries,
        dictionary_dir,
        ensure_layout,
        load_staging,
    )

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--language", default="en")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--speaker", default="")
    args = ap.parse_args(argv)

    root = ensure_layout(args.root or dictionary_dir())
    entries = approved_entries(load_staging(root, args.language))[: max(0, args.limit)]
    # Skip entries that already have crisp/gold
    todo = []
    for e in entries:
        slot = (e.audio or {}).get(args.language)
        q = getattr(slot, "quality", None) if slot else None
        if q in ("crisp", "gold"):
            continue
        todo.append(e)

    result = asyncio.run(_run(todo, args.language, root, args.concurrency, args.speaker))
    print(result)
    return 0 if result.get("ok") or result.get("error") == "COSYVOICE_URL not set" else 1


if __name__ == "__main__":
    raise SystemExit(main())
