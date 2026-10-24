"""Snapshot EVERY edge-tts voice into tts_bakeoff/edge_voices.json (needs the edge-tts package and network).

  python3 -m tts_bakeoff.snapshot_edge_voices            # rewrite tts_bakeoff/edge_voices.json
  python3 -m tts_bakeoff.snapshot_edge_voices --print    # summary only

The committed file is what the catalog, the tests and the lab use, so nothing else needs the network. The service's own
tags (VoicePersonalities, ContentCategories) are kept as-is. Re-run it when Microsoft adds voices.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent / "edge_voices.json"


def normalize(raw: dict) -> dict:
    tag = raw.get("VoiceTag") or {}
    return {
        "name": raw["ShortName"],
        "locale": raw["Locale"],
        "gender": raw["Gender"],
        "friendly": raw.get("FriendlyName", ""),
        "status": raw.get("Status", ""),
        "personalities": list(tag.get("VoicePersonalities") or []),
        "categories": list(tag.get("ContentCategories") or []),
        "codec": raw.get("SuggestedCodec", ""),
    }


async def fetch() -> list[dict]:
    import edge_tts

    return [normalize(v) for v in await edge_tts.list_voices()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", action="store_true")
    args = ap.parse_args(argv)
    voices = sorted(asyncio.run(fetch()), key=lambda v: v["name"])
    locales = sorted({v["locale"] for v in voices})
    print(f"{len(voices)} voices, {len(locales)} locales, {len({v['locale'].split('-')[0] for v in voices})} languages")
    if args.print:
        return 0
    from .edge_catalog import SKIPPED_EXTRAS, derive

    doc = {"retrieved": time.strftime("%Y-%m-%d"), "source": "edge_tts.list_voices()", "count": len(voices),
           "skipped_extras": SKIPPED_EXTRAS, "catalog": derive(voices), "voices": voices}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
