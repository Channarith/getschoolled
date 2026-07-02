#!/usr/bin/env python3
"""Register a custom presenter voice from a reference recording."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "packages" / "shared" / "src"))

from aoep_shared.meeting.clone_tts import elevenlabs_add_voice  # noqa: E402
from aoep_shared.meeting.voice_profiles import VoiceProfile, save_voice_profile  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Register a cloned presenter voice from a WAV/MP3 sample.",
    )
    ap.add_argument("voice_id", help="short id, e.g. bayon or instructor_jane")
    ap.add_argument("sample", help="path to 6-60s clean reference recording")
    ap.add_argument("--label", default="", help="display name (default: voice_id title case)")
    ap.add_argument("--language", default="en", help="BCP-47 language (default en)")
    ap.add_argument("--engine", default="clone",
                    choices=("clone", "chatterbox", "xtts", "elevenlabs"),
                    help="preferred clone backend (clone = try all configured)")
    ap.add_argument("--present-mode", default="", help="optional presentation arc preset")
    ap.add_argument("--elevenlabs", action="store_true",
                    help="upload sample to ElevenLabs and store voice_id in profile")
    ap.add_argument("--out-dir", default="", help="override voices root (default: repo voices/)")
    args = ap.parse_args(argv)

    sample = Path(args.sample).expanduser()
    if not sample.is_file():
        raise SystemExit(f"sample not found: {sample}")

    vid = args.voice_id.strip().lower().replace(" ", "_").replace("-", "_")
    label = args.label.strip() or vid.replace("_", " ").title()
    out_root = Path(args.out_dir) if args.out_dir else _REPO / "voices"
    dest = out_root / vid
    dest.mkdir(parents=True, exist_ok=True)

    ext = sample.suffix.lower() or ".wav"
    dest_sample = dest / f"sample{ext}"
    if sample.resolve() != dest_sample.resolve():
        shutil.copy2(sample, dest_sample)

    el_id = ""
    if args.elevenlabs or args.engine == "elevenlabs":
        el_id = elevenlabs_add_voice(label, dest_sample) or ""
        if not el_id:
            print("Warning: ElevenLabs upload failed (check ELEVENLABS_API_KEY)", file=sys.stderr)

    profile = VoiceProfile(
        id=vid,
        label=label,
        sample_path=f"sample{ext}",
        language=args.language,
        description=f"Custom cloned voice registered from {sample.name}",
        tts_engine=args.engine,
        present_mode=args.present_mode,
        elevenlabs_voice_id=el_id,
    )
    path = save_voice_profile(profile, repo_root=_REPO, out_root=out_root)
    print(json.dumps({
        "profile": str(path),
        "voice_id": vid,
        "persona": vid,
        "voice_token": profile.voice_token,
        "sample": str(dest_sample),
        "elevenlabs_voice_id": el_id or None,
        "present": (
            f'python3 scripts/present_course.py "output/harvest/algebra.course.json" '
            f"--persona {vid} --tts-engine clone --with-media"
        ),
        "test": (
            f"python3 scripts/test_voice_engines.py --sample {dest_sample} --voice-id {vid}"
        ),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
