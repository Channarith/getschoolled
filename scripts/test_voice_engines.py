#!/usr/bin/env python3
"""Try all TTS engines (edge, chatterbox, xtts, elevenlabs) with one sample."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "packages" / "shared" / "src"))

from aoep_shared.meeting.clone_tts import (  # noqa: E402
    engine_status,
    synthesize_chatterbox,
    synthesize_cloned,
    synthesize_elevenlabs,
    synthesize_xtts,
)
from aoep_shared.meeting.natural_tts import (  # noqa: E402
    play_audio_file,
    synthesize_neural,
    tts_engine_status,
)
from aoep_shared.meeting.voice_profiles import get_voice_profile  # noqa: E402


DEFAULT_TEXT = (
    "Welcome to today's lesson. In the next few minutes we'll walk through "
    "the key ideas together, with examples you can try on your own."
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", required=True, help="reference WAV/MP3 for clone engines")
    ap.add_argument("--text", default=DEFAULT_TEXT, help="phrase to synthesize")
    ap.add_argument("--voice-id", default="", help="registered voice id (loads profile + sample)")
    ap.add_argument("--out-dir", default="output/voice_tests", help="write test clips here")
    ap.add_argument("--play", action="store_true", help="play each successful clip")
    ap.add_argument("--engines", default="edge,chatterbox,xtts,elevenlabs,clone",
                    help="comma-separated engines to try")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sample = Path(args.sample)
    if args.voice_id:
        prof = get_voice_profile(args.voice_id, repo_root=_REPO)
        if prof:
            sample = prof.resolved_sample(repo_root=_REPO)
    if not sample.is_file():
        raise SystemExit(f"sample not found: {sample}")

    text = args.text.strip()
    engines = [e.strip().lower() for e in args.engines.split(",") if e.strip()]
    results = {"status": engine_status(), "tts": tts_engine_status(), "runs": []}

    for name in engines:
        out = out_dir / f"{name}.mp3"
        ok = False
        detail = ""
        try:
            if name == "edge":
                ok = synthesize_neural(text, out, voice="en-US-JennyNeural")
                detail = "edge-tts neural (no clone)"
            elif name == "chatterbox":
                ok = synthesize_chatterbox(text, sample, out)
            elif name == "xtts":
                ok = synthesize_xtts(text, sample, out)
            elif name == "elevenlabs":
                prof = get_voice_profile(args.voice_id, repo_root=_REPO) if args.voice_id else None
                el_id = (prof.elevenlabs_voice_id if prof else "") or ""
                ok = synthesize_elevenlabs(text, out, voice_id=el_id, sample_path=sample)
            elif name == "clone":
                prof = get_voice_profile(args.voice_id, repo_root=_REPO) if args.voice_id else None
                el_id = prof.elevenlabs_voice_id if prof else ""
                ok, used = synthesize_cloned(
                    text, out, sample_path=sample, engine="clone", voice_id=el_id,
                )
                detail = f"used={used}" if ok else "no clone backend reachable"
            else:
                detail = "unknown engine"
        except Exception as exc:
            detail = str(exc)
        row = {"engine": name, "ok": ok, "output": str(out) if ok else None, "detail": detail}
        results["runs"].append(row)
        if ok and args.play:
            print(f"Playing {name}…", file=sys.stderr)
            play_audio_file(out)

    print(json.dumps(results, indent=2))
    failed = [r for r in results["runs"] if not r["ok"]]
    return 0 if not failed or len(failed) < len(results["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
