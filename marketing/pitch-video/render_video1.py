#!/usr/bin/env python3
"""Salareen promo Video 1 - "Have You Heard?" (realistic AI cast).

Photoreal AI-generated actors (public/actors/) are animated with cinematic
Ken Burns motion + crossfades, brand captions stand in for the spoken lines
(add VO/music after), and a branded end card closes it out. Browser-free:
Pillow draws frames, ffmpeg (libx264) encodes.

Output: docs/demos/salareen_promo_have_you_heard.mp4
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(HERE, "public")
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "docs", "demos",
                                   "salareen_promo_have_you_heard.mp4"))
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
    # pan: move crop window across the extra space
    maxx, maxy = nw - W, nh - H
    cx = maxx * (0.5 + px * (p - 0.5))
    cy = maxy * (0.5 + py * (p - 0.5))
    cx = min(max(cx, 0), maxx); cy = min(max(cy, 0), maxy)
    return img.crop((int(cx), int(cy), int(cx) + W, int(cy) + H))

# bottom scrim for caption legibility (precomputed, vectorized)
def _scrim():
    import numpy as np
    ys = np.arange(H, dtype=np.float32)
    f = np.clip((ys - H * 0.45) / (H * 0.55), 0, 1) ** 1.6
    a = (200 * f).astype(np.uint8)
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    arr[..., 0] = 5; arr[..., 1] = 8; arr[..., 2] = 18
    arr[..., 3] = a[:, None]
    return Image.fromarray(arr, "RGBA")
SCRIM = None

# ---- captions --------------------------------------------------------------
def draw_caption(d, img, kicker, line, line2, accent, t_in, chip=None):
    """Lower-third caption with accent bar, fading/sliding in by t_in[0..1]."""
    a = ease(t_in)
    yo = int((1 - a) * 30)
    al = int(255 * a)
    x = 130
    base_y = 840
    # accent bar
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
    d.text((x, base_y + yo), line, font=black(64), fill=C["text"] + (al,), anchor="lm")
    if line2:
        d.text((x, base_y + 78 + yo), line2, font=black(64),
               fill=C["text"] + (al,), anchor="lm")

def draw_disclaimer(d, t_in):
    a = ease(t_in)
    d.text((W - 60, H - 50), "Dramatization. Individual results vary.",
           font=reg(24), fill=C["muted"] + (int(200 * a),), anchor="rm")

# ---- mascot for end card ---------------------------------------------------
_mascot = {}
def mascot(width):
    if width in _mascot:
        return _mascot[width]
    im = Image.open(os.path.join(PUB, "brand", "mascot.png")).convert("RGBA")
    h = int(width * im.height / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    import numpy as np
    vy, vx = np.mgrid[0:h, 0:width].astype(np.float32)
    nx = (vx - width / 2) / (width / 2); ny = (vy - h / 2) / (h / 2)
    r = (nx ** 2 + ny ** 2) ** 0.5
    a = (clamp01_arr(1 - (r - 0.7) / 0.45) ** 1.3 * 255).astype("uint8")
    im.putalpha(Image.fromarray(a, "L"))
    _mascot[width] = im
    return im

def clamp01_arr(x):
    import numpy as np
    return np.clip(x, 0, 1)

def gradient_text(s, font, c1, c2):
    import numpy as np
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

def endcard(p):
    """Brand end card with its own animation, returns RGB image."""
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = (xx / W) * 0.5 + (yy / H) * 0.5
    base = (np.array(C["bg"], np.float32)[None, None] * (1 - d)[..., None]
            + np.array(C["bgDeep"], np.float32)[None, None] * d[..., None])
    cx, cy = W * 0.5, H * 0.42
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    glow = np.clip(1 - dist / (W * 0.5), 0, 1) ** 2 * 0.5
    base += np.array(C["brand"], np.float32)[None, None] * glow[..., None]
    img = Image.fromarray(np.clip(base, 0, 255).astype("uint8"), "RGB").convert("RGBA")
    dr = ImageDraw.Draw(img)
    pm = ease(clamp01(p / 0.35))
    mw = int(230 * (0.75 + 0.25 * pm))
    m = mascot(mw)
    img.alpha_composite(m, (int(W / 2 - m.width / 2), int(H * 0.30 - m.height / 2 - (1 - pm) * 20)))
    a1 = ease(clamp01((p - 0.2) / 0.3))
    gw = gradient_text("Salareen", black(150), C["brand"], C["mint"])
    if a1 > 0:
        r, g, b, al = gw.split(); al = al.point(lambda v: int(v * a1))
        gw2 = Image.merge("RGBA", (r, g, b, al))
        img.alpha_composite(gw2, (int(W / 2 - gw2.width / 2), 560))
    a2 = ease(clamp01((p - 0.4) / 0.3))
    dr.text((W / 2, 760), "Learning people actually remember.",
            font=bold(48), fill=C["text"] + (int(255 * a2),), anchor="mm")
    a3 = ease(clamp01((p - 0.6) / 0.3))
    label = "salareen.com"
    f = black(40); tw = dr.textlength(label, font=f)
    pw, ph = tw + 80, 76
    dr.rounded_rectangle([W / 2 - pw / 2, 850, W / 2 + pw / 2, 850 + ph], 14,
                         fill=C["red"] + (int(255 * a3),))
    dr.text((W / 2, 888), label, font=f, fill=(255, 255, 255, int(255 * a3)), anchor="mm")
    return img.convert("RGB")

# ---- timeline --------------------------------------------------------------
SHOTS = [
    dict(img="actors/v1_shot1_cafe.png", z0=1.06, z1=1.16, px=0.4, py=0.1,
         kicker="HAVE YOU HEARD?", line='"I learned Spanish', line2='in 3 days."',
         accent=C["mint"], chip=None, disc=True),
    dict(img="actors/v1_shot2_market.png", z0=1.16, z1=1.06, px=-0.3, py=0.0,
         kicker=None, line='...so I ordered lunch', line2='in Spanish.',
         accent=C["mint"], chip=None, disc=True),
    dict(img="actors/v1_shot3_walk.png", z0=1.05, z1=1.15, px=0.3, py=0.2,
         kicker=None, line='"My classes ride along', line2='on my walk. Hands-free."',
         accent=C["brand"], chip="DRIVE MODE", disc=False),
    dict(img="actors/v1_shot4_kitchen.png", z0=1.14, z1=1.05, px=0.2, py=-0.1,
         kicker=None, line='"My daughter actually', line2='asks to learn."',
         accent=C["gold"], chip=None, disc=False),
]
SHOT_DUR = 165   # frames each (~5.5s)
XF = 18          # crossfade frames
END_DUR = 165
END_XF = 18

def shot_frame(s, lf, dur):
    p = lf / dur
    return kenburns(s["img"], p, s["z0"], s["z1"], s["px"], s["py"])

def main():
    global SCRIM
    SCRIM = _scrim()
    # layer windows
    starts = []
    t = 0
    for i in range(len(SHOTS)):
        starts.append(t); t += SHOT_DUR - (XF if i < len(SHOTS) - 1 else 0)
    end_start = starts[-1] + SHOT_DUR - END_XF
    total = end_start + END_DUR
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for g in range(total):
        # base photo track (with crossfades)
        frame = None
        for i, s in enumerate(SHOTS):
            st = starts[i]
            if st <= g < st + SHOT_DUR:
                lf = g - st
                ph = shot_frame(s, lf, SHOT_DUR)
                if frame is None:
                    frame = ph.convert("RGBA")
                else:
                    a = clamp01(lf / XF)
                    frame = Image.blend(frame, ph.convert("RGBA"), a)
        # end card crossfade
        if g >= end_start:
            ep = (g - end_start) / END_DUR
            ec = endcard(ep).convert("RGBA")
            if frame is None:
                frame = ec
            else:
                a = clamp01((g - end_start) / END_XF)
                frame = Image.blend(frame, ec, a)
        if frame is None:
            frame = Image.new("RGBA", (W, H), C["bgDeep"] + (255,))
        # overlays only while a photo shot is dominant (not during end card)
        if g < end_start + END_XF:
            frame.alpha_composite(SCRIM)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(ov)
            # current dominant shot
            for i, s in enumerate(SHOTS):
                st = starts[i]
                cap_in = st + XF + 6
                cap_out = st + SHOT_DUR - XF - 6
                if cap_in <= g < cap_out:
                    t_in = clamp01((g - cap_in) / 12)
                    t_out = clamp01((cap_out - g) / 12)
                    fade = min(t_in, t_out)
                    draw_caption(d, frame, s["kicker"], s["line"], s["line2"],
                                 s["accent"], fade, chip=s["chip"])
                    if s["disc"]:
                        draw_disclaimer(d, fade)
            frame.alpha_composite(ov)
        proc.stdin.write(frame.convert("RGB").tobytes())
        if g % 30 == 0:
            sys.stderr.write(f"\r{g}/{total}"); sys.stderr.flush()
    proc.stdin.close(); proc.wait()
    sys.stderr.write(f"\r{total}/{total}\n")
    print("wrote", OUT, "rc", proc.returncode, "frames", total)

if __name__ == "__main__":
    main()
