#!/usr/bin/env python3
"""Shared, browser-free promo rendering helpers for Salareen films.

Pillow draws every frame; ffmpeg (libx264) encodes. No browser/Chromium needed.
Used by render_video1.py-style photo films and the motion-graphics data spots.

Brand: deep navy bg, electric-blue -> mint gradient brand mark, Netflix-red CTA.
Captions are designed to read with sound off; add VO/music in post.
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(HERE, "public")
DEMOS = os.path.abspath(os.path.join(HERE, "..", "..", "docs", "demos"))
W, H, FPS = 1920, 1080, 30

C = {
    "bg": (11, 16, 32), "bgDeep": (7, 10, 22), "panel": (21, 28, 52),
    "text": (240, 244, 252), "muted": (158, 170, 198),
    "accent": (110, 168, 254), "brand": (14, 165, 233), "mint": (139, 233, 192),
    "gold": (251, 191, 36), "red": (229, 9, 20),
}
FONT_DIR = "/System/Library/Fonts/Supplemental"


def black(s): return ImageFont.truetype(os.path.join(FONT_DIR, "Arial Black.ttf"), s)
def bold(s):  return ImageFont.truetype(os.path.join(FONT_DIR, "Arial Bold.ttf"), s)
def reg(s):   return ImageFont.truetype(os.path.join(FONT_DIR, "Arial.ttf"), s)


def clamp01(x): return max(0.0, min(1.0, x))
def ease(t): return 1 - (1 - t) ** 3
def ease_io(t): return 3 * t * t - 2 * t * t * t


# ---- Ken Burns photo layer ------------------------------------------------
_cover_cache = {}


def cover(path):
    if path in _cover_cache:
        return _cover_cache[path]
    im = Image.open(os.path.join(PUB, path)).convert("RGB")
    sc = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
    left = (im.width - W) // 2
    top = (im.height - H) // 2
    im = im.crop((left, top, left + W, top + H))
    _cover_cache[path] = im
    return im


def kenburns(path, p, z0, z1, px, py):
    """p in [0,1]; zoom z0->z1, pan direction (px,py) in fractions."""
    base = cover(path)
    z = z0 + (z1 - z0) * ease_io(p)
    nw, nh = int(W * z), int(H * z)
    img = base.resize((nw, nh), Image.LANCZOS)
    maxx, maxy = nw - W, nh - H
    cx = maxx * (0.5 + px * (p - 0.5))
    cy = maxy * (0.5 + py * (p - 0.5))
    cx = min(max(cx, 0), maxx); cy = min(max(cy, 0), maxy)
    return img.crop((int(cx), int(cy), int(cx) + W, int(cy) + H))


def grade(img, sat=1.0, tint=None, tint_a=0.0, darken=0.0):
    """Optional color grade: desaturate, color tint, darken. Returns RGB image."""
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    if sat != 1.0:
        lum = arr @ np.array([0.299, 0.587, 0.114], np.float32)
        arr = lum[..., None] + (arr - lum[..., None]) * sat
    if tint is not None and tint_a > 0:
        arr = arr * (1 - tint_a) + np.array(tint, np.float32)[None, None] * tint_a
    if darken > 0:
        arr *= (1 - darken)
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGB")


# bottom scrim for caption legibility (vectorized)
def make_scrim(strength=200, start=0.45):
    ys = np.arange(H, dtype=np.float32)
    f = np.clip((ys - H * start) / (H * (1 - start)), 0, 1) ** 1.6
    a = (strength * f).astype(np.uint8)
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    arr[..., 0] = 5; arr[..., 1] = 8; arr[..., 2] = 18
    arr[..., 3] = a[:, None]
    return Image.fromarray(arr, "RGBA")


# ---- captions --------------------------------------------------------------
def draw_caption(d, kicker, line, line2, accent, t_in, chip=None,
                 source=None, line_size=64):
    """Lower-third caption with accent bar; optional small source footer."""
    a = ease(t_in)
    yo = int((1 - a) * 30)
    al = int(255 * a)
    x = 130
    base_y = 824 if source else 840
    bar_h = 150 if line2 else 96
    d.rounded_rectangle([x - 30, base_y - 20 + yo, x - 18, base_y - 20 + bar_h + yo],
                        6, fill=accent + (al,))
    if chip:
        cf = bold(28)
        cw = d.textlength(chip, font=cf) + 40
        d.rounded_rectangle([x, base_y - 78 + yo, x + cw, base_y - 30 + yo], 24,
                            fill=accent + (int(40 * a),), outline=accent + (al,), width=2)
        d.text((x + cw / 2, base_y - 54 + yo), chip, font=cf,
               fill=C["text"] + (al,), anchor="mm")
    elif kicker:
        d.text((x, base_y - 56 + yo), kicker, font=bold(30),
               fill=accent + (al,), anchor="lm")
    d.text((x, base_y + yo), line, font=black(line_size), fill=C["text"] + (al,), anchor="lm")
    last_y = base_y
    if line2:
        d.text((x, base_y + 78 + yo), line2, font=black(line_size),
               fill=C["text"] + (al,), anchor="lm")
        last_y = base_y + 78
    if source:
        d.text((x, last_y + 58 + yo), source, font=reg(26),
               fill=C["muted"] + (int(220 * a),), anchor="lm")


def draw_disclaimer(d, t_in, text="Dramatization. Individual results vary."):
    a = ease(t_in)
    d.text((W - 60, H - 50), text, font=reg(24),
           fill=C["muted"] + (int(200 * a),), anchor="rm")


# ---- mascot / brand --------------------------------------------------------
_mascot = {}


def mascot(width):
    if width in _mascot:
        return _mascot[width]
    im = Image.open(os.path.join(PUB, "brand", "mascot.png")).convert("RGBA")
    h = int(width * im.height / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    vy, vx = np.mgrid[0:h, 0:width].astype(np.float32)
    nx = (vx - width / 2) / (width / 2); ny = (vy - h / 2) / (h / 2)
    r = (nx ** 2 + ny ** 2) ** 0.5
    a = (np.clip(1 - (r - 0.7) / 0.45, 0, 1) ** 1.3 * 255).astype("uint8")
    im.putalpha(Image.fromarray(a, "L"))
    _mascot[width] = im
    return im


def gradient_text(s, font, c1, c2):
    tmp = Image.new("L", (10, 10)); td = ImageDraw.Draw(tmp)
    bb = td.textbbox((0, 0), s, font=font); tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = 24
    mask = Image.new("L", (tw + pad * 2, th + pad * 2), 0)
    ImageDraw.Draw(mask).text((pad - bb[0], pad - bb[1]), s, font=font, fill=255)
    g = np.linspace(0, 1, mask.width, dtype=np.float32)[None, :, None]
    col = (np.array(c1, np.float32)[None, None, :] * (1 - g)
           + np.array(c2, np.float32)[None, None, :] * g)
    col = np.repeat(col, mask.height, axis=0)
    out = Image.fromarray(col.astype("uint8"), "RGB").convert("RGBA")
    out.putalpha(mask)
    return out


def fade_rgba(rgba, a):
    r, g, b, al = rgba.split()
    al = al.point(lambda v: int(v * a))
    return Image.merge("RGBA", (r, g, b, al))


def bg_gradient():
    """Brand radial+linear background (RGB array as float for further drawing)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = (xx / W) * 0.5 + (yy / H) * 0.5
    base = (np.array(C["bg"], np.float32)[None, None] * (1 - d)[..., None]
            + np.array(C["bgDeep"], np.float32)[None, None] * d[..., None])
    cx, cy = W * 0.5, H * 0.42
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    glow = np.clip(1 - dist / (W * 0.5), 0, 1) ** 2 * 0.5
    base += np.array(C["brand"], np.float32)[None, None] * glow[..., None]
    return Image.fromarray(np.clip(base, 0, 255).astype("uint8"), "RGB").convert("RGBA")


