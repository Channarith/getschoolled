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


def _render_gold_text(text: str, font_size: int, scale: int = 4) -> Image.Image:
    """Render `text` in photo-real gold-leaf style.

    Pipeline:
      1. High-resolution alpha mask via Pillow + raqm/HarfBuzz
         (preserves Khmer cluster shaping, including U+17C0).
      2. Vertical gold gradient masked by alpha (the metal look).
      3. Drop shadow (blurred dark alpha, offset down).
      4. Top-edge highlight (light catch on the upper facets).

    Returns RGBA at 1x.
    """
    from PIL import ImageChops, ImageFilter
    font = _khmer_font(font_size * scale)
    probe = Image.new("L", (font_size * len(text) * 6 * scale,
                             font_size * 4 * scale), 0)
    bbox = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font,
                                           language="km")
    pad = font_size * scale
    w = bbox[2] - bbox[0] + 2 * pad
    h = bbox[3] - bbox[1] + 2 * pad
    alpha_hi = Image.new("L", (w, h), 0)
    ImageDraw.Draw(alpha_hi).text(
        (pad - bbox[0], pad - bbox[1]),
        text, font=font, fill=255, language="km",
    )
    out_w, out_h = w // scale, h // scale
    alpha = alpha_hi.resize((out_w, out_h), Image.LANCZOS)

    shadow_a = alpha.filter(ImageFilter.GaussianBlur(radius=font_size // 5))
    shadow = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    shadow.putalpha(shadow_a.point(lambda p: int(p * 0.85)))
    shadow_canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    dy = max(2, font_size // 14)
    shadow_canvas.paste(shadow, (0, dy), shadow)

    gradient = Image.new("RGB", (out_w, out_h), (0, 0, 0))
    gd = ImageDraw.Draw(gradient)
    stops = [
        (0.00, (255, 235, 180)),
        (0.25, (240, 195,  90)),
        (0.50, (210, 158,  45)),
        (0.75, (170, 122,  32)),
        (1.00, (215, 168,  68)),
    ]
    for y in range(out_h):
        t = y / max(1, out_h - 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                k = (t - t0) / max(1e-6, t1 - t0)
                r = int(c0[0] + k * (c1[0] - c0[0]))
                g = int(c0[1] + k * (c1[1] - c0[1]))
                b = int(c0[2] + k * (c1[2] - c0[2]))
                gd.line([(0, y), (out_w, y)], fill=(r, g, b))
                break
    gold = gradient.convert("RGBA")
    gold.putalpha(alpha)

    edge = alpha.filter(ImageFilter.FIND_EDGES)
    edge_top = ImageChops.subtract(
        edge, edge.filter(ImageFilter.GaussianBlur(radius=2)),
    ).point(lambda p: min(255, p * 2))
    highlight = Image.new("RGBA", (out_w, out_h), (255, 245, 215, 0))
    highlight.putalpha(edge_top.point(lambda p: int(p * 0.85)))

    composed = Image.alpha_composite(shadow_canvas, gold)
    composed = Image.alpha_composite(composed, highlight)
    return composed


def build_photoreal_lockup(medallion_path: Path, *,
                           total_w: int = 2048) -> Image.Image:
    """Compose the photo-real medallion + gold-leaf Khmer wordmark on
    a navy field with a cinematic vignette.

    The medallion master (AI-generated, square, with dark edges) is
    cut to a feathered circular alpha mask before pasting so it
    blends seamlessly into the navy background instead of showing a
    visible square seam.
    """
    from PIL import ImageChops, ImageFilter
    NAVY_RGB = (11, 16, 32)

    src = Image.open(medallion_path).convert("RGBA")
    sw, sh = src.size
    mask = Image.new("L", (sw, sh), 0)
    md = ImageDraw.Draw(mask)
    cx, cy = sw // 2, int(sh * 0.535)
    rr = int(sw * 0.47)
    md.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=int(sw * 0.012)))
    medallion = src.copy()
    medallion.putalpha(ImageChops.multiply(medallion.split()[3], mask))

    med_target = int(total_w * 0.78)
    med = medallion.resize((med_target, med_target), Image.LANCZOS)

    wm = _render_gold_text(KHMER, font_size=int(total_w * 0.13))
    wm_w_target = int(total_w * 0.62)
    sf = wm_w_target / wm.width
    wm = wm.resize((wm_w_target, int(wm.height * sf)), Image.LANCZOS)

    margin_top = int(total_w * 0.04)
    gap = int(total_w * 0.005)
    margin_bot = int(total_w * 0.07)
    h = margin_top + med_target + gap + wm.height + margin_bot

    canvas = Image.new("RGBA", (total_w, h), NAVY_RGB + (255,))

    vg = Image.new("L", (total_w, h), 0)
    vd = ImageDraw.Draw(vg)
    cx, cy = total_w // 2, int(h * 0.40)
    rmax = int(min(total_w, h) * 0.7)
    for r in range(rmax, 0, -1):
        t = r / rmax
        vd.ellipse((cx - r, cy - r, cx + r, cy + r),
                   fill=int(55 * (1 - t)))
    light = Image.new("RGBA", (total_w, h), (160, 168, 200, 0))
    light.putalpha(vg.filter(ImageFilter.GaussianBlur(radius=120)))
    canvas = Image.alpha_composite(canvas, light)

    canvas.paste(med, ((total_w - med_target) // 2, margin_top), med)
    canvas.paste(wm, ((total_w - wm.width) // 2,
                      margin_top + med_target + gap), wm)
    return canvas


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
    #
    # The realistic lockup uses the photo_real_lockup helper below to
    # match the medallion's gold-leaf material on the Khmer wordmark
    # (gold gradient + drop shadow + edge highlight). The cartoon
    # lockup uses the simpler flat-fill compose_lockup() because the
    # cartoon mark is itself flat-styled.
    realistic_sq = BRAND_DIR / "salarean_mark_realistic_square.png"
    if realistic_sq.exists():
        rl = build_photoreal_lockup(realistic_sq, total_w=2048)
        rl.convert("RGB").save(
            BRAND_DIR / "salarean_lockup_realistic_2x.png",
            format="PNG", optimize=True)
        rl_1024 = rl.resize((1024, rl.height // 2), Image.LANCZOS)
        rl_1024.convert("RGB").save(
            BRAND_DIR / "salarean_lockup_realistic.png",
            format="PNG", optimize=True)
        for w in (1024, 768, 512):
            sf = w / rl_1024.width
            sc = rl_1024.resize(
                (w, int(rl_1024.height * sf)), Image.LANCZOS)
            out = PUBLIC / (f"logo-realistic-lockup.webp"
                            if w == 1024 else
                            f"logo-realistic-lockup-{w}.webp")
            sc.convert("RGBA").save(
                out, format="WEBP", quality=92, method=6)
    else:
        print(f"  (skip realistic lockup; missing {realistic_sq.name})")

    cartoon_sq = BRAND_DIR / "salarean_mark_cartoon_square.png"
    if cartoon_sq.exists():
        master = Image.open(cartoon_sq).convert("RGBA")
        wm_for_cartoon = render_khmer(
            KHMER, font_size=180, color="#0b1020", bg=None, padding=32)
        lk = compose_lockup(master, wm_for_cartoon, bg="#fdf6e3",
                            total_w=1024, gap=44)
        lk.convert("RGB").save(
            BRAND_DIR / "salarean_lockup_cartoon.png",
            format="PNG", optimize=True)
        for w in (1024, 768, 512):
            ratio = w / lk.width
            sc = lk.resize((w, int(lk.height * ratio)), Image.LANCZOS)
            out = PUBLIC / (f"logo-cartoon-lockup.webp"
                            if w == 1024 else
                            f"logo-cartoon-lockup-{w}.webp")
            sc.convert("RGBA").save(
                out, format="WEBP", quality=92, method=6)
    else:
        print(f"  (skip cartoon lockup; missing {cartoon_sq.name})")

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
        BRAND_DIR / "salarean_lockup_realistic_2x.png",
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
