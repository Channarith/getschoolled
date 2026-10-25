#!/usr/bin/env python3
"""Pre-render the home-page mascot lines in the default Salane voice (edge-tts) as static mp3 clips.

  python3 scripts/render_landing_voice.py [--out apps/web/public/landing-voice] [--check]

Needs edge-tts >= 7.3.1 (Microsoft rejects older clients) and network. Clips are named by the same hash the player uses
(tts_bakeoff.demo_voice.clip_hash) and listed in <out>/salane/index.json. Existing clips are kept. --check only verifies
that every line has a clip. Internal reference: edge-tts is an unofficial client of Microsoft's Edge Read Aloud service;
the licensed route to the same voices is Azure AI Speech.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tts_bakeoff.demo_voice.clip_hash import clip_hash, normalize  # noqa: E402

LINES = ROOT / "apps" / "web" / "app" / "lib" / "landingVoiceLines.json"
OUT = ROOT / "apps" / "web" / "public" / "landing-voice"


async def _render(text: str, voice: str, path: Path) -> None:
    import edge_tts

    path.parent.mkdir(parents=True, exist_ok=True)
    await edge_tts.Communicate(text, voice, rate="-2%").save(str(path))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    cfg = json.loads(LINES.read_text(encoding="utf-8"))
    voice_dir = Path(args.out) / cfg["voice"]
    clips: dict[str, list[str]] = {}
    missing = 0
    for row in cfg["lines"]:
        lang, text = row["lang"].split("-")[0], normalize(row["text"])
        h = clip_hash(lang, text)
        path = voice_dir / lang / f"{h}.mp3"
        if not path.exists() or path.stat().st_size < 2000:
            if args.check:
                print(f"missing {lang} {h}: {text[:50]}")
                missing += 1
                continue
            asyncio.run(_render(text, cfg["default_edge_voice"][lang], path))
            print(f"rendered {lang} {h} ({path.stat().st_size} bytes)")
        clips.setdefault(lang, []).append(h)
    if not args.check:
        index = {"voice": cfg["voice"], "engine": "edge-tts", "ext": "mp3",
                 "edge_voice": cfg["default_edge_voice"], "clips": {k: sorted(v) for k, v in clips.items()}}
        voice_dir.mkdir(parents=True, exist_ok=True)
        (voice_dir / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
