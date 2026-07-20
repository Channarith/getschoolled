#!/usr/bin/env python3
"""Render a first-cut animated intro video for the Salareen platform."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


WIDTH = 1920
HEIGHT = 1080
FPS = 30

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "docs" / "demos" / "salareen_ecosystem_animated_intro_v1.mp4"
LOGO_PATH = ROOT / "apps" / "web" / "public" / "bayon-mark.webp"
ECOSYSTEM_PATH = ROOT / "docs" / "brand" / "salareen_platform_ecosystem.png"


@dataclass(frozen=True)
class Scene:
    duration_s: float
    title: str
    subtitle: str
    bullets: tuple[str, ...]
    base_color: tuple[int, int, int]  # RGB
    accent_color: tuple[int, int, int]  # RGB
    use_ecosystem_image: bool = False


SCENES: tuple[Scene, ...] = (
    Scene(
        duration_s=5.0,
        title="Salareen AI Education Ecosystem",
        subtitle="One intelligent platform. Every learner journey.",
        bullets=(
            "Live AI-taught classes + adaptive pathways",
            "Mobile drive mode + multilingual tutoring",
            "Human-in-the-loop oversight and trust controls",
        ),
        base_color=(10, 19, 38),
        accent_color=(63, 132, 255),
    ),
    Scene(
        duration_s=6.0,
        title="Connected Learning Network",
        subtitle="A full-stack ecosystem designed for student outcomes.",
        bullets=(
            "Identity, billing, rewards, and secure auth",
            "Curriculum generation, assessments, and RAG tutoring",
            "Arcade, engagement loops, and retention tooling",
        ),
        base_color=(11, 28, 56),
        accent_color=(118, 85, 255),
        use_ecosystem_image=True,
    ),
    Scene(
        duration_s=6.0,
        title="Flawless Live-Class Experience",
        subtitle="Presence-aware AI classrooms with safety and quality gates.",
        bullets=(
            "Camera-driven presence hold with automatic resume",
            "Liveness and face-count checks for attendance integrity",
            "Instructor moderation, queue controls, and analytics",
        ),
        base_color=(22, 34, 60),
        accent_color=(24, 200, 158),
    ),
    Scene(
        duration_s=6.0,
        title="Mobile + Web Parity",
        subtitle="Learn anywhere with consistent premium UX.",
        bullets=(
            "Live rooms, group classes, and AI Q&A on every device",
            "Drive mode narration and uninterrupted learning paths",
            "Fast gameplay loops, progress tracking, and rewards",
        ),
        base_color=(30, 21, 57),
        accent_color=(255, 120, 80),
    ),
    Scene(
        duration_s=6.0,
        title="Instructor Marketplace + Enterprise",
        subtitle="Teach, monetize, audit, and scale with confidence.",
        bullets=(
            "Audited instructor onboarding and verified teaching quality",
            "Payment-gated attendance, unique attendee codes, anti-piggybacking",
            "Corporate bridges (Teams/Cisco camera ingest) and premium controls",
        ),
        base_color=(18, 26, 47),
        accent_color=(244, 195, 85),
    ),
    Scene(
        duration_s=5.0,
        title="Build the Future of Learning",
        subtitle="Salareen brings AI, humans, and outcomes together.",
        bullets=(
            "Adaptive • Transparent • Global • Real-time",
            "Web + Mobile + Live Classes + Enterprise Integrations",
            "www.salareen.com",
        ),
        base_color=(6, 16, 33),
        accent_color=(91, 219, 255),
    ),
)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - pow(1.0 - t, 3)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size=size)


def rgb_gradient(base: tuple[int, int, int], accent: tuple[int, int, int], phase: float) -> np.ndarray:
    y = np.linspace(0.0, 1.0, HEIGHT, dtype=np.float32).reshape(HEIGHT, 1, 1)
    x = np.linspace(0.0, 1.0, WIDTH, dtype=np.float32).reshape(1, WIDTH, 1)
    w = np.clip(0.15 + 0.75 * (0.5 + 0.5 * np.sin(phase + x * 3.2 + y * 2.1)), 0.0, 1.0)
    base_arr = np.array(base, dtype=np.float32).reshape(1, 1, 3)
    accent_arr = np.array(accent, dtype=np.float32).reshape(1, 1, 3)
    rgb = base_arr * (1.0 - w) + accent_arr * w
    return np.clip(rgb, 0, 255).astype(np.uint8)


def draw_floating_orbs(img: Image.Image, accent: tuple[int, int, int], local_t: float) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    orb = (*accent, 40)
    orb2 = (*accent, 22)
    for i, r in enumerate((220, 140, 100)):
        phase = local_t * 2.4 + i * 1.3
        cx = int(lerp(150, WIDTH - 180, (0.5 + 0.5 * np.sin(phase * 0.9 + i))))
        cy = int(lerp(130, HEIGHT - 130, (0.5 + 0.5 * np.cos(phase * 1.1 + i))))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=orb if i == 0 else orb2)


def alpha_text(
    canvas: Image.Image,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
    alpha: int,
) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.text(position, text, font=font, fill=(*color, alpha))
    canvas.alpha_composite(layer)


def draw_card(draw: ImageDraw.ImageDraw, y0: int, accent: tuple[int, int, int]) -> None:
    draw.rounded_rectangle((100, y0, WIDTH - 100, y0 + 560), radius=30, fill=(8, 14, 28, 188), outline=(*accent, 210), width=2)


def render_scene(scene: Scene, frame_index: int, total_frames: int, logo: Image.Image, ecosystem: Image.Image) -> np.ndarray:
    t = frame_index / max(1, total_frames - 1)
    entry = ease_out_cubic(min(1.0, t * 1.7))
    bg_np = rgb_gradient(scene.base_color, scene.accent_color, phase=t * np.pi * 2.0)
    canvas = Image.fromarray(bg_np, mode="RGB").convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")

    draw_floating_orbs(canvas, scene.accent_color, t)
    draw_card(draw, 90, scene.accent_color)

    logo_sz = int(160 + 12 * np.sin(t * np.pi * 3.0))
    logo_img = logo.resize((logo_sz, logo_sz), Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo_img, (120, 130))

    title_font = load_font(66, bold=True)
    subtitle_font = load_font(34, bold=False)
    bullet_font = load_font(34, bold=False)
    kicker_font = load_font(24, bold=True)

    x_title = int(lerp(340, 280, entry))
    alpha_text(canvas, (x_title, 145), scene.title, title_font, (245, 249, 255), int(255 * entry))
    alpha_text(canvas, (x_title, 235), scene.subtitle, subtitle_font, (214, 228, 255), int(240 * entry))
    alpha_text(canvas, (x_title, 295), "AI EDUCATION • LIVE LEARNING • TRUST AT SCALE", kicker_font, scene.accent_color, int(225 * entry))

    y = 360
    for idx, bullet in enumerate(scene.bullets):
        bt = max(0.0, min(1.0, (t - 0.14 * idx) * 2.5))
        be = ease_out_cubic(bt)
        x = int(lerp(360, 320, be))
        alpha = int(235 * be)
        alpha_text(canvas, (x, y), f"• {bullet}", bullet_font, (238, 243, 255), alpha)
        y += 78

    if scene.use_ecosystem_image:
        target_w = 650
        ratio = ecosystem.height / max(1, ecosystem.width)
        target_h = int(target_w * ratio)
        ex = WIDTH - target_w - 120
        ey = HEIGHT - target_h - 120
        pan = int(16 * np.sin(t * np.pi * 2.0))
        eco = ecosystem.resize((target_w, target_h), Image.Resampling.LANCZOS)
        card = Image.new("RGBA", (target_w + 24, target_h + 24), (12, 20, 38, 220))
        card_draw = ImageDraw.Draw(card)
        card_draw.rounded_rectangle((0, 0, target_w + 24, target_h + 24), radius=20, outline=(255, 255, 255, 70), width=2)
        card.alpha_composite(eco.convert("RGBA"), (12, 12))
        canvas.alpha_composite(card, (ex + pan, ey - pan))

    fade_out = 1.0 if t < 0.92 else max(0.0, 1.0 - (t - 0.92) / 0.08)
    if fade_out < 1.0:
        veil = Image.new("RGBA", canvas.size, (0, 0, 0, int((1.0 - fade_out) * 190)))
        canvas.alpha_composite(veil)
    return cv2.cvtColor(np.array(canvas.convert("RGB")), cv2.COLOR_RGB2BGR)


def iter_scene_frames(scene: Scene, logo: Image.Image, ecosystem: Image.Image) -> Iterable[np.ndarray]:
    frames = max(1, int(scene.duration_s * FPS))
    for i in range(frames):
        yield render_scene(scene, i, frames, logo, ecosystem)


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    logo = Image.open(LOGO_PATH).convert("RGBA")
    ecosystem = Image.open(ECOSYSTEM_PATH).convert("RGBA")

    writer = cv2.VideoWriter(
        str(OUT_PATH),
        cv2.VideoWriter_fourcc(*"mp4v"),
        FPS,
        (WIDTH, HEIGHT),
    )
    if not writer.isOpened():
        raise RuntimeError("Could not initialize video writer")

    for scene in SCENES:
        for frame in iter_scene_frames(scene, logo, ecosystem):
            writer.write(frame)
    writer.release()
    print(f"Rendered: {OUT_PATH}")


if __name__ == "__main__":
    main()
