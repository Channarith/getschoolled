#!/usr/bin/env python3
"""Generate short seamless video loops for the homepage concept windows.

Nano Banana mode (default) asks Gemini for one base still per clip plus three
small edits of it, caches them under output/home-concept-clips/, then blends
them into a 6-second ping-pong loop with a periodic camera drift.

--fallback renders the same twelve clips locally from the Serenity lip/blink
keyframes and site art, so the windows work without an API key.

Usage:
  set -a && . config/local.env && set +a
  python3 scripts/generate_home_concept_clips.py
  python3 scripts/generate_home_concept_clips.py --only signal-voice
  python3 scripts/generate_home_concept_clips.py --fallback
"""

from __future__ import annotations

import argparse
import io
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_home_concept_assets import _request  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps/web/public"
OUT = PUBLIC / "landing-concepts/clips"
CACHE = ROOT / "output/home-concept-clips"
AVATAR = ROOT / "subrepos/theodore_course_studio/src/theodore_course_studio/avatar_static"
SIZE = (960, 540)
FPS = 24
SECONDS = 6
FRAMES = FPS * SECONDS

GUARD = (
    " Wide 16:9 landscape frame, photorealistic or premium 3D render, natural light, shallow depth of field."
    " The AI teacher is Sala: the friendly glowing blue holographic child character from the reference image,"
    " with the medallion showing a silver S and a green leaf. Keep Sala's design faithful to the reference."
    " No readable text, letters, logos, watermarks, temples, or religious imagery."
)

THEMES = {
    "aurora": {"tint": (236, 214, 255), "alpha": 0.34, "accent": (255, 196, 150), "ink": (40, 30, 48)},
    "worlds": {"tint": (120, 230, 190), "alpha": 0.32, "accent": (240, 107, 67), "ink": (20, 83, 74)},
    "signal": {"tint": (40, 50, 170), "alpha": 0.40, "accent": (140, 255, 219), "ink": (240, 240, 250)},
    "journal": {"tint": (240, 190, 130), "alpha": 0.30, "accent": (182, 58, 46), "ink": (32, 27, 24)},
}


@dataclass
class Clip:
    slug: str
    theme: str
    scene: str
    prompt: str
    edits: list[str]
    options: dict = field(default_factory=dict)


