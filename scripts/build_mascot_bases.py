#!/usr/bin/env python3
"""Build transparent, cropped mascot *base* carvings from reference-guided raws.

Each locale's base carving has a slightly different physique (build) and arm/leg
placement (pose) while keeping the same serene face, Khmer lotus crown, and the
S-with-bodhi-leaf medallion. The raw art is produced from the canonical Khmer
master (apps/web/public/bayon-mark.webp) with a reference-guided image model on a
plain white background; this step keys out the white, trims the halo, tight-crops
to the figure, caps the longest side, and writes transparent WebP bases to
apps/web/public/mascots/base/{locale}.webp.

The Khmer (km) base is the canonical master (unchanged geometry). Run this once
whenever the raws change; scripts/generate_locale_mascots.py then applies each
locale's deterministic stone color tint on top of its base.

Raw dir: env MASCOT_RAW_DIR (files named mascot_{locale}.png), default ./mascot-raws.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = Path(os.environ.get("MASCOT_RAW_DIR", ROOT / "mascot-raws"))
BASE_OUT = ROOT / "apps" / "web" / "public" / "mascots" / "base"
MASTER = ROOT / "apps" / "web" / "public" / "bayon-mark.webp"

WHITE_THRESH = 32          # flood-fill tolerance from the white corners
MARGIN_FRAC = 0.04         # transparent padding around the figure
MAX_SIDE = 512             # cap the longest side (matches the master scale)
CANONICAL_LOCALE = "km"    # base = master, geometry unchanged


def _key_and_crop(img):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    rgb = img.convert("RGB")
    w, h = rgb.size

    # Flood-fill the white background to a sentinel colour from every edge seed,
    # so background pockets reachable from the border are all captured while the
    # (darker) figure and medallion are left untouched.
    sentinel = (1, 254, 2)
    seeds = [
        (0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
        (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2),
    ]
    work = rgb.copy()
    for s in seeds:
        ImageDraw.floodfill(work, s, sentinel, thresh=WHITE_THRESH)

    arr = np.asarray(work)
    bg = (arr[:, :, 0] == sentinel[0]) & (arr[:, :, 1] == sentinel[1]) & (arr[:, :, 2] == sentinel[2])

    rgba = np.array(img.convert("RGBA"))
    rgba[:, :, 3] = np.where(bg, 0, rgba[:, :, 3]).astype(rgba.dtype)
    out = Image.fromarray(rgba, "RGBA")

    # Erode the alpha by 1px to remove the anti-aliased white halo at the edge.
    alpha = out.getchannel("A").filter(ImageFilter.MinFilter(3))
    out.putalpha(alpha)

    bbox = out.getbbox()
    if bbox is None:
        return out
    fig = out.crop(bbox)
    fw, fh = fig.size

    longest = max(fw, fh)
    if longest > MAX_SIDE:
        scale = MAX_SIDE / longest
        fig = fig.resize((max(1, round(fw * scale)), max(1, round(fh * scale))), Image.LANCZOS)
        fw, fh = fig.size

    m = max(1, int(max(fw, fh) * MARGIN_FRAC))
    canvas = Image.new("RGBA", (fw + 2 * m, fh + 2 * m), (0, 0, 0, 0))
    canvas.paste(fig, (m, m), fig)
    return canvas


def main() -> None:
    from PIL import Image

    BASE_OUT.mkdir(parents=True, exist_ok=True)

    # Canonical Khmer base is the master carving (geometry unchanged).
    if not MASTER.is_file():
        raise SystemExit(f"missing master mascot: {MASTER}")
    shutil.copy2(MASTER, BASE_OUT / f"{CANONICAL_LOCALE}.webp")

    raws = sorted(RAW_DIR.glob("mascot_*.png"))
    built = [CANONICAL_LOCALE]
    for raw in raws:
        locale = raw.stem[len("mascot_"):]
        if locale.startswith("pilot") or locale == CANONICAL_LOCALE:
            continue
        with Image.open(raw) as im:
            base = _key_and_crop(im)
        base.save(BASE_OUT / f"{locale}.webp", format="WEBP", quality=92, method=6)
        built.append(locale)

    print(f"Built {len(built)} mascot bases -> {BASE_OUT}")
    print("locales:", ",".join(sorted(built)))


if __name__ == "__main__":
    main()
