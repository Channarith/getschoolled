#!/usr/bin/env python3
"""Generate Play Lab / Pop Quiz Toss artwork with Gemini "Nano Banana" (image generation).

Writes WebP files and a manifest.json into the Play Lab static/art folder. The game loads the
manifest at runtime and falls back to its built-in SVG/emoji art for anything that is missing, so
running this is optional and a failed run never breaks the game.

The API key is read from GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment and is never printed
or written anywhere. Source config/local.env in a subshell only for the generation run.

Usage:
  python3 scripts/generate_game_art.py --estimate          # list assets and the expected cost
  python3 scripts/generate_game_art.py                     # generate whatever is missing
  python3 scripts/generate_game_art.py --only sala-cheer   # one asset (comma list)
  python3 scripts/generate_game_art.py --force             # regenerate everything
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "subrepos/theodore_children_webcam_lab/src/theodore_children_webcam_lab/static"
OUT = STATIC / "art"
SALA_REF = STATIC / "sala-gold.png"

MODELS = [m for m in (os.environ.get("GAME_ART_MODEL"), os.environ.get("SERENITY_IMAGE_MODEL"), "gemini-nano-banana-2.1", "gemini-2.5-flash-image") if m]
PRICE_PER_IMAGE = float(os.environ.get("GAME_ART_PRICE_PER_IMAGE", "0.04"))  # USD, planning estimate
MAX_RETRIES = 2

STYLE = (
    "Warm, friendly children's-game illustration, soft 3D clay-and-gold look matching a small carved "
    "golden temple-guardian child named Sala, rich saturated colors, clean shapes, gentle lighting. "
    "Absolutely no text, letters, numbers, captions, logos or watermarks anywhere. Child safe, no weapons."
)
SPRITE_BG = "on a plain pure white background, centered, with generous empty margin, no shadow on the floor"
GREEN_BG = "on a plain flat pure bright green (#00FF00) background, centered, with generous empty margin, no shadow"
SALA_POSE = (
    "Use the attached reference of Sala exactly: same face, golden carved style, crown, medallion with the "
    "green leaf and gold S, and outfit. Keep the character identical and ONLY change the pose and expression: "
)

# name: (kind, width, height, byte cap, prompt)
ASSETS: dict[str, tuple[str, int, int, int, str]] = {
    "sala-thinking": ("sala", 384, 512, 90_000, SALA_POSE + "one finger on the chin, eyes looking up thoughtfully, curious small smile."),
    "sala-cheer": ("sala", 384, 512, 90_000, SALA_POSE + "both arms raised high in joy, big open happy smile, eyes sparkling."),
    "sala-oops": ("sala", 384, 512, 90_000, SALA_POSE + "a gentle sympathetic 'oh well, try again' look, head tilted, one hand raised kindly, soft smile (not sad)."),
    "ball-soccer": ("sprite", 256, 256, 40_000, "A single glossy soccer ball for a children's toss game, " + SPRITE_BG),
    "ball-tennis": ("sprite", 256, 256, 40_000, "A single fuzzy bright yellow-green tennis ball with white seam, " + SPRITE_BG),
    "ball-beach": ("sprite", 256, 256, 40_000, "A single colorful striped beach ball, " + SPRITE_BG),
    "ball-fire": ("sprite", 256, 256, 45_000, "A cheerful magical glowing orange fireball (a ball wrapped in friendly flames, not scary), " + SPRITE_BG),
    "ball-rainbow": ("sprite", 256, 256, 45_000, "A glowing ball made of swirling rainbow colors with tiny sparkles, " + SPRITE_BG),
    "ball-comet": ("sprite", 256, 256, 45_000, "A friendly shining comet ball with a short sparkly blue-white tail, " + SPRITE_BG),
    "target-dartboard": ("sprite", 320, 320, 50_000, "A big round bullseye target with red, cream and green rings, front view, " + SPRITE_BG),
    "target-pins": ("sprite", 320, 320, 50_000, "A cute smiling white bowling pin with two red stripes and a friendly face, complete and undamaged, " + GREEN_BG),
    "target-teddy": ("sprite", 320, 320, 50_000, "A soft cuddly teddy bear sitting and smiling, front view, " + SPRITE_BG),
    "target-bouquet": ("sprite", 320, 320, 50_000, "A bright bouquet of colorful flowers wrapped in a ribbon, " + SPRITE_BG),
    "bg-dartboard": ("bg", 960, 540, 180_000, "An EMPTY scene with no characters, no people, no animals, no toys in the center. A soft, blurred, low-contrast carnival game-booth background in warm coral and cream, with room in the middle; very calm so foreground objects stand out. 16:9 landscape."),
    "bg-pins": ("bg", 960, 540, 180_000, "An EMPTY scene with no characters, no people, no animals, no toys in the center. A soft, blurred, low-contrast bowling-alley play-room background in friendly sky blue and cream, very calm so foreground objects stand out. 16:9 landscape."),
    "bg-teddy": ("bg", 960, 540, 180_000, "An EMPTY scene with no characters, no people, no animals, no toys in the center. A soft, blurred, low-contrast cozy toy-room background in honey yellow and peach with faint star shapes, very calm so foreground objects stand out. 16:9 landscape."),
    "bg-bouquet": ("bg", 960, 540, 180_000, "An EMPTY scene with no characters, no people, no animals, no toys in the center. A soft, blurred, low-contrast sunny garden background in fresh green and pale pink, very calm so foreground objects stand out. 16:9 landscape."),
    "tut-stand": ("scene", 512, 384, 110_000, "A friendly illustration of a child standing two steps back from a laptop camera, both hands and shoulders in view, lamp lighting from the front. Simple clean scene, cream background."),
    "tut-hands": ("scene", 512, 384, 110_000, "A friendly illustration of a child with a left hand and a right hand held up, a glowing arrow from each hand pointing to its own answer bubble (left hand to the left bubble, right hand to the right bubble). Leave the bubbles blank. Cream background."),
    "tut-throw": ("scene", 512, 384, 110_000, "A friendly illustration of a child closing a fist around a glowing ball, pulling back like a slingshot, then opening the hand to send it forward; show a soft three-step motion trail. Cream background."),
    "tut-speak": ("scene", 512, 384, 110_000, "A friendly illustration of a child speaking toward a microphone with colorful sound waves while also throwing a ball toward a target; a happy star burst. Cream background."),
    "tut-win": ("scene", 512, 384, 110_000, "A friendly celebration illustration of a golden trophy with confetti, stars and a rainbow ribbon. Cream background."),
    "win-card": ("scene", 640, 360, 150_000, "A joyful celebration banner scene for winning a game: golden trophy, confetti, rainbow ribbons, stars, soft warm glow, with a clear calm center. 16:9."),
}


def api_key() -> str:
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


def _png_ref(path: Path, side: int = 768) -> bytes:
    im = Image.open(path).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def _request(model: str, prompt: str, ref: bytes | None, key: str) -> bytes:
    parts: list[dict] = [{"text": prompt}]
    if ref:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(ref).decode()}})
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode())
    for part in payload["candidates"][0]["content"]["parts"]:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError("the model returned no image")


def generate(prompt: str, ref: bytes | None, key: str, state: dict) -> bytes:
    """Try the preferred model, falling back to the next when a model id is not available."""
    last: Exception | None = None
    for model in ([state["model"]] if state.get("model") else MODELS):
        for attempt in range(3):
            try:
                raw = _request(model, prompt, ref, key)
                state["model"] = model
                return raw
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code in (400, 404):
                    break  # wrong model id for this key: try the next one
                time.sleep(2 ** attempt)
            except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                last = exc
                time.sleep(2 ** attempt)
        if state.get("model"):
            break
    raise RuntimeError(f"generation failed ({type(last).__name__}, status {getattr(last, 'code', '-')})")


def cut_out_white(im: Image.Image, tolerance: int = 40, green: bool = False) -> Image.Image:
    """Make the plain white (or green-screen) backdrop transparent by flood-filling in from the borders."""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]

    def near_white(c: tuple[int, int, int, int]) -> bool:
        if green:
            return c[1] > 150 and c[1] - max(c[0], c[2]) > 70
        return min(c[0], c[1], c[2]) >= 255 - tolerance

    while stack:
        x, y = stack.pop()
        i = y * w + x
        if seen[i] or not near_white(px[x, y]):
            continue
        seen[i] = 1
        px[x, y] = (255, 255, 255, 0)
        if x > 0:
            stack.append((x - 1, y))
        if x < w - 1:
            stack.append((x + 1, y))
        if y > 0:
            stack.append((x, y - 1))
        if y < h - 1:
            stack.append((x, y + 1))
    # Pull the cut edge in by two pixels so no halo of the old backdrop colour survives.
    im.putalpha(im.getchannel("A").filter(ImageFilter.MinFilter(5)))
    return im


def fit(im: Image.Image, w: int, h: int, kind: str, green: bool = False) -> Image.Image:
    if kind in ("sala", "sprite"):
        im = cut_out_white(im, green=green)
        bbox = im.getchannel("A").getbbox()
        if bbox:
            im = im.crop(bbox)
        scale = min((w * 0.92) / im.width, (h * 0.92) / im.height)
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2), im)
        return canvas
    # bg / scene: cover-crop to the target aspect
    im = im.convert("RGB")
    ratio = w / h
    cur = im.width / im.height
    if cur > ratio:
        nw = round(im.height * ratio)
        im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
    else:
        nh = round(im.width / ratio)
        im = im.crop((0, (im.height - nh) // 2, im.width, (im.height - nh) // 2 + nh))
    return im.resize((w, h), Image.Resampling.LANCZOS)


def encode(im: Image.Image, cap: int) -> bytes:
    for quality in (86, 78, 70, 62, 54, 46):
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=quality, method=6)
        if buf.tell() <= cap:
            return buf.getvalue()
    return buf.getvalue()


def blank_check(im: Image.Image) -> str | None:
    """Cheap automatic reject for empty or flat images; a human still views every picture."""
    small = im.convert("RGBA").resize((32, 32))
    px = list(small.get_flattened_data()) if hasattr(small, "get_flattened_data") else list(small.getdata())
    visible = [p for p in px if p[3] > 30]
    if len(visible) < 40:
        return "almost empty after cut-out"
    lum = [(p[0] + p[1] + p[2]) / 3 for p in visible]
    if max(lum) - min(lum) < 12:
        return "flat, no detail"
    return None


def write_manifest(entries: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "generator": "scripts/generate_game_art.py", "assets": entries}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def current_entries() -> dict:
    entries = {}
    for name, (kind, w, h, cap, _prompt) in ASSETS.items():
        path = OUT / f"{name}.webp"
        if path.is_file():
            data = path.read_bytes()
            entries[name] = {"kind": kind, "w": w, "h": h, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()[:16]}
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma list of asset names")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--estimate", action="store_true")
    args = ap.parse_args()

    names = [n for n in (args.only.split(",") if args.only else ASSETS) if n]
    unknown = [n for n in names if n not in ASSETS]
    if unknown:
        print(f"unknown assets: {unknown}", file=sys.stderr)
        return 2
    todo = [n for n in names if args.force or not (OUT / f"{n}.webp").is_file()]
    est = len(todo) * PRICE_PER_IMAGE
    print(f"{len(todo)} of {len(names)} assets to generate; planning estimate ${est:.2f} "
          f"(${PRICE_PER_IMAGE:.3f}/image, up to {MAX_RETRIES} retries each; set GAME_ART_PRICE_PER_IMAGE to refine)")
    if args.estimate:
        for n in todo:
            print(f"  {n}  {ASSETS[n][0]}  {ASSETS[n][1]}x{ASSETS[n][2]}")
        return 0
    key = api_key()
    if not key:
        print("No GEMINI_API_KEY / GOOGLE_API_KEY in the environment: nothing generated. "
              "The game keeps its built-in SVG/emoji art.", file=sys.stderr)
        return 3

    OUT.mkdir(parents=True, exist_ok=True)
    sala_ref = _png_ref(SALA_REF) if SALA_REF.is_file() else None
    state: dict = {}
    failed: list[str] = []
    for name in todo:
        kind, w, h, cap, prompt = ASSETS[name]
        full = f"{prompt}\n\n{STYLE}"
        ok = False
        for attempt in range(MAX_RETRIES + 1):
            try:
                raw = generate(full, sala_ref if kind == "sala" else None, key, state)
                im = fit(Image.open(io.BytesIO(raw)), w, h, kind, green="#00FF00" in prompt)
                problem = blank_check(im) if kind in ("sala", "sprite") else None
                if problem:
                    print(f"  {name}: rejected ({problem}), attempt {attempt + 1}")
                    continue
                data = encode(im, cap)
                (OUT / f"{name}.webp").write_bytes(data)
                print(f"  {name}: {len(data) // 1024} KB (model {state.get('model')})")
                ok = True
                break
            except Exception as exc:  # noqa: BLE001 - report and move on; the game has fallbacks
                print(f"  {name}: {exc}", file=sys.stderr)
                if "generation failed" in str(exc) and attempt >= 1:
                    break
        if not ok:
            failed.append(name)
    write_manifest(current_entries())
    total = sum(e["bytes"] for e in current_entries().values())
    print(f"manifest written: {len(current_entries())} assets, {total // 1024} KB total; failed: {failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
