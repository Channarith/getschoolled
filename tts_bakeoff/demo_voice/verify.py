"""Check every manifest clip has audio for each active voice.  python3 -m tts_bakeoff.demo_voice.verify [--assets DIR] [--voice ID]

Exit 0 when complete for the languages the voice's model supports; 1 and a per-language count of what is missing."""
from __future__ import annotations

import argparse
import json
import sys

from .render import assets_dir, clip_path, load_manifest

SUPPORTED = {"voxcpm2": {"en", "es", "zh", "vi", "th", "km", "sw", "hi"}}


def missing(root, manifest, voice_id: str, model: str) -> list[dict]:
    sup = SUPPORTED.get(model)
    return [c for c in manifest["clips"]
            if (not sup or c["lang"] in sup) and not clip_path(root, voice_id, c["lang"], c["hash"]).exists()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets")
    ap.add_argument("--voice")
    args = ap.parse_args(argv)
    root, m = assets_dir(args.assets), load_manifest()
    bad = 0
    for v in m["voices"]:
        if args.voice and v["id"] != args.voice:
            continue
        miss = missing(root, m, v["id"], v.get("model", ""))
        by: dict[str, int] = {}
        for c in miss:
            by[c["lang"]] = by.get(c["lang"], 0) + 1
        total = len([c for c in m["clips"] if not SUPPORTED.get(v.get("model", "")) or c["lang"] in SUPPORTED[v["model"]]])
        print(f"{v['id']}: {total - len(miss)}/{total} clips present" + (f"; missing {json.dumps(by)}" if by else ""))
        bad += len(miss)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
