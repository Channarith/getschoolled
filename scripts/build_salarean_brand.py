#!/usr/bin/env python3
"""Render the canonical Salarean brand asset pack from the SVG source.

Source of truth: ``docs/brand/salarean_mark.svg`` - the Bodhi-leaf-
crowned S-in-circle mark.

Outputs (all regenerated, idempotent):

  docs/brand/
    salarean_mark.svg              square mark (256x256 viewBox)
    salarean_mark.png              1024x1024 light-on-navy
    salarean_mark_256.png          256x256 nav-size preview
    salarean_mark_binary.png       1024 1-bit threshold (print)
    salarean_lockup.svg            mark + Khmer wordmark below
    salarean_lockup.png            1024 wide composited lockup
    salarean_lockup_binary.png     1-bit print version
    salarean_wordmark.png          Khmer-only wordmark
    salarean_wordmark_binary.png   1-bit Khmer wordmark

  apps/web/public/
    favicon.ico                    multi-size 16/32/48/64
    logo-mark.svg                  the mark SVG (themable)
    logo-mark.webp                 128 nav-size raster
    logo.webp                      512 hero / apple-touch-icon
    wordmark.webp                  1024 wordmark for press

The Khmer wordmark (សាលារៀន) is rendered via Pillow + raqm/HarfBuzz
because librsvg's text shaper renders the U+17C0 (ie) vowel sign as a
dotted-circle tofu; the two passes are composited into the lockup
PNGs. Browsers + Figma + Illustrator render the SVG `<text>` element
in salarean_lockup.svg correctly via HarfBuzz.

Plain text per the repo no-markdown rule.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "docs" / "brand"
PUBLIC = ROOT / "apps" / "web" / "public"

NAVY = "#0b1020"
LIGHT = "#e8ecf6"

# Khmer for "school" (sala-rean), the source word the brand romanises.
KHMER = "\u179f\u17b6\u179b\u17b6\u179a\u17c0\u1793"

KHMER_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Bold.ttf",
    "/usr/share/fonts/truetype/khmeros/KhmerOS_battambang.ttf",
    "/usr/share/fonts/truetype/khmeros/KhmerOS.ttf",
)


def _rsvg(svg: Path, w: int, h: int, fill: str, bg: str | None) -> Image.Image:
    style = Path("/tmp/_salarean_style.css")
    style.write_text(f"svg{{color:{fill};}}")
    cmd = ["rsvg-convert", "-w", str(w), "-h", str(h), "-a",
           "--stylesheet", str(style)]
    if bg:
        cmd += ["--background-color", bg]
    cmd.append(str(svg))
    return Image.open(io.BytesIO(subprocess.check_output(cmd))).convert("RGBA")


def _khmer_font(size: int) -> ImageFont.FreeTypeFont:
    for path in KHMER_FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError(
        "no Khmer font installed; apt install fonts-noto fonts-khmeros")


def render_khmer(text: str, *, font_size: int, color: str, bg: str | None,
                 padding: int = 24) -> Image.Image:
    """Tightly-cropped RGBA image of ``text`` via Pillow + raqm."""
    font = _khmer_font(font_size)
    probe = Image.new("RGBA", (font_size * len(text) * 3, font_size * 3),
                      (0, 0, 0, 0))
    bbox = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0] + 2 * padding
    h = bbox[3] - bbox[1] + 2 * padding
    img = Image.new("RGBA", (w, h), bg if bg else (0, 0, 0, 0))
    ImageDraw.Draw(img).text((padding - bbox[0], padding - bbox[1]),
                             text, font=font, fill=color)
    return img


def _round_corners(im: Image.Image, radius: int) -> Image.Image:
    """Rounded-corner alpha mask for app-icon style outputs."""
    rgba = im.convert("RGBA")
    mask = Image.new("L", rgba.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, rgba.width - 1, rgba.height - 1), radius=radius, fill=255,
    )
    rgba.putalpha(mask)
    return rgba


def compose_lockup(mark: Image.Image, wordmark: Image.Image, *, bg: str,
                   total_w: int, gap: int = 36) -> Image.Image:
    """Stack mark over wordmark, centered."""
    mark_target = int(total_w * 0.62)
    mark = mark.resize((mark_target, mark_target), Image.LANCZOS)
    wm_target_w = int(mark_target * 0.95)
    scale = wm_target_w / wordmark.width
    wm_target_h = int(wordmark.height * scale)
    wm = wordmark.resize((wm_target_w, wm_target_h), Image.LANCZOS)
    margin = (total_w - mark_target) // 2
    h = margin + mark_target + gap + wm_target_h + margin
    out = Image.new("RGBA", (total_w, h), bg)
    out.paste(mark, (margin, margin), mark)
    out.paste(wm, ((total_w - wm_target_w) // 2, margin + mark_target + gap), wm)
    return out


def main() -> int:
    if shutil.which("rsvg-convert") is None:
        print("rsvg-convert missing (apt install librsvg2-bin)", file=sys.stderr)
        return 2

    svg = BRAND_DIR / "salarean_mark.svg"
    if not svg.exists():
        print(f"missing {svg}", file=sys.stderr)
        return 2
    PUBLIC.mkdir(parents=True, exist_ok=True)

    # ----- Mark (color + 1-bit + 256 nav) ---------------------------------
    mark_1024 = _rsvg(svg, 1024, 1024, fill=LIGHT, bg=NAVY)
    mark_1024.convert("RGB").save(
        BRAND_DIR / "salarean_mark.png", format="PNG", optimize=True)

    flat = _rsvg(svg, 1024, 1024, fill="#000000", bg="#ffffff").convert("L")
    flat.point(lambda p: 0 if p < 128 else 255, mode="1").save(
        BRAND_DIR / "salarean_mark_binary.png", format="PNG", optimize=True)

    mark_256 = _rsvg(svg, 256, 256, fill=LIGHT, bg=NAVY)
    mark_256.convert("RGB").save(
        BRAND_DIR / "salarean_mark_256.png", format="PNG", optimize=True)

    # ----- Khmer wordmark (PIL + raqm) ------------------------------------
    wordmark_color = render_khmer(KHMER, font_size=160, color=LIGHT, bg=NAVY,
                                   padding=48)
    wordmark_color.convert("RGB").save(
        BRAND_DIR / "salarean_wordmark.png", format="PNG", optimize=True)

    wordmark_bw = render_khmer(KHMER, font_size=200, color="#000000",
                                bg="#ffffff", padding=64).convert("L")
    wordmark_bw.point(lambda p: 0 if p < 128 else 255, mode="1").save(
        BRAND_DIR / "salarean_wordmark_binary.png",
        format="PNG", optimize=True)

    # ----- Lockup (mark + wordmark, composited) ---------------------------
    mark_no_bg = _rsvg(svg, 1024, 1024, fill=LIGHT, bg=None)
    wm_no_bg = render_khmer(KHMER, font_size=180, color=LIGHT, bg=None,
                             padding=32)
    lockup = compose_lockup(mark_no_bg, wm_no_bg, bg=NAVY, total_w=1024, gap=40)
    lockup.convert("RGB").save(
        BRAND_DIR / "salarean_lockup.png", format="PNG", optimize=True)

    mark_bw_src = _rsvg(svg, 1024, 1024, fill="#000000", bg=None)
    wm_bw_src = render_khmer(KHMER, font_size=180, color="#000000", bg=None,
                              padding=32)
    lockup_bw = compose_lockup(mark_bw_src, wm_bw_src, bg="#ffffff",
                               total_w=1024, gap=40)
    lockup_bw_l = lockup_bw.convert("L")
    lockup_bw_l.point(lambda p: 0 if p < 128 else 255, mode="1").save(
        BRAND_DIR / "salarean_lockup_binary.png",
        format="PNG", optimize=True)

    # ----- Realistic + Cartoon variant lockups ----------------------------
    # If the AI-generated photo-real and cartoon master PNGs are present,
    # build per-variant lockups (variant mark + Khmer wordmark below) and
    # publish 1024 / 768 / 512 web copies. The masters live at
    # docs/brand/salarean_mark_realistic.png and
    # docs/brand/salarean_mark_cartoon.png; they are produced by the
    # GenerateImage tool with the binary mark as silhouette reference and
    # then square-cropped into salarean_mark_<variant>_square.png.
    for variant, wordmark_color_hex, lockup_bg in (
        ("realistic", "#f5e9c8", "#0b1020"),
        ("cartoon",   "#0b1020", "#fdf6e3"),
    ):
        sq = BRAND_DIR / f"salarean_mark_{variant}_square.png"
        if not sq.exists():
            print(f"  (skip {variant} lockup; missing {sq.name})")
            continue
        master = Image.open(sq).convert("RGBA")
        wm_for_variant = render_khmer(
            KHMER, font_size=180, color=wordmark_color_hex, bg=None,
            padding=32)
        lk = compose_lockup(master, wm_for_variant, bg=lockup_bg,
                            total_w=1024, gap=44)
        lk_path = BRAND_DIR / f"salarean_lockup_{variant}.png"
        lk.convert("RGB").save(lk_path, format="PNG", optimize=True)
        # Web-delivery copies (smaller webp).
        for w in (1024, 768, 512):
            ratio = w / lk.width
            scaled = lk.resize(
                (w, int(lk.height * ratio)), Image.LANCZOS)
            out = PUBLIC / (f"logo-{variant}-lockup.webp"
                            if w == 1024 else
                            f"logo-{variant}-lockup-{w}.webp")
            scaled.convert("RGBA").save(
                out, format="WEBP", quality=92, method=6)

    # ----- Web public assets ----------------------------------------------
    # SVG (themable via currentColor).
    shutil.copy2(svg, PUBLIC / "logo-mark.svg")

    # 128 nav mark, rounded corners for the icon-like nav look.
    nav = _rsvg(svg, 128, 128, fill=LIGHT, bg=NAVY)
    _round_corners(nav, int(128 * 0.22)).save(
        PUBLIC / "logo-mark.webp", format="WEBP", quality=92, method=6)

    # 512 hero / apple-touch-icon.
    hero = _rsvg(svg, 512, 512, fill=LIGHT, bg=NAVY)
    _round_corners(hero, int(512 * 0.22)).save(
        PUBLIC / "logo.webp", format="WEBP", quality=92, method=6)

    # Wordmark for press kits.
    wordmark_color.convert("RGBA").save(
        PUBLIC / "wordmark.webp", format="WEBP", quality=92, method=6)

    # Multi-size favicon.ico (Pillow rasterises down from the 256 source).
    fav_src = _rsvg(svg, 256, 256, fill=LIGHT, bg=NAVY).convert("RGBA")
    fav_src.save(
        PUBLIC / "favicon.ico", format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )

    print("wrote:")
    for p in [
        BRAND_DIR / "salarean_mark.svg",
        BRAND_DIR / "salarean_mark.png",
        BRAND_DIR / "salarean_mark_binary.png",
        BRAND_DIR / "salarean_mark_256.png",
        BRAND_DIR / "salarean_lockup.png",
        BRAND_DIR / "salarean_lockup_binary.png",
        BRAND_DIR / "salarean_lockup_realistic.png",
        BRAND_DIR / "salarean_lockup_cartoon.png",
        BRAND_DIR / "salarean_wordmark.png",
        BRAND_DIR / "salarean_wordmark_binary.png",
        PUBLIC / "logo-mark.svg",
        PUBLIC / "logo-mark.webp",
        PUBLIC / "logo.webp",
        PUBLIC / "wordmark.webp",
        PUBLIC / "favicon.ico",
        PUBLIC / "logo-realistic-lockup.webp",
        PUBLIC / "logo-realistic-lockup-768.webp",
        PUBLIC / "logo-realistic-lockup-512.webp",
        PUBLIC / "logo-cartoon-lockup.webp",
        PUBLIC / "logo-cartoon-lockup-768.webp",
        PUBLIC / "logo-cartoon-lockup-512.webp",
    ]:
        if p.exists():
            kb = p.stat().st_size / 1024
            print(f"  {p.relative_to(ROOT)}  ({kb:.1f} kB)")
        else:
            print(f"  MISSING: {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
