#!/usr/bin/env python3
"""Render documentation screenshots for every Theodore experiment subrepo.

Chrome/Playwright capture is not always available in agent environments, so
these are deterministic Pillow mockups that match each lab's real palette and
layout (same approach as scripts/render_sdk_docs_screenshots.py).

Writes webp files into:
  - subrepos/<lab>/docs/screens/
  - docs/screens/ (canonical copies referenced from the root README)

Re-run after UI changes:
  python3 scripts/render_lab_docs_screenshots.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "screens"
WIDTH, HEIGHT = 1400, 900


def _font(size: int, *, mono: bool = False, bold: bool = False):
    candidates = (
        [
            "/System/Library/Fonts/SFNSMono.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]
        if mono
        else (
            [
                "/System/Library/Fonts/SFNSDisplay-Bold.otf",
                "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
            if bold
            else [
                "/System/Library/Fonts/Supplemental/Georgia.ttf",
                "/System/Library/Fonts/SFNS.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        )
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


TITLE = _font(34, bold=True)
SUB = _font(16)
H2 = _font(18, bold=True)
BODY = _font(15)
SMALL = _font(12)
MONO = _font(13, mono=True)
KIDS = _font(22, bold=True)


def _save(image: Image.Image, lab: str, name: str) -> Path:
    lab_dir = ROOT / "subrepos" / lab / "docs" / "screens"
    lab_dir.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    dest_lab = lab_dir / name
    dest_docs = DOCS / name
    image.save(dest_lab, format="WEBP", quality=90, method=6)
    image.save(dest_docs, format="WEBP", quality=90, method=6)
    return dest_lab


def _header(draw: ImageDraw.ImageDraw, box, bg, title, subtitle, accent):
    x0, y0, x1, y1 = box
    draw.rectangle((x0, y0, x1, y1), fill=bg)
    draw.ellipse((x0 + 28, y0 + 22, x0 + 62, y0 + 56), fill=accent)
    draw.text((x0 + 78, y0 + 18), title, font=TITLE, fill="#f4fff8")
    draw.text((x0 + 80, y0 + 58), subtitle, font=SUB, fill="#a7c4b5")


def _panel(draw, box, fill, outline, title, title_color):
    draw.rounded_rectangle(box, radius=12, fill=fill, outline=outline, width=2)
    draw.text((box[0] + 16, box[1] + 12), title, font=H2, fill=title_color)


def _badge(draw, xy, text, fill, outline, color):
    x, y = xy
    w = max(70, int(draw.textlength(text, font=SMALL)) + 18)
    draw.rounded_rectangle((x, y, x + w, y + 22), radius=11, fill=fill, outline=outline)
    draw.text((x + 9, y + 4), text, font=SMALL, fill=color)


def _bar(draw, box, pct, fill):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=6, fill="#0a1210", outline="#3a5548")
    inner = x0 + 2 + int((x1 - x0 - 4) * max(0.0, min(1.0, pct)))
    draw.rounded_rectangle((x0 + 2, y0 + 2, inner, y1 - 2), radius=5, fill=fill)


def render_course_studio() -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), "#14201a")
    draw = ImageDraw.Draw(img)
    _header(
        draw,
        (0, 0, WIDTH, 96),
        "#1b3a2f",
        "Theodore Course Studio",
        "Early-learning Make & teach  ·  Pre-K–Grade 2  ·  Certification prep",
        "#3d9a74",
    )
    # Kids builder
    draw.rounded_rectangle(
        (18, 112, WIDTH - 18, 250),
        radius=16,
        fill="#fff7ed",
        outline="#f59e0b",
        width=3,
    )
    draw.text((36, 126), "Make a children's lesson", font=H2, fill="#7c2d12")
    draw.text(
        (36, 156),
        "Level: Kindergarten    Topic: Counting 1–10    Language: Spanish (es)",
        font=BODY,
        fill="#172554",
    )
    draw.rounded_rectangle((36, 196, 180, 232), radius=8, fill="#ea580c")
    draw.text((58, 204), "Make & teach", font=BODY, fill="#fff")
    draw.rounded_rectangle((196, 196, 310, 232), radius=8, fill="#fff", outline="#f59e0b")
    draw.text((214, 204), "Read aloud", font=BODY, fill="#7c2d12")

    _panel(draw, (18, 268, 690, 870), "#18261f", "#2f5a48", "Teach stage", "#9fddc0")
    draw.rounded_rectangle((36, 310, 672, 520), radius=10, fill="#0f1a15", outline="#3a5548")
    draw.text((56, 330), "Count the apples", font=KIDS, fill="#e8efe9")
    draw.text(
        (56, 380),
        "Hay tres manzanas rojas.  ¿Cuántas hay?",
        font=BODY,
        fill="#d7e6dc",
    )
    draw.text(
        (56, 430),
        "Narration: Cuenta conmigo — uno, dos, tres.",
        font=BODY,
        fill="#9fddc0",
    )
    draw.rounded_rectangle((56, 470, 420, 500), radius=16, fill="#312e81")
    draw.text((76, 476), "Activity: Point and say the numbers", font=SMALL, fill="#fff")

    _panel(draw, (710, 268, WIDTH - 18, 560), "#18261f", "#2f5a48", "Corpus / review", "#9fddc0")
    for i, (name, tag) in enumerate(
        (
            ("colors_prek.esl.json", "good"),
            ("dmv_permit_ca.pdf", "cert"),
            ("policy_appendix.pptx", "reject"),
        )
    ):
        y = 320 + i * 60
        draw.rounded_rectangle((728, y, WIDTH - 36, y + 48), radius=8, fill="#21362c")
        draw.text((746, y + 14), name, font=MONO, fill="#e8efe9")
        color = {"good": "#3d9a74", "cert": "#0284c7", "reject": "#9a3d3d"}[tag]
        _badge(draw, (WIDTH - 150, y + 12), tag, "#20332a", color, color)

    _panel(draw, (710, 580, WIDTH - 18, 870), "#18261f", "#2f5a48", "Studio tuning", "#9fddc0")
    for i, (label, pct) in enumerate(
        (("slide_budget", 0.72), ("engagement_floor", 0.55), ("narration_pace", 0.4))
    ):
        y = 640 + i * 60
        draw.text((730, y), label, font=SMALL, fill="#9bb5a8")
        _bar(draw, (730, y + 22, WIDTH - 50, y + 38), pct, "#3d9a74")

    _save(img, "theodore_course_studio", "theodore_course_studio.webp")


def render_audio_lab() -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), "#08111f")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, WIDTH, 100), fill="#08111f")
    draw.ellipse((28, 24, 62, 58), fill="#24c8a5")
    draw.text((78, 20), "Theodore Audio Translation Lab", font=TITLE, fill="#e8f2ff")
    draw.text(
        (80, 62),
        "Realtime mic → ASR → 27-language fan-out  ·  Theodore replies after each turn",
        font=SUB,
        fill="#94abc7",
    )

    _panel(draw, (16, 118, 560, 870), "#101d30", "#263d5c", "Capture", "#b6d8ff")
    draw.rounded_rectangle((36, 160, 540, 360), radius=12, fill="#02060a", outline="#263d5c")
    draw.text((190, 240), "Webcam / mic preview", font=BODY, fill="#94abc7")
    _bar(draw, (36, 380, 540, 396), 0.62, "#25c8a6")
    draw.text((36, 410), "Mic level  ·  gate −39 dB  ·  window 1.2s", font=SMALL, fill="#94abc7")
    for i, b in enumerate(("ASR: Whisper", "Latency: Balanced", "Gate: ON", "Lang: Auto")):
        _badge(
            draw,
            (36 + (i % 2) * 170, 450 + (i // 2) * 34),
            b,
            "#113a33",
            "#23836f",
            "#9ef5df",
        )
    draw.rounded_rectangle((36, 540, 220, 578), radius=8, fill="#24c8a5")
    draw.text((70, 550), "Start session", font=BODY, fill="#04261f")
    draw.rounded_rectangle((236, 540, 390, 578), radius=8, fill="#213955", outline="#355778")
    draw.text((258, 550), "Join as viewer", font=BODY, fill="#e8f2ff")

    _panel(draw, (580, 118, WIDTH - 16, 870), "#101d30", "#263d5c", "Live feed", "#b6d8ff")
    cards = [
        ("learner · es", "Buenos días clase", "Good morning class", False),
        ("Theodore · teach · km", "Suosdei! Let's begin in Khmer.", "Hello! Let's begin.", True),
        ("teacher · fr", "Répétez après moi", "Repeat after me", False),
    ]
    for i, (meta, source, trans, theo) in enumerate(cards):
        y = 168 + i * 200
        fill = "#211b43" if theo else "#0b1727"
        outline = "#6d57ba" if theo else "#263d5c"
        draw.rounded_rectangle((600, y, WIDTH - 36, y + 170), radius=12, fill=fill, outline=outline)
        draw.text((620, y + 14), meta, font=SMALL, fill="#94abc7")
        draw.text((620, y + 44), source, font=BODY, fill="#c8d8ec")
        draw.text((620, y + 84), trans, font=KIDS, fill="#ddd4ff" if theo else "#e8f2ff")
        if theo:
            draw.text((620, y + 130), "spoken · reply language km", font=SMALL, fill="#9ef5df")

    _save(img, "theodore_audio_translation_lab", "theodore_audio_translation_lab.webp")


def render_webcam_lab() -> None:
    # Webcam already ships real captures; also emit a summary board for the gallery.
    img = Image.new("RGB", (WIDTH, HEIGHT), "#0f1419")
    draw = ImageDraw.Draw(img)
    _header(
        draw,
        (0, 0, WIDTH, 96),
        "#162028",
        "Theodore Webcam Lab",
        "Live monitor  ·  vision tuning  ·  lesson alerts  ·  26-language voice",
        "#5ec8ff",
    )
    metrics = [
        ("Avg distance", "0.82 m"),
        ("Light", "0.91"),
        ("Image", "0.88"),
        ("Mic", "ok"),
        ("Presence", "2 / 2"),
    ]
    for i, (k, v) in enumerate(metrics):
        x0 = 20 + i * 275
        draw.rounded_rectangle((x0, 120, x0 + 255, 210), radius=12, fill="#1b2730", outline="#2f4554")
        draw.text((x0 + 18, 138), k, font=SMALL, fill="#8aa0b2")
        draw.text((x0 + 18, 164), v, font=KIDS, fill="#e8f2ff")

    for i, name in enumerate(("Maya · attentive", "Jordan · distracted")):
        x0 = 20 + i * 690
        draw.rounded_rectangle((x0, 240, x0 + 660, 860), radius=14, fill="#152029", outline="#2f4554")
        draw.rounded_rectangle((x0 + 18, 270, x0 + 642, 520), radius=10, fill="#0a1016")
        draw.text((x0 + 40, 380), "camera frame", font=BODY, fill="#5a7386")
        draw.text((x0 + 24, 540), name, font=H2, fill="#e8f2ff")
        for j, (label, pct) in enumerate(
            (("sharpness", 0.8 if i == 0 else 0.35), ("light", 0.9 if i == 0 else 0.45), ("mic", 0.7 if i == 0 else 0.2))
        ):
            y = 590 + j * 55
            draw.text((x0 + 24, y), label, font=SMALL, fill="#8aa0b2")
            _bar(draw, (x0 + 24, y + 22, x0 + 620, y + 38), pct, "#5ec8ff" if i == 0 else "#f4b942")
        if i == 1:
            draw.rounded_rectangle((x0 + 24, 780, x0 + 280, 820), radius=8, fill="#6b2121")
            draw.text((x0 + 48, 790), "Lesson alert: looking away", font=SMALL, fill="#ffd0d0")

    _save(img, "theodore_webcam_lab", "theodore_webcam_lab_overview.webp")


def _lab_console(
    *,
    lab: str,
    filename: str,
    title: str,
    subtitle: str,
    accent: str,
    left_title: str,
    left_rows: list[tuple[str, str]],
    right_title: str,
    right_lines: list[str],
    pills: list[str],
) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), "#0b1020")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, WIDTH, 100), fill="#121a2e")
    draw.ellipse((28, 24, 62, 58), fill=accent)
    draw.text((78, 20), title, font=TITLE, fill="#f5f7ff")
    draw.text((80, 62), subtitle, font=SUB, fill="#9aa6c1")
    for i, pill in enumerate(pills):
        _badge(draw, (78 + i * 150, 110), pill, "#1a243a", accent, accent)

    _panel(draw, (20, 160, 680, 860), "#121a2e", "#2a3755", left_title, accent)
    for i, (k, v) in enumerate(left_rows):
        y = 220 + i * 48
        draw.text((44, y), k, font=BODY, fill="#9aa6c1")
        draw.text((320, y), v, font=MONO, fill="#e8eeff")
        draw.line((44, y + 32, 650, y + 32), fill="#1f2a42")

    _panel(draw, (710, 160, WIDTH - 20, 860), "#121a2e", "#2a3755", right_title, accent)
    draw.rounded_rectangle((730, 210, WIDTH - 40, 820), radius=12, fill="#0a0f1c", outline="#2a3755")
    y = 240
    for line in right_lines:
        color = accent if line.startswith("$") or line.startswith("→") else "#d7def2"
        if line.startswith("#"):
            color = "#7f8bab"
        draw.text((760, y), line, font=MONO, fill=color)
        y += 34

    _save(img, lab, filename)


def render_rag_lab() -> None:
    _lab_console(
        lab="theodore_rag_lab",
        filename="theodore_rag_lab.webp",
        title="Theodore RAG Lab",
        subtitle="Private knowledge-base auto-tune  ·  hours-a-day bakeoff  ·  :8095",
        accent="#7DD3FC",
        left_title="Live tuning",
        left_rows=[
            ("top_k", "8"),
            ("min_score", "0.18"),
            ("groundedness_min", "0.62"),
            ("lexical_vs_fts", "hybrid"),
            ("chunk_tokens", "420"),
            ("champion_rounds", "47"),
            ("golden_examples", "16"),
            ("docs_indexed", "128"),
        ],
        right_title="Bakeoff console",
        right_lines=[
            "$ uvicorn theodore_rag_lab.main:app --port 8095",
            "# POST /api/rag/eval",
            "→ groundedness 0.71  recall@8 0.88",
            "# POST /api/rag/train/start  hours=1.0",
            "→ status running  round 12/≈240",
            "# GET /api/rag/champion",
            "→ top_k=8  min_score=0.18  promoted",
            "# GET /api/rag/telemetry",
            "→ evals=94  promotes=3  reverts=1",
        ],
        pills=["offline", "no GPU", "promote-ready"],
    )


def render_drive_lab() -> None:
    _lab_console(
        lab="theodore_drive_lab",
        filename="theodore_drive_lab.webp",
        title="Theodore Drive Lab",
        subtitle="Hands-free audio agent fine-tune  ·  wake / echo / TTS / Q&A  ·  :8096",
        accent="#D6A84B",
        left_title="Drive tuning",
        left_rows=[
            ("wake_phrase", "Hey Sala / Salareen"),
            ("wake_precision", "0.94"),
            ("wake_recall", "0.91"),
            ("echo_reject_db", "-28"),
            ("pause_to_submit_ms", "650"),
            ("resume_delay_ms", "400"),
            ("tts_engine", "edge-tts → device"),
            ("grounding_min", "0.55"),
        ],
        right_title="Eval console",
        right_lines=[
            "$ uvicorn theodore_drive_lab.main:app --port 8096",
            "# POST /api/drive/wake/eval",
            "→ precision 0.94  recall 0.91  F1 0.92",
            "# POST /api/drive/answer/eval",
            "→ grounding 0.78  covered 11/12",
            "# POST /api/drive/bakeoff  rounds=12",
            "→ champion pause_to_submit_ms=650",
            "# GET /api/drive/telemetry",
            "→ wake_evals=24  answer_evals=18",
        ],
        pills=["wake", "echo", "TTS prosody"],
    )


def render_homework_lab() -> None:
    _lab_console(
        lab="theodore_homework_lab",
        filename="theodore_homework_lab.webp",
        title="Theodore Homework Lab",
        subtitle="50+ methodologies  ·  generate + grade quality battery  ·  :8098",
        accent="#7DD3A8",
        left_title="Methodologies (sample)",
        left_rows=[
            ("registered", "52"),
            ("choice", "mcq · multi_select · true_false"),
            ("open", "short_answer · essay"),
            ("media", "picture_id · hotspot · video"),
            ("audio", "dictation · pronunciation"),
            ("language", "grammar · idioms · translate"),
            ("games", "scramble · memory · karaoke"),
            ("gold battery", "100% pass"),
        ],
        right_title="Generate / grade",
        right_lines=[
            "$ uvicorn theodore_homework_lab.main:app --port 8098",
            "# GET /api/homework/methodologies",
            "→ count 52  families 16",
            "# POST /api/homework/generate",
            "→ assignment 12 items  subject=science",
            "# POST /api/homework/grade",
            "→ score 0.83  feedback per item",
            "# GET /api/homework/telemetry",
            "→ generated=40  graded=40",
        ],
        pills=["offline", "50+ methods", "gold battery"],
    )


def render_music_lab() -> None:
    _lab_console(
        lab="theodore_music_lab",
        filename="theodore_music_lab.webp",
        title="Theodore Music Lab",
        subtitle="Storyboard theater  ·  karaoke  ·  sing in 27 languages  ·  :8097",
        accent="#C4B5FD",
        left_title="Player",
        left_rows=[
            ("featured MP3s", "3 (+100 text songs)"),
            ("storyboard", "22 scenes · 15 backdrops"),
            ("cast", "23 SVG characters + props"),
            ("camera", "push · pan · tilt · ken burns"),
            ("karaoke", "bouncing ball · word colour"),
            ("translation", "27 languages, every line"),
            ("narration", "on screen, spoken on request"),
            ("sing-along", "English track → 27 languages"),
            ("clips / videos", "6 clips · 6 lyric videos"),
        ],
        right_title="Full-screen theater",
        right_lines=[
            "♪ Wheels on the Bus (learning version)",
            "Scene 2/6 · The bus rolls through town · pan-right",
            "  [ town street · bus wheels spin · door opens ]",
            "El autobús cruza la ciudad. Sus ruedas giran.",
            "  Wheels on the bus go ●round● and round",
            "    Las ruedas del autobús giran y giran",
            "  → All through the town · Por toda la ciudad",
            "  [x] Sing in Spanish · English ducked to backing",
            "ask: why 'round and round'?",
            "→ chorus repeats one pattern · town = pueblo",
        ],
        pills=["full-screen scenes", "movie camera moves", "sing in any language"],
    )


def main() -> None:
    render_course_studio()
    render_audio_lab()
    render_webcam_lab()
    render_rag_lab()
    render_drive_lab()
    render_homework_lab()
    render_music_lab()
    print("wrote lab screenshots to subrepos/*/docs/screens and docs/screens/")


if __name__ == "__main__":
    main()
