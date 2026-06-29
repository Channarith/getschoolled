#!/usr/bin/env python3
"""Regenerate the legacy "S" wordmark + print brand assets from the SVG sources.

Source of truth: docs/brand/aiclassroom_mark.svg (icon) and
docs/brand/aiclassroom_wordmark.svg (horizontal lockup).

NOTE: the canonical brand mark is now the Bayon Buddy holding the golden "S"
medallion. ALL buddy brand rasters - the web browser/app icons, the docs/brand
color + 1-bit logos, the mascot, docs/images/logo.png, and the marketing
mascot.png - are built from that master by scripts/build_bayon_icons.py and are
NOT produced here, so re-running this script never regresses the buddy brand.
This script only emits the legacy 1-color "S" wordmark lockup.

Outputs:
  apps/web/public/logo-mark.svg      raw SVG (themable via currentColor)
  apps/web/public/wordmark.webp      1024x224 light mark on navy

Plain text per the repo no-markdown rule. Idempotent; safe to re-run.
"""

from __future__ import annotations
import io
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "docs" / "brand"
PUBLIC = ROOT / "apps" / "web" / "public"

MARK_SVG = BRAND / "aiclassroom_mark.svg"
WORDMARK_SVG = BRAND / "aiclassroom_wordmark.svg"

NAVY = "#0b1020"
LIGHT = "#e8ecf6"


def _rsvg(svg: Path, width: int, height: int, fill: str, bg: str | None) -> bytes:
    """Rasterize an SVG via rsvg-convert; inject `fill` via a CSS stylesheet
    so the SVG's `currentColor` resolves to our brand color."""
    style_css = f"svg{{color:{fill};}}".encode()
    style_path = Path("/tmp/_rsvg_style.css")
    style_path.write_bytes(style_css)
    cmd = [
        "rsvg-convert",
        "-w", str(width),
        "-h", str(height),
        "-a",
        "--stylesheet", str(style_path),
        str(svg),
    ]
    if bg:
        cmd += ["--background-color", bg]
    return subprocess.check_output(cmd)


def _round_corners(im: Image.Image, radius: int) -> Image.Image:
    """Apply rounded corners (RGBA) to a square image."""
    from PIL import ImageDraw
    rgba = im.convert("RGBA")
    mask = Image.new("L", rgba.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, rgba.width - 1, rgba.height - 1), radius=radius, fill=255,
    )
    rgba.putalpha(mask)
    return rgba


def render_icon(size: int, fill: str = LIGHT, bg: str = NAVY,
                rounded: bool = True) -> Image.Image:
    png = _rsvg(MARK_SVG, size, size, fill=fill, bg=bg)
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    if rounded:
        im = _round_corners(im, radius=int(size * 0.22))
    return im


def render_wordmark(width: int, height: int) -> Image.Image:
    png = _rsvg(WORDMARK_SVG, width, height, fill=LIGHT, bg=NAVY)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main() -> int:
    if not MARK_SVG.exists():
        print(f"missing: {MARK_SVG}", file=sys.stderr)
        return 2
    if shutil.which("rsvg-convert") is None:
        print("rsvg-convert not installed (apt install librsvg2-bin)",
              file=sys.stderr)
        return 2

    PUBLIC.mkdir(parents=True, exist_ok=True)

    # The buddy brand rasters (web icons + docs/brand color & 1-bit logos +
    # mascot + docs/images/logo.png + marketing mascot.png) are derived from the
    # Bayon Buddy master by scripts/build_bayon_icons.py - do not regenerate them
    # here. This script only produces the legacy 1-color "S" wordmark lockup.
    shutil.copy2(MARK_SVG, PUBLIC / "logo-mark.svg")

    wordmark = render_wordmark(1024, 224)
    wordmark.save(PUBLIC / "wordmark.webp", format="WEBP", quality=92, method=6)

    print("wrote:")
    for p in [
        PUBLIC / "logo-mark.svg", PUBLIC / "wordmark.webp",
    ]:
        try:
            kb = p.stat().st_size / 1024
            print(f"  {p.relative_to(ROOT)}  ({kb:.1f} kB)")
        except FileNotFoundError:
            print(f"  MISSING: {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
