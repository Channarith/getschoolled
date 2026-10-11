#!/usr/bin/env python3
"""Generate Serenity lip/blink keyframes with Gemini Nano Banana (image edit).

Uses the rest portrait as a reference so pose/medallion stay locked while only
mouth or eyelids change. Writes PNGs into Course Studio avatar_static/serenity_kf/
and mirrors them under docs/brand/serenity/keyframes/.

Usage:
  . .venv/bin/activate && set -a && . config/local.env && set +a
  python3 scripts/generate_serenity_keyframes.py
  python3 scripts/generate_serenity_keyframes.py --only aa,blink,half
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REST = (
    ROOT
    / "subrepos/theodore_course_studio/src/theodore_course_studio/avatar_static"
    / "presenter_serenity.png"
)
OUT_STUDIO = (
    ROOT
    / "subrepos/theodore_course_studio/src/theodore_course_studio/avatar_static"
    / "serenity_kf"
)
OUT_DOCS = ROOT / "docs/brand/serenity/keyframes"

MODEL = os.environ.get("SERENITY_IMAGE_MODEL", "gemini-nano-banana-2.1")
API = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

_BASE = (
    "Edit this exact holographic AI teacher character (Serenity). "
    "Keep pose, kneeling stance, medallion with silver S and green leaf, "
    "crown with AI crest, blue hologram look, camera angle, framing, and background identical. "
    "Do NOT add any text, letters, captions, watermarks, or labels anywhere on the medallion or body. "
    "Do NOT change clothing, hands, medallion design, or hologram overlays. "
)

FRAMES: dict[str, str] = {
    "aa": _BASE
    + "ONLY change the mouth: open naturally as if saying 'ah' — sculpted lips, slight jaw drop, "
    "hint of upper teeth. Eyes stay fully open looking forward. Soft friendly expression.",
    "oh": _BASE
    + "ONLY change the mouth: rounded lips as if saying 'oh'/'oo' — natural lip purse, small round opening. "
    "Eyes stay fully open looking forward.",
    "ee": _BASE
    + "ONLY change the mouth: wide smile-talk as if saying 'ee' — lips stretched sideways, teeth lightly visible. "
    "Eyes stay fully open looking forward.",
    "mbp": _BASE
    + "ONLY change the mouth: lips gently pressed closed as if saying 'm'/'b'/'p' — no teeth, soft closed smile. "
    "Eyes stay fully open looking forward.",
    "half": _BASE
    + "ONLY change the mouth: lips slightly parted mid-speech (halfway open), natural and subtle. "
    "Eyes stay fully open looking forward.",
    "eyes_half": _BASE
    + "ONLY change the eyelids: lower them to the MIDPOINT of a natural blink "
    "(upper lids covering about half of each iris, lower lids slightly raised). "
    "This is a blink mid-frame, NOT a squint, NOT a smile-eyes expression. "
    "Mouth stays a soft closed smile identical to the reference. Keep head pose identical.",
    "eyes_closed": _BASE
    + "ONLY change the eyelids: close them fully in a soft natural blink "
    "(gentle curved closed lids resting over the eyes, lashes meeting). "
    "Not flat lines. Mouth stays a soft closed smile identical to the reference. "
    "Keep head pose identical.",
}

FILE_FOR = {
    "aa": "mouth_aa.png",
    "oh": "mouth_oh.png",
    "ee": "mouth_ee.png",
    "mbp": "mouth_mbp.png",
    "half": "mouth_half.png",
    "eyes_half": "eyes_half.png",
    "eyes_closed": "eyes_closed.png",
}


def _jpeg_ref(path: Path, max_side: int = 896) -> tuple[bytes, tuple[int, int]]:
    im = Image.open(path).convert("RGB")
    target = im.size
    work = im.copy()
    work.thumbnail((max_side, max_side * 2))
    buf = io.BytesIO()
    work.save(buf, format="JPEG", quality=90)
    return buf.getvalue(), target


def _generate(prompt: str, jpeg: bytes, api_key: str, retries: int = 4) -> bytes:
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpeg).decode()}},
                ]
            }
        ],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    data = json.dumps(body).encode()
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{API}?key={api_key}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                payload = json.loads(resp.read().decode())
            parts = payload["candidates"][0]["content"]["parts"]
            for part in parts:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
            raise RuntimeError(f"no image in response: {json.dumps(payload)[:400]}")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last_err = exc
            wait = 2 ** attempt
            print(f"  retry {attempt + 1}/{retries} after {exc!r}; sleep {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"generate failed: {last_err}")


def _align(raw: bytes, size: tuple[int, int]) -> Image.Image:
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    if im.size != size:
        im = im.resize(size, Image.Resampling.LANCZOS)
    return im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma list of frame keys")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    if not api_key and not args.dry_run:
        print("GEMINI_API_KEY required", file=sys.stderr)
        return 2
    if not REST.is_file():
        print(f"missing rest portrait: {REST}", file=sys.stderr)
        return 2

    wanted = [k.strip() for k in args.only.split(",") if k.strip()] or list(FRAMES)
    unknown = [k for k in wanted if k not in FRAMES]
    if unknown:
        print(f"unknown frames: {unknown}", file=sys.stderr)
        return 2

    OUT_STUDIO.mkdir(parents=True, exist_ok=True)
    OUT_DOCS.mkdir(parents=True, exist_ok=True)
    jpeg, size = _jpeg_ref(REST)
    print(f"model={MODEL} rest={REST.name} size={size} frames={wanted}")

    for key in wanted:
        name = FILE_FOR[key]
        print(f"→ {key} ({name})")
        if args.dry_run:
            continue
        raw = _generate(FRAMES[key], jpeg, api_key)
        im = _align(raw, size)
        studio_path = OUT_STUDIO / name
        docs_path = OUT_DOCS / name
        im.save(studio_path, format="PNG", optimize=True)
        im.save(docs_path, format="PNG", optimize=True)
        print(f"  wrote {studio_path.relative_to(ROOT)} ({studio_path.stat().st_size} bytes)")

    # Keep an eyes-open closed-mouth docs copy in sync with rest.
    if not args.dry_run:
        rest_im = Image.open(REST).convert("RGB")
        if rest_im.size != size:
            rest_im = rest_im.resize(size, Image.Resampling.LANCZOS)
        rest_im.save(OUT_DOCS / "eyes_open_mouth_closed.png", format="PNG", optimize=True)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
