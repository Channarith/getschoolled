#!/usr/bin/env python3
"""Browser-free renderer for the Salareen investor pitch video.

Chromium cannot launch in this sandbox, so instead of Remotion this script
draws every frame with Pillow + numpy and pipes raw RGB frames into ffmpeg
(libx264). Output: docs/demos/salareen_investor_pitch.mp4

The high-fidelity Remotion project in src/ produces the same storyboard and can
be rendered locally (`npm run render`) where a real Chrome is available.
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(HERE, "public")
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "docs", "demos",
                                   "salareen_investor_pitch.mp4"))

W, H, FPS = 1920, 1080, 30

# --- brand palette (docs/brand/branding.txt + globals.css) ------------------
C = {
    "bg": (11, 16, 32), "bgDeep": (7, 10, 22),
    "panel": (21, 28, 52), "panel2": (29, 39, 70),
    "text": (232, 236, 246), "muted": (154, 166, 194),
    "border": (42, 52, 97), "accent": (110, 168, 254),
    "brand": (14, 165, 233), "mint": (139, 233, 192),
    "gold": (251, 191, 36), "red": (229, 9, 20),
}

FONT_DIR = "/System/Library/Fonts/Supplemental"
def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)

def black(s): return _font("Arial Black.ttf", s)
def bold(s):  return _font("Arial Bold.ttf", s)
def reg(s):   return _font("Arial.ttf", s)

# --- easing -----------------------------------------------------------------
def clamp01(x): return max(0.0, min(1.0, x))
def ease_out(t): return 1 - (1 - t) ** 3
def appear(f, start, dur=10): return ease_out(clamp01((f - start) / dur))

# --- background (precomputed gradient + per-frame moving glow) --------------
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
_diag = ((XX / W) * 0.5 + (YY / H) * 0.5)
_base = (np.array(C["bg"], np.float32)[None, None, :] * (1 - _diag)[..., None]
         + np.array(C["bgDeep"], np.float32)[None, None, :] * _diag[..., None])

def background(accent, f):
    cx = W * (0.5 + 0.06 * math.sin(f / 40))
    cy = H * (0.30 + 0.04 * math.sin(f / 33))
    d = np.sqrt((XX - cx) ** 2 + (YY - cy) ** 2)
    g = np.clip(1 - d / (W * 0.55), 0, 1) ** 2 * 0.45
    img = _base + np.array(accent, np.float32)[None, None, :] * g[..., None]
    # secondary mint glow, lower-left, gentle
    cx2, cy2 = W * 0.18, H * 0.82
    d2 = np.sqrt((XX - cx2) ** 2 + (YY - cy2) ** 2)
    g2 = np.clip(1 - d2 / (W * 0.5), 0, 1) ** 2 * 0.16
    img += np.array(C["mint"], np.float32)[None, None, :] * g2[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")

# --- text helpers -----------------------------------------------------------
def text_center(d, cx, y, s, font, fill, anchor="mm"):
    d.text((cx, y), s, font=font, fill=fill, anchor=anchor)

def tracked(d, cx, y, s, font, fill, track):
    widths = [d.textlength(ch, font=font) for ch in s]
    total = sum(widths) + track * (len(s) - 1)
    x = cx - total / 2
    for ch, w in zip(s, widths):
        d.text((x, y), ch, font=font, fill=fill, anchor="lm")
        x += w + track

def kicker(d, cx, y, s, color, size=26):
    tracked(d, cx, y, s.upper(), bold(size), color + (255,), 8)

def gradient_text(s, font, c1, c2):
    """Render a left->right gradient word as an RGBA image."""
    tmp = Image.new("L", (10, 10))
    td = ImageDraw.Draw(tmp)
    bbox = td.textbbox((0, 0), s, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 20
    mask = Image.new("L", (tw + pad * 2, th + pad * 2), 0)
    ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), s, font=font, fill=255)
    grad = np.linspace(0, 1, mask.width, dtype=np.float32)[None, :, None]
    col = (np.array(c1, np.float32)[None, None, :] * (1 - grad)
           + np.array(c2, np.float32)[None, None, :] * grad)
    col = np.repeat(col, mask.height, axis=0)
    out = Image.fromarray(col.astype(np.uint8), "RGB").convert("RGBA")
    out.putalpha(mask)
    return out

def paste_alpha(base, layer, cx, cy, a=1.0):
    if a <= 0:
        return
    if a < 1:
        r, g, b, al = layer.split()
        al = al.point(lambda v: int(v * a))
        layer = Image.merge("RGBA", (r, g, b, al))
    base.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))

# --- asset cache ------------------------------------------------------------
_cards, _mascot = {}, {}

def rounded_mask(size, rad):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], rad, fill=255)
    return m

def card(path, width):
    key = (path, width)
    if key in _cards:
        return _cards[key]
    im = Image.open(os.path.join(PUB, path)).convert("RGBA")
    h = int(width * im.height / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    rad = 18
    im.putalpha(rounded_mask((width, h), rad))
    pad = 60
    canvas = Image.new("RGBA", (width + pad * 2, h + pad * 2), (0, 0, 0, 0))
    # drop shadow
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [pad, pad + 16, pad + width, pad + h + 16], rad, fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(26))
    canvas.alpha_composite(sh)
    # border frame
    fr = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(fr).rounded_rectangle(
        [pad - 6, pad - 6, pad + width + 6, pad + h + 6], rad + 4,
        outline=C["border"] + (255,), width=3)
    canvas.alpha_composite(fr)
    canvas.alpha_composite(im, (pad, pad))
    _cards[key] = canvas
    return canvas

def mascot(width):
    if width in _mascot:
        return _mascot[width]
    im = Image.open(os.path.join(PUB, "brand", "mascot.png")).convert("RGBA")
    h = int(width * im.height / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    # vignette alpha so the navy backdrop melts into the scene
    vy, vx = np.mgrid[0:h, 0:width].astype(np.float32)
    nx = (vx - width / 2) / (width / 2)
    ny = (vy - h / 2) / (h / 2)
    r = np.sqrt(nx ** 2 + ny ** 2)
    a = np.clip(1 - (r - 0.7) / 0.45, 0, 1) ** 1.3
    al = (a * 255).astype(np.uint8)
    im.putalpha(Image.fromarray(al, "L"))
    _mascot[width] = im
    return im

# ============================================================================
# SCENES — each returns an RGBA content layer for local frame f (0..dur)
# ============================================================================
def L():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))

def scene_hook(f, dur):
    img = L(); d = ImageDraw.Draw(img)
    kicker(d, W / 2, 300, "The classroom of 1825", C["muted"])
    # count up 200
    val = int(ease_out(clamp01((f - 12) / 45)) * 200)
    p = appear(f, 10)
    big = black(220)
    d.text((W / 2, 480), f"{val} years", font=big, fill=C["text"] + (int(255 * p),), anchor="mm")
    if f > 26:
        a = appear(f, 28)
        d.text((W / 2, 660), "One teacher. One pace. Thirty different minds.",
               font=bold(48), fill=C["muted"] + (int(255 * a),), anchor="mm")
    # row of identical desks, one fading out (left behind)
    pa = appear(f, 40)
    n = 9; cw, gap = 70, 28
    total = n * cw + (n - 1) * gap
    x0 = W / 2 - total / 2
    for i in range(n):
        x = x0 + i * (cw + gap)
        left_behind = (i == 6)
        col = C["panel"] if left_behind else C["panel2"]
        bd = C["red"] if left_behind else C["border"]
        a = int(255 * pa * (0.5 if left_behind else 1.0))
        d.rounded_rectangle([x, 760, x + cw, 810], 8, fill=col + (a,), outline=bd + (a,), width=3)
    return img

def scene_problem(f, dur):
    img = L(); d = ImageDraw.Draw(img)
    kicker(d, W / 2, 250, "The same lesson, the same speed", C["red"])
    rows = [("Races ahead - bored", 1.0, C["mint"], 12),
            ("Keeps up - for now", 0.6, C["accent"], 22),
            ("Falls behind - left out", 0.28, C["red"], 32)]
    y = 380
    for label, val, col, delay in rows:
        a = appear(f, delay)
        d.text((760, y), label, font=bold(34), fill=C["muted"] + (int(255 * a),), anchor="rm")
        bx0, bx1 = 800, 1500
        d.rounded_rectangle([bx0, y - 16, bx1, y + 16], 16, fill=C["panel"] + (int(255 * a),))
        fill = ease_out(clamp01((f - delay) / 30)) * val
        if fill > 0:
            d.rounded_rectangle([bx0, y - 16, bx0 + (bx1 - bx0) * fill, y + 16], 16,
                                fill=col + (int(255 * a),))
        y += 90
    if f > 54:
        a = appear(f, 56)
        d.text((W / 2, 720), "What if every learner had their own teacher?",
               font=black(58), fill=C["text"] + (int(255 * a),), anchor="mm")
    return img

def scene_reveal(f, dur):
    img = L(); d = ImageDraw.Draw(img)
    pm = appear(f, 6, 16)
    mw = int(420 * (0.7 + 0.3 * pm))
    paste_alpha(img, mascot(mw), 470, H / 2, pm)
    lx = 760
    if f > 14:
        a = appear(f, 14)
        d.text((lx, 360), "SALAREEN - KHMER FOR 'TO GO TO SCHOOL'",
               font=bold(24), fill=C["brand"] + (int(255 * a),), anchor="lm")
    # headline "Meet Salareen"
    if f > 20:
        a = appear(f, 22)
        mfont = black(116)
        d.text((lx, 470), "Meet", font=mfont, fill=C["text"] + (int(255 * a),), anchor="lm")
        meet_w = d.textlength("Meet", font=mfont)
        gw = gradient_text("Salareen", mfont, C["brand"], C["mint"])
        gap = 44
        center = lx + meet_w + gap + gw.width / 2 - 20
        paste_alpha(img, gw, center, 470, a)
    if f > 32:
        a = appear(f, 34)
        d.text((lx, 600), "Thousands of classes. One AI campus.",
               font=bold(54), fill=C["text"] + (int(255 * a),), anchor="lm")
    if f > 44:
        a = appear(f, 46)
        d.text((lx, 690), "A patient, brilliant teacher for every learner -",
               font=reg(36), fill=C["muted"] + (int(255 * a),), anchor="lm")
        d.text((lx, 740), "in their language, on any device.",
               font=reg(36), fill=C["muted"] + (int(255 * a),), anchor="lm")
    return img

FEATURES = [
    ("screens/live_class_grounded_answer.webp", "An AI tutor that shows its work",
     "Cites its sources. Never bluffs.", C["accent"]),
    ("screens/drive_mode_player.webp", "Class on your commute",
     "Hands-free audio - eyes on the road.", C["mint"]),
    ("screens/languages_grid.webp", "Teaches in your language",
     "All 27 of them.", C["brand"]),
    ("screens/careers_match.webp", "Links lessons to real jobs",
     "Learn the skill the role actually needs.", C["gold"]),
    ("screens/kids_mode.webp", "Safe and playful for kids",
     "Games, rewards, guardrails built in.", C["mint"]),
]

def scene_features(f, dur):
    img = L(); d = ImageDraw.Draw(img)
    kicker(d, W / 2, 90, "Like Netflix for learning", C["accent"])
    d.text((W / 2, 165), "...but it actually teaches.", font=black(56),
           fill=C["text"] + (255,), anchor="mm")
    per = 36
    idx = min(int(f // per), len(FEATURES) - 1)
    local = f - idx * per
    path, title, body, col = FEATURES[idx]
    a = ease_out(clamp01(local / 8))
    out = clamp01((per - local) / 6) if local > per - 6 else 1.0
    a = min(a, out) if idx < len(FEATURES) - 1 else a
    c = card(path, 720)
    slide = (1 - ease_out(clamp01(local / 10))) * 80
    paste_alpha(img, c, W / 2, 560 + slide, a)
    d.text((W / 2, 880), title, font=black(50), fill=col + (int(255 * a),), anchor="mm")
    d.text((W / 2, 945), body, font=reg(34), fill=C["muted"] + (int(255 * a),), anchor="mm")
    # progress dots
    n = len(FEATURES); dot = 16; gap = 22
    tot = n * dot + (n - 1) * gap
    x0 = W / 2 - tot / 2
    for i in range(n):
        x = x0 + i * (dot + gap)
        on = (i == idx)
        d.ellipse([x, 1010, x + dot, 1010 + dot],
                  fill=(col if on else C["border"]) + (255,))
    return img

def scene_safety(f, dur):
    img = L(); d = ImageDraw.Draw(img)
    a = appear(f, 2)
    d.text((W / 2, 300), "No one else puts it", font=black(72),
           fill=C["text"] + (int(255 * a),), anchor="mm")
    gw = gradient_text("all in one campus.", black(72), C["brand"], C["mint"])
    paste_alpha(img, gw, W / 2, 390, a)
    chips = [("A real teacher reviews where it matters", C["mint"], 18),
             ("Private & consent-gated - can run on-device", C["accent"], 26),
             ("Helps teachers - never replaces them", C["gold"], 34)]
    # layout chips on a centered row (fit within margins)
    fonts = bold(25)
    widths = [d.textlength(t, font=fonts) + 48 for t, _, _ in chips]
    gap = 26
    total = sum(widths) + gap * (len(chips) - 1)
    x = W / 2 - total / 2
    for (t, col, delay), w in zip(chips, widths):
        ca = appear(f, delay)
        y0, y1 = 560, 632
        d.rounded_rectangle([x, y0, x + w, y1], 36,
                            fill=col + (int(30 * ca),), outline=col + (int(180 * ca),), width=2)
        d.text((x + w / 2, (y0 + y1) / 2), t, font=fonts,
               fill=C["text"] + (int(255 * ca),), anchor="mm")
        x += w + gap
    if f > 42:
        a2 = appear(f, 44)
        d.text((W / 2, 760), "Built to lift students up - never to put them at risk.",
               font=reg(40), fill=C["muted"] + (int(255 * a2),), anchor="mm")
    return img

STATS = [("5M", "learners a day, ready on day one", C["brand"], 14, 5, "M", 0),
         ("$0.0012", "cost per learner / month", C["mint"], 20, 0.0012, "", 4),
         ("27", "languages, one platform", C["gold"], 26, 27, "", 0),
         ("6.3ms", "to answer - fast at any size", C["accent"], 30, 6.3, "ms", 1)]

def _fmt(target, suf, dec, t):
    v = ease_out(t) * target
    if dec == 0:
        s = f"{int(round(v))}"
    else:
        s = f"{v:.{dec}f}"
    pre = "$" if suf == "" and target < 1 else ""
    return f"{pre}{s}{suf}"

def scene_scale(f, dur):
    img = L(); d = ImageDraw.Draw(img)
    kicker(d, W / 2, 175, "Built like a power grid - it grows itself", C["brand"])
    d.text((W / 2, 250), "From one laptop to millions - same code, anywhere.",
           font=black(58), fill=C["text"] + (255,), anchor="mm")
    cw, ch, gap = 410, 240, 30
    n = len(STATS)
    total = n * cw + (n - 1) * gap
    x0 = W / 2 - total / 2
    y0 = 400
    for i, (disp, label, col, delay, target, suf, dec) in enumerate(STATS):
        p = appear(f, delay, 14)
        x = x0 + i * (cw + gap)
        yo = (1 - p) * 40
        a = int(255 * p)
        d.rounded_rectangle([x, y0 + yo, x + cw, y0 + ch + yo], 24,
                            fill=C["panel"] + (a,), outline=col + (int(170 * p),), width=2)
        t = clamp01((f - delay) / 40)
        d.text((x + cw / 2, y0 + 95 + yo), _fmt(target, suf, dec, t),
               font=black(82), fill=col + (a,), anchor="mm")
        # label may wrap into two lines
        for li, line in enumerate(_wrap(label, 22)):
            d.text((x + cw / 2, y0 + 165 + li * 38 + yo), line,
                   font=reg(28), fill=C["muted"] + (a,), anchor="mm")
    if f > 46:
        a2 = appear(f, 48)
        d.text((W / 2, 760), "A whole campus for the price of one small server -",
               font=reg(38), fill=C["muted"] + (int(255 * a2),), anchor="mm")
        d.text((W / 2, 808), "and it plugs into the tools schools already use.",
               font=reg(38), fill=C["muted"] + (int(255 * a2),), anchor="mm")
    return img

def _wrap(text, width):
    words = text.split(); lines = []; cur = ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines

def scene_close(f, dur):
    img = L(); d = ImageDraw.Draw(img)
    pm = appear(f, 6, 16)
    paste_alpha(img, mascot(int(240 * (0.7 + 0.3 * pm))), W / 2, 280, pm)
    if f > 14:
        a = appear(f, 14)
        gw = gradient_text("Salareen", black(170), C["brand"], C["mint"])
        paste_alpha(img, gw, W / 2, 500, a)
    if f > 24:
        a = appear(f, 24)
        d.text((W / 2, 620), "Education that adapts to every child. Safely.",
               font=bold(52), fill=C["text"] + (int(255 * a),), anchor="mm")
    if f > 38:
        a = appear(f, 40)
        # CTA pill
        label = "salareen.com"
        fnt = black(40)
        tw = d.textlength(label, font=fnt)
        pw, ph = tw + 88, 80
        cx = W / 2 - 230
        d.rounded_rectangle([cx - pw / 2, 730, cx + pw / 2, 730 + ph], 14,
                            fill=C["red"] + (int(255 * a),))
        d.text((cx, 770), label, font=fnt, fill=(255, 255, 255, int(255 * a)), anchor="mm")
        d.text((cx + pw / 2 + 40, 770), "Invest in the next 200 years of school.",
               font=bold(36), fill=C["muted"] + (int(255 * a),), anchor="lm")
    return img

# ----------------------------------------------------------------------------
SCENES = [
    (scene_hook, 110, C["muted"]),
    (scene_problem, 110, C["red"]),
    (scene_reveal, 150, C["brand"]),
    (scene_features, 195, C["accent"]),
    (scene_safety, 85, C["mint"]),
    (scene_scale, 150, C["brand"]),
    (scene_close, 85, C["brand"]),
]
TOTAL = sum(s[1] for s in SCENES)

def accent_at(g):
    """Blend scene accent across boundaries for a continuous backdrop."""
    starts, acc = [], []
    t = 0
    for fn, dur, a in SCENES:
        starts.append(t); acc.append(a); t += dur
    # find scene index
    idx = 0
    for i, st in enumerate(starts):
        if g >= st:
            idx = i
    a0 = np.array(acc[idx], np.float32)
    nxt = min(idx + 1, len(acc) - 1)
    end = starts[idx] + SCENES[idx][1]
    blend = clamp01((g - (end - 12)) / 12) if idx < len(SCENES) - 1 else 0
    a1 = np.array(acc[nxt], np.float32)
    return tuple((a0 * (1 - blend) + a1 * blend))

def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # scene start lookup
    starts = []
    t = 0
    for fn, dur, a in SCENES:
        starts.append(t); t += dur
    g = 0
    for si, (fn, dur, acc) in enumerate(SCENES):
        for lf in range(dur):
            bg = background(accent_at(g), g).convert("RGBA")
            content = fn(lf, dur)
            # quick scene-in fade for content
            fin = clamp01(lf / 6)
            if fin < 1:
                r, gg, b, al = content.split()
                al = al.point(lambda v: int(v * fin))
                content = Image.merge("RGBA", (r, gg, b, al))
            bg.alpha_composite(content)
            proc.stdin.write(bg.convert("RGB").tobytes())
            g += 1
            if g % 30 == 0:
                sys.stderr.write(f"\rrendered {g}/{TOTAL} frames"); sys.stderr.flush()
    proc.stdin.close()
    proc.wait()
    sys.stderr.write(f"\rrendered {TOTAL}/{TOTAL} frames\n")
    print("wrote", OUT, "rc", proc.returncode)

if __name__ == "__main__":
    main()
