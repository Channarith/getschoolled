#!/usr/bin/env python3
"""Render sanitized, deterministic SDK documentation screenshots."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "screens" / "sdk"
WIDTH = 1600
HEIGHT = 900

NAVY = "#111827"
NAVY_2 = "#172033"
GOLD = "#D6A84B"
CREAM = "#FFF8E8"
WHITE = "#FFFFFF"
MUTED = "#9CA3AF"
GREEN = "#7DD3A8"
BLUE = "#7DD3FC"
PURPLE = "#C4B5FD"
RED = "#FDA4AF"


def _font(size: int, *, mono: bool = False, bold: bool = False):
    candidates = (
        [
            "/System/Library/Fonts/SFNSMono.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]
        if mono
        else [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    if bold and not mono:
        candidates.insert(0, "/System/Library/Fonts/SFNSDisplay-Bold.otf")
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


TITLE = _font(42, bold=True)
SUBTITLE = _font(22)
HEADING = _font(25, bold=True)
BODY = _font(20)
MONO = _font(19, mono=True)
MONO_SMALL = _font(17, mono=True)


def _canvas(title: str, subtitle: str):
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 112), fill=NAVY_2)
    draw.ellipse((48, 30, 98, 80), fill=GOLD)
    draw.text((118, 26), title, font=TITLE, fill=WHITE)
    draw.text((120, 76), subtitle, font=SUBTITLE, fill=MUTED)
    return image, draw


def _panel(draw, box, title: str, *, fill: str = NAVY_2, outline: str = "#334155"):
    draw.rounded_rectangle(box, radius=18, fill=fill, outline=outline, width=2)
    draw.text((box[0] + 24, box[1] + 18), title, font=HEADING, fill=GOLD)


def _terminal(draw, box, lines: list[tuple[str, str]], title: str):
    draw.rounded_rectangle(box, radius=16, fill="#0B1020", outline="#374151", width=2)
    draw.rectangle((box[0], box[1], box[2], box[1] + 46), fill="#202A3D")
    for index, color in enumerate((RED, GOLD, GREEN)):
        x = box[0] + 24 + index * 24
        draw.ellipse((x, box[1] + 15, x + 13, box[1] + 28), fill=color)
    draw.text((box[0] + 118, box[1] + 12), title, font=MONO_SMALL, fill=MUTED)
    y = box[1] + 68
    for text, color in lines:
        draw.text((box[0] + 28, y), text, font=MONO, fill=color)
        y += 30


def render_architecture() -> None:
    image, draw = _canvas(
        "AOEP Python SDK",
        "One developer surface for remote services and embedded platform capabilities",
    )
    _panel(draw, (55, 150, 435, 805), "Developer application")
    draw.text((85, 220), "AOEPClient", font=HEADING, fill=WHITE)
    for index, name in enumerate(
        ("orchestrator", "identity", "curriculum", "memory", "raw request()")
    ):
        y = 280 + index * 68
        draw.rounded_rectangle((85, y, 395, y + 46), radius=10, fill="#26344F")
        draw.text((105, y + 10), name, font=BODY, fill=BLUE)
    draw.text((85, 650), "Credentials", font=HEADING, fill=WHITE)
    draw.text((85, 695), "Bearer / Internal / Admin", font=BODY, fill=MUTED)
    draw.text((85, 735), "X-Request-ID on every call", font=BODY, fill=MUTED)

    _panel(draw, (585, 150, 1015, 805), "AOEP service ecosystem")
    services = [
        ("Orchestrator", "lessons, sessions, Q&A"),
        ("Identity", "accounts and rewards"),
        ("Curriculum", "search and catalog"),
        ("Memory", "signals and mastery"),
        ("Other services", "speech, vision, billing"),
    ]
    for index, (name, detail) in enumerate(services):
        y = 220 + index * 104
        draw.rounded_rectangle((620, y, 980, y + 76), radius=12, fill="#203047")
        draw.text((642, y + 10), name, font=HEADING, fill=WHITE)
        draw.text((642, y + 43), detail, font=BODY, fill=MUTED)

    _panel(draw, (1165, 150, 1545, 805), "In-process library")
    capabilities = (
        "Provider factory",
        "RAG retrieval",
        "Adaptive learning",
        "Course harvesting",
        "Teaching pipeline",
        "Training agents",
    )
    for index, name in enumerate(capabilities):
        y = 225 + index * 78
        draw.rounded_rectangle((1200, y, 1510, y + 48), radius=10, fill="#2A2545")
        draw.text((1220, y + 11), name, font=BODY, fill=PURPLE)

    draw.line((435, 470, 585, 470), fill=GOLD, width=5)
    draw.polygon(((585, 470), (565, 458), (565, 482)), fill=GOLD)
    draw.text((462, 425), "JSON/HTTP", font=BODY, fill=CREAM)
    draw.line((1015, 470, 1165, 470), fill=GOLD, width=5)
    draw.polygon(((1165, 470), (1145, 458), (1145, 482)), fill=GOLD)
    draw.text((1032, 425), "same engines", font=BODY, fill=CREAM)
    image.save(OUTPUT / "sdk_architecture.png", optimize=True)


def render_quickstart() -> None:
    image, draw = _canvas(
        "SDK quick start",
        "Install, configure, authenticate, and start a teaching session",
    )
    install = [
        ("$ python3 -m pip install -e packages/shared", BLUE),
        ("$ python3 -m pip install -e packages/sdk", BLUE),
        ("$ export AOEP_BASE_URL=https://learn.example.com", PURPLE),
        ("$ python3 packages/sdk/examples/quickstart.py", GREEN),
        ("", WHITE),
        ("Signed in as: developer@example.com", WHITE),
        ("Lesson: Python foundations", WHITE),
        ("Session: session-7f42", WHITE),
        ("Theodore: We will learn variables and loops.", GOLD),
    ]
    _terminal(draw, (55, 155, 1545, 490), install, "terminal - sanitized example")

    code = [
        ("from aoep_sdk import AOEPClient", PURPLE),
        ("", WHITE),
        ("aoep = AOEPClient()", WHITE),
        ("account = aoep.authenticate(email, password)[\"account\"]", WHITE),
        ("lessons = aoep.orchestrator.list_lessons(language=\"en\")", WHITE),
        ("view = aoep.orchestrator.start_session(", WHITE),
        ("    lessons[0][\"lesson_id\"], student_id=account[\"id\"]", BLUE),
        (")", WHITE),
        (
            "answer = aoep.orchestrator.ask(view[\"session\"][\"session_id\"], "
            "\"What will I learn?\")",
            WHITE,
        ),
    ]
    _terminal(draw, (55, 520, 1545, 880), code, "quickstart.py")
    image.save(OUTPUT / "sdk_quickstart.png", optimize=True)


def render_inprocess() -> None:
    image, draw = _canvas(
        "Embedded AOEP capabilities",
        "Use retrieval and learning engines directly without a network service",
    )
    code = [
        ("from aoep_sdk.inprocess import Document, RagIndex", PURPLE),
        ("", WHITE),
        ("index = RagIndex([", WHITE),
        ("    Document.from_text(", WHITE),
        ("        \"loops\", \"Python loops\",", BLUE),
        ("        \"A for loop repeats work for every item.\"", BLUE),
        ("    ),", WHITE),
        ("    Document.from_text(", WHITE),
        ("        \"functions\", \"Python functions\",", BLUE),
        ("        \"Functions group reusable behavior.\"", BLUE),
        ("    ),", WHITE),
        ("])", WHITE),
        ("", WHITE),
        ("for result in index.retrieve(\"How do I repeat work?\", top_k=2):", WHITE),
        ("    print(result.document.title, result.score)", BLUE),
    ]
    _terminal(draw, (55, 155, 1010, 800), code, "inprocess_rag.py")

    _panel(draw, (1060, 155, 1545, 490), "Deterministic result")
    draw.text((1095, 235), "Python loops", font=HEADING, fill=WHITE)
    draw.text((1095, 280), "relevance score: 0.071", font=MONO, fill=GREEN)
    draw.line((1095, 335, 1505, 335), fill="#374151", width=2)
    draw.text((1095, 370), "No service process", font=BODY, fill=MUTED)
    draw.text((1095, 410), "No network request", font=BODY, fill=MUTED)
    draw.text((1095, 450), "Same shared engine", font=BODY, fill=MUTED)

    _panel(draw, (1060, 530, 1545, 800), "Also available")
    for index, name in enumerate(
        ("AdaptivePolicy", "generate_course", "teach_course", "training_agents")
    ):
        draw.text((1095, 600 + index * 46), name, font=MONO, fill=PURPLE)
    image.save(OUTPUT / "sdk_inprocess_rag.png", optimize=True)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    render_architecture()
    render_quickstart()
    render_inprocess()
    print(f"wrote SDK screenshots to {OUTPUT}")


if __name__ == "__main__":
    main()
