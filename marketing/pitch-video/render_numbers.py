#!/usr/bin/env python3
"""Salareen data spot - "By the Numbers".

Animated stat reveals (count-ups) of the global learning crisis, then a turn:
"Salareen changes the math." Pure motion graphics on the brand gradient — no
cast. Built on the same Pillow + ffmpeg pipeline as the other films.

Output: docs/demos/salareen_by_the_numbers.mp4
"""
import os

from PIL import Image, ImageDraw

import promo_lib as P

OUT = os.path.join(P.DEMOS, "salareen_by_the_numbers.mp4")
C = P.C
W, H = P.W, P.H

BG = P.bg_gradient()

STATS = [
    dict(prefix="", value=70, dec=0, suffix="%", accent=C["red"],
         l1="of 10-year-olds can't read", l2="a simple story.",
         source="World Bank / UNESCO, 2022"),
    dict(prefix="$", value=21, dec=0, suffix="T", accent=C["gold"],
         l1="in lost lifetime earnings", l2="for this generation.",
         source="World Bank / UNESCO / UNICEF, 2022"),
    dict(prefix="", value=44, dec=0, suffix="M", accent=C["accent"],
         l1="teachers the world is", l2="missing by 2030.",
         source="UNESCO, 2024"),
    dict(prefix="", value=250, dec=0, suffix="M+", accent=C["brand"],
         l1="children and youth", l2="are out of school.",
         source="UNESCO, 2024"),
    dict(prefix="", value=90, dec=0, suffix="%", accent=C["mint"],
         l1="of new training is forgotten", l2="within a week.",
         source="Research suggests — Ebbinghaus; Murre & Dros, 2015"),
]

SOLUTIONS = [
    ("1:1 adaptive tutoring, at scale", C["brand"]),
    ("Taught in the learner's language", C["mint"]),
    ("Spaced repetition that sticks", C["gold"]),
    ("Mobile, offline, hands-free", C["accent"]),
]


def header(d, a):
    al = int(210 * a)
    txt = "THE LEARNING CRISIS  ·  BY THE NUMBERS"
    d.text((W / 2, 150), txt, font=P.bold(30), fill=C["muted"] + (al,), anchor="mm")


def dots(d, active, a):
    n = len(STATS)
    gap = 46
    x0 = W / 2 - (n - 1) * gap / 2
    for i in range(n):
        on = i == active
        r = 9 if on else 6
        col = (STATS[i]["accent"] if on else C["muted"]) + (int((255 if on else 120) * a),)
        cx = x0 + i * gap
        d.ellipse([cx - r, 952 - r, cx + r, 952 + r], fill=col)


def fmt(v, dec):
    return f"{v:.{dec}f}"


def draw_stat(stat, idx, p):
    """p in [0,1] local scene progress. Returns RGB frame."""
    a_in = P.ease(P.clamp01(p / 0.16))
    a_out = P.ease(P.clamp01((1 - p) / 0.12))
    a = min(a_in, a_out)
    yo = int((1 - a_in) * 44)
    frame = BG.copy()
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    header(d, a)
    cv = stat["value"] * P.ease(P.clamp01(p / 0.5))
    num = f'{stat["prefix"]}{fmt(cv, stat["dec"])}{stat["suffix"]}'
    al = int(255 * a)
    # big number
    nf = P.black(240)
    d.text((W / 2, 420 + yo), num, font=nf, fill=C["text"] + (al,), anchor="mm")
    # accent underline
    bw = 150
    d.rounded_rectangle([W / 2 - bw / 2, 560 + yo, W / 2 + bw / 2, 570 + yo], 5,
                        fill=stat["accent"] + (al,))
    # label
    d.text((W / 2, 648 + yo), stat["l1"], font=P.bold(52), fill=C["text"] + (al,), anchor="mm")
    d.text((W / 2, 712 + yo), stat["l2"], font=P.bold(52), fill=C["text"] + (al,), anchor="mm")
    # source
    d.text((W / 2, 808 + yo), stat["source"], font=P.reg(28),
           fill=C["muted"] + (int(220 * a),), anchor="mm")
    dots(d, idx, a)
    frame.alpha_composite(ov)
    return frame.convert("RGB")


