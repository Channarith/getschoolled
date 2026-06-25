#!/usr/bin/env python3
"""Generate Salareen mobile launcher icons from the photorealistic Bayon medallion art.

Source: apps/web/public/bayon-mark.webp (canonical mascot master).
Outputs:
  apps/mobile/assets/salareen_icon_1024.png           — iOS launcher + splash
  apps/mobile/assets/salareen_adaptive_fg_1024.png    — Android adaptive foreground
  apps/mobile/assets/salareen_mark_256.png            — in-app header logo (HomeScreen)

Android adaptive icons mask to a circle; only the center ~66% is guaranteed visible.
We crop the mascot upper body + full medallion (S + bodhi leaf) and scale conservatively
so the full S and part of the mascot survive the circular mask.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "apps" / "web" / "public" / "bayon-mark.webp"
OUT_DIR = ROOT / "apps" / "mobile" / "assets"

# Mascot face, hands, and full medallion (complete golden S + bodhi leaf).
# Master is 250x512; this box is the upper-body square used for launcher art.
LAUNCHER_CROP = (0, 40, 250, 380)

# Tighter crop for the small in-app mark (medallion + chin, no crown tip).
MARK_CROP = (20, 155, 230, 365)

BRAND_BG = (11, 16, 32, 255)  # #0b1020

# Fill ratios: fraction of canvas used by artwork (rest = brand padding).
IOS_FILL = 0.62
ANDROID_ADAPTIVE_FILL = 0.54  # extra inset for circular mask
MARK_FILL = 0.88


def render_icon(
    size: int,
    crop_box: tuple[int, int, int, int],
    *,
    fill_ratio: float,
) -> Image.Image:
    src = Image.open(MASTER).convert("RGBA")
    crop = src.crop(crop_box)
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

    icon_path = OUT_DIR / "salareen_icon_1024.png"
    adaptive_path = OUT_DIR / "salareen_adaptive_fg_1024.png"
    mark_path = OUT_DIR / "salareen_mark_256.png"

    render_icon(1024, LAUNCHER_CROP, fill_ratio=IOS_FILL).save(icon_path)
    render_icon(1024, LAUNCHER_CROP, fill_ratio=ANDROID_ADAPTIVE_FILL).save(adaptive_path)
    render_icon(256, MARK_CROP, fill_ratio=MARK_FILL).save(mark_path)

    print(f"Wrote {icon_path} (iOS fill={IOS_FILL})")
    print(f"Wrote {adaptive_path} (Android adaptive fill={ANDROID_ADAPTIVE_FILL})")
    print(f"Wrote {mark_path} (in-app mark fill={MARK_FILL})")


if __name__ == "__main__":
    main()
