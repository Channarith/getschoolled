#!/usr/bin/env python3
"""Build the final Salareen brand assets from the SVG source.

Mark + Khmer wordmark lockup. Renders:

  docs/brand/salareen/salareen_mark.png            1024 light-on-navy
  docs/brand/salareen/salareen_mark_binary.png     1-bit hard threshold
  docs/brand/salareen/salareen_lockup.png          1024 wide, mark on top
                                                   + Khmer wordmark below
  docs/brand/salareen/salareen_lockup_binary.png   1-bit version
  docs/brand/salareen/salareen_wordmark.png        Khmer-only wordmark
                                                   (for press kits)

Why two render paths?
  * The mark uses rsvg-convert (vector -> raster, currentColor injected
    via stylesheet so the same SVG inverts on light/dark).
  * The Khmer wordmark uses Pillow + raqm/HarfBuzz, because librsvg's
    text shaper renders the U+17C0 (ie) vowel sign as a dotted-circle
    tofu. Pillow with raqm composes Khmer clusters correctly.
  * The two PNGs are then composited into one image, so consumers get
    a single asset that always renders the Khmer wordmark right.

Browsers and design tools (Figma, Illustrator) render the SVG <text>
element via HarfBuzz directly, so salareen_lockup.svg works there
without the PIL fallback.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "brand" / "salareen"

NAVY = "#0b1020"
LIGHT = "#e8ecf6"

# Sala-rian (Khmer for "school"; the romanisation our brand uses)
KHMER = "\u179f\u17b6\u179b\u17b6\u179a\u17c0\u1793"

KHMER_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Bold.ttf",
    "/usr/share/fonts/truetype/khmeros/KhmerOS_battambang.ttf",
    "/usr/share/fonts/truetype/khmeros/KhmerOS.ttf",
)


def _rsvg(svg: Path, w: int, h: int, fill: str, bg: str | None) -> Image.Image:
    style = Path("/tmp/_salareen_style.css")
    style.write_text(f"svg{{color:{fill};}}")
    cmd = ["rsvg-convert", "-w", str(w), "-h", str(h), "-a",
           "--stylesheet", str(style)]
    if bg:
        cmd += ["--background-color", bg]
    cmd.append(str(svg))
    png = subprocess.check_output(cmd)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def _khmer_font(size: int) -> ImageFont.FreeTypeFont:
    for path in KHMER_FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError(
        "no Khmer font installed; apt install fonts-noto fonts-khmeros")


def render_khmer(text: str, *, font_size: int, color: str, bg: str | None,
                 padding: int = 24) -> Image.Image:
    """Render `text` to a tightly-cropped RGBA image via Pillow + raqm."""
    font = _khmer_font(font_size)
    # First measure on an oversized canvas, then crop to bbox + padding.
    probe = Image.new("RGBA", (font_size * len(text) * 3, font_size * 3),
                      (0, 0, 0, 0))
    bbox = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0] + 2 * padding
    h = bbox[3] - bbox[1] + 2 * padding
    img = Image.new("RGBA", (w, h), bg if bg else (0, 0, 0, 0))
    ImageDraw.Draw(img).text((padding - bbox[0], padding - bbox[1]),
                             text, font=font, fill=color)
    return img


def compose_lockup(mark: Image.Image, wordmark: Image.Image, *,
                   bg: str, total_w: int, gap: int = 28) -> Image.Image:
    """Stack `mark` (square) over `wordmark` (any width), centered, on `bg`."""
    # Scale the mark to fit total_w with margin.
    mark_target = int(total_w * 0.62)
    mark_resized = mark.resize((mark_target, mark_target), Image.LANCZOS)
    # Scale the wordmark to fit ~mark_target width (slightly narrower).
    wm_target_w = int(mark_target * 0.95)
    scale = wm_target_w / wordmark.width
    wm_target_h = int(wordmark.height * scale)
    wm_resized = wordmark.resize((wm_target_w, wm_target_h), Image.LANCZOS)
    # Compose.
    margin = (total_w - mark_target) // 2
    h = margin + mark_target + gap + wm_target_h + margin
    out = Image.new("RGBA", (total_w, h), bg)
    out.paste(mark_resized, (margin, margin), mark_resized)
    out.paste(wm_resized,
              ((total_w - wm_target_w) // 2, margin + mark_target + gap),
              wm_resized)
    return out


def main() -> int:
    if shutil.which("rsvg-convert") is None:
        print("rsvg-convert missing (apt install librsvg2-bin)", file=sys.stderr)
        return 2
    svg = DIR / "salareen_mark.svg"
    if not svg.exists():
        print(f"missing {svg}", file=sys.stderr)
        return 2

    # ----- Mark (color + 1-bit) -------------------------------------------
    mark = _rsvg(svg, 1024, 1024, fill=LIGHT, bg=NAVY)
    mark.convert("RGB").save(DIR / "salareen_mark.png", format="PNG", optimize=True)

    flat = _rsvg(svg, 1024, 1024, fill="#000000", bg="#ffffff").convert("L")
    bw = flat.point(lambda p: 0 if p < 128 else 255, mode="1")
    bw.save(DIR / "salareen_mark_binary.png", format="PNG", optimize=True)

    # ----- Khmer wordmark stand-alone (Pillow + raqm) ----------------------
    wordmark = render_khmer(KHMER, font_size=160, color=LIGHT, bg=NAVY,
                            padding=48)
    wordmark.convert("RGB").save(DIR / "salareen_wordmark.png",
                                 format="PNG", optimize=True)

    # 1-bit Khmer wordmark (for print)
    wordmark_bw = render_khmer(KHMER, font_size=200, color="#000000",
                               bg="#ffffff", padding=64).convert("L")
    wordmark_bw_bin = wordmark_bw.point(lambda p: 0 if p < 128 else 255, mode="1")
    wordmark_bw_bin.save(DIR / "salareen_wordmark_binary.png",
                         format="PNG", optimize=True)

    # ----- Lockup (mark + Khmer wordmark composited) ----------------------
    # Color
    mark_t = _rsvg(svg, 1024, 1024, fill=LIGHT, bg=None)
    wm_t = render_khmer(KHMER, font_size=180, color=LIGHT, bg=None,
                        padding=32)
    lockup = compose_lockup(mark_t, wm_t, bg=NAVY, total_w=1024, gap=40)
    lockup.convert("RGB").save(DIR / "salareen_lockup.png",
                               format="PNG", optimize=True)

    # 1-bit lockup
    mark_bw_src = _rsvg(svg, 1024, 1024, fill="#000000", bg=None)
    wm_bw_src = render_khmer(KHMER, font_size=180, color="#000000", bg=None,
                             padding=32)
    lockup_bw = compose_lockup(mark_bw_src, wm_bw_src,
                               bg="#ffffff", total_w=1024, gap=40)
    lockup_bw_l = lockup_bw.convert("L")
    lockup_bw_bin = lockup_bw_l.point(lambda p: 0 if p < 128 else 255, mode="1")
    lockup_bw_bin.save(DIR / "salareen_lockup_binary.png",
                      format="PNG", optimize=True)

    # ----- Small favicon-size preview for sanity --------------------------
    fav = _rsvg(svg, 256, 256, fill=LIGHT, bg=NAVY)
    fav.convert("RGB").save(DIR / "salareen_mark_256.png",
                            format="PNG", optimize=True)

    print("wrote:")
    for p in [
        DIR / "salareen_mark.png", DIR / "salareen_mark_binary.png",
        DIR / "salareen_mark_256.png",
        DIR / "salareen_wordmark.png", DIR / "salareen_wordmark_binary.png",
        DIR / "salareen_lockup.png", DIR / "salareen_lockup_binary.png",
    ]:
        try:
            print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size / 1024:.1f} kB)")
        except FileNotFoundError:
            print(f"  MISSING: {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