CLIPS = [
    Clip("aurora-avatar", "aurora", "avatar",
         "Sala the holographic AI teacher appears in a live video-call feed, teaching with one hand raised toward a"
         " small floating glowing solar system model, soft pearl and lilac iridescent studio backdrop, calm and premium.",
         ["Edit this exact image: Sala's mouth gently open mid-sentence, the floating planets moved slightly along their orbits. Keep everything else identical.",
          "Edit this exact image: Sala's raised hand turned a little as if explaining, eyes looking at the planets. Keep everything else identical.",
          "Edit this exact image: Sala smiling warmly with eyes back to the camera, planets moved a little further. Keep everything else identical."]),
    Clip("aurora-student", "aurora", "student",
         "Over-the-shoulder view of a curious teenage student at a bright home desk in soft morning light, laptop"
         " screen showing Sala the holographic AI teacher in a video call, student taking notes in a paper notebook.",
         ["Edit this exact image: the student's pen hand moved slightly as if writing the next word. Keep everything else identical.",
          "Edit this exact image: the student tilting their head slightly toward the laptop, listening. Keep everything else identical.",
          "Edit this exact image: Sala on the laptop screen gesturing with one hand. Keep everything else identical."],
         {"screen": "laptop"}),
    Clip("aurora-group", "aurora", "group",
         "A live online group class shown as a clean video-call grid of six tiles: Sala the holographic AI teacher in"
         " the large tile, five diverse smiling learners of different ages in their homes in the other tiles, airy light.",
         ["Edit this exact image: Sala's mouth open mid-sentence and one learner raising a hand. Keep everything else identical.",
          "Edit this exact image: two learners nodding and smiling, Sala gesturing. Keep everything else identical.",
          "Edit this exact image: one learner laughing gently, the raised hand lowered. Keep everything else identical."]),
    Clip("worlds-play", "worlds", "play",
         "A joyful child at a kitchen table holding a green leaf up to a tablet camera; on the tablet screen, playful"
         " augmented-reality bubbles and a small Sala the holographic AI teacher cheering, bright mint and tangerine colors.",
         ["Edit this exact image: the child turning the leaf slightly, eyes wide with delight. Keep everything else identical.",
          "Edit this exact image: Sala on the tablet raising both arms in celebration. Keep everything else identical.",
          "Edit this exact image: the child laughing, leaf held a little closer to the camera. Keep everything else identical."],
         {"image": "themes/kids.png"}),
    Clip("worlds-group", "worlds", "group",
         "Three kids around a table building a tiny weather-station kit from craft materials, a tablet propped up shows"
         " Sala the holographic AI teacher guiding them, playful 3D paper-craft styled room, warm afternoon light.",
         ["Edit this exact image: one child lifting the small wind vane, others watching. Keep everything else identical.",
          "Edit this exact image: Sala on the tablet pointing to the wind vane. Keep everything else identical.",
          "Edit this exact image: the kids smiling at each other, wind vane slightly turned. Keep everything else identical."],
         {"layout": "spotlight"}),
    Clip("worlds-avatar", "worlds", "avatar",
         "Sala the holographic AI teacher in a colorful playful classroom, pointing at large floating fraction blocks"
         " in mint, yellow and tangerine, friendly and encouraging, soft 3D render.",
         ["Edit this exact image: Sala's mouth open as if explaining, one fraction block moved up slightly. Keep everything else identical.",
          "Edit this exact image: Sala tilting the head with a big smile, blocks shifted a little. Keep everything else identical.",
          "Edit this exact image: Sala's pointing hand moved to the next block. Keep everything else identical."]),
    Clip("signal-vision", "signal", "vision",
         "Close-up of a student's hand-written algebra on paper under a desk lamp, viewed through a phone camera with"
         " glowing cyan detection boxes around each symbol, dark cinematic studio with ultraviolet rim light.",
         ["Edit this exact image: the detection boxes shifted to the next symbols, a soft scan line across the paper. Keep everything else identical.",
          "Edit this exact image: a small glowing Sala hologram appearing at the corner of the paper. Keep everything else identical.",
          "Edit this exact image: the student's pencil tip moved to write the answer. Keep everything else identical."]),
    Clip("signal-voice", "signal", "voice",
         "An adult learner with headphones practicing a new language at night, a translucent Sala the holographic AI"
         " teacher floating beside a glowing cyan audio waveform, deep cobalt and ultraviolet cinematic lighting.",
         ["Edit this exact image: the learner speaking with mouth open, waveform taller. Keep everything else identical.",
          "Edit this exact image: Sala responding with mouth open, waveform reshaped. Keep everything else identical.",
          "Edit this exact image: the learner smiling and nodding, waveform settling. Keep everything else identical."]),
    Clip("signal-play", "signal", "play",
         "A teenager playing an adaptive geometry puzzle game on a tablet, neon wireframe shapes floating above the"
         " screen, Sala the holographic AI teacher small at the edge giving a thumbs-up, dark electric blue studio.",
         ["Edit this exact image: the floating wireframe shapes rotated a little, the teen's finger swiping. Keep everything else identical.",
          "Edit this exact image: the shapes snapped together glowing brighter. Keep everything else identical.",
          "Edit this exact image: the teen grinning, Sala's thumbs-up raised higher. Keep everything else identical."]),
    Clip("journal-student", "journal", "student",
         "Documentary photograph of an adult learner at a kitchen table in the evening, warm lamp light, tablet propped"
         " against a mug showing Sala the holographic AI teacher in a video call, candid and humane.",
         ["Edit this exact image: the learner leaning slightly closer with a small smile. Keep everything else identical.",
          "Edit this exact image: Sala on the tablet gesturing gently. Keep everything else identical.",
          "Edit this exact image: the learner writing a short note, steam rising from the mug. Keep everything else identical."],
         {"screen": "tablet"}),
    Clip("journal-group", "journal", "group",
         "A warm human science teacher leading a live online class from a sunlit studio, video-call tiles of learners,"
         " and a small side panel with Sala the holographic AI teacher quietly assisting, editorial documentary style.",
         ["Edit this exact image: the teacher holding up a small plant to the camera. Keep everything else identical.",
          "Edit this exact image: a learner in one tile raising a hand, Sala pointing toward that tile. Keep everything else identical.",
          "Edit this exact image: the teacher smiling and answering, hand lowered. Keep everything else identical."],
         {"teacher": "human"}),
    Clip("journal-avatar", "journal", "avatar",
         "Editorial portrait of Sala the holographic AI teacher in a sunlit modern study with paper and wood textures,"
         " soft window light, speaking warmly and patiently toward the camera.",
         ["Edit this exact image: Sala's mouth open mid-sentence. Keep everything else identical.",
          "Edit this exact image: Sala blinking softly with a gentle smile. Keep everything else identical.",
          "Edit this exact image: Sala's hands slightly lifting the medallion as if explaining. Keep everything else identical."]),
]


