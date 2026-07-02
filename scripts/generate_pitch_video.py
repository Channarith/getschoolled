"""Generate the Salareen investor pitch deck video.

Assembles a ~4m30s investor pitch video from:
  - Existing MP4 product demos (docs/demos/*.mp4)
  - Screenshot stills (docs/screens/*.webp)
  - Programmatically rendered text slides (PIL + ffmpeg)

Output: docs/demos/salareen_pitch_deck_2026.mp4 (1080p, H.264)

Usage:
    python3 scripts/generate_pitch_video.py
    python3 scripts/generate_pitch_video.py --preview   # first 3 segments only
    python3 scripts/generate_pitch_video.py --out /path/to/output.mp4
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).parent.parent
DEMOS = REPO / "docs" / "demos"
SCREENS = REPO / "docs" / "screens"
BRAND = REPO / "docs" / "brand"
OUT_DIR = DEMOS
DEFAULT_OUT = DEMOS / "salareen_pitch_deck_2026.mp4"

# Fonts are resolved at import time so the generator runs on Linux (CI),
# macOS (local), or anywhere matplotlib's bundled DejaVu fonts are available.
# DejaVu is preferred so the look matches across platforms; macOS system fonts
# are the last-resort fallback. Missing fonts were the root cause of unreadable
# (tiny fallback) text + skipped overlays when run off a Linux box.

def _mpl_font_dir() -> str:
    try:
        import matplotlib  # bundled DejaVu ttfs, cross-platform
        return os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    except Exception:
        return ""


def _resolve_font(*candidates: str) -> str:
    for c in candidates:
        if c and os.path.exists(c):
            return c
    # Return the first candidate anyway so failures are loud/diagnosable.
    return next((c for c in candidates if c), "")


_MPL = _mpl_font_dir()

FONT_BOLD = _resolve_font(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    os.path.join(_MPL, "DejaVuSans-Bold.ttf") if _MPL else "",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
)
FONT_REG = _resolve_font(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    os.path.join(_MPL, "DejaVuSans.ttf") if _MPL else "",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
)
FONT_MONO = _resolve_font(
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    os.path.join(_MPL, "DejaVuSansMono.ttf") if _MPL else "",
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/System/Library/Fonts/Menlo.ttc",
)

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
BG      = (11, 16, 32)          # #0b1020
GOLD    = (201, 160, 60)        # #C9A03C
WHITE   = (245, 245, 245)       # #F5F5F5
GREY    = (140, 150, 170)
RED_ACC = (200, 60, 60)
GRN_ACC = (60, 180, 100)

W, H = 1920, 1080
FPS  = 30

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), check=check, capture_output=True)


def ffmpeg(*args: str) -> None:
    run("ffmpeg", "-y", *args)


def _probe_duration(src: Path) -> float:
    """Return a media file's duration in seconds."""
    result = run(
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", str(src),
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _wrap(text: str, max_chars: int) -> list[str]:
    return textwrap.wrap(text, max_chars) or [""]


# ---------------------------------------------------------------------------
# Slide renderer — PIL → PNG
# ---------------------------------------------------------------------------

def render_slide(
    tmp_dir: Path,
    name: str,
    *,
    headline: str = "",
    subhead: str = "",
    body_lines: list[str] | None = None,
    tag: str = "",
    logo: bool = True,
    accent_bar: bool = True,
    columns: list[tuple[str, str]] | None = None,  # [(header, content), ...]
    big_stat: str = "",
    big_stat_label: str = "",
) -> Path:
    """Render a dark-branded slide and save as PNG. Returns the PNG path."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_tag    = _font(FONT_REG,  30)
    f_head   = _font(FONT_BOLD, 80)
    f_sub    = _font(FONT_BOLD, 48)
    f_body   = _font(FONT_REG,  38)
    f_small  = _font(FONT_REG,  28)
    f_mono   = _font(FONT_MONO, 34)
    f_big    = _font(FONT_BOLD, 180)
    f_big_lbl= _font(FONT_REG,  40)

    # Gold accent bar top
    if accent_bar:
        draw.rectangle([(80, 36), (1840, 44)], fill=GOLD)

    # Tag (top-left label, e.g. "THE PROBLEM")
    if tag:
        draw.text((80, 60), tag.upper(), font=f_tag, fill=GOLD)

    # Headline
    y = 100
    if tag:
        y = 130
    if headline:
        for line in _wrap(headline, 34):
            draw.text((80, y), line, font=f_head, fill=WHITE)
            y += 94
        y += 10

    # Sub-headline
    if subhead:
        for line in _wrap(subhead, 55):
            draw.text((80, y), line, font=f_sub, fill=GOLD)
            y += 60
        y += 20

    # Big stat (centered)
    if big_stat:
        bw = draw.textlength(big_stat, font=f_big)
        draw.text(((W - bw) // 2, 300), big_stat, font=f_big, fill=GOLD)
        if big_stat_label:
            label_lines = big_stat_label.replace("\\n", "\n").split("\n")
            ly = 510
            for ll in label_lines:
                lw = draw.textlength(ll.strip(), font=f_big_lbl)
                draw.text(((W - lw) // 2, ly), ll.strip(), font=f_big_lbl, fill=GREY)
                ly += 50

    # Body lines
    if body_lines:
        for line in body_lines:
            if not line.strip():
                y += 20
                continue
            color = WHITE
            fnt = f_body
            if line.startswith("  ") or line.startswith("    "):
                color = GREY
                fnt = f_mono
            elif line.startswith("//"):
                color = GOLD
                fnt = f_sub
                line = line[2:].strip()
            elif line.startswith("!!"):
                color = GRN_ACC
                fnt = f_body
                line = line[2:].strip()
            elif line.startswith("--"):
                color = RED_ACC
                fnt = f_body
                line = line[2:].strip()
            draw.text((80, y), line, font=fnt, fill=color)
            y += 52

    # Multi-column layout — starts BELOW the headline (so it never collides
    # with a wrapped 2-line title) and honors explicit newlines in both the
    # column header and body so nothing overruns.
    if columns:
        col_w = (W - 200) // len(columns)
        col_top = max(280, y + 24)
        f_colhead = _font(FONT_BOLD, 40)
        gutter = 24
        for ci, (ch, cc) in enumerate(columns):
            cx = 80 + ci * col_w
            cy = col_top
            for hl in ch.split("\n"):
                draw.text((cx, cy), hl, font=f_colhead, fill=GOLD)
                cy += 50
            cy += 16
            for para in cc.split("\n"):
                if not para.strip():
                    cy += 18
                    continue
                for ln in _wrap(para, 24):
                    draw.text((cx, cy), ln, font=f_body, fill=WHITE)
                    cy += 46

    # Logo (bottom-right wordmark) — right-aligned so it never clips the edge
    if logo:
        wm = "SALAREEN"
        ww = draw.textlength(wm, font=f_sub)
        wx = W - 80 - ww
        draw.text((wx, H - 70), wm, font=f_sub, fill=GOLD)
        draw.rectangle([(wx, H - 80), (W - 80, H - 78)], fill=GOLD)

    # Bottom slide-number tag (bottom-left)
    if tag:
        draw.text((80, H - 65), "Investor Pitch  •  2026", font=f_small, fill=GREY)

    out = tmp_dir / f"{name}.png"
    img.save(str(out), "PNG")
    return out


def png_to_clip(png: Path, duration: float, tmp_dir: Path, name: str) -> Path:
    """Convert a PNG to a silent H.264 clip of given duration."""
    out = tmp_dir / f"{name}.mp4"
    ffmpeg(
        "-loop", "1", "-i", str(png),
        "-t", str(duration),
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0b1020",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    )
    return out


def image_to_clip(img_path: Path, duration: float, tmp_dir: Path, name: str) -> Path:
    """Convert any image (webp/png/jpg) to a silent clip."""
    out = tmp_dir / f"{name}.mp4"
    ffmpeg(
        "-loop", "1", "-i", str(img_path),
        "-t", str(duration),
        "-vf", (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0b1020,"
            f"setsar=1"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    )
    return out


def panel_image_to_clip(img_path: Path, duration: float, tmp_dir: Path, name: str) -> Path:
    """Show a full image as a 'hero' slide: sharp, centered, with a subtle
    blurred-cover background filling the 16:9 frame (no empty pillarbox bars).

    Used for the provided product/architecture diagrams so they read cleanly at
    full size without distortion or cropping their labels.
    """
    out = tmp_dir / f"{name}.mp4"
    ffmpeg(
        "-loop", "1", "-i", str(img_path),
        "-t", str(duration),
        "-filter_complex", (
            f"[0:v]split=2[bg][fg];"
            f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"gblur=sigma=24,eq=brightness=-0.20:saturation=0.85[bgb];"
            f"[fg]scale={W-160}:{H-110}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
        ),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
        str(out),
    )
    return out


def extract_clip(src: Path, start: float, duration: float, tmp_dir: Path, name: str) -> Path:
    """Extract a time range from an existing MP4 (no re-encode for speed)."""
    out = tmp_dir / f"{name}.mp4"
    ffmpeg(
        "-ss", str(start), "-i", str(src),
        "-t", str(duration),
        "-vf", (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0b1020,"
            f"setsar=1"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    )
    return out


def gif_to_clip(gif_path: Path, duration: float, tmp_dir: Path, name: str) -> Path:
    """Convert a GIF to a looped silent clip of given duration."""
    out = tmp_dir / f"{name}.mp4"
    ffmpeg(
        "-stream_loop", "-1", "-i", str(gif_path),
        "-t", str(duration),
        "-vf", (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0b1020,"
            f"fps={FPS},setsar=1"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        str(out),
    )
    return out


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    """Word-wrap text to fit within max_w pixels for the given font."""
    if not text:
        return []
    lines: list[str] = []
    cur = ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def render_caption_png(
    tmp_dir: Path,
    name: str,
    *,
    title: str = "",
    subtitle: str = "",
    position: str = "bottom",
) -> Path:
    """Render a transparent caption band (PIL) sized to fit its wrapped text.

    Done in PIL (not ffmpeg drawtext) so it works on any platform regardless of
    whether ffmpeg was built with libfreetype, and so long captions wrap instead
    of running off-screen. The band auto-sizes so title and subtitle never
    overlap.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    f_title = _font(FONT_BOLD, 46)
    f_sub = _font(FONT_REG, 30)
    max_w = W - 240

    title_lines = _wrap_to_width(draw, title, f_title, max_w)
    sub_lines = _wrap_to_width(draw, subtitle, f_sub, max_w)

    title_lh, sub_lh, gap, pad = 56, 40, 14, 30
    content_h = pad
    if title_lines:
        content_h += len(title_lines) * title_lh
    if sub_lines:
        content_h += (gap if title_lines else 0) + len(sub_lines) * sub_lh
    content_h += pad
    band_h = max(112, content_h)
    band_top = 0 if position == "top" else H - band_h

    # Solid, high-opacity band for guaranteed legibility over busy footage.
    draw.rectangle([(0, band_top), (W, band_top + band_h)], fill=(11, 16, 32, 224))
    # Gold rule on the edge facing the video content.
    if position == "top":
        draw.rectangle([(0, band_top + band_h - 4), (W, band_top + band_h)], fill=(201, 160, 60, 245))
    else:
        draw.rectangle([(0, band_top), (W, band_top + 4)], fill=(201, 160, 60, 245))

    y = band_top + pad
    for ln in title_lines:
        tw = draw.textlength(ln, font=f_title)
        draw.text(((W - tw) // 2, y), ln, font=f_title, fill=(245, 245, 245, 255))
        y += title_lh
    if sub_lines:
        y += gap
        for ln in sub_lines:
            sw = draw.textlength(ln, font=f_sub)
            draw.text(((W - sw) // 2, y), ln, font=f_sub, fill=(201, 160, 60, 255))
            y += sub_lh

    out = tmp_dir / f"{name}_cap.png"
    img.save(str(out), "PNG")
    return out


def add_title_overlay(
    base_clip: Path,
    tmp_dir: Path,
    name: str,
    *,
    title: str = "",
    subtitle: str = "",
    position: str = "bottom",   # top | bottom
) -> Path:
    """Composite a readable PIL caption band onto a clip via ffmpeg overlay."""
    out = tmp_dir / f"{name}.mp4"

    if not (title or subtitle):
        ffmpeg(
            "-i", str(base_clip),
            "-vf", (
                f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0b1020,setsar=1"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(out),
        )
        return out

    cap = render_caption_png(tmp_dir, name, title=title, subtitle=subtitle, position=position)
    ffmpeg(
        "-i", str(base_clip),
        "-i", str(cap),
        "-filter_complex", (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0b1020,setsar=1[v];"
            f"[v][1:v]overlay=0:0[vo]"
        ),
        "-map", "[vo]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
        str(out),
    )
    return out


def concatenate_clips(clips: list[Path], out: Path, tmp_dir: Path) -> Path:
    """Concatenate clips with a brief fade-through-black between segments.

    Uses transition=fadeblack (not a dissolve) so two text-heavy slides are
    never superimposed during the transition — a plain crossfade made captions
    and slide text overlap and become unreadable.
    """
    if len(clips) == 1:
        shutil.copy(str(clips[0]), str(out))
        return out

    fade_dur = 0.6

    # Build the xfade filter chain
    inputs = []
    for c in clips:
        inputs += ["-i", str(c)]

    # Get durations
    durations: list[float] = []
    for c in clips:
        result = run(
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0", str(c),
        )
        durations.append(float(result.stdout.strip()))

    # Build xfade filter chain
    # [0][1] xfade offset=dur0-1 [v01]; [v01][2] xfade offset=dur0+dur1-2 [v012]; ...
    filter_parts = []
    current_label = "[0:v]"
    cumulative_dur = 0.0
    for i in range(1, len(clips)):
        offset = cumulative_dur + durations[i - 1] - fade_dur
        cumulative_dur += durations[i - 1] - fade_dur
        out_label = "[vout]" if i == len(clips) - 1 else f"[v{i}]"
        filter_parts.append(
            f"{current_label}[{i}:v]xfade=transition=fadeblack:duration={fade_dur}:offset={offset}{out_label}"
        )
        current_label = out_label

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def simple_concat(clips: list[Path], out: Path, tmp_dir: Path) -> Path:
    """Simple concat (no transitions) via concat demuxer."""
    list_file = tmp_dir / "concat_list.txt"
    lines = [f"file '{str(c.resolve())}'\n" for c in clips]
    list_file.write_text("".join(lines))
    ffmpeg(
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    )
    return out


# ---------------------------------------------------------------------------
# Slide definitions — each returns a list of clip segments
# ---------------------------------------------------------------------------

def seg_title(tmp: Path) -> list[Path]:
    """Cover slide: SALAREEN wordmark + tagline. 4 seconds."""
    sl = render_slide(tmp, "s00_cover",
        headline="SALAREEN",
        subhead="What if every learner had their own teacher?",
        tag="",
        logo=False,
        accent_bar=False,
    )
    return [png_to_clip(sl, 4.0, tmp, "c00_cover")]


# The opening narrative the deck cold-opens on. Its narration audio is muxed
# back over the final timeline in build_video (the slide pipeline is silent).
STORY_INTRO_SRC = DEMOS / "salareen_unteachable_wisdom.mp4"


def seg_story_intro(tmp: Path) -> list[Path]:
    """Cold-open: the full 'Unteachable Wisdom' brand story (video; audio muxed later)."""
    src = STORY_INTRO_SRC
    if not src.exists():
        # Fall back to the prior investor-pitch opening if the story isn't present.
        return seg_story_existing(tmp)
    dur = _probe_duration(src) or 46.0
    c = extract_clip(src, 0, dur, tmp, "c00_story_intro")
    return [c]


def seg_story_existing(tmp: Path) -> list[Path]:
    """Use the full existing investor pitch video as the opening story."""
    src = DEMOS / "salareen_investor_pitch.mp4"
    if not src.exists():
        return []
    # Use the full 29.5s video
    c = extract_clip(src, 0, 29.5, tmp, "c01_story")
    return [c]


def seg_problem(tmp: Path) -> list[Path]:
    """Slide 2: The Problem. ~15 seconds."""
    sl = render_slide(tmp, "s02_problem",
        tag="The Problem",
        headline="Education is broken\nin three directions",
        body_lines=[
            "",
            "// Personalization gap — one pace fails 66% of students",
            "",
            "  1 in 3 learners is bored, struggling, or invisible",
            "",
            "// Access gap — 1 in 5 children worldwide has no quality teacher",
            "",
            "  In sub-Saharan Africa: 1 in 2",
            "",
            "// Skills gap — 85 million jobs unfilled by 2030",
            "",
            "  Education moves too slowly for the economy",
        ],
    )
    c = png_to_clip(sl, 10.0, tmp, "c02_problem")

    # Stat card
    sl2 = render_slide(tmp, "s02b_stat",
        tag="The Problem",
        big_stat="$89T",
        big_stat_label="in lost human productivity lost per decade\n(McKinsey Global Institute, 2023)",
    )
    c2 = png_to_clip(sl2, 5.0, tmp, "c02b_stat")
    return [c, c2]


def seg_solution(tmp: Path) -> list[Path]:
    """Slide 3: The Solution — product demos. ~30 seconds total."""
    # Intro slide
    sl = render_slide(tmp, "s03_solution",
        tag="The Solution",
        headline="One AI campus.\nEvery learner.\nEvery language.",
        subhead='Like Netflix for learning — but it actually teaches.',
        body_lines=[
            "",
            "  Live AI classes   •   Drive Mode   •   27 languages",
            "  Careers track     •   Kids mode    •   Adaptive memory",
        ],
    )
    clips = [png_to_clip(sl, 5.0, tmp, "c03_intro")]

    # Live class demo
    gif_live = DEMOS / "persona_live_ai_class_student.gif"
    if gif_live.exists():
        c = gif_to_clip(gif_live, 6.0, tmp, "c03_live")
        c = add_title_overlay(c, tmp, "c03_live_t",
            title="Live AI Class — real-time adaptive tutor",
            subtitle="Perceives attention · adapts difficulty · answers in your language")
        clips.append(c)

    # Drive Mode
    gif_drive = DEMOS / "drive_mode_audio_courses_demo.gif"
    if gif_drive.exists():
        c = gif_to_clip(gif_drive, 5.0, tmp, "c03_drive")
        c = add_title_overlay(c, tmp, "c03_drive_t",
            title="Drive Mode — learn hands-free on your commute",
            subtitle="Audio-only · picks up where you left off")
        clips.append(c)

    # Language
    gif_lang = DEMOS / "language_learning_demo.gif"
    if gif_lang.exists():
        c = gif_to_clip(gif_lang, 5.0, tmp, "c03_lang")
        c = add_title_overlay(c, tmp, "c03_lang_t",
            title="27 Languages — teach and learn in any language",
            subtitle="Khmer · Swahili · Vietnamese · Portuguese · Arabic · and 22 more")
        clips.append(c)

    # Careers
    gif_careers = DEMOS / "careers_jobs_matching_demo.gif"
    if gif_careers.exists():
        c = gif_to_clip(gif_careers, 5.0, tmp, "c03_careers")
        c = add_title_overlay(c, tmp, "c03_careers_t",
            title="Careers Track — every lesson linked to real jobs",
            subtitle="Real-time job description parsing · skills-to-role matching")
        clips.append(c)

    # Kids
    gif_kids = DEMOS / "kids_mode_platform_demo.gif"
    if gif_kids.exists():
        c = gif_to_clip(gif_kids, 4.0, tmp, "c03_kids")
        c = add_title_overlay(c, tmp, "c03_kids_t",
            title="Kids Mode — safe, gamified, consent-gated",
            subtitle="Built to lift students up · never to put them at risk")
        clips.append(c)

    return clips


# Provided product/architecture diagrams — how the platform reaches users.
SLIDE_ARCH = DEMOS / "salareen_slide_architecture.png"
SLIDE_LIVE = DEMOS / "salareen_slide_live_class.png"
SLIDE_MEMORY = DEMOS / "salareen_slide_memory.png"


def seg_how_it_works(tmp: Path) -> list[Path]:
    """How the software is delivered to users: architecture → live class → memory."""
    sl = render_slide(tmp, "s_how",
        tag="How It Works",
        headline="From any device to a\npersonal AI campus",
        subhead="One platform — deployed where your learners already are.",
        body_lines=[
            "",
            "// Meet learners where they are",
            "  Web · Zoom · Microsoft Teams · Google Meet",
            "",
            "// One agent brain does it all",
            "  Teaching · perception · speech · memory · compliance",
            "",
            "// Remembers every learner across classes — private by design",
        ],
    )
    clips = [png_to_clip(sl, 6.0, tmp, "c_how_intro")]

    # Full diagrams shown clean (their own labels stay readable — no overlay).
    for img, dur, name in [
        (SLIDE_ARCH, 8.0, "c_how_arch"),
        (SLIDE_LIVE, 7.0, "c_how_live"),
        (SLIDE_MEMORY, 8.0, "c_how_mem"),
    ]:
        if img.exists():
            clips.append(panel_image_to_clip(img, dur, tmp, name))
    return clips


def seg_uvp(tmp: Path) -> list[Path]:
    """Slide 4: Unique Value Proposition. ~12 seconds."""
    sl = render_slide(tmp, "s04_uvp",
        tag="Why Us",
        headline="Eight unfair advantages",
        body_lines=[
            "// Truthful AI    Shows its work · cites sources · never bluffs",
            "// One campus     Teach · assess · remember — one unified system",
            "// Private        Biometrics on-device · consent-gated · FERPA/GDPR",
            "// Efficient      $0.0012 per learner / month at 5M daily users",
            "// Fast           6.3 ms response · 5 million DAU ready today",
            "// Human-backed   Real teacher review where it matters (HIL console)",
            "// Robot-ready    Same brain drives embodied humanoid tutors",
            "// Foresight™     Patent-pending predictive AI for learning outcomes",
        ],
    )
    c = png_to_clip(sl, 8.0, tmp, "c04_uvp")

    # Scale card from existing video
    src = DEMOS / "salareen_by_the_numbers.mp4"
    if src.exists():
        c2 = extract_clip(src, 0, 10.0, tmp, "c04_numbers")
        return [c, c2]
    return [c]


def seg_market(tmp: Path) -> list[Path]:
    """Slide 5: Market Opportunity. ~10 seconds."""
    sl = render_slide(tmp, "s05_market",
        tag="Market Opportunity",
        headline="A $7.3 trillion market\nat a once-in-a-century inflection point",
        columns=[
            ("TAM\n$7.3T / yr",
             "Global education\n(all spending)\nUNESCO / OECD 2023"),
            ("SAM\n$340B / yr",
             "EdTech: K-12,\nCorporate L&D,\nHigher Ed online\n14.3% CAGR"),
            ("SOM\n$18B / yr",
             "AI tutoring &\nadaptive learning\nplatforms\n2024-2027"),
        ],
    )
    c = png_to_clip(sl, 8.0, tmp, "c05_market")

    sl2 = render_slide(tmp, "s05b_why_now",
        tag="Market Opportunity",
        headline="Why now?",
        body_lines=[
            "",
            "!!  AI capability crossed the threshold of genuine usefulness in 2023",
            "",
            "!!  Mobile internet reached 60%+ penetration in the developing world",
            "",
            "!!  The global teacher shortage became a crisis in 132 countries",
            "",
            "  These three forces converge now — not in five years — now.",
        ],
    )
    c2 = png_to_clip(sl2, 7.0, tmp, "c05b_why_now")
    return [c, c2]


def seg_traction(tmp: Path) -> list[Path]:
    """Slide 6: Traction & Milestones. ~12 seconds."""
    sl = render_slide(tmp, "s06_traction",
        tag="Traction",
        headline="We did not pitch this idea.\nWe built it.",
        body_lines=[
            "",
            "!!  Platform live: web · iOS · Android · 27 languages",
            "!!  7 microservices in production on Kubernetes",
            "!!  739 automated tests · all passing (v0.10.0)",
            "!!  Foresight predictive engine: provisional patent filed",
            "!!  FERPA · GDPR · COPPA · BIPA compliance controls live",
            "!!  Human-in-the-Loop educator console: live for B2B pilots",
            "!!  100+ corporate and academic curriculum units",
            "",
            "  $0.0012 / learner / month (measured)   ·   6.3ms p95 (measured)",
        ],
    )
    c = png_to_clip(sl, 10.0, tmp, "c06_traction")

    # Platform screenshot
    screen = SCREENS / "live_class_grounded_answer.webp"
    if screen.exists():
        c2 = image_to_clip(screen, 4.0, tmp, "c06_screen")
        c2 = add_title_overlay(c2, tmp, "c06_screen_t",
            title="Live platform — production today",
            subtitle="AI tutor · grounded answers · citations · adaptive pacing")
        return [c, c2]
    return [c]


def seg_business_model(tmp: Path) -> list[Path]:
    """Slide 7: Business Model. ~12 seconds."""
    sl = render_slide(tmp, "s07_biz",
        tag="Business Model",
        headline="Three revenue streams.\nOne platform.",
        columns=[
            ("B2C Subscriptions",
             "Free tier — funnel\nPro   $15/mo — core\nPremium $29/mo — all-in\n\nCAC ~$8  LTV ~$252\nLTV/CAC  31.5x\nGross margin  72%"),
            ("B2B Seat Licensing",
             "$15-30/seat/month\nCorporate L&D\nSite licensing\nAPI licensing\n\nAvg cohort 50 seats\nEnterprise contract"),
            ("Marketplace & Add-ons",
             "Curriculum marketplace\n30% platform fee\n\nCertifications\n$49-199 per exam\n\nPremium AI add-ons\nMetered GPU minutes"),
        ],
    )
    return [png_to_clip(sl, 12.0, tmp, "c07_biz")]


def seg_competition(tmp: Path) -> list[Path]:
    """Slide 8: Competition. ~10 seconds."""
    sl = render_slide(tmp, "s08_comp",
        tag="The Competition",
        headline="No one puts it all\nin one campus.",
        body_lines=[
            "",
            "                      Adaptive  Multi-lingual  Live AI  Human  On-device",
            "--  Khan Academy       YES         No            No       No      No",
            "--  Duolingo           No          YES           No       No      No",
            "--  Coursera           No          Partial       Partial  No      No",
            "--  Synthesis          YES         No            No       No      No",
            "--  Squirrel AI        YES         No            No       No      No",
            "",
            "!!  Salareen           YES         YES           YES      YES     YES",
        ],
    )
    c = png_to_clip(sl, 10.0, tmp, "c08_comp")

    sl2 = render_slide(tmp, "s08b_moat",
        tag="The Competition",
        headline="We are not trying\nto out-Duolingo Duolingo.",
        subhead="We are replacing the category question.",
        body_lines=[
            "",
            '  "Where do I go to actually learn something?"',
            "",
            "  → Salareen. Because we do all of it.",
        ],
    )
    c2 = png_to_clip(sl2, 6.0, tmp, "c08b_moat")
    return [c, c2]


def seg_team(tmp: Path) -> list[Path]:
    """Slide 9: Team. ~8 seconds."""
    sl = render_slide(tmp, "s09_team",
        tag="The Team",
        headline="Why this team?",
        body_lines=[
            "",
            "// We shipped first.",
            "",
            "  v0.10.0 is a live, deployed, multi-service platform.",
            "  7 microservices · multi-agent AI · iOS · Android · 739 tests.",
            "  That is the proof.",
            "",
            "// Domain expertise across the full stack:",
            "",
            "  AI systems · adaptive pedagogy · multilingual NLP",
            "  LiveKit WebRTC · compliance (FERPA/GDPR) · mobile",
            "",
            "// The founding team built the platform before raising capital.",
            "  That is the strongest signal of execution quality.",
        ],
    )
    return [png_to_clip(sl, 10.0, tmp, "c09_team")]


def seg_financials(tmp: Path) -> list[Path]:
    """Slide 10: Financial Projections. ~12 seconds."""
    sl = render_slide(tmp, "s10_fin",
        tag="Financial Projections",
        headline="A realistic path\nto $100M ARR.",
        body_lines=[
            "",
            "                  Year 1       Year 2       Year 3",
            "  Active learners  25,000      150,000      600,000",
            "  Total ARR        $3.6M        $21.6M       $86.4M",
            "  Gross margin     68%          72%          75%",
            "  EBITDA           -$2.4M       +$1.1M       +$18.2M",
            "",
            "// Key assumption: $0.0012 / learner / month (measured production cost)",
            "// Profitability: Year 2. Series A ready: Month 18.",
            "",
            "  Duolingo at IPO (2021): $250M ARR, 40% YoY growth",
            "  We have more verticals and better unit economics.",
        ],
    )
    return [png_to_clip(sl, 12.0, tmp, "c10_fin")]


def seg_ask(tmp: Path) -> list[Path]:
    """Slide 11: The Ask. ~15 seconds."""
    sl = render_slide(tmp, "s11_ask",
        tag="The Ask",
        headline="$5,000,000 Seed Round",
        subhead="SAFE Note · $20M valuation cap · 20% discount · Q3 2026 close",
        body_lines=[
            "",
            "  Growth & Acquisition    40%  →  $2,000,000",
            "  !! Funds 250,000 learner acquisitions at $8 CAC",
            "",
            "  Engineering & AI R&D    30%  →  $1,500,000",
            "  !! Fine-tune education model · Foresight · robot integration",
            "",
            "  B2B Sales               20%  →  $1,000,000",
            "  !! Corporate L&D cohorts · API licensing · institutional contracts",
            "",
            "  Operations & Compliance 10%  →  $500,000",
            "  !! FERPA audit · GDPR DPA · enterprise infrastructure",
        ],
    )
    c = png_to_clip(sl, 10.0, tmp, "c11_ask")

    sl2 = render_slide(tmp, "s11b_milestones",
        tag="The Ask",
        headline="Milestones this round funds",
        body_lines=[
            "",
            "!!  Month 3   →  10,000 active learners",
            "!!  Month 6   →  First paying B2B cohort (500+ seats)",
            "!!  Month 12  →  $3.6M ARR run rate",
            "!!  Month 18  →  Series A ready ($15-20M target)",
            "",
            "",
            "// We are not asking you to believe in a vision.",
            "// We are asking you to fund the next phase of",
            "// something that already works.",
        ],
    )
    c2 = png_to_clip(sl2, 8.0, tmp, "c11b_milestones")
    return [c, c2]


def seg_closing(tmp: Path) -> list[Path]:
    """Closing slide: back to story + tagline."""
    sl = render_slide(tmp, "s12_close",
        tag="",
        headline="",
        logo=False,
        accent_bar=False,
        body_lines=[],
    )
    # Reuse the existing investor pitch closing (last 8 seconds)
    src = DEMOS / "salareen_investor_pitch.mp4"
    if src.exists():
        dur = 29.5
        c = extract_clip(src, max(0, dur - 8), 8.0, tmp, "c12_close_existing")
        return [c]

    # Fallback
    sl_close = render_slide(tmp, "s12_close_fallback",
        tag="",
        headline="Invest in the next\n200 years of school.",
        logo=True,
        accent_bar=True,
        body_lines=[
            "",
            "  salareen.com  ·  Seed Round 2026",
        ],
    )
    return [png_to_clip(sl_close, 5.0, tmp, "c12_close")]


def seg_platform_tour(tmp: Path) -> list[Path]:
    """Short platform tour from existing MP4. Used as a bridge."""
    src = DEMOS / "platform_walkthrough.mp4"
    if not src.exists():
        return []
    c = extract_clip(src, 0, 12.0, tmp, "cbridge_tour")
    c = add_title_overlay(c, tmp, "cbridge_tour_t",
        title="Salareen — platform tour",
        subtitle="Live today on web · iOS · Android",
        position="bottom")
    return [c]


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------

def build_video(out_path: Path, preview: bool = False) -> None:
    print(f"\n{'='*60}")
    print("Salareen Investor Pitch Video Generator")
    print(f"Output: {out_path}")
    print(f"{'='*60}\n")

    with tempfile.TemporaryDirectory(prefix="salareen_pitch_") as td:
        tmp = Path(td)
        all_clips: list[Path] = []

        segments = [
            ("Opening Story",     seg_story_intro),
            ("Cover",             seg_title),
            ("The Problem",       seg_problem),
            ("The Solution",      seg_solution),
            ("How It Works",      seg_how_it_works),
            ("Platform Tour",     seg_platform_tour),
            ("Unique Value",      seg_uvp),
            ("Market",            seg_market),
            ("Traction",          seg_traction),
            ("Business Model",    seg_business_model),
            ("Competition",       seg_competition),
            ("Team",              seg_team),
            ("Financials",        seg_financials),
            ("The Ask",           seg_ask),
            ("Closing",           seg_closing),
        ]

        if preview:
            segments = segments[:5]
            print("[PREVIEW MODE — first 5 segments only]\n")

        for i, (label, fn) in enumerate(segments):
            print(f"[{i+1:2d}/{len(segments)}] Rendering: {label}...")
            try:
                clips = fn(tmp)
                all_clips.extend(clips)
                print(f"        → {len(clips)} clip(s)")
            except Exception as exc:
                print(f"        ⚠  Skipped ({exc})")

        if not all_clips:
            print("ERROR: No clips generated.")
            sys.exit(1)

        print(f"\nConcatenating {len(all_clips)} clips...")
        concat_out = tmp / "final_concat.mp4"
        try:
            concatenate_clips(all_clips, concat_out, tmp)
        except Exception as exc:
            print(f"xfade concat failed ({exc}), falling back to simple concat...")
            simple_concat(all_clips, concat_out, tmp)

        # Final pass: clean single re-encode to 1080p H.264. When the opening
        # story exists, its narration is muxed IN THIS SAME PASS (no separate
        # stream-copy step, which previously corrupted frame timing). The story
        # is the first segment, so its audio starts at t=0; apad fills the rest
        # of the timeline with silence and -shortest trims audio to video length.
        print("Writing final output...")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        final_vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0b1020,setsar=1"
        )
        if STORY_INTRO_SRC.exists() and not preview:
            ffmpeg(
                "-i", str(concat_out),
                "-i", str(STORY_INTRO_SRC),
                "-filter_complex", f"[0:v]{final_vf}[v];[1:a]aresample=48000,apad[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                "-shortest",
                "-movflags", "+faststart",
                str(out_path),
            )
        else:
            ffmpeg(
                "-i", str(concat_out),
                "-vf", final_vf,
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-movflags", "+faststart",
                str(out_path),
            )

        dur_s = _probe_duration(out_path)
        size_mb = out_path.stat().st_size / 1_048_576
        m, s = divmod(int(dur_s), 60)

    print(f"\n{'='*60}")
    print(f"✓  Done: {out_path}")
    print(f"   Duration: {m}m {s:02d}s")
    print(f"   Size:     {size_mb:.1f} MB")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate Salareen investor pitch video")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Output path")
    ap.add_argument("--preview", action="store_true", help="Render first 5 segments only")
    args = ap.parse_args()
    build_video(Path(args.out), preview=args.preview)