def endcard(p, tagline, url="salareen.com"):
    """Brand end card with its own animation. Returns RGB image."""
    img = bg_gradient()
    dr = ImageDraw.Draw(img)
    pm = ease(clamp01(p / 0.35))
    mw = int(230 * (0.75 + 0.25 * pm))
    m = mascot(mw)
    img.alpha_composite(m, (int(W / 2 - m.width / 2),
                            int(H * 0.30 - m.height / 2 - (1 - pm) * 20)))
    a1 = ease(clamp01((p - 0.2) / 0.3))
    gw = gradient_text("Salareen", black(150), C["brand"], C["mint"])
    if a1 > 0:
        gw2 = fade_rgba(gw, a1)
        img.alpha_composite(gw2, (int(W / 2 - gw2.width / 2), 560))
    a2 = ease(clamp01((p - 0.4) / 0.3))
    dr.text((W / 2, 760), tagline, font=bold(48),
            fill=C["text"] + (int(255 * a2),), anchor="mm")
    a3 = ease(clamp01((p - 0.6) / 0.3))
    f = black(40); tw = dr.textlength(url, font=f)
    pw, ph = tw + 80, 76
    dr.rounded_rectangle([W / 2 - pw / 2, 850, W / 2 + pw / 2, 850 + ph], 14,
                         fill=C["red"] + (int(255 * a3),))
    dr.text((W / 2, 888), url, font=f, fill=(255, 255, 255, int(255 * a3)), anchor="mm")
    return img.convert("RGB")


