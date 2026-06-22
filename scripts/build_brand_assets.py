#!/usr/bin/env python3
"""Regenerate the AI Classroom brand assets from the SVG sources.

Source of truth: docs/brand/aiclassroom_mark.svg (icon) and
docs/brand/aiclassroom_wordmark.svg (horizontal lockup).

Outputs:
  apps/web/public/favicon.ico        16/32/48 multi-size, light mark on navy
  apps/web/public/logo-mark.webp     128x128 light mark on navy (nav)
  apps/web/public/logo.webp          512x512 light mark on navy (hero)
  apps/web/public/logo-mark.svg      raw SVG (themable via currentColor)
  apps/web/public/wordmark.webp      1024x224 light mark on navy

  docs/brand/aiclassroom_logo.png        1024 color on navy
  docs/brand/aiclassroom_logo.webp       1024 color on navy
  docs/brand/aiclassroom_logo_binary.png            1-bit dithered (print)
  docs/brand/aiclassroom_logo_binary_threshold.png  1-bit hard threshold (stamp)

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

    nav = render_icon(128)
    nav.save(PUBLIC / "logo-mark.webp", format="WEBP", quality=92, method=6)
    hero = render_icon(512)
    hero.save(PUBLIC / "logo.webp", format="WEBP", quality=92, method=6)

    shutil.copy2(MARK_SVG, PUBLIC / "logo-mark.svg")

    wordmark = render_wordmark(1024, 224)
    wordmark.save(PUBLIC / "wordmark.webp", format="WEBP", quality=92, method=6)

    sizes = [16, 32, 48, 64]
    favicon_src = render_icon(256, rounded=False)
    favicon_src.save(
        PUBLIC / "favicon.ico", format="ICO",
        sizes=[(s, s) for s in sizes],
    )

    color = render_icon(1024)
    color.save(BRAND / "aiclassroom_logo.png", format="PNG", optimize=True)
    color.save(BRAND / "aiclassroom_logo.webp", format="WEBP", quality=92, method=6)

    flat = render_icon(1024, fill="#000000", bg="#ffffff", rounded=False).convert("RGB")
    flat.convert("L").convert("1", dither=Image.FLOYDSTEINBERG).save(
        BRAND / "aiclassroom_logo_binary.png", format="PNG", optimize=True,
    )
    gray = flat.convert("L")
    threshold = gray.point(lambda p: 0 if p < 128 else 255, mode="1")
    threshold.save(
        BRAND / "aiclassroom_logo_binary_threshold.png",
        format="PNG", optimize=True,
    )

    print("wrote:")
    for p in [
        PUBLIC / "logo-mark.webp", PUBLIC / "logo.webp",
        PUBLIC / "logo-mark.svg", PUBLIC / "wordmark.webp",
        PUBLIC / "favicon.ico",
        BRAND / "aiclassroom_logo.png", BRAND / "aiclassroom_logo.webp",
        BRAND / "aiclassroom_logo_binary.png",
        BRAND / "aiclassroom_logo_binary_threshold.png",
    ]:
        try:
            kb = p.stat().st_size / 1024
            print(f"  {p.relative_to(ROOT)}  ({kb:.1f} kB)")
        except FileNotFoundError:
            print(f"  MISSING: {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
