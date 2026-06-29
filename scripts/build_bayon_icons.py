#!/usr/bin/env python3
"""Generate the web brand icons from the Bayon Buddy master art.

The canonical brand mark is the photorealistic Bayon Buddy holding the golden
"S" medallion (apps/web/public/bayon-mark.webp). This script renders the square
browser/app icons used by apps/web so the favicon, nav badge, apple-touch icon
and OG/hero image all match the buddy brand.

Source of truth:
  apps/web/public/bayon-mark.webp        full-body buddy, transparent (250x512)

Outputs (apps/web/public/, served from /):
  favicon.ico        16/32/48/64 multi-size browser icon (buddy on navy)
  logo-mark.webp     128x128 nav + profile badge (buddy on navy, rounded)
  logo.webp          512x512 apple-touch / hero / OG image (buddy on navy)
  icon.png           512x512 PNG icon (PNG fallback for the same art)

Pillow-only (no rsvg dependency). Plain text per the repo no-markdown rule.
Idempotent; safe to re-run.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps" / "web" / "public"
MASTER = PUBLIC / "bayon-mark.webp"

NAVY = (11, 16, 32, 255)  # #0b1020 brand background

# Fraction of the square canvas the buddy artwork fills (rest = brand padding).
# The buddy is a tall portrait; this keeps the full figure (face -> medallion)
# visible while leaving a small, balanced margin.
FILL = 0.92


def _rounded_square(size: int, radius_ratio: float = 0.22) -> Image.Image:
    """A navy rounded square of `size`px (RGBA)."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * radius_ratio), fill=255,
    )
    fill = Image.new("RGBA", (size, size), NAVY)
    canvas.paste(fill, (0, 0), mask)
    return canvas


def render_badge(size: int, *, rounded: bool = True, fill: float = FILL) -> Image.Image:
    """Render the buddy centered on a navy (optionally rounded) square."""
    src = Image.open(MASTER).convert("RGBA")
    # Tight-crop to the buddy's visible pixels so framing ignores transparent margins.
    bbox = src.getbbox()
    if bbox:
        src = src.crop(bbox)

    canvas = _rounded_square(size) if rounded else Image.new("RGBA", (size, size), NAVY)

    target = int(size * fill)
    scale = min(target / src.width, target / src.height)
    nw = max(1, int(src.width * scale))
    nh = max(1, int(src.height * scale))
    art = src.resize((nw, nh), Image.Resampling.LANCZOS)

    x = (size - nw) // 2
    y = (size - nh) // 2
    canvas.paste(art, (x, y), art)
    return canvas


def main() -> int:
    if not MASTER.is_file():
        print(f"missing master art: {MASTER}", file=sys.stderr)
        return 2

    PUBLIC.mkdir(parents=True, exist_ok=True)

    nav = render_badge(128)
    nav.save(PUBLIC / "logo-mark.webp", format="WEBP", quality=92, method=6)

    hero = render_badge(512)
    hero.save(PUBLIC / "logo.webp", format="WEBP", quality=92, method=6)
    hero.save(PUBLIC / "icon.png", format="PNG", optimize=True)

    # Favicon: square (not rounded) so the OS/browser can apply its own mask.
    favicon_sizes = [16, 32, 48, 64]
    favicon_src = render_badge(256, rounded=False)
    favicon_src.save(
        PUBLIC / "favicon.ico", format="ICO",
        sizes=[(s, s) for s in favicon_sizes],
    )

    print("wrote:")
    for p in [
        PUBLIC / "logo-mark.webp", PUBLIC / "logo.webp",
        PUBLIC / "icon.png", PUBLIC / "favicon.ico",
    ]:
        try:
            kb = p.stat().st_size / 1024
            print(f"  {p.relative_to(ROOT)}  ({kb:.1f} kB)")
        except FileNotFoundError:
            print(f"  MISSING: {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
