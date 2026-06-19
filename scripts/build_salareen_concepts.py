#!/usr/bin/env python3
"""Render the 5 Salareen logo concepts.

Source-of-truth SVGs in docs/brand/salareen/*.svg use fill="currentColor",
so we inject a CSS stylesheet to colorize them at render time. Outputs:

  docs/brand/salareen/<concept>.png             1024x1024 light-on-navy
  docs/brand/salareen/<concept>_binary.png      1-bit threshold (print)
  docs/brand/salareen/_contact_sheet.png        all 5 side by side (and
                                                 the 1-bit versions in a
                                                 second row, for the 'binary
                                                 design' check)

Usage: python3 scripts/build_salareen_concepts.py
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
TILE = 512   # render size per concept in the contact sheet
PAD = 28
NAVY = "#0b1020"
LIGHT = "#e8ecf6"

CONCEPTS = [
    ("concept_1_seal",         "1. Seal"),
    ("concept_2_sirorekha",    "2. Sirorekha (headline bar)"),
    ("concept_3_angkor",       "3. Angkor (stone-cut)"),
    ("concept_4_calligraphic", "4. Calligraphic curl"),
    ("concept_5_lotus",        "5. Lotus crown"),
]


def _rsvg(svg: Path, w: int, h: int, fill: str, bg: str | None) -> bytes:
    style = Path("/tmp/_salareen_style.css")
    style.write_text(f"svg{{color:{fill};}}")
    cmd = [
        "rsvg-convert", "-w", str(w), "-h", str(h), "-a",
        "--stylesheet", str(style),
    ]
    if bg:
        cmd += ["--background-color", bg]
    cmd.append(str(svg))
    return subprocess.check_output(cmd)


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> int:
    if shutil.which("rsvg-convert") is None:
        print("rsvg-convert missing (apt install librsvg2-bin)", file=sys.stderr)
        return 2
    if not DIR.exists():
        print(f"missing {DIR}", file=sys.stderr)
        return 2

    color_tiles: list[Image.Image] = []
    binary_tiles: list[Image.Image] = []

    for name, _ in CONCEPTS:
        svg = DIR / f"{name}.svg"
        if not svg.exists():
            print(f"missing {svg}", file=sys.stderr)
            return 2

        # Color version: light mark on navy (1024x1024).
        png_color = _rsvg(svg, 1024, 1024, fill=LIGHT, bg=NAVY)
        (DIR / f"{name}.png").write_bytes(png_color)

        # 1-bit threshold: black mark on white, hard threshold (the
        # "simplified binary design" the user asked for).
        png_flat = _rsvg(svg, 1024, 1024, fill="#000000", bg="#ffffff")
        gray = Image.open(io.BytesIO(png_flat)).convert("L")
        bw = gray.point(lambda p: 0 if p < 128 else 255, mode="1")
        (DIR / f"{name}_binary.png").write_bytes(_to_bytes(bw, "PNG"))

        # Tiles for the contact sheet.
        tile_color = Image.open(io.BytesIO(_rsvg(svg, TILE, TILE, fill=LIGHT, bg=NAVY))).convert("RGBA")
        color_tiles.append(tile_color)
        tile_bw = Image.open(io.BytesIO(_rsvg(svg, TILE, TILE, fill="#000000", bg="#ffffff"))).convert("RGBA")
        binary_tiles.append(tile_bw)

    # Build 5-up contact sheet: top row in color, bottom row 1-bit print.
    label_h = 64
    sheet_w = TILE * 5 + PAD * 6
    sheet_h = (TILE + label_h + PAD) * 2 + PAD
    sheet = Image.new("RGB", (sheet_w, sheet_h), NAVY)
    draw = ImageDraw.Draw(sheet)
    font = _font(28)
    title_font = _font(34)

    draw.text(
        (PAD, 10),
        "Salareen logo concepts  -  pick your favorite",
        fill=LIGHT, font=title_font,
    )

    for i, (name, label) in enumerate(CONCEPTS):
        x = PAD + i * (TILE + PAD)
        y = PAD + 36
        sheet.paste(color_tiles[i], (x, y))
        draw.text((x, y + TILE + 6), label, fill=LIGHT, font=font)

    y2 = PAD + 36 + TILE + label_h + PAD
    for i, (name, label) in enumerate(CONCEPTS):
        x = PAD + i * (TILE + PAD)
        sheet.paste(binary_tiles[i], (x, y2))
        draw.text((x, y2 + TILE + 6),
                  f"{label} - 1-bit print", fill=LIGHT, font=font)

    out = DIR / "_contact_sheet.png"
    sheet.save(out, format="PNG", optimize=True)
    print("wrote contact sheet:", out)
    print()
    for name, label in CONCEPTS:
        for ext in ("png", "_binary.png"):
            p = DIR / f"{name}{'.' + ext if not ext.startswith('_') else ext}"
            if p.exists():
                print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size/1024:.1f} kB)")
    return 0


def _to_bytes(im: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format=fmt, optimize=True)
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