def _font(size: int, name: str = "Arial.ttf") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = Path("/System/Library/Fonts/Supplemental") / name
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _ease(x: float) -> float:
    return x * x * (3 - 2 * x)


def _jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def _drift(image: Image.Image, t: float, amount: float = 0.04) -> Image.Image:
    """Periodic zoom + pan so frame 0 and frame N match exactly."""
    phase = 2 * math.pi * t
    scale = 1 + amount * (0.5 + 0.5 * math.sin(phase))
    w, h = image.size
    cw, ch = w / scale, h / scale
    cx = w / 2 + (w - cw) / 2 * 0.6 * math.sin(phase)
    cy = h / 2 + (h - ch) / 2 * 0.4 * math.cos(phase)
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return image.resize(SIZE, Image.Resampling.BICUBIC, box=box)


# ---------- Nano Banana mode ----------

def _nano_frames(clip: Clip, api_key: str, reuse: bool) -> list[Image.Image]:
    folder = CACHE / clip.slug
    folder.mkdir(parents=True, exist_ok=True)
    paths = [folder / f"{index}.png" for index in range(4)]
    if not (reuse and all(path.is_file() for path in paths)):
        reference = Image.open(PUBLIC / "brand/serenity/hero.jpg")
        reference.thumbnail((768, 768))
        base_raw = _request(clip.prompt + GUARD, _jpeg(reference), api_key)
        base = ImageOps.fit(Image.open(io.BytesIO(base_raw)).convert("RGB"), SIZE, Image.Resampling.LANCZOS)
        base.save(paths[0])
        for index, edit in enumerate(clip.edits, start=1):
            raw = _request(edit + " No text or watermarks.", _jpeg(base), api_key)
            frame = ImageOps.fit(Image.open(io.BytesIO(raw)).convert("RGB"), SIZE, Image.Resampling.LANCZOS)
            frame.save(paths[index])
            print(f"  {clip.slug}: frame {index}/3")
    return [Image.open(path).convert("RGB") for path in paths]


def _render_nano(keys: list[Image.Image]):
    order = [0, 1, 2, 3, 2, 1, 0]
    segments = len(order) - 1
    oversized = [image.resize((int(SIZE[0] * 1.08), int(SIZE[1] * 1.08)), Image.Resampling.LANCZOS) for image in keys]
    for frame in range(FRAMES):
        t = frame / FRAMES
        position = t * segments
        index = min(int(position), segments - 1)
        local = position - index
        hold = 0.35
        mix = 0.0 if local < hold else _ease((local - hold) / (1 - hold))
        blended = Image.blend(oversized[order[index]], oversized[order[index + 1]], mix)
        yield _drift(blended, t, 0.05)


# ---------- local fallback mode ----------

