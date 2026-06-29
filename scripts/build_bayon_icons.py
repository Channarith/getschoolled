#!/usr/bin/env python3
"""Generate every brand raster from the Bayon Buddy master art.

The canonical brand mark is the photorealistic Bayon Buddy holding the golden
"S" medallion + green bodhi leaf (apps/web/public/bayon-mark.webp). This script
renders ALL derived brand rasters from that single master so the favicon, app
icons, docs brand sheet, hero/marketing mascot, and print marks all match.

Source of truth:
  apps/web/public/bayon-mark.webp        full-figure buddy, transparent (250x512)

Outputs:
  Web (apps/web/public/, served from /):
    favicon.ico        16/32/48/64 multi-size browser icon (buddy on navy)
    logo-mark.webp     128x128 nav + profile badge (buddy on navy, rounded)
    logo.webp          512x512 apple-touch / hero / OG image (buddy on navy)
    icon.png           512x512 PNG app icon (PNG fallback for the same art)
    salareen-mascot.webp  web-optimized transparent buddy (Our Story / hero)

  Docs brand sheet (docs/brand/):
    aiclassroom_logo.png / .webp                1024 color buddy on navy (rounded)
    aiclassroom_logo_binary.png                 1-bit Floyd-Steinberg dither (print)
    aiclassroom_logo_binary_threshold.png       1-bit hard threshold (stamp)
    salareen_bayon_buddy_mascot.png             1536x1024 buddy on navy (hero/mascot)

  Docs images (docs/images/):
    logo.png           1536x1024 app-icon presentation (buddy badge on white)

  Marketing pitch video (marketing/pitch-video/public/brand/):
    mascot.png         1536x1024 buddy on navy (used by the pitch video)

Pillow-only (no rsvg dependency). Plain text per the repo no-markdown rule.
Idempotent; safe to re-run.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps" / "web" / "public"
BRAND = ROOT / "docs" / "brand"
DOCS_IMAGES = ROOT / "docs" / "images"
MARKETING_BRAND = ROOT / "marketing" / "pitch-video" / "public" / "brand"
MASTER = PUBLIC / "bayon-mark.webp"

NAVY = (11, 16, 32, 255)  # #0b1020 brand background
WHITE = (255, 255, 255, 255)

# Fraction of a square canvas the buddy artwork fills (rest = brand padding).
FILL = 0.92


def _buddy() -> Image.Image:
    """The buddy master, tight-cropped to its visible pixels."""
    src = Image.open(MASTER).convert("RGBA")
    bbox = src.getbbox()
    return src.crop(bbox) if bbox else src


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255,
    )
    return mask


def _paste_centered(canvas: Image.Image, art: Image.Image, fill: float) -> Image.Image:
    cw, ch = canvas.size
    target = int(min(cw, ch) * fill)
    scale = min(target / art.width, target / art.height)
    nw = max(1, int(art.width * scale))
    nh = max(1, int(art.height * scale))
    resized = art.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((cw - nw) // 2, (ch - nh) // 2), resized)
    return canvas


def render_badge(size: int, *, rounded: bool = True, fill: float = FILL) -> Image.Image:
    """Buddy centered on a navy (optionally rounded) square."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if rounded:
        fill_layer = Image.new("RGBA", (size, size), NAVY)
        canvas.paste(fill_layer, (0, 0), _rounded_mask((size, size), int(size * 0.22)))
    else:
        canvas = Image.new("RGBA", (size, size), NAVY)
    return _paste_centered(canvas, _buddy(), fill)


def render_canvas(w: int, h: int, bg: tuple[int, int, int, int], *,
                  fill: float = 0.78) -> Image.Image:
    """Buddy centered on a flat w x h canvas."""
    canvas = Image.new("RGBA", (w, h), bg)
    return _paste_centered(canvas, _buddy(), fill)


def render_icon_on_white(w: int, h: int) -> Image.Image:
    """A navy rounded app-icon badge centered on a white canvas (presentation)."""
    canvas = Image.new("RGBA", (w, h), WHITE)
    side = int(min(w, h) * 0.82)
    badge = render_badge(side, rounded=True)
    canvas.paste(badge, ((w - side) // 2, (h - side) // 2), badge)
    return canvas


def render_one_bit(size: int, *, dither: bool) -> Image.Image:
    """1-bit print mark: buddy flattened on white, then dithered/thresholded."""
    art = render_canvas(size, size, WHITE, fill=0.9).convert("RGB")
    gray = art.convert("L")
    if dither:
        return gray.convert("1", dither=Image.FLOYDSTEINBERG)
    return gray.point(lambda p: 0 if p < 128 else 255, mode="1")


def main() -> int:
    if not MASTER.is_file():
        print(f"missing master art: {MASTER}", file=sys.stderr)
        return 2

    for d in (PUBLIC, BRAND, DOCS_IMAGES, MARKETING_BRAND):
        d.mkdir(parents=True, exist_ok=True)

    # --- web browser/app icons ---
    render_badge(128).save(PUBLIC / "logo-mark.webp", format="WEBP", quality=92, method=6)
    hero = render_badge(512)
    hero.save(PUBLIC / "logo.webp", format="WEBP", quality=92, method=6)
    hero.save(PUBLIC / "icon.png", format="PNG", optimize=True)
    favicon_src = render_badge(256, rounded=False)
    favicon_src.save(
        PUBLIC / "favicon.ico", format="ICO",
        sizes=[(s, s) for s in (16, 32, 48, 64)],
    )

    # Transparent web-optimized buddy for in-page use (Our Story, hero).
    buddy = _buddy()
    mw = 512
    mh = round(mw * buddy.height / buddy.width)
    buddy.resize((mw, mh), Image.Resampling.LANCZOS).save(
        PUBLIC / "salareen-mascot.webp", format="WEBP", quality=90, method=6)

    # --- docs brand sheet ---
    color = render_badge(1024)
    color.save(BRAND / "aiclassroom_logo.png", format="PNG", optimize=True)
    color.save(BRAND / "aiclassroom_logo.webp", format="WEBP", quality=92, method=6)
    render_one_bit(1024, dither=True).save(
        BRAND / "aiclassroom_logo_binary.png", format="PNG", optimize=True)
    render_one_bit(1024, dither=False).save(
        BRAND / "aiclassroom_logo_binary_threshold.png", format="PNG", optimize=True)

    mascot = render_canvas(1536, 1024, NAVY, fill=0.74).convert("RGB")
    mascot.save(BRAND / "salareen_bayon_buddy_mascot.png", format="PNG", optimize=True)
    mascot.save(MARKETING_BRAND / "mascot.png", format="PNG", optimize=True)

    render_icon_on_white(1536, 1024).convert("RGB").save(
        DOCS_IMAGES / "logo.png", format="PNG", optimize=True)

    print("wrote:")
    for p in [
        PUBLIC / "logo-mark.webp", PUBLIC / "logo.webp",
        PUBLIC / "icon.png", PUBLIC / "favicon.ico",
        PUBLIC / "salareen-mascot.webp",
        BRAND / "aiclassroom_logo.png", BRAND / "aiclassroom_logo.webp",
        BRAND / "aiclassroom_logo_binary.png",
        BRAND / "aiclassroom_logo_binary_threshold.png",
        BRAND / "salareen_bayon_buddy_mascot.png",
        DOCS_IMAGES / "logo.png",
        MARKETING_BRAND / "mascot.png",
    ]:
        try:
            kb = p.stat().st_size / 1024
            print(f"  {p.relative_to(ROOT)}  ({kb:.1f} kB)")
        except FileNotFoundError:
            print(f"  MISSING: {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
