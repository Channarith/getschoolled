"""Picture-first Driver Ed slides: a road scene, a real sign, and three short points.

Every Driver Ed slide gets the same treatment from data: the topic picks a
traffic diagram, the bank in ``traffic_signs`` supplies the sign face, and the
slide body is cut down to short points. Narration still carries the full rule;
the scene's accessible label carries it too. Nothing loads from the network.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

from .traffic_signs import SIGN_LESSONS, RoadSign, _shape_markup, sign_for_title
from .types import CourseSlide

ROAD_SCENE_LAYOUT = "road-scene"
ROAD_SCENE_STYLE = "driver-road-scene"
# The course opens on real footage. The permit cartoon is a later lesson, not the start.
OPENING_SLIDE_TITLE = "california driver education"
OPENING_VIDEO_URL = "/api/studio/voice-overlay/drivers-ed-intro.mp4"
MAX_POINTS = 3
_POINT_WORDS = 16
_CONDITION_WORDS = frozenset(
    {"if", "when", "while", "unless", "after", "before", "on", "at", "in", "as", "until", "once", "where"}
)


@dataclass(frozen=True)
class SceneSpec:
    scene_id: str
    label: str
    keywords: tuple[str, ...]
    sign: str | None


# Order breaks ties: a school-bus slide also says "stop", and must stay a bus.
SCENES: tuple[SceneSpec, ...] = (
    SceneSpec("railroad", "Railroad crossing", ("railroad", "rail", "train", "track", "crossbuck", "rxr"), "Railroad crossbuck"),
    SceneSpec("school-bus", "School bus stopped", ("school bus", "bus"), "School bus stop ahead"),
    SceneSpec("work-zone", "Work zone", ("work zone", "road work", "flagger", "detour", "cone", "construction", "lane closed"), "Road work ahead"),
    SceneSpec("crosswalk", "Crosswalk", ("pedestrian", "crosswalk", "wheelchair", "school", "children", "playground", "walk"), "Pedestrian crossing"),
    SceneSpec("signal", "Traffic signal", ("traffic light", "signal light", "red light", "green light", "yellow light", "on red", "signal ahead", "arrow"), "Signal ahead"),
    SceneSpec("freeway", "Freeway lanes", ("freeway", "hov", "carpool", "interstate", "double white", "exit"), "HOV 2 or more"),
    SceneSpec("merge", "Merging traffic", ("merge", "ramp", "lane ends", "added lane"), "Merge"),
    SceneSpec("curve", "Curves and hills", ("curve", "winding", "hill", "grade", "slippery", "bridge", "narrow", "shoulder"), "Curve right"),
    SceneSpec("parking", "Curb and parking", ("parking", "park ", "parked", "curb", "no stopping", "tow", "standing"), "No parking"),
    SceneSpec("following", "Following distance", ("following", "three-second", "3-second", "gap", "tailgat", "space cushion"), None),
    SceneSpec("lanes", "Changing lanes", ("lane change", "blind spot", "mirror", "passing", "keep right", "keep left", "bike", "lane"), "Keep Right"),
    SceneSpec("emergency", "After a crash", ("crash", "collision", "emergency", "ambulance", "siren", "hazard", "fire"), None),
    SceneSpec("cabin", "Inside the car", ("seat belt", "phone", "text", "dui", "alcohol", "bac", "drowsy", "impair", "distract"), None),
    SceneSpec("intersection", "Intersection", ("stop", "yield", "right-of-way", "four-way", "all way", "intersection", "roundabout", "turn", "wrong way", "do not enter", "one way"), "Stop"),
    SceneSpec("speed", "Speed", ("speed", "mph", "limit"), "Speed limit 25"),
    SceneSpec("permit", "Your permit", ("permit", "license", "dmv", "course", "study"), None),
)
_DEFAULT = SceneSpec("road", "On the road", (), None)

_FILLER = re.compile(
    r"decide before you move|name the shape and color|teach the rule in one sentence"
    r"|here are a few friendly examples|^examples?:?$",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s*")


def is_driver_ed(category: Any) -> bool:
    value = getattr(category, "value", category)
    return str(value or "").strip().lower() == "driver_education"


_SIGN_LESSON_SCENES = {
    "ca-dmv-sign-stop-yield": "intersection",
    "ca-dmv-sign-turns": "intersection",
    "ca-dmv-sign-speed-hov": "speed",
    "ca-dmv-sign-merge-curves": "curve",
    "ca-dmv-sign-crossings": "crosswalk",
    "ca-dmv-sign-railroad": "railroad",
    "ca-dmv-sign-work-guide": "work-zone",
}


def _sign_lesson(sign: RoadSign | None) -> str:
    if sign is None:
        return ""
    for lesson in SIGN_LESSONS:
        if sign in lesson.signs:
            return lesson.lesson_id
    return ""


def scene_for(slide: CourseSlide, sign: RoadSign | None = None) -> SceneSpec:
    title = (slide.title or "").lower()
    rest = " ".join(
        part for part in (sign.meaning if sign else "", slide.body or "", slide.slide_key or "") if part
    ).lower()
    lesson_scene = _SIGN_LESSON_SCENES.get(_sign_lesson(sign), "")
    best, best_score = _DEFAULT, 0
    for spec in SCENES:
        score = sum(3 for word in spec.keywords if word in title)
        score += sum(1 for word in spec.keywords if word in rest)
        if spec.scene_id == lesson_scene:
            score += 2
        if score > best_score:
            best, best_score = spec, score
    return best


def _short(sentence: str) -> str:
    text = sentence.strip().rstrip(".").strip()
    if ":" in text:
        head, tail = text.split(":", 1)
        if len(head.split()) <= 5 and len(tail.split()) >= 3:
            text = tail.strip()
    words = text.split()
    if len(words) > _POINT_WORDS:
        # A leading "If…," or "When…," clause is the condition; cutting there
        # would turn the rule into a fragment.
        conditional = words[0].lower() in _CONDITION_WORDS
        for mark in (": ", ", ", "; ", " — ", " - ", " unless ", " because "):
            head = text.split(mark, 1)[0]
            if conditional and mark == ", ":
                continue
            if 4 <= len(head.split()) <= _POINT_WORDS:
                text = head
                break
        else:
            text = " ".join(words[:_POINT_WORDS - 1]) + "…"
    return text[:1].upper() + text[1:] if text else ""


def key_points(slide: CourseSlide, limit: int = MAX_POINTS) -> list[str]:
    body = slide.body or slide.narration or ""
    match = re.search(r"\n\s*Examples?:\s*", body)
    rule, examples = (body[: match.start()], body[match.end():]) if match else (body, "")
    candidates = [part for part in _SENTENCE.split(" ".join(rule.split())) if part.strip()]
    candidates += [_NUMBERED.sub("", line) for line in examples.splitlines() if line.strip()]
    title = (slide.title or "").strip().rstrip(".").lower()
    points: list[str] = []
    for candidate in candidates:
        if _FILLER.search(candidate):
            continue
        short = _short(candidate)
        if not short or short.lower() == title or short in points:
            continue
        points.append(short)
        if len(points) >= limit:
            break
    return points or [_short(slide.title or "Drive safely")]


def _car(x: float, y: float, color: str, angle: float = 0, moving: bool = False) -> str:
    car = (
        f'<g transform="translate({x} {y}) rotate({angle})">'
        f'<rect x="-26" y="-14" width="52" height="28" rx="8" fill="{color}" stroke="#0f172a" stroke-width="2"/>'
        '<rect x="6" y="-10" width="12" height="20" rx="3" fill="#cbd5e1"/>'
        '<rect x="-20" y="-10" width="9" height="20" rx="3" fill="#94a3b8"/>'
        "</g>"
    )
    return f'<g class="dz-move">{car}</g>' if moving else car


def _road_h(y: float, height: float = 150, *, dashed: bool = True, x0: float = 0, x1: float = 620) -> str:
    out = f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="{height}" fill="#475569"/>'
    out += f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="5" fill="#e2e8f0"/>'
    out += f'<rect x="{x0}" y="{y + height - 5}" width="{x1 - x0}" height="5" fill="#e2e8f0"/>'
    if dashed:
        mid = y + height / 2 - 3
        out += f'<line x1="{x0}" y1="{mid + 3}" x2="{x1}" y2="{mid + 3}" stroke="#facc15" stroke-width="5" stroke-dasharray="28 20"/>'
    return out


def _arrow(d: str, color: str = "#22c55e") -> str:
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round" '
        'marker-end="url(#dz-head)"/>'
    )


def _intersection(extra: str = "") -> str:
    return (
        _road_h(130, 160, dashed=False)
        + '<rect x="230" y="0" width="160" height="430" fill="#475569"/>'
        + '<rect x="230" y="130" width="160" height="160" fill="#52606f"/>'
        + '<line x1="225" y1="210" x2="225" y2="285" stroke="#f8fafc" stroke-width="8"/>'
        + '<line x1="395" y1="135" x2="395" y2="210" stroke="#f8fafc" stroke-width="8"/>'
        + '<line x1="235" y1="125" x2="310" y2="125" stroke="#f8fafc" stroke-width="8"/>'
        + '<line x1="310" y1="295" x2="385" y2="295" stroke="#f8fafc" stroke-width="8"/>'
        + _car(185, 250, "#2563eb")
        + _car(440, 170, "#ef4444", 180)
        + _car(270, 85, "#f59e0b", 90)
        + _car(350, 335, "#10b981", -90)
        + extra
    )


def _scene_body(scene_id: str) -> str:
    if scene_id == "intersection":
        return _intersection(_arrow("M190 250 H300 Q310 250 310 230 V150", "#22c55e"))
    if scene_id == "signal":
        light = (
            '<rect x="430" y="20" width="56" height="150" rx="12" fill="#111827"/>'
            '<circle cx="458" cy="52" r="18" fill="#ef4444"/>'
            '<circle cx="458" cy="96" r="18" fill="#57534e"/>'
            '<circle cx="458" cy="140" r="18" fill="#57534e"/>'
        )
        return _intersection(light)
    if scene_id == "lanes":
        return (
            '<rect x="0" y="90" width="620" height="240" fill="#475569"/>'
            '<line x1="0" y1="210" x2="620" y2="210" stroke="#f8fafc" stroke-width="5" stroke-dasharray="30 22"/>'
            '<polygon points="210,270 310,240 310,300" fill="#facc15" opacity=".45"/>'
            + _car(160, 270, "#2563eb", moving=True)
            + _car(350, 270, "#64748b")
            + _car(420, 150, "#ef4444")
            + _arrow("M200 262 C260 262 270 160 340 150")
        )
    if scene_id == "following":
        return (
            _road_h(140, 150)
            + _car(140, 250, "#2563eb", moving=True)
            + _car(470, 250, "#ef4444")
            + '<path d="M180 315 V330 H430 V315" fill="none" stroke="#0f172a" stroke-width="4"/>'
            + '<text x="305" y="365" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700" font-size="30" fill="#0f172a">3 seconds</text>'
        )
    if scene_id == "speed":
        return (
            _road_h(170, 150)
            + _car(150, 285, "#2563eb", moving=True)
            + '<path d="M330 140 A110 110 0 0 1 550 140" fill="none" stroke="#0f172a" stroke-width="14"/>'
            + '<path d="M330 140 A110 110 0 0 1 400 46" fill="none" stroke="#22c55e" stroke-width="14"/>'
            + '<line x1="440" y1="140" x2="395" y2="70" stroke="#ef4444" stroke-width="8" stroke-linecap="round"/>'
            + '<circle cx="440" cy="140" r="12" fill="#0f172a"/>'
        )
    if scene_id == "school-bus":
        return (
            _road_h(120, 200)
            + '<g transform="translate(250 175)"><rect x="-90" y="-36" width="180" height="72" rx="10" fill="#facc15" stroke="#0f172a" stroke-width="3"/>'
            '<rect x="-70" y="-24" width="120" height="22" fill="#1e293b"/>'
            '<circle cx="80" cy="-26" r="8" fill="#ef4444"/><circle cx="80" cy="26" r="8" fill="#ef4444"/>'
            '<polygon points="137.0,11.7 124.7,24.0 107.3,24.0 95.0,11.7 95.0,-5.7 107.3,-18.0 124.7,-18.0 137.0,-5.7" fill="#dc2626" stroke="#fff" stroke-width="2"/><text x="116" y="6" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-weight="800" font-size="9" fill="#fff" textLength="26" lengthAdjust="spacingAndGlyphs">STOP</text></g>'
            + _car(60, 175, "#2563eb")
            + _car(520, 270, "#ef4444", 180)
            + '<line x1="110" y1="140" x2="110" y2="215" stroke="#f8fafc" stroke-width="8"/>'
            + '<line x1="470" y1="225" x2="470" y2="300" stroke="#f8fafc" stroke-width="8"/>'
        )
    if scene_id == "railroad":
        ties = "".join(f'<rect x="{x}" y="196" width="14" height="58" fill="#78350f"/>' for x in range(10, 620, 34))
        return (
            '<rect x="230" y="0" width="160" height="430" fill="#475569"/>'
            + ties
            + '<rect x="0" y="206" width="620" height="7" fill="#9ca3af"/><rect x="0" y="238" width="620" height="7" fill="#9ca3af"/>'
            + '<line x1="235" y1="330" x2="385" y2="330" stroke="#f8fafc" stroke-width="8"/>'
            + _car(310, 380, "#2563eb", -90)
            + '<path d="M410 330 V255" stroke="#0f172a" stroke-width="4" marker-end="url(#dz-head)"/>'
            + '<text x="420" y="300" font-family="Arial, sans-serif" font-weight="700" font-size="26" fill="#0f172a">15 ft</text>'
        )
    if scene_id == "merge":
        return (
            _road_h(110, 150)
            + '<path d="M0 420 L360 260 L470 260 L470 300 L380 300 L60 440 Z" fill="#475569"/>'
            + _car(470, 225, "#ef4444")
            + _car(150, 360, "#2563eb", -24, moving=True)
            + _arrow("M190 340 C260 300 300 270 360 250")
        )
    if scene_id == "curve":
        return (
            '<path d="M-20 400 C200 400 260 120 640 110" fill="none" stroke="#475569" stroke-width="150"/>'
            '<path d="M-20 400 C200 400 260 120 640 110" fill="none" stroke="#facc15" stroke-width="5" stroke-dasharray="28 20"/>'
            + _car(120, 370, "#2563eb", -8, moving=True)
        )
    if scene_id == "crosswalk":
        stripes = "".join(f'<rect x="{x}" y="130" width="22" height="170" fill="#f8fafc"/>' for x in range(300, 440, 36))
        return (
            _road_h(130, 170, dashed=False)
            + stripes
            + '<line x1="270" y1="135" x2="270" y2="295" stroke="#f8fafc" stroke-width="8"/>'
            + '<g transform="translate(370 210)"><circle cx="0" cy="-48" r="14" fill="#0f172a"/>'
            '<path d="M0 -32 V12 M0 -18 L-22 0 M0 -18 L22 -4 M0 12 L-18 46 M0 12 L18 46" stroke="#0f172a" stroke-width="8" stroke-linecap="round"/></g>'
            + _car(200, 250, "#2563eb")
        )
    if scene_id == "parking":
        zones = (("#ef4444", "No stop"), ("#facc15", "Load"), ("#f8fafc", "Pick up"), ("#22c55e", "Limited"), ("#2563eb", "Disabled"))
        curb = "".join(
            f'<rect x="{20 + i * 118}" y="300" width="110" height="16" fill="{color}" stroke="#0f172a"/>'
            f'<text x="{75 + i * 118}" y="350" text-anchor="middle" font-family="Arial, sans-serif" font-size="20" fill="#0f172a">{label}</text>'
            for i, (color, label) in enumerate(zones)
        )
        return _road_h(120, 180) + curb + _car(260, 260, "#2563eb")
    if scene_id == "work-zone":
        cones = "".join(
            f'<polygon points="{x},{y} {x - 12},{y + 34} {x + 12},{y + 34}" fill="#f97316" stroke="#7c2d12" stroke-width="2"/>'
            for x, y in ((240, 260), (300, 240), (360, 220), (420, 205), (480, 205), (540, 205))
        )
        return (
            _road_h(130, 170)
            + cones
            + _car(110, 250, "#2563eb", moving=True)
            + _arrow("M150 245 C210 240 230 180 300 175", "#f97316")
        )
    if scene_id == "freeway":
        return (
            '<rect x="0" y="60" width="620" height="320" fill="#475569"/>'
            + "".join(
                f'<line x1="0" y1="{y}" x2="620" y2="{y}" stroke="#f8fafc" stroke-width="5" stroke-dasharray="30 22"/>'
                for y in (220, 300)
            )
            + '<line x1="0" y1="136" x2="620" y2="136" stroke="#f8fafc" stroke-width="5"/>'
            + '<line x1="0" y1="146" x2="620" y2="146" stroke="#f8fafc" stroke-width="5"/>'
            + '<polygon points="300,82 322,100 300,118 278,100" fill="none" stroke="#f8fafc" stroke-width="5"/>'
            + _car(160, 100, "#22c55e", moving=True)
            + _car(260, 180, "#2563eb")
            + _car(420, 260, "#ef4444")
            + _car(120, 340, "#64748b")
        )
    if scene_id == "emergency":
        return (
            _road_h(130, 170)
            + _car(260, 200, "#2563eb", 20)
            + _car(330, 230, "#ef4444", -30)
            + '<polygon points="500,190 540,260 460,260" fill="none" stroke="#f97316" stroke-width="10" stroke-linejoin="round"/>'
        )
    if scene_id == "cabin":
        return (
            '<rect x="0" y="0" width="620" height="430" fill="#1e293b"/>'
            '<path d="M0 280 Q310 200 620 280 V430 H0 Z" fill="#0f172a"/>'
            '<circle cx="250" cy="330" r="110" fill="none" stroke="#94a3b8" stroke-width="22"/>'
            '<circle cx="250" cy="330" r="22" fill="#94a3b8"/>'
            '<line x1="80" y1="40" x2="200" y2="260" stroke="#ef4444" stroke-width="18" stroke-linecap="round"/>'
            '<rect x="440" y="90" width="80" height="140" rx="12" fill="#e2e8f0" stroke="#0f172a" stroke-width="4"/>'
            '<circle cx="480" cy="160" r="62" fill="none" stroke="#ef4444" stroke-width="10"/>'
            '<line x1="436" y1="116" x2="524" y2="204" stroke="#ef4444" stroke-width="10"/>'
        )
    if scene_id == "permit":
        return (
            _road_h(250, 150)
            + _car(140, 360, "#2563eb", moving=True)
            + '<rect x="230" y="40" width="300" height="180" rx="16" fill="#f8fafc" stroke="#1e3a5f" stroke-width="5"/>'
            '<rect x="252" y="66" width="80" height="100" rx="8" fill="#cbd5e1"/>'
            '<rect x="350" y="72" width="150" height="14" fill="#1e3a5f"/>'
            '<rect x="350" y="102" width="120" height="12" fill="#94a3b8"/>'
            '<rect x="350" y="128" width="140" height="12" fill="#94a3b8"/>'
            '<text x="380" y="200" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700" font-size="24" fill="#1e3a5f">PERMIT</text>'
        )
    return _road_h(140, 160) + _car(150, 255, "#2563eb", moving=True) + _car(460, 185, "#ef4444", 180)


def scene_svg(scene: SceneSpec, sign: RoadSign | None, label: str) -> str:
    sign_part = ""
    if sign is not None:
        sign_part = (
            '<rect x="768" y="300" width="22" height="200" fill="#6b7280"/>'
            f'<g transform="translate(779 190) scale(0.92) translate(-400 -175)">{_shape_markup(sign)}</g>'
        )
    else:
        sign_part = (
            '<circle cx="779" cy="200" r="120" fill="#f8fafc" stroke="#1e3a5f" stroke-width="8"/>'
            f'<text x="779" y="210" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700" font-size="24" fill="#1e3a5f">{html.escape(scene.label.upper()[:18])}</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" preserveAspectRatio="xMidYMid meet" '
        f'role="img" aria-label="{html.escape(label, quote=True)}">'
        f"<title>{html.escape(label)}</title>"
        "<defs>"
        '<marker id="dz-head" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4" markerHeight="4" orient="auto">'
        '<path d="M0 0 L10 5 L0 10 z" fill="context-stroke"/></marker>'
        "<style>.dz-move{animation:dzDrive 5s ease-in-out infinite alternate}"
        "@keyframes dzDrive{from{transform:translateX(0)}to{transform:translateX(40px)}}"
        "@media (prefers-reduced-motion: reduce){.dz-move{animation:none}}</style>"
        "</defs>"
        '<rect width="960" height="540" fill="#dbe7f3"/>'
        '<rect width="620" height="430" fill="#9fc28b"/>'
        f'<g aria-hidden="true">{_scene_body(scene.scene_id)}</g>'
        '<rect x="620" width="340" height="540" fill="#eef4fa"/>'
        f'<g aria-hidden="true">{sign_part}</g>'
        "</svg>"
    )


def _sentence_groups(sentences: list[str], count: int) -> list[list[str]]:
    count = max(1, count)
    if not sentences:
        return [[] for _ in range(count)]
    groups: list[list[str]] = [[] for _ in range(count)]
    for index, sentence in enumerate(sentences):
        groups[min(count - 1, index * count // len(sentences))].append(sentence)
    return groups


def road_scene_timeline(
    slide: CourseSlide,
    base: dict[str, Any],
    sentences: list[str],
) -> dict[str, Any]:
    """Replace a word-led timeline with one persistent scene and a point per section."""
    sign = sign_for_title(slide.title or "")
    scene = scene_for(slide, sign)
    if sign is None and scene.sign:
        sign = sign_for_title(scene.sign)
    points = key_points(slide)
    title = (slide.title or scene.label).strip()
    opening = title.lower() == OPENING_SLIDE_TITLE
    if opening:
        scene = SceneSpec("opening-video", "Driver's Ed", (), None)
        sign = None
    meaning = sign.meaning if sign is not None and sign.name == slide.title else " ".join(points)
    sign_words = f" Sign: {sign.name}." if sign is not None else ""
    label = f"{scene.label} diagram.{sign_words} {title}: {meaning}".strip()
    svg = scene_svg(scene, sign, label)
    spoken = [part.strip() for part in sentences if part and part.strip()]
    duration = float(base.get("duration_s") or 0) or max(4.0, 0.4 * len(" ".join(spoken).split()))
    groups = _sentence_groups(spoken, len(points))
    total_chars = sum(len(part) for part in spoken) or 1
    cues: list[dict[str, Any]] = []
    elapsed = 0
    for index, point in enumerate(points):
        group = groups[index]
        start = round(duration * elapsed / total_chars, 3) if spoken else round(duration * index / len(points), 3)
        elapsed += sum(len(part) for part in group)
        end = round(duration * elapsed / total_chars, 3) if spoken else round(duration * (index + 1) / len(points), 3)
        layers: list[dict[str, Any]] = []
        if index == 0:
            if opening:
                layers.append(
                    {
                        "kind": "video",
                        "url": OPENING_VIDEO_URL,
                        "alt": "Driver's Education starts with the road video.",
                        "text": "opening-video",
                        "z_index": 1,
                        "transition": "fade",
                        "persistent": True,
                    }
                )
            else:
                layers.append(
                    {
                        "kind": "storyboard",
                        "svg": svg,
                        "alt": label,
                        "text": scene.scene_id,
                        "z_index": 1,
                        "transition": "fade",
                        "persistent": True,
                    }
                )
        layers.append(
            {
                "kind": "keypoints",
                "title": title,
                "items": points,
                "active": index,
                "text": point,
                "alt": point,
                "z_index": 3,
                "transition": "fade",
            }
        )
        cues.append(
            {
                "start_s": start,
                "duration_s": max(0.25, round(end - start, 3)) if index < len(points) - 1 else max(0.25, round(duration - start, 3)),
                "transition": "fade",
                "caption": " ".join(group) or point,
                "layers": layers,
            }
        )
    return {
        **base,
        "presentation_style_id": ROAD_SCENE_STYLE,
        "style_label": "",
        "family": "picture",
        "layout": ROAD_SCENE_LAYOUT,
        "duration_s": duration,
        "scene_id": scene.scene_id,
        "sign": sign.name if sign is not None else "",
        "cues": cues,
    }