# ---- encoder ---------------------------------------------------------------
def open_encoder(out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---- generic photo film runner --------------------------------------------
def run_photo_film(shots, out_path, end_tagline, end_url="salareen.com",
                   shot_dur=165, xf=18, end_dur=165, end_xf=18,
                   scrim_strength=205):
    """Render a crossfaded Ken Burns photo film with lower-third captions.

    Each shot dict: img, z0, z1, px, py, kicker, line, line2, accent,
    chip(optional), source(optional), disc(bool), and optional grade kwargs
    (sat, tint, tint_a, darken).
    """
    scrim = make_scrim(scrim_strength)
    starts = []
    t = 0
    for i in range(len(shots)):
        starts.append(t)
        t += shot_dur - (xf if i < len(shots) - 1 else 0)
    end_start = starts[-1] + shot_dur - end_xf
    total = end_start + end_dur
    proc = open_encoder(out_path)

    def shot_img(s, lf):
        p = lf / shot_dur
        im = kenburns(s["img"], p, s["z0"], s["z1"], s["px"], s["py"])
        gkw = {k: s[k] for k in ("sat", "tint", "tint_a", "darken") if k in s}
        if gkw:
            im = grade(im, **gkw)
        return im

    for g in range(total):
        frame = None
        for i, s in enumerate(shots):
            st = starts[i]
            if st <= g < st + shot_dur:
                lf = g - st
                ph = shot_img(s, lf).convert("RGBA")
                if frame is None:
                    frame = ph
                else:
                    frame = Image.blend(frame, ph, clamp01(lf / xf))
        if g >= end_start:
            ep = (g - end_start) / end_dur
            ec = endcard(ep, end_tagline, end_url).convert("RGBA")
            if frame is None:
                frame = ec
            else:
                frame = Image.blend(frame, ec, clamp01((g - end_start) / end_xf))
        if frame is None:
            frame = Image.new("RGBA", (W, H), C["bgDeep"] + (255,))
        if g < end_start + end_xf:
            frame.alpha_composite(scrim)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(ov)
            for i, s in enumerate(shots):
                st = starts[i]
                cap_in = st + xf + 6
                cap_out = st + shot_dur - xf - 6
                if cap_in <= g < cap_out:
                    fade = min(clamp01((g - cap_in) / 12), clamp01((cap_out - g) / 12))
                    draw_caption(d, s.get("kicker"), s["line"], s.get("line2"),
                                 s["accent"], fade, chip=s.get("chip"),
                                 source=s.get("source"),
                                 line_size=s.get("line_size", 64))
                    if s.get("disc"):
                        draw_disclaimer(d, fade)
            frame.alpha_composite(ov)
        proc.stdin.write(frame.convert("RGB").tobytes())
        if g % 30 == 0:
            sys.stderr.write(f"\r{g}/{total}"); sys.stderr.flush()
    proc.stdin.close(); proc.wait()
    sys.stderr.write(f"\r{total}/{total}\n")
    print("wrote", out_path, "rc", proc.returncode, "frames", total)
    return proc.returncode
