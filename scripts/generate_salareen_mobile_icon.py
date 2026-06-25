#!/usr/bin/env python3
"""Generate Salareen mobile launcher icons from the photorealistic Bayon medallion art.

Source: apps/web/public/bayon-mark.webp (canonical mascot master).
Outputs:
  apps/mobile/assets/salareen_icon_1024.png  — iOS/Android launcher + splash
  apps/mobile/assets/salareen_mark_256.png   — in-app header logo (HomeScreen)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "apps" / "web" / "public" / "bayon-mark.webp"
OUT_DIR = ROOT / "apps" / "mobile" / "assets"

# Crop box on 250x512 master: photorealistic gold medallion + bodhi leaf only.
MEDALLION_CROP = (52, 215, 198, 361)
BRAND_BG = (11, 16, 32, 255)  # #0b1020


def render_icon(size: int, fill_ratio: float = 0.82) -> Image.Image:
    src = Image.open(MASTER).convert("RGBA")
    crop = src.crop(MEDALLION_CROP)
    canvas = Image.new("RGBA", (size, size), BRAND_BG)
    target = int(size * fill_ratio)
    scale = min(target / crop.width, target / crop.height)
    nw = max(1, int(crop.width * scale))
    nh = max(1, int(crop.height * scale))
    resized = crop.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (size - nw) // 2
    y = (size - nh) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def main() -> None:
    if not MASTER.is_file():
        raise SystemExit(f"Missing master art: {MASTER}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    icon_1024 = render_icon(1024)
    mark_256 = render_icon(256)

    icon_path = OUT_DIR / "salareen_icon_1024.png"
    mark_path = OUT_DIR / "salareen_mark_256.png"
    icon_1024.save(icon_path)
    mark_256.save(mark_path)
    print(f"Wrote {icon_path} ({icon_1024.size[0]}x{icon_1024.size[1]})")
    print(f"Wrote {mark_path} ({mark_256.size[0]}x{mark_256.size[1]})")


if __name__ == "__main__":
    main()
