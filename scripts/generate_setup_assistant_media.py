#!/usr/bin/env python3
"""Generate reusable setup-assistant explainers and seamless motion loops.

With a Google API key this uses Nano Banana to create the base art. Without a
key (or with --fallback), deterministic branded scenes are rendered locally.
Both paths emit posters and short muted MP4 loops for web and mobile.
"""

from __future__ import annotations

import argparse
import io
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_home_concept_assets import _request  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WEB_OUT = ROOT / "apps/web/public/setup-assistant"
MOBILE_OUT = ROOT / "apps/mobile/assets/setup-assistant"
CACHE = ROOT / "output/setup-assistant-media"
SALA = (
    ROOT
    / "subrepos/theodore_course_studio/src/theodore_course_studio/avatar_static"
    / "presenter_serenity.png"
)
SIZE = (1080, 1080)
FPS = 24
FRAMES = FPS * 4

SCENES = {
    "welcome": (
        (27, 29, 72),
        (86, 190, 255),
        "Premium cinematic square scene: Sala, a friendly blue holographic AI teacher, "
        "welcoming a diverse learner into a luminous personalized learning studio, "
        "calm indigo and cyan light, spacious composition, no text.",
    ),
    "privacy": (
        (14, 58, 65),
        (80, 241, 190),
        "Sala beside a translucent privacy shield surrounding abstract face and voice "
        "symbols, reassuring premium educational technology scene, emerald and cyan, no text.",
    ),
    "portrait": (
        (32, 35, 83),
        (150, 210, 255),
        "Friendly learner centered in a camera portrait guide while Sala encourages them, "
        "soft studio light, inclusive, calm, clear face framing, no text.",
    ),
    "pose": (
        (68, 35, 88),
        (239, 160, 255),
        "Learner gently turning their head through four directions inside an elegant "
        "camera guide, Sala demonstrating beside them, premium purple holographic style, no text.",
    ),
    "voice": (
        (11, 47, 78),
        (88, 225, 255),
        "Learner speaking naturally while a luminous audio waveform flows toward Sala, "
        "quiet home studio, trustworthy blue cinematic lighting, no text.",
    ),
    "identity": (
        (78, 45, 20),
        (255, 194, 94),
        "Abstract government identity card held inside a secure golden verification portal, "
        "Sala nearby, no readable details, no numbers, premium warm cinematic scene, no text.",
    ),
}


def _sala_sprite(height: int) -> Image.Image:
    image = Image.open(SALA).convert("RGBA")
    crop = image.crop((0, 50, image.width, min(image.height, 1170)))
    ratio = height / crop.height
    return crop.resize((int(crop.width * ratio), height), Image.Resampling.LANCZOS)