class Sala:
    """Serenity lip/blink keyframes as a reusable talking sprite."""

    VISEMES = ["mouth_half", "mouth_aa", "mouth_oh", "mouth_mbp", "mouth_ee", "mouth_half", "rest", "mouth_aa", "mouth_mbp", "rest"]

    def __init__(self) -> None:
        names = ["mouth_half", "mouth_aa", "mouth_oh", "mouth_mbp", "mouth_ee", "eyes_half", "eyes_closed"]
        crop = (0, 60, 704, 1150)
        self.frames = {"rest": Image.open(AVATAR / "presenter_serenity.png").convert("RGB").crop(crop)}
        for name in names:
            self.frames[name] = Image.open(AVATAR / "serenity_kf" / f"{name}.png").convert("RGB").crop(crop)
        self._cache: dict[tuple[str, int], Image.Image] = {}

    def frame(self, t: float, height: int, talking: bool = True) -> Image.Image:
        blink = t % 0.5
        if 0.40 <= blink < 0.415 or 0.43 <= blink < 0.445:
            name = "eyes_half"
        elif 0.415 <= blink < 0.43:
            name = "eyes_closed"
        elif talking:
            name = self.VISEMES[int(t * FRAMES / 3) % len(self.VISEMES)]
        else:
            name = "rest"
        key = (name, height)
        if key not in self._cache:
            source = self.frames[name]
            width = round(source.width * height / source.height)
            self._cache[key] = source.resize((width, height), Image.Resampling.LANCZOS)
        return self._cache[key]

    def backdrop(self, theme: str) -> Image.Image:
        base = ImageOps.fit(self.frames["rest"], SIZE, Image.Resampling.LANCZOS, centering=(0.5, 0.2))
        base = base.filter(ImageFilter.GaussianBlur(28))
        tone = THEMES[theme]
        return Image.blend(base, Image.new("RGB", SIZE, tone["tint"]), tone["alpha"])


_FEATHER: dict[tuple[int, int], Image.Image] = {}