def draw_intro(p):
    a = P.ease(P.clamp01(p / 0.25))
    ao = P.ease(P.clamp01((1 - p) / 0.18))
    a = min(a, ao)
    yo = int((1 - P.ease(P.clamp01(p / 0.25))) * 40)
    frame = BG.copy()
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.text((W / 2, 430 + yo), "THE LEARNING CRISIS", font=P.bold(46),
           fill=C["muted"] + (int(230 * a),), anchor="mm")
    gw = P.gradient_text("By the Numbers", P.black(140), C["brand"], C["mint"])
    gw = P.fade_rgba(gw, a)
    frame.alpha_composite(ov)
    frame.alpha_composite(gw, (int(W / 2 - gw.width / 2), int(520 + yo)))
    return frame.convert("RGB")


def draw_turn(p):
    a_in = P.ease(P.clamp01(p / 0.22))
    a_out = P.ease(P.clamp01((1 - p) / 0.16))
    a = min(a_in, a_out)
    yo = int((1 - a_in) * 40)
    frame = BG.copy()
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    gw = P.gradient_text("Salareen", P.black(120), C["brand"], C["mint"])
    gw = P.fade_rgba(gw, a)
    frame.alpha_composite(ov)
    frame.alpha_composite(gw, (int(W / 2 - gw.width / 2), int(420 + yo)))
    d2 = ImageDraw.Draw(frame)
    d2.text((W / 2, 640 + yo), "changes the math.", font=P.black(72),
            fill=C["text"] + (int(255 * a),), anchor="mm")
    return frame.convert("RGB")


def draw_solutions(p):
    a_out = P.ease(P.clamp01((1 - p) / 0.12))
    frame = BG.copy()
    d = ImageDraw.Draw(frame)
    d.text((W / 2, 200), "Built to flip every number.", font=P.bold(40),
           fill=C["muted"] + (int(220 * a_out),), anchor="mm")
    n = len(SOLUTIONS)
    y0 = 340
    rh = 118
    for i, (label, accent) in enumerate(SOLUTIONS):
        stagger = P.clamp01((p - i * 0.12) / 0.18)
        a = min(P.ease(stagger), a_out)
        if a <= 0:
            continue
        xo = int((1 - P.ease(stagger)) * 60)
        al = int(255 * a)
        y = y0 + i * rh
        x1, x2 = 460 + xo, W - 460 + xo
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        do = ImageDraw.Draw(ov)
        do.rounded_rectangle([x1, y, x2, y + 88], 22,
                             fill=C["panel"] + (int(235 * a),),
                             outline=accent + (al,), width=2)
        do.ellipse([x1 + 30, y + 30, x1 + 58, y + 58], fill=accent + (al,))
        do.text((x1 + 86, y + 44), label, font=P.bold(40),
                fill=C["text"] + (al,), anchor="lm")
        frame.alpha_composite(ov)
    return frame.convert("RGB")


def main():
    proc = P.open_encoder(OUT)
    timeline = []
    timeline.append((54, draw_intro))
    for i, st in enumerate(STATS):
        timeline.append((78, (lambda st, i: (lambda g, n: draw_stat(st, i, g / n)))(st, i)))
    timeline.append((66, lambda g, n: draw_turn(g / n)))
    timeline.append((132, lambda g, n: draw_solutions(g / n)))
    # endcard
    END = 150
    total = sum(n for n, _ in timeline) + END
    written = 0
    # intro special signature (g/n)
    for n, fn in timeline:
        for g in range(n):
            if fn is draw_intro:
                img = draw_intro(g / n)
            else:
                img = fn(g, n)
            proc.stdin.write(img.tobytes())
            written += 1
            if written % 30 == 0:
                import sys
                sys.stderr.write(f"\r{written}/{total}"); sys.stderr.flush()
    for g in range(END):
        img = P.endcard(g / END, "The math finally works.", "salareen.com").convert("RGB")
        proc.stdin.write(img.tobytes())
        written += 1
    proc.stdin.close(); proc.wait()
    import sys
    sys.stderr.write(f"\r{total}/{total}\n")
    print("wrote", OUT, "rc", proc.returncode, "frames", total)


if __name__ == "__main__":
    main()
