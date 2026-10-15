#!/usr/bin/env python3
"""Generate four Salareen homepage concept backgrounds with Gemini image generation.

The API key is read only from GEMINI_API_KEY or GOOGLE_API_KEY. It is never
written to disk or sent to the web application. Use --fallback to create
deterministic local compositions when image-generation credentials are absent.

Usage:
  set -a && . config/local.env && set +a
  python3 scripts/generate_home_concept_assets.py
  python3 scripts/generate_home_concept_assets.py --fallback
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps/web/public"
OUT = PUBLIC / "landing-concepts"
REFERENCE = PUBLIC / "bayon-mark.webp"
MODEL = os.environ.get("SALAREEN_IMAGE_MODEL", "gemini-nano-banana-2.1")
API = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
SIZE = (1600, 1000)
SCREENS = ROOT / "docs/screens"

CONCEPTS = {
    "aurora-story": {
        "source": PUBLIC / "wallpapers/wisdom_bodhi.webp",
        "prompt": (
            "Create premium cinematic website background art for Salareen, an adaptive learning platform. "
            "Iridescent pearl light, translucent educational layers, warm amber and lilac aurora arcs, "
            "abundant negative space for interface text, refined editorial product photography. "
            "The supplied Salareen Bayon Buddy is only a brand reference: do not copy, alter, recolor, "
            "or place the mascot. No text, letters, logos, watermarks, temples, or religious imagery."
        ),
        "overlay": (240, 203, 255, 88),
    },
    "learning-worlds": {
        "source": PUBLIC / "themes/kids.png",
        "prompt": (
            "Create a wide playful isometric learning world for Salareen: floating science garden, language "
            "pavilion, creative game paths, tiny abstract learner silhouettes, mint sky and tangerine details, "
            "polished 3D paper-craft style, generous calm areas for web UI. The supplied mascot is only a brand "
            "reference; do not copy or modify it. No text, logos, watermarks, temples, or religious imagery."
        ),
        "overlay": (116, 238, 203, 75),
    },
    "signal-studio": {
        "source": PUBLIC / "wallpapers/surreal_dreamscape.webp",
        "prompt": (
            "Create a dark high-energy spatial learning interface background for Salareen, electric cobalt "
            "and ultraviolet signal trails, abstract audio wave, vision grid, game geometry, deep black studio, "
            "cinematic depth and clean negative space, premium technology campaign. The supplied mascot is only "
            "a brand reference; do not copy or modify it. No text, logos, watermarks, or religious imagery."
        ),
        "overlay": (25, 42, 120, 115),
    },
    "human-journal": {
        "source": PUBLIC / "wallpapers/realistic_library.webp",
        "prompt": (
            "Create warm documentary editorial background art for Salareen, a sunlit modern learning studio, "
            "natural paper and wood textures, human hands arranging study cards, coral and ink accents, candid "
            "and humane, sophisticated education magazine photography, clear areas for headlines. The supplied "
            "mascot is only a brand reference; do not copy or modify it. No text, logos, watermarks, temples, "
            "or religious imagery."
        ),
        "overlay": (245, 217, 171, 72),
    },
}


def _reference_jpeg() -> bytes:
    image = Image.open(REFERENCE).convert("RGB")
    image.thumbnail((768, 768))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def _request(prompt: str, reference: bytes, api_key: str, retries: int = 4) -> bytes:
    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(reference).decode(),
                }},
            ],
        }],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    payload = json.dumps(body).encode()
    error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            f"{API}?key={api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode())
            for part in result["candidates"][0]["content"]["parts"]:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
            raise RuntimeError("Gemini response did not contain an image")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"image generation failed: {error}")


def _fit(raw: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    return ImageOps.fit(image, SIZE, method=Image.Resampling.LANCZOS)


def _fallback(source: Path, overlay: tuple[int, int, int, int]) -> Image.Image:
    image = Image.open(source).convert("RGB")
    image = ImageOps.fit(image, SIZE, method=Image.Resampling.LANCZOS)
    image = ImageEnhance.Color(image).enhance(0.8).filter(ImageFilter.GaussianBlur(8))
    tint = Image.new("RGBA", SIZE, overlay)
    return Image.alpha_composite(image.convert("RGBA"), tint).convert("RGB")


def _font(size: int, serif: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    name = "Georgia.ttf" if serif else "Arial.ttf"
    path = Path("/System/Library/Fonts/Supplemental") / name
    return ImageFont.truetype(path, size) if path.is_file() else ImageFont.load_default()


def _review_artifacts() -> None:
    """Render stable concept boards when a browser capture is unavailable."""
    SCREENS.mkdir(parents=True, exist_ok=True)
    titles = {
        "aurora-story": ("Every mind has\nits own light.", "CINEMATIC PRODUCT NARRATIVE", (246, 240, 240)),
        "learning-worlds": ("Where do you want\nto go today?", "PLAYFUL EXPLORABLE CAMPUS", (242, 242, 218)),
        "signal-studio": ("LEARNING\nRESPONDS.", "KINETIC TECHNOLOGY SHOWCASE", (6, 7, 12)),
        "human-journal": ("We taught it\nto care.", "EDITORIAL LEARNING MANIFESTO", (242, 238, 229)),
    }
    boards: list[Image.Image] = []
    for slug, (title, label, background) in titles.items():
        board = Image.new("RGB", (1440, 960), background)
        art = Image.open(OUT / f"{slug}.webp").convert("RGB")
        art = ImageOps.fit(art, (700, 800), method=Image.Resampling.LANCZOS)
        board.paste(art, (680, 80))
        draw = ImageDraw.Draw(board)
        dark = slug == "signal-studio"
        ink = (245, 243, 250) if dark else (28, 25, 28)
        accent = (143, 255, 216) if dark else (177, 72, 62)
        draw.text((70, 55), "SALAREEN", font=_font(18), fill=ink)
        draw.text((70, 180), label, font=_font(14), fill=accent)
        draw.multiline_text((70, 235), title, font=_font(70, serif=slug != "signal-studio"), fill=ink, spacing=4)
        draw.multiline_text(
            (70, 520),
            "One adaptive tutor. Immersive practice.\nLive human connection. A path made for you.",
            font=_font(22),
            fill=ink,
            spacing=12,
        )
        draw.rounded_rectangle((70, 670, 260, 722), radius=26, fill=ink)
        draw.text((108, 685), "START FREE CLASS", font=_font(12), fill=background)
        draw.text((70, 830), f"{list(titles).index(slug) + 1:02d} / 04   HOMEPAGE CONCEPT", font=_font(12), fill=accent)
        destination = SCREENS / f"salareen_concept_{slug.split('-')[-1]}.webp"
        board.save(destination, "WEBP", quality=88, method=6)
        boards.append(board.resize((576, 384), Image.Resampling.LANCZOS))
        print(f"wrote {destination.relative_to(ROOT)}")
    gallery = Image.new("RGB", (1200, 900), (241, 237, 229))
    for index, board in enumerate(boards):
        gallery.paste(board, ((index % 2) * 600 + 12, (index // 2) * 430 + 60))
    ImageDraw.Draw(gallery).text((20, 18), "SALAREEN — FOUR HOMEPAGE FUTURES", font=_font(20), fill=(25, 22, 25))
    destination = SCREENS / "salareen_home_concepts_gallery.webp"
    gallery.save(destination, "WEBP", quality=88, method=6)
    print(f"wrote {destination.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=tuple(CONCEPTS))
    parser.add_argument("--fallback", action="store_true")
    parser.add_argument("--review-artifacts", action="store_true")
    args = parser.parse_args()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    if not args.fallback and not api_key:
        parser.error("GEMINI_API_KEY or GOOGLE_API_KEY is required (or use --fallback)")

    OUT.mkdir(parents=True, exist_ok=True)
    reference = _reference_jpeg() if not args.fallback else b""
    selected = {args.only: CONCEPTS[args.only]} if args.only else CONCEPTS
    print(f"mode={'fallback' if args.fallback else MODEL} concepts={len(selected)}")
    for slug, config in selected.items():
        if args.fallback:
            image = _fallback(config["source"], config["overlay"])
        else:
            image = _fit(_request(config["prompt"], reference, api_key))
        destination = OUT / f"{slug}.webp"
        image.save(destination, "WEBP", quality=88, method=6)
        print(f"wrote {destination.relative_to(ROOT)} ({destination.stat().st_size} bytes)")
    if args.review_artifacts:
        _review_artifacts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