def _feather(size: tuple[int, int]) -> Image.Image:
    """Soft oval mask so the sprite's own backdrop dissolves into the scene."""
    if size not in _FEATHER:
        w, h = size
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).ellipse((w * 0.08, h * 0.02, w * 0.92, h * 1.25), fill=255)
        _FEATHER[size] = mask.filter(ImageFilter.GaussianBlur(max(6, w // 9)))
    return _FEATHER[size]


def _feed(sala: Sala, theme: str, t: float, height: int, size: tuple[int, int], talking: bool = True) -> Image.Image:
    """A small video-call feed of Sala, sized for screens and tiles."""
    tile = ImageOps.fit(sala.backdrop(theme), size, Image.Resampling.LANCZOS)
    sprite = sala.frame(t, height, talking)
    tile.paste(sprite, ((size[0] - sprite.width) // 2, size[1] - sprite.height + height // 9), _feather(sprite.size))
    return tile


def _rounded(canvas: Image.Image, tile: Image.Image, xy: tuple[int, int], radius: int) -> None:
    mask = Image.new("L", tile.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *tile.size), radius=radius, fill=255)
    canvas.paste(tile, xy, mask)


def _avatar(clip: Clip, sala: Sala, t: float, backdrop: Image.Image) -> Image.Image:
    phase = 2 * math.pi * t
    canvas = backdrop.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    tone = THEMES[clip.theme]
    accent = tone["accent"]
    if clip.theme == "aurora":
        cx, cy = 720, 230
        draw.ellipse((cx - 150, cy - 55, cx + 150, cy + 55), outline=(255, 255, 255, 120), width=2)
        draw.ellipse((cx - 90, cy - 32, cx + 90, cy + 32), outline=(255, 255, 255, 90), width=2)
        draw.ellipse((cx - 26, cy - 26, cx + 26, cy + 26), fill=(255, 214, 150, 230))
        for radius, speed, colour in ((150, 1, (200, 170, 255)), (90, 2, (160, 230, 235))):
            angle = phase * speed
            px, py = cx + radius * math.cos(angle), cy + radius * 0.36 * math.sin(angle)
            draw.ellipse((px - 11, py - 11, px + 11, py + 11), fill=(*colour, 255))
    elif clip.theme == "worlds":
        colours = [(255, 210, 90), (240, 107, 67), (110, 220, 180)]
        for index, colour in enumerate(colours):
            bob = 14 * math.sin(phase + index * 2.1)
            x, y = 90 + index * 110, 300 + bob
            draw.rounded_rectangle((x, y, x + 90, y + 60 + index * 20), radius=12, fill=(*colour, 235))
            draw.line((x + 45, y + 8, x + 45, y + 52 + index * 20), fill=(255, 255, 255, 160), width=3)
    elif clip.theme == "journal":
        for index in range(3):
            sway = 10 * math.sin(phase + index)
            x = 600 + index * 70
            draw.polygon([(x + sway, 0), (x + 60 + sway, 0), (x - 180, 540), (x - 260, 540)], fill=(255, 236, 200, 26))
        for index in range(3):
            bob = 8 * math.sin(phase + index * 1.7)
            x, y = 90 + index * 26, 120 + index * 120 + bob
            draw.rounded_rectangle((x, y, x + 150, y + 90), radius=8, fill=(250, 244, 232, 210))
            for line in range(3):
                draw.line((x + 16, y + 22 + line * 20, x + 120 - line * 22, y + 22 + line * 20), fill=(*accent, 150), width=3)
    pulse = 1 + 0.012 * math.sin(phase * 2)
    sprite = sala.frame(t, int(500 * pulse))
    x = 480 - sprite.width // 2 if clip.theme != "aurora" else 300 - sprite.width // 2
    glow = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((x - 40, 60, x + sprite.width + 40, 560), fill=(120, 190, 255, 70))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(40))).convert("RGB")
    canvas.paste(sprite, (x, SIZE[1] - sprite.height + 40), _feather(sprite.size))
    return canvas


def _student(clip: Clip, sala: Sala, t: float, backdrop: Image.Image) -> Image.Image:
    phase = 2 * math.pi * t
    warm = clip.theme == "journal"
    wall = (52, 40, 34) if warm else (238, 232, 246)
    desk = (122, 84, 58) if warm else (222, 206, 190)
    canvas = Image.new("RGB", SIZE, wall)
    draw = ImageDraw.Draw(canvas, "RGBA")
    if warm:
        draw.ellipse((40, -80, 420, 300), fill=(255, 196, 120, 60))
    else:
        draw.rectangle((640, 40, 900, 300), fill=(255, 255, 255, 140))
        draw.line((770, 40, 770, 300), fill=wall, width=6)
    draw.rectangle((0, 360, 960, 540), fill=desk)
    screen = (300, 200) if clip.options.get("screen") == "tablet" else (380, 230)
    sx, sy = 110, 360 - screen[1] - 20
    draw.rounded_rectangle((sx - 14, sy - 14, sx + screen[0] + 14, sy + screen[1] + 14), radius=18, fill=(22, 22, 28))
    _rounded(canvas, _feed(sala, clip.theme, t, int(screen[1] * 1.15), screen), (sx, sy), 8)
    if clip.options.get("screen") != "tablet":
        draw.polygon([(sx - 60, 380), (sx + screen[0] + 60, 380), (sx + screen[0] + 20, 360), (sx - 20, 360)], fill=(40, 40, 48))
    else:
        draw.rounded_rectangle((sx + screen[0] + 30, 300, sx + screen[0] + 100, 380), radius=10, fill=(236, 226, 210))
        for index in range(3):
            rise = (t * 3 + index / 3) % 1
            draw.ellipse((sx + screen[0] + 55 + 8 * math.sin(phase + index), 290 - rise * 90, sx + screen[0] + 75 + 8 * math.sin(phase + index), 310 - rise * 90), fill=(255, 255, 255, int(110 * (1 - rise))))
    nx, ny = 600, 390
    draw.polygon([(nx, ny), (nx + 260, ny - 10), (nx + 280, ny + 120), (nx + 10, ny + 132)], fill=(250, 248, 240))
    progress = (t * 2) % 1
    ink = (40, 40, 70, 230)
    for line in range(4):
        length = max(0.0, min(1.0, progress * 4 - line))
        if length > 0:
            y = ny + 22 + line * 24
            draw.line((nx + 24, y, nx + 24 + 200 * length, y - 2), fill=ink, width=3)
    tip = min(3, int(progress * 4))
    pen_x = nx + 24 + 200 * max(0.0, min(1.0, progress * 4 - tip))
    pen_y = ny + 22 + tip * 24
    draw.line((pen_x, pen_y, pen_x + 70, pen_y - 90), fill=(30, 30, 36), width=9)
    return _drift(canvas, t, 0.03)


def _group(clip: Clip, sala: Sala, t: float, backdrop: Image.Image) -> Image.Image:
    tone = THEMES[clip.theme]
    dark = clip.theme in ("signal", "journal")
    canvas = Image.new("RGB", SIZE, (18, 18, 24) if dark else (244, 240, 246))
    draw = ImageDraw.Draw(canvas, "RGBA")
    gap, cols, rows = 10, 3, 2
    speaker = int(t * 6) % 6
    human_teacher = clip.options.get("teacher") == "human"
    palette = [(255, 196, 150), (160, 210, 240), (190, 230, 180), (240, 180, 210), (250, 225, 150), (200, 190, 250)]
    names = ["Maya", "Sala", "Kiri", "Leo", "Ana", "Jun"] if human_teacher else ["Sala", "Amir", "Kiri", "Leo", "Ana", "Jun"]
    font = _font(15, "Arial Bold.ttf")
    if clip.options.get("layout") == "spotlight":
        big_w = int(SIZE[0] * 0.62)
        small_w = (SIZE[0] - big_w - gap * 4) // 2
        small_h = (SIZE[1] - gap * 4) // 3
        cells = [(gap, gap, big_w, SIZE[1] - gap * 2)]
        cells += [(big_w + gap * 2 + (k % 2) * (small_w + gap), gap + (k // 2) * (small_h + gap), small_w, small_h) for k in range(5)]
    else:
        tw, th = (SIZE[0] - gap * (cols + 1)) // cols, (SIZE[1] - gap * (rows + 1)) // rows
        cells = [(gap + (k % cols) * (tw + gap), gap + (k // cols) * (th + gap), tw, th) for k in range(6)]
    for index, (x, y, tw, th) in enumerate(cells):
        is_sala = names[index] == "Sala"
        if is_sala:
            tile = _feed(sala, clip.theme, t, int(th * 1.25), (tw, th), talking=speaker in (0, 1, 2, 3) or not human_teacher)
        else:
            colour = palette[index]
            tile = Image.new("RGB", (tw, th), tuple(int(c * 0.55) for c in colour) if dark else colour)
            td = ImageDraw.Draw(tile, "RGBA")
            bob = 4 * math.sin(2 * math.pi * t * 2 + index)
            cx = tw // 2
            td.ellipse((cx - 38, th // 2 - 62 + bob, cx + 38, th // 2 + 14 + bob), fill=(255, 255, 255, 150))
            td.rounded_rectangle((cx - 78, th // 2 + 24 + bob, cx + 78, th + 40), radius=60, fill=(255, 255, 255, 120))
            if names[index] == "Maya" or (index == 3 and (t % 1) > 0.55):
                td.rounded_rectangle((cx + 60, th // 2 - 40 + bob, cx + 82, th // 2 + 30 + bob), radius=10, fill=(255, 255, 255, 170))
        _rounded(canvas, tile, (x, y), 12)
        talking = (index == speaker and not is_sala) or (is_sala and speaker < 4)
        if talking:
            draw.rounded_rectangle((x - 2, y - 2, x + tw + 2, y + th + 2), radius=14, outline=(*tone["accent"], 255), width=4)
        label_w = int(draw.textlength(names[index], font=font)) + 20
        draw.rounded_rectangle((x + 10, y + th - 34, x + 10 + label_w, y + th - 10), radius=8, fill=(0, 0, 0, 120))
        draw.text((x + 20, y + th - 31), names[index], font=font, fill=(255, 255, 255))
    return canvas


def _play(clip: Clip, sala: Sala, t: float, backdrop: Image.Image) -> Image.Image:
    source = Image.open(PUBLIC / clip.options.get("image", "themes/kids.png")).convert("RGB")
    source = ImageOps.fit(source, (int(SIZE[0] * 1.15), int(SIZE[1] * 1.15)), Image.Resampling.LANCZOS)
    canvas = _drift(source, t, 0.06)
    draw = ImageDraw.Draw(canvas, "RGBA")
    targets = [((180, 160, 380, 360), "Leaf · 96%"), ((520, 120, 720, 300), "Flower · 91%"), ((600, 300, 820, 470), "Rock · 88%")]
    position = t * len(targets)
    index = int(position) % len(targets)
    local = _ease(min(1.0, (position - int(position)) * 2.5))
    a, b = targets[index][0], targets[(index + 1) % len(targets)][0]
    box = [a[k] + (b[k] - a[k]) * local for k in range(4)]
    accent = THEMES[clip.theme]["accent"]
    corner = 26
    for (px, py, dx, dy) in ((box[0], box[1], 1, 1), (box[2], box[1], -1, 1), (box[0], box[3], 1, -1), (box[2], box[3], -1, -1)):
        draw.line((px, py, px + dx * corner, py), fill=(255, 255, 255, 255), width=5)
        draw.line((px, py, px, py + dy * corner), fill=(255, 255, 255, 255), width=5)
    label = targets[(index + 1) % len(targets)][1] if local > 0.98 else targets[index][1]
    font = _font(18, "Arial Bold.ttf")
    width = int(draw.textlength(label, font=font)) + 26
    draw.rounded_rectangle((box[0], box[1] - 40, box[0] + width, box[1] - 8), radius=16, fill=(*accent, 240))
    draw.text((box[0] + 13, box[1] - 36), label, font=font, fill=(255, 255, 255))
    feed = _feed(sala, clip.theme, t, 190, (170, 140))
    _rounded(canvas, feed, (SIZE[0] - 190, SIZE[1] - 160), 16)
    draw.rounded_rectangle((SIZE[0] - 192, SIZE[1] - 162, SIZE[0] - 18, SIZE[1] - 18), radius=17, outline=(255, 255, 255, 220), width=3)
    return canvas


def _signal_base(t: float) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    canvas = Image.new("RGB", SIZE, (6, 7, 14))
    draw = ImageDraw.Draw(canvas, "RGBA")
    for x in range(0, SIZE[0], 48):
        draw.line((x, 0, x, SIZE[1]), fill=(255, 255, 255, 12))
    for y in range(0, SIZE[1], 48):
        draw.line((0, y, SIZE[0], y), fill=(255, 255, 255, 12))
    glow = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((500, -100, 1100, 500), fill=(110, 80, 255, 60))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(80))).convert("RGB")
    return canvas, ImageDraw.Draw(canvas, "RGBA")


def _vision(clip: Clip, sala: Sala, t: float, backdrop: Image.Image) -> Image.Image:
    canvas, draw = _signal_base(t)
    draw.polygon([(150, 90), (810, 70), (830, 470), (130, 480)], fill=(236, 232, 222))
    hand = _font(64, "Bradley Hand Bold.ttf")
    tokens = ["3x", "+", "5", "=", "20"]
    x = 210
    boxes = []
    for token in tokens:
        width = draw.textlength(token, font=hand)
        draw.text((x, 200), token, font=hand, fill=(40, 40, 70))
        boxes.append((x - 10, 195, x + width + 10, 285))
        x += width + 36
    shown = int((t * 2 % 1) * (len(tokens) + 2))
    cyan = THEMES["signal"]["accent"]
    for index, box in enumerate(boxes[:shown]):
        draw.rounded_rectangle(box, radius=6, outline=(*cyan, 255), width=3)
    if shown > len(tokens):
        draw.text((210, 320), "x = 5", font=hand, fill=(110, 80, 255))
    scan = 90 + ((t * 2) % 1) * 380
    draw.rectangle((140, scan - 3, 820, scan + 3), fill=(*cyan, 120))
    draw.rectangle((140, scan - 30, 820, scan), fill=(*cyan, 18))
    return _drift(canvas, t, 0.03)


def _voice(clip: Clip, sala: Sala, t: float, backdrop: Image.Image) -> Image.Image:
    canvas, draw = _signal_base(t)
    phase = 2 * math.pi * t
    feed = _feed(sala, "signal", t, 420, (300, 380), talking=(t % 0.5) > 0.25)
    _rounded(canvas, feed, (60, 80), 22)
    draw.rounded_rectangle((58, 78, 362, 462), radius=24, outline=(140, 255, 219, 160), width=2)
    learner_speaking = (t % 0.5) <= 0.25
    cyan = THEMES["signal"]["accent"]
    for index in range(36):
        x = 420 + index * 13
        energy = 0.25 + 0.75 * abs(math.sin(phase * 4 + index * 0.55)) * abs(math.sin(phase * 2 + index * 0.2))
        height = 18 + 150 * energy * (1.0 if learner_speaking else 0.55)
        colour = cyan if learner_speaking else (170, 150, 255)
        draw.rounded_rectangle((x, 270 - height / 2, x + 7, 270 + height / 2), radius=4, fill=(*colour, 230))
    font = _font(24, "Arial Bold.ttf")
    words = ["¿Dónde", "está", "la", "biblioteca?"]
    lit = int((t * 2 % 0.5) / 0.5 * (len(words) + 1))
    x = 420
    for index, word in enumerate(words):
        colour = (255, 255, 255) if index < lit else (110, 110, 130)
        draw.text((x, 410), word, font=font, fill=colour)
        x += draw.textlength(word + " ", font=font)
    return canvas


def _game(clip: Clip, sala: Sala, t: float, backdrop: Image.Image) -> Image.Image:
    canvas, draw = _signal_base(t)
    phase = 2 * math.pi * t
    horizon = 300
    for index in range(-8, 9):
        draw.line((480 + index * 30, horizon, 480 + index * 160, SIZE[1]), fill=(140, 120, 255, 70), width=2)
    for index in range(7):
        y = horizon + (index + (t * 7) % 1) ** 2 * 6
        draw.line((0, y, SIZE[0], y), fill=(140, 120, 255, 60), width=2)
    shapes = [(300, 170, 3, 70, (140, 255, 219)), (480, 140, 4, 80, (170, 150, 255)), (660, 180, 6, 64, (255, 160, 220))]
    snap = 0.5 + 0.5 * math.sin(phase)
    for index, (cx, cy, sides, radius, colour) in enumerate(shapes):
        angle = phase * (1 + index * 0.5) + index
        cx = cx + (480 - cx) * 0.25 * snap
        points = [(cx + radius * math.cos(angle + k * 2 * math.pi / sides), cy + radius * math.sin(angle + k * 2 * math.pi / sides)) for k in range(sides)]
        draw.polygon(points, outline=(*colour, 255), width=4)
        draw.polygon(points, fill=(*colour, int(30 + 50 * snap)))
    draw.rounded_rectangle((380, 470, 580, 494), radius=12, outline=(255, 255, 255, 140), width=2)
    draw.rounded_rectangle((384, 474, 384 + 192 * snap, 490), radius=10, fill=(140, 255, 219, 230))
    feed = _feed(sala, "signal", t, 170, (150, 130))
    _rounded(canvas, feed, (SIZE[0] - 175, 25), 14)
    return canvas


RENDERERS = {"avatar": _avatar, "student": _student, "group": _group, "play": _play, "vision": _vision, "voice": _voice}


def _render_fallback(clip: Clip, sala: Sala):
    renderer = _game if clip.slug == "signal-play" else RENDERERS[clip.scene]
    backdrop = sala.backdrop(clip.theme)
    for frame in range(FRAMES):
        yield renderer(clip, sala, frame / FRAMES, backdrop)


def _encode(frames, destination: Path) -> None:
    command = [
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{SIZE[0]}x{SIZE[1]}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-an", str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    poster = None
    for image in frames:
        if poster is None:
            poster = image
        process.stdin.write(image.convert("RGB").tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {destination.name}")
    poster.save(destination.with_suffix(".webp"), "WEBP", quality=78, method=6)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=[clip.slug for clip in CLIPS])
    parser.add_argument("--fallback", action="store_true")
    parser.add_argument("--regenerate", action="store_true", help="ignore cached Nano Banana frames")
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        parser.error("ffmpeg is required")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    if not args.fallback and not api_key:
        parser.error("GEMINI_API_KEY or GOOGLE_API_KEY is required (or use --fallback)")
    OUT.mkdir(parents=True, exist_ok=True)
    sala = Sala()
    selected = [clip for clip in CLIPS if not args.only or clip.slug == args.only]
    print(f"mode={'fallback' if args.fallback else 'nano-banana'} clips={len(selected)}")
    for clip in selected:
        destination = OUT / f"{clip.slug}.mp4"
        if args.fallback:
            frames = _render_fallback(clip, sala)
        else:
            frames = _render_nano(_nano_frames(clip, api_key, reuse=not args.regenerate))
        _encode(frames, destination)
        print(f"wrote {destination.relative_to(ROOT)} ({destination.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