def _fallback_scene(slug: str, base: tuple[int, int, int], accent: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", SIZE, base)
    draw = ImageDraw.Draw(image, "RGBA")
    for radius in range(680, 80, -45):
        alpha = int(3 + 22 * (1 - radius / 680))
        draw.ellipse(
            (540 - radius, 520 - radius, 540 + radius, 520 + radius),
            fill=(*accent, alpha),
        )
    for x, y, radius in ((120, 180, 190), (920, 180, 230), (860, 900, 300)):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*accent, 20))
    image = image.filter(ImageFilter.GaussianBlur(12))
    draw = ImageDraw.Draw(image, "RGBA")
    sprite = _sala_sprite(790 if slug in {"welcome", "privacy"} else 650)
    image.paste(sprite, (SIZE[0] - sprite.width - 70, SIZE[1] - sprite.height + 40), sprite)
    center = (350, 500)
    if slug == "welcome":
        for radius in (120, 180, 250):
            draw.ellipse(
                (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
                outline=(*accent, 100),
                width=5,
            )
    elif slug == "privacy":
        points = [(350, 220), (560, 310), (520, 650), (350, 790), (180, 650), (140, 310)]
        draw.polygon(points, fill=(*accent, 42), outline=(*accent, 210))
        draw.ellipse((290, 390, 410, 510), outline=(255, 255, 255, 210), width=12)
        draw.rounded_rectangle((250, 500, 450, 650), 45, outline=(255, 255, 255, 210), width=12)
    elif slug == "portrait":
        draw.rounded_rectangle((115, 130, 620, 900), 70, outline=(*accent, 220), width=12)
        draw.ellipse((245, 260, 490, 505), fill=(220, 176, 140, 255))
        draw.rounded_rectangle((180, 520, 555, 850), 120, fill=(80, 120, 180, 210))
    elif slug == "pose":
        draw.ellipse((145, 250, 545, 650), fill=(220, 176, 140, 245))
        for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
            x = 345 + int(math.cos(angle) * 270)
            y = 450 + int(math.sin(angle) * 270)
            draw.line((345, 450, x, y), fill=(*accent, 200), width=12)
            draw.ellipse((x - 20, y - 20, x + 20, y + 20), fill=(*accent, 255))
    elif slug == "voice":
        points = []
        for x in range(80, 660, 8):
            amplitude = 35 + 120 * math.sin((x - 80) / 580 * math.pi) ** 2
            y = 520 + math.sin(x * 0.085) * amplitude
            points.append((x, y))
        draw.line(points, fill=(*accent, 245), width=10, joint="curve")
    else:
        draw.rounded_rectangle((100, 260, 610, 730), 50, fill=(255, 244, 218, 235))
        draw.ellipse((160, 350, 315, 505), fill=(*accent, 180))
        for y in (365, 435, 505, 575):
            draw.rounded_rectangle((350, y, 545, y + 18), 9, fill=(*base, 100))
        draw.rounded_rectangle((70, 220, 645, 770), 70, outline=(*accent, 210), width=12)
    return image


def _nano_scene(slug: str, prompt: str, api_key: str) -> Image.Image:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{slug}.png"
    if cached.is_file():
        return Image.open(cached).convert("RGB")
    reference = Image.open(SALA).convert("RGB")
    reference.thumbnail((768, 768))
    buffer = io.BytesIO()
    reference.save(buffer, "JPEG", quality=90)
    raw = _request(
        prompt
        + " Keep Sala faithful to the supplied reference, including the silver S and green leaf medallion."
        + " No logos, captions, letters, watermarks, religious imagery, or readable text.",
        buffer.getvalue(),
        api_key,
    )
    image = ImageOps.fit(
        Image.open(io.BytesIO(raw)).convert("RGB"), SIZE, Image.Resampling.LANCZOS
    )
    image.save(cached, optimize=True)
    return image


def _motion_frame(base: Image.Image, frame: int) -> Image.Image:
    phase = 2 * math.pi * frame / FRAMES
    zoom = 1.035 + 0.015 * math.sin(phase)
    width, height = base.size
    crop_w, crop_h = width / zoom, height / zoom
    x = width / 2 + math.sin(phase) * 10
    y = height / 2 + math.cos(phase) * 8
    moved = base.resize(
        SIZE,
        Image.Resampling.BICUBIC,
        box=(x - crop_w / 2, y - crop_h / 2, x + crop_w / 2, y + crop_h / 2),
    )
    overlay = Image.new("RGBA", SIZE)
    draw = ImageDraw.Draw(overlay)
    radius = 160 + int(35 * (1 + math.sin(phase)))
    draw.ellipse(
        (540 - radius, 520 - radius, 540 + radius, 520 + radius),
        outline=(255, 255, 255, 40),
        width=8,
    )
    return Image.alpha_composite(moved.convert("RGBA"), overlay).convert("RGB")


def _encode(slug: str, image: Image.Image) -> None:
    WEB_OUT.mkdir(parents=True, exist_ok=True)
    MOBILE_OUT.mkdir(parents=True, exist_ok=True)
    poster = WEB_OUT / f"{slug}.webp"
    image.save(poster, "WEBP", quality=86, method=6)
    process = subprocess.Popen(
        [
            "ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{SIZE[0]}x{SIZE[1]}", "-r", str(FPS), "-i", "-", "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-crf", "25", str(WEB_OUT / f"{slug}.mp4"),
        ],
        stdin=subprocess.PIPE,
    )
    assert process.stdin is not None
    for frame in range(FRAMES):
        process.stdin.write(_motion_frame(image, frame).tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {slug}")
    shutil.copy2(poster, MOBILE_OUT / poster.name)
    shutil.copy2(WEB_OUT / f"{slug}.mp4", MOBILE_OUT / f"{slug}.mp4")


def _font(size: int):
    for path in (
        Path("/System/Library/Fonts/SFNS.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ):
        if path.is_file():
            from PIL import ImageFont

            return ImageFont.truetype(str(path), size)
    from PIL import ImageFont

    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _review_artifacts() -> None:
    """Emit fresh review captures even when a browser binary is unavailable."""
    screens = ROOT / "docs/screens"
    demos = ROOT / "docs/demos"
    screens.mkdir(parents=True, exist_ok=True)
    demos.mkdir(parents=True, exist_ok=True)
    welcome = Image.open(WEB_OUT / "welcome.webp").convert("RGB")

    web = Image.new("RGB", (1440, 900), (8, 11, 29))
    web.paste(ImageOps.fit(welcome, (790, 900), Image.Resampling.LANCZOS), (0, 0))
    draw = ImageDraw.Draw(web)
    draw.rectangle((720, 0, 1440, 900), fill=(8, 11, 29))
    draw.text((815, 170), "OPTIONAL IDENTITY SETUP", font=_font(16), fill=(114, 216, 255))
    title = _wrap(draw, "A simpler way to prove it’s you.", _font(62), 510)
    y = 215
    for line in title:
        draw.text((815, y), line, font=_font(62), fill=(248, 251, 255))
        y += 72
    body = _wrap(
        draw,
        "Four short checks protect your learning record and unlock accredited courses.",
        _font(24),
        500,
    )
    y += 18
    for line in body:
        draw.text((815, y), line, font=_font(24), fill=(189, 199, 223))
        y += 36
    draw.rounded_rectangle((815, y + 42, 1010, y + 98), 28, fill=(114, 216, 255))
    draw.text((860, y + 57), "Continue", font=_font(20), fill=(4, 17, 29))
    web.save(screens / "setup-assistant-web.png", optimize=True)

    mobile = Image.new("RGB", (430, 932), (8, 11, 29))
    mobile.paste(ImageOps.fit(welcome, (430, 455), Image.Resampling.LANCZOS), (0, 0))
    draw = ImageDraw.Draw(mobile)
    draw.rounded_rectangle((0, 420, 430, 932), 30, fill=(8, 11, 29))
    draw.text((24, 470), "SETUP ASSISTANT · 1 OF 5", font=_font(12), fill=(114, 216, 255))
    y = 510
    for line in _wrap(draw, "Welcome to Salareen.", _font(43), 380):
        draw.text((24, y), line, font=_font(43), fill=(248, 251, 255))
        y += 52
    for line in _wrap(draw, "Let’s shape a learning space around you.", _font(19), 375):
        draw.text((24, y + 12), line, font=_font(19), fill=(189, 199, 223))
        y += 30
    draw.rounded_rectangle((24, 800, 406, 856), 28, fill=(114, 216, 255))
    draw.text((176, 817), "Continue", font=_font(18), fill=(4, 17, 29))
    mobile.save(screens / "setup-assistant-mobile.png", optimize=True)

    demo = subprocess.Popen(
        [
            "ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", "720x720", "-r", "24", "-i", "-", "-an", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-crf", "25",
            str(demos / "setup-assistant-walkthrough.mp4"),
        ],
        stdin=subprocess.PIPE,
    )
    assert demo.stdin is not None
    for slug in ("welcome", "privacy", "portrait", "pose", "voice", "identity"):
        frame = ImageOps.fit(
            Image.open(WEB_OUT / f"{slug}.webp").convert("RGB"),
            (720, 720),
            Image.Resampling.LANCZOS,
        )
        for _ in range(48):
            demo.stdin.write(frame.tobytes())
    demo.stdin.close()
    if demo.wait() != 0:
        raise RuntimeError("ffmpeg failed for review walkthrough")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fallback", action="store_true")
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    wanted = set(args.only.split(",")) if args.only else set(SCENES)
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    use_nano = bool(key) and not args.fallback
    print(f"renderer={'nano-banana' if use_nano else 'deterministic-fallback'}")
    for slug, (base, accent, prompt) in SCENES.items():
        if slug not in wanted:
            continue
        image = _nano_scene(slug, prompt, key) if use_nano else _fallback_scene(slug, base, accent)
        _encode(slug, image)
        print(f"wrote {slug}.webp + {slug}.mp4")
    if wanted == set(SCENES):
        _review_artifacts()
        print("wrote review screenshots + walkthrough")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
