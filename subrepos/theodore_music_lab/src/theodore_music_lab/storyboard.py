"""Full-screen storyboard animation for the featured songs.

Each featured song has a hand-authored storyboard: a sequence of scenes, every
scene pinned to a range of lyric lines so the visuals follow the singing. A
scene names one backdrop (layered SVG art built here, no external assets), a
cast of SVG characters with their own motion, and one camera move (push in,
pull out, pan, tilt, Ken Burns, zoom punch, dolly shake).

Scene start/end seconds come from the same syllable-weighted estimator that
drives the karaoke ball (``timing.song_timings``), so a scene cut lands on a
line boundary at any audio duration.

Narration is authored in English and hand-translated into the five curated
languages; other languages fall back to English narration, while the lyric
caption underneath stays translated in all 27 (the player joins scene lines to
the translation it already loaded).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .catalog import Song
from . import timing

CAMERA_MOVES: tuple[str, ...] = (
    "push-in",
    "pull-out",
    "pan-right",
    "pan-left",
    "ken-burns",
    "zoom-punch",
    "tilt-up",
    "dolly-shake",
)

MOTIONS: tuple[str, ...] = (
    "wave",
    "walk",
    "bob",
    "sway",
    "hop",
    "spin",
    "drive",
    "shine",
    "fall",
    "point-up",
    "point-down",
    "turn",
    "float",
    "cross-right",
    "cross-left",
)

# Languages with hand-written narration. Same five as the curated lyric lines.
NARRATION_LANGUAGES: tuple[str, ...] = ("es", "fr", "de", "it", "pt")

# Cameras zoom up to ~1.26x and pan ~3.5%, so the outer tenth of the stage is
# cropped for part of every scene. Cast members live inside this action-safe
# band, which leaves room for a wide sprite's own half-width on top of the zoom.
SAFE_X_MIN = 15.0
SAFE_X_MAX = 82.0

# Motions that deliberately drive a sprite across the frame and out of it.
CROSSING_MOTIONS: frozenset[str] = frozenset({"drive", "cross-right", "cross-left"})


@dataclass(frozen=True)
class Cast:
    """One character or prop placed on the scene, in percent of the frame."""

    kind: str
    x: float
    y: float
    scale: float = 1.0
    motion: str = "bob"
    flip: bool = False
    rot: float = 0.0
    label: str = ""
    delay: float = 0.0


@dataclass(frozen=True)
class Scene:
    scene_id: str
    title: str
    backdrop: str
    camera: str
    start_line: int
    end_line: int
    narration: dict[str, str]
    cast: tuple[Cast, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------
# SVG art: characters and props
# --------------------------------------------------------------------------


def _face(cx: float, cy: float, skin: str) -> str:
    return (
        f'<circle class="head" cx="{cx}" cy="{cy}" r="26" fill="{skin}"/>'
        f'<circle cx="{cx - 9}" cy="{cy - 3}" r="3.4" fill="#1f2937"/>'
        f'<circle cx="{cx + 9}" cy="{cy - 3}" r="3.4" fill="#1f2937"/>'
        f'<path d="M{cx - 9} {cy + 9} Q{cx} {cy + 18} {cx + 9} {cy + 9}" stroke="#1f2937"'
        ' stroke-width="2.6" fill="none" stroke-linecap="round"/>'
        f'<circle cx="{cx - 18}" cy="{cy + 4}" r="4" fill="#f8a1a1" opacity=".7"/>'
        f'<circle cx="{cx + 18}" cy="{cy + 4}" r="4" fill="#f8a1a1" opacity=".7"/>'
    )


def _person(shirt: str, pants: str, hair: str, skin: str = "#f6d3ac", tall: bool = False) -> str:
    top = 18 if tall else 26
    return (
        '<svg viewBox="0 0 120 200" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        f'<ellipse cx="60" cy="192" rx="26" ry="6" fill="#0b1220" opacity=".35"/>'
        f'<rect class="leg-l" x="46" y="{top + 104}" width="13" height="{62 if tall else 54}"'
        f' rx="6" fill="{pants}"/>'
        f'<rect class="leg-r" x="61" y="{top + 104}" width="13" height="{62 if tall else 54}"'
        f' rx="6" fill="{pants}"/>'
        f'<rect class="arm-l" x="25" y="{top + 56}" width="12" height="48" rx="6" fill="{shirt}"/>'
        f'<rect class="arm-r" x="83" y="{top + 56}" width="12" height="48" rx="6" fill="{shirt}"/>'
        f'<rect class="torso" x="39" y="{top + 50}" width="42" height="58" rx="17" fill="{shirt}"/>'
        f'<path d="M34 {top + 4} Q60 {top - 22} 86 {top + 4} Q60 {top + 6} 34 {top + 4} Z"'
        f' fill="{hair}"/>'
        + _face(60, top + 26, skin)
        + "</g></svg>"
    )


def _dog() -> str:
    return (
        '<svg viewBox="0 0 160 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<ellipse cx="80" cy="114" rx="42" ry="5" fill="#0b1220" opacity=".35"/>'
        '<rect class="leg-l" x="46" y="72" width="12" height="36" rx="6" fill="#a16207"/>'
        '<rect class="leg-r" x="94" y="72" width="12" height="36" rx="6" fill="#a16207"/>'
        '<rect x="38" y="46" width="80" height="34" rx="17" fill="#ca8a04"/>'
        '<path class="tail" d="M118 54 Q140 44 134 24" stroke="#ca8a04" stroke-width="9"'
        ' fill="none" stroke-linecap="round"/>'
        '<circle cx="34" cy="44" r="21" fill="#ca8a04"/>'
        '<path d="M18 30 Q10 12 26 20 Z" fill="#a16207"/>'
        '<circle cx="27" cy="41" r="3" fill="#1f2937"/>'
        '<circle cx="16" cy="48" r="4.5" fill="#1f2937"/>'
        "</g></svg>"
    )


def _bus() -> str:
    return (
        '<svg viewBox="0 0 320 180" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<ellipse cx="160" cy="168" rx="120" ry="8" fill="#0b1220" opacity=".35"/>'
        '<rect x="18" y="34" width="284" height="104" rx="22" fill="#facc15"/>'
        '<rect x="18" y="96" width="284" height="18" fill="#f59e0b"/>'
        '<rect x="40" y="50" width="52" height="38" rx="8" fill="#bae6fd"/>'
        '<rect x="104" y="50" width="52" height="38" rx="8" fill="#bae6fd"/>'
        '<rect x="168" y="50" width="52" height="38" rx="8" fill="#bae6fd"/>'
        '<rect class="door" x="236" y="50" width="46" height="82" rx="8" fill="#7dd3fc"'
        ' stroke="#0369a1" stroke-width="3"/>'
        '<circle cx="300" cy="60" r="9" fill="#fef3c7"/>'
        '<circle class="wheel" cx="80" cy="140" r="26" fill="#1f2937"/>'
        '<circle class="wheel" cx="240" cy="140" r="26" fill="#1f2937"/>'
        '<circle cx="80" cy="140" r="9" fill="#cbd5e1"/>'
        '<circle cx="240" cy="140" r="9" fill="#cbd5e1"/>'
        "</g></svg>"
    )


def _car() -> str:
    return (
        '<svg viewBox="0 0 220 130" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<ellipse cx="110" cy="120" rx="86" ry="6" fill="#0b1220" opacity=".35"/>'
        '<path d="M14 92 Q18 58 58 54 L86 30 Q120 22 152 34 L176 56 Q206 62 206 92 Z"'
        ' fill="#ef4444"/>'
        '<path d="M92 36 L146 40 L164 56 L92 56 Z" fill="#bae6fd"/>'
        '<path d="M84 36 L84 56 L48 56 Q58 40 84 36 Z" fill="#bae6fd"/>'
        '<circle class="wheel" cx="62" cy="98" r="20" fill="#1f2937"/>'
        '<circle class="wheel" cx="160" cy="98" r="20" fill="#1f2937"/>'
        '<circle cx="62" cy="98" r="7" fill="#cbd5e1"/>'
        '<circle cx="160" cy="98" r="7" fill="#cbd5e1"/>'
        "</g></svg>"
    )


def _train() -> str:
    return (
        '<svg viewBox="0 0 300 150" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<ellipse cx="150" cy="138" rx="126" ry="6" fill="#0b1220" opacity=".35"/>'
        '<rect x="150" y="46" width="132" height="70" rx="12" fill="#0ea5e9"/>'
        '<rect x="166" y="58" width="34" height="28" rx="6" fill="#e0f2fe"/>'
        '<rect x="212" y="58" width="34" height="28" rx="6" fill="#e0f2fe"/>'
        '<path d="M20 116 L20 62 Q20 42 46 42 L104 42 Q130 42 130 70 L130 116 Z" fill="#1d4ed8"/>'
        '<rect x="40" y="56" width="40" height="30" rx="6" fill="#e0f2fe"/>'
        '<rect x="52" y="14" width="22" height="28" rx="5" fill="#1e293b"/>'
        '<circle class="puff" cx="63" cy="8" r="11" fill="#e2e8f0" opacity=".85"/>'
        '<circle class="wheel" cx="52" cy="122" r="16" fill="#1f2937"/>'
        '<circle class="wheel" cx="104" cy="122" r="16" fill="#1f2937"/>'
        '<circle class="wheel" cx="186" cy="122" r="16" fill="#1f2937"/>'
        '<circle class="wheel" cx="252" cy="122" r="16" fill="#1f2937"/>'
        "</g></svg>"
    )


def _plane() -> str:
    return (
        '<svg viewBox="0 0 260 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<path d="M12 66 Q70 44 196 46 L242 30 L214 66 L242 100 L196 84 Q70 86 12 66 Z"'
        ' fill="#e2e8f0"/>'
        '<path d="M96 52 L130 12 L150 14 L124 54 Z" fill="#38bdf8"/>'
        '<path d="M96 78 L130 112 L150 110 L124 76 Z" fill="#0ea5e9"/>'
        '<circle cx="60" cy="64" r="6" fill="#38bdf8"/>'
        '<circle cx="82" cy="63" r="6" fill="#38bdf8"/>'
        "</g></svg>"
    )


def _sun() -> str:
    rays = "".join(
        f'<rect x="76" y="8" width="8" height="22" rx="4" fill="#fde68a"'
        f' transform="rotate({deg} 80 80)"/>'
        for deg in range(0, 360, 45)
    )
    return (
        '<svg viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f'<g class="figure">{rays}'
        '<circle cx="80" cy="80" r="40" fill="#fbbf24"/>'
        '<circle cx="80" cy="80" r="30" fill="#fde68a" opacity=".7"/>'
        "</g></svg>"
    )


def _cloud() -> str:
    return (
        '<svg viewBox="0 0 220 110" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure" fill="#f8fafc" opacity=".92">'
        '<circle cx="70" cy="62" r="34"/><circle cx="112" cy="46" r="40"/>'
        '<circle cx="156" cy="66" r="30"/><rect x="40" y="62" width="140" height="36" rx="18"/>'
        "</g></svg>"
    )


def _raincloud() -> str:
    drops = "".join(
        f'<path class="drop" d="M{x} 96 q6 12 0 18 q-6-6 0-18 Z" fill="#7dd3fc"'
        f' style="animation-delay:{i * 0.22}s"/>'
        for i, x in enumerate((70, 100, 130, 160))
    )
    return (
        '<svg viewBox="0 0 220 150" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<g fill="#94a3b8"><circle cx="70" cy="58" r="32"/><circle cx="112" cy="42" r="38"/>'
        '<circle cx="154" cy="62" r="28"/><rect x="42" y="58" width="134" height="34" rx="17"/></g>'
        f"{drops}</g></svg>"
    )


def _tree() -> str:
    return (
        '<svg viewBox="0 0 160 220" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<ellipse cx="80" cy="212" rx="34" ry="6" fill="#0b1220" opacity=".35"/>'
        '<rect x="70" y="120" width="20" height="92" rx="8" fill="#78350f"/>'
        '<circle class="crown" cx="80" cy="94" r="52" fill="#16a34a"/>'
        '<circle class="crown" cx="44" cy="118" r="32" fill="#15803d"/>'
        '<circle class="crown" cx="116" cy="118" r="32" fill="#22c55e"/>'
        "</g></svg>"
    )


def _sign(text: str, color: str) -> str:
    return (
        '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<rect x="92" y="70" width="14" height="126" rx="6" fill="#78350f"/>'
        f'<rect x="10" y="24" width="180" height="62" rx="14" fill="{color}"'
        ' stroke="#0f172a" stroke-width="4"/>'
        f'<text x="100" y="65" text-anchor="middle" font-size="34" font-family="Trebuchet MS,'
        f' sans-serif" font-weight="bold" fill="#0f172a">{text}</text>'
        "</g></svg>"
    )


def _arrow() -> str:
    return (
        '<svg viewBox="0 0 140 140" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<path d="M70 12 L118 74 L92 74 L92 128 L48 128 L48 74 L22 74 Z" fill="#38bdf8"'
        ' stroke="#0f172a" stroke-width="4" stroke-linejoin="round"/>'
        "</g></svg>"
    )


def _note() -> str:
    return (
        '<svg viewBox="0 0 140 160" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<rect x="86" y="16" width="10" height="98" rx="5" fill="#f8fafc"/>'
        '<path d="M96 16 Q128 24 124 54 Q106 34 96 46 Z" fill="#f8fafc"/>'
        '<ellipse cx="66" cy="118" rx="28" ry="21" fill="#fbbf24"/>'
        "</g></svg>"
    )


def _cup() -> str:
    return (
        '<svg viewBox="0 0 160 140" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<path class="puff" d="M64 22 q12-14 0-22" stroke="#e2e8f0" stroke-width="6"'
        ' fill="none" stroke-linecap="round"/>'
        '<path d="M26 44 L118 44 L108 108 Q104 122 88 122 L56 122 Q40 122 36 108 Z"'
        ' fill="#f8fafc"/>'
        '<path d="M34 52 L110 52 L106 74 L38 74 Z" fill="#b45309" opacity=".8"/>'
        '<path d="M118 58 q28 4 24 22 q-4 18-26 16" stroke="#f8fafc" stroke-width="9"'
        ' fill="none" stroke-linecap="round"/>'
        '<ellipse cx="72" cy="130" rx="46" ry="6" fill="#0b1220" opacity=".3"/>'
        "</g></svg>"
    )


def _sandwich() -> str:
    return (
        '<svg viewBox="0 0 180 130" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<path d="M20 52 Q90 6 160 52 L160 62 L20 62 Z" fill="#fcd34d"/>'
        '<rect x="20" y="62" width="140" height="12" fill="#16a34a"/>'
        '<rect x="20" y="74" width="140" height="14" fill="#f87171"/>'
        '<path d="M20 88 L160 88 Q150 116 90 116 Q30 116 20 88 Z" fill="#fbbf24"/>'
        "</g></svg>"
    )


def _bag() -> str:
    return (
        '<svg viewBox="0 0 150 170" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<path d="M48 44 q0-28 27-28 q27 0 27 28" stroke="#0f172a" stroke-width="8"'
        ' fill="none"/>'
        '<rect x="20" y="44" width="110" height="106" rx="20" fill="#0ea5e9"/>'
        '<rect x="40" y="86" width="70" height="34" rx="10" fill="#e0f2fe"/>'
        "</g></svg>"
    )


def _ticket() -> str:
    return (
        '<svg viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<g class="figure">'
        '<rect x="12" y="22" width="176" height="76" rx="14" fill="#fef3c7"'
        ' stroke="#b45309" stroke-width="4"/>'
        '<circle cx="118" cy="22" r="9" fill="#0f172a" opacity=".6"/>'
        '<circle cx="118" cy="98" r="9" fill="#0f172a" opacity=".6"/>'
        '<rect x="30" y="44" width="66" height="10" rx="5" fill="#b45309"/>'
        '<rect x="30" y="62" width="46" height="10" rx="5" fill="#d97706"/>'
        '<path d="M140 46 l22 14 l-22 14 Z" fill="#0ea5e9"/>'
        "</g></svg>"
    )


SPRITES: dict[str, str] = {
    "kid-teal": _person("#0d9488", "#1e3a8a", "#3b2417"),
    "kid-red": _person("#e11d48", "#334155", "#111827"),
    "kid-purple": _person("#7c3aed", "#0f172a", "#78350f", skin="#c68642"),
    "grown-up": _person("#0369a1", "#1f2937", "#4b5563", skin="#e0b48c", tall=True),
    "dog": _dog(),
    "bus": _bus(),
    "car": _car(),
    "train": _train(),
    "plane": _plane(),
    "sun": _sun(),
    "cloud": _cloud(),
    "raincloud": _raincloud(),
    "tree": _tree(),
    "sign-bank": _sign("BANK", "#fde68a"),
    "sign-shop": _sign("SHOP", "#bbf7d0"),
    "sign-food": _sign("FOOD", "#fecaca"),
    "sign-hotel": _sign("HOTEL", "#bfdbfe"),
    "arrow": _arrow(),
    "note": _note(),
    "cup": _cup(),
    "sandwich": _sandwich(),
    "bag": _bag(),
    "ticket": _ticket(),
}

# Height of each sprite at scale 1.0, in percent of the frame height. Without
# this a bus and a teacup would be drawn the same size.
SPRITE_HEIGHT_PCT: dict[str, float] = {
    "kid-teal": 30,
    "kid-red": 30,
    "kid-purple": 30,
    "grown-up": 34,
    "dog": 13,
    "bus": 24,
    "car": 15,
    "train": 18,
    "plane": 13,
    "sun": 16,
    "cloud": 12,
    "raincloud": 14,
    "tree": 32,
    "sign-bank": 22,
    "sign-shop": 22,
    "sign-food": 22,
    "sign-hotel": 22,
    "arrow": 14,
    "note": 13,
    "cup": 12,
    "sandwich": 10,
    "bag": 14,
    "ticket": 10,
}


# --------------------------------------------------------------------------
# SVG art: backdrops, composed from reusable layers
# --------------------------------------------------------------------------

_VIEW = 'viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice"'


def _sky(bid: str, top: str, bottom: str) -> str:
    return (
        f'<defs><linearGradient id="{bid}-sky" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>'
        "</linearGradient></defs>"
        f'<rect width="1600" height="900" fill="url(#{bid}-sky)"/>'
    )


def _hills(near: str, far: str) -> str:
    return (
        f'<g class="bg-far"><path d="M0 620 Q260 470 520 610 Q760 470 1040 600'
        f' Q1320 470 1600 590 L1600 900 L0 900 Z" fill="{far}"/></g>'
        f'<g class="bg-mid"><path d="M0 700 Q300 580 640 700 Q980 580 1600 690'
        f' L1600 900 L0 900 Z" fill="{near}"/></g>'
    )


def _buildings(bid: str, base: int, color: str, accent: str) -> str:
    out = [f'<g class="bg-mid" id="{bid}-town">']
    x = -40
    heights = (240, 320, 180, 280, 200, 340, 220, 300, 190, 260)
    for i, h in enumerate(heights):
        w = 150 if i % 2 else 190
        out.append(f'<rect x="{x}" y="{base - h}" width="{w}" height="{h}" rx="10" fill="{color}"/>')
        for row in range(3):
            for col in range(3):
                wx = x + 26 + col * 48
                wy = base - h + 34 + row * 62
                if wy < base - 40:
                    out.append(
                        f'<rect x="{wx}" y="{wy}" width="26" height="34" rx="5"'
                        f' fill="{accent}" opacity=".85"/>'
                    )
        x += w + 24
    out.append("</g>")
    return "".join(out)


def _road(y: int, color: str = "#334155") -> str:
    dashes = "".join(
        f'<rect x="{x}" y="{y + 86}" width="76" height="12" rx="6" fill="#f8fafc" opacity=".8"/>'
        for x in range(20, 1600, 160)
    )
    return (
        f'<g class="bg-near"><rect x="0" y="{y}" width="1600" height="{900 - y}" fill="{color}"/>'
        f'<rect x="0" y="{y}" width="1600" height="14" fill="#94a3b8" opacity=".5"/>'
        f"{dashes}</g>"
    )


def _floor(color: str, y: int = 700, stripe: str = "") -> str:
    stripes = ""
    if stripe:
        stripes = "".join(
            f'<rect x="{x}" y="{y}" width="80" height="{900 - y}" fill="{stripe}" opacity=".35"/>'
            for x in range(0, 1600, 160)
        )
    return (
        f'<g class="bg-near"><rect x="0" y="{y}" width="1600" height="{900 - y}" fill="{color}"/>'
        f"{stripes}</g>"
    )


def _wall(bid: str, top: str, bottom: str, y: int = 700) -> str:
    return (
        f'<defs><linearGradient id="{bid}-wall" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>'
        "</linearGradient></defs>"
        f'<rect width="1600" height="{y}" fill="url(#{bid}-wall)"/>'
    )


def _stars(count: int = 40) -> str:
    out = []
    for i in range(count):
        x = (i * 137) % 1560 + 20
        y = (i * 79) % 420 + 30
        r = 2 + (i % 3)
        out.append(f'<circle class="twinkle" cx="{x}" cy="{y}" r="{r}" fill="#f8fafc"'
                   f' opacity=".8" style="animation-delay:{(i % 7) * 0.4}s"/>')
    return f'<g class="bg-far">{"".join(out)}</g>'


def _stalls(y: int = 560) -> str:
    out = ['<g class="bg-mid">']
    colors = ("#f87171", "#fbbf24", "#34d399", "#60a5fa", "#c084fc")
    for i, color in enumerate(colors):
        x = 60 + i * 310
        out.append(
            f'<rect x="{x}" y="{y}" width="240" height="180" rx="12" fill="#1e293b"/>'
            f'<path d="M{x - 20} {y} L{x + 260} {y} L{x + 236} {y - 60} L{x + 4} {y - 60} Z"'
            f' fill="{color}"/>'
            f'<rect x="{x + 30}" y="{y + 60}" width="180" height="90" rx="10" fill="#0f172a"'
            ' opacity=".55"/>'
        )
    out.append("</g>")
    return "".join(out)


def _lights() -> str:
    beams = "".join(
        f'<path class="beam" d="M{x} 0 L{x - 150} 900 L{x + 150} 900 Z" fill="#f8fafc"'
        f' opacity=".10" style="animation-delay:{i * 0.7}s"/>'
        for i, x in enumerate((260, 640, 1000, 1380))
    )
    curtain = "".join(
        f'<rect x="{x}" y="0" width="70" height="900" fill="#7f1d1d" opacity=".85"/>'
        for x in (0, 90, 1440, 1530)
    )
    return f'<g class="bg-far">{beams}</g><g class="bg-mid">{curtain}</g>'


def _windows_row(y: int, color: str = "#bae6fd") -> str:
    return "".join(
        f'<rect x="{x}" y="{y}" width="150" height="120" rx="16" fill="{color}" opacity=".55"/>'
        for x in range(90, 1500, 260)
    )


def _map_lines() -> str:
    return (
        '<g class="bg-mid" stroke="#38bdf8" stroke-width="10" fill="none" opacity=".8">'
        '<path class="dash" d="M120 760 Q420 520 700 660 Q980 800 1460 420"'
        ' stroke-dasharray="34 26"/>'
        "</g>"
        '<g class="bg-near" fill="#f8fafc">'
        '<circle cx="120" cy="760" r="18"/><circle cx="1460" cy="420" r="18"/>'
        "</g>"
    )


def _backdrops() -> dict[str, str]:
    out: dict[str, str] = {}

    def add(bid: str, body: str) -> None:
        out[bid] = f'<svg {_VIEW} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{body}</svg>'

    add(
        "town-morning",
        _sky("tm", "#7dd3fc", "#fef9c3")
        + _hills("#4ade80", "#86efac")
        + _buildings("tm", 700, "#475569", "#fde68a")
        + _road(700)
        + '<g class="bg-near"><rect x="1180" y="560" width="18" height="150" fill="#64748b"/>'
        '<rect x="1120" y="500" width="140" height="70" rx="10" fill="#0ea5e9"/>'
        '<text x="1190" y="546" text-anchor="middle" font-size="34" font-weight="bold"'
        ' font-family="Trebuchet MS,sans-serif" fill="#f8fafc">BUS</text></g>',
    )
    add(
        "town-street",
        _sky("ts", "#38bdf8", "#e0f2fe")
        + _buildings("ts", 660, "#1e293b", "#93c5fd")
        + _road(660, "#3f3f46"),
    )
    add(
        "town-sunset",
        _sky("tsu", "#fb923c", "#7c2d12")
        + _hills("#7c2d12", "#c2410c")
        + _buildings("tsu", 690, "#27272a", "#fbbf24")
        + _road(690, "#292524"),
    )
    add(
        "park-path",
        _sky("pp", "#60a5fa", "#dbeafe")
        + _hills("#22c55e", "#4ade80")
        + '<g class="bg-near"><path d="M0 900 Q420 700 800 740 Q1180 780 1600 700 L1600 900 Z"'
        ' fill="#d6d3d1"/></g>'
        + _floor("#16a34a", 760),
    )
    add(
        "bus-interior",
        _wall("bi", "#fde68a", "#f59e0b", 720)
        + f'<g class="bg-mid">{_windows_row(140)}</g>'
        + '<g class="bg-mid">'
        + "".join(
            f'<rect x="{x}" y="440" width="200" height="150" rx="18" fill="#0369a1"/>'
            f'<rect x="{x + 16}" y="330" width="168" height="120" rx="16" fill="#0284c7"/>'
            for x in (110, 470, 830, 1190)
        )
        + "</g>"
        + _floor("#44403c", 720, "#57534e"),
    )
    add(
        "city-morning",
        _sky("cm", "#818cf8", "#fbcfe8")
        + _buildings("cm", 700, "#312e81", "#fde68a")
        + '<g class="bg-mid"><rect x="640" y="300" width="320" height="400" rx="18"'
        ' fill="#1e1b4b"/>'
        + _windows_row(340, "#fcd34d")
        + "</g>"
        + _road(700, "#3f3f46"),
    )
    add(
        "street-walk",
        _sky("sw", "#22d3ee", "#ecfeff")
        + _buildings("sw", 640, "#334155", "#a5f3fc")
        + '<g class="bg-near"><rect x="0" y="640" width="1600" height="60" fill="#94a3b8"/></g>'
        + _road(700, "#3f3f46"),
    )
    add(
        "market-row",
        _sky("mr", "#fbbf24", "#fef3c7")
        + _buildings("mr", 560, "#78350f", "#fed7aa")
        + _stalls(560)
        + _floor("#a8a29e", 740, "#d6d3d1"),
    )
    add(
        "airport-hall",
        _wall("ah", "#e0f2fe", "#93c5fd", 700)
        + f'<g class="bg-far">{_windows_row(120, "#0ea5e9")}</g>'
        + '<g class="bg-mid"><rect x="80" y="420" width="1440" height="30" rx="15"'
        ' fill="#1e293b" opacity=".7"/>'
        '<rect x="560" y="250" width="480" height="130" rx="14" fill="#0f172a"/>'
        '<text x="800" y="336" text-anchor="middle" font-size="66" font-weight="bold"'
        ' font-family="Trebuchet MS,sans-serif" fill="#4ade80">GATE 7</text></g>'
        + _floor("#cbd5e1", 700, "#e2e8f0"),
    )
    add(
        "cafe-table",
        _wall("ct", "#7c2d12", "#b45309", 680)
        + '<g class="bg-mid">'
        + "".join(
            f'<rect x="{x}" y="180" width="120" height="160" rx="12" fill="#fcd34d"'
            ' opacity=".35"/>'
            for x in (140, 400, 1100, 1360)
        )
        + '<rect x="520" y="140" width="560" height="220" rx="18" fill="#0f172a" opacity=".5"/>'
        '<text x="800" y="270" text-anchor="middle" font-size="72" font-weight="bold"'
        ' font-family="Trebuchet MS,sans-serif" fill="#fde68a">MENU</text></g>'
        + '<g class="bg-near"><rect x="0" y="680" width="1600" height="70" fill="#fef3c7"/>'
        '<rect x="0" y="750" width="1600" height="150" fill="#78350f"/></g>',
    )
    add(
        "sunrise-hill",
        _sky("sh", "#f472b6", "#fde68a")
        + '<g class="bg-far"><circle cx="1180" cy="420" r="150" fill="#fbbf24" opacity=".55"/></g>'
        + _hills("#15803d", "#22c55e")
        + _floor("#166534", 780),
    )
    add(
        "arrows-room",
        _wall("ar", "#312e81", "#1e1b4b", 720)
        + _stars(28)
        + '<g class="bg-mid" stroke="#38bdf8" stroke-width="6" opacity=".45" fill="none">'
        + "".join(f'<path d="M{x} 120 L{x} 700"/>' for x in range(160, 1600, 240))
        + "".join(f'<path d="M60 {y} L1540 {y}"/>' for y in range(200, 700, 160))
        + "</g>"
        + _floor("#0f172a", 720, "#1e293b"),
    )
    add(
        "stage-lights",
        _wall("sl", "#1e1b4b", "#0f172a", 760)
        + _lights()
        + '<g class="bg-mid">'
        + "".join(
            f'<circle class="twinkle" cx="{x}" cy="90" r="26" fill="#fde68a"'
            f' style="animation-delay:{i * 0.5}s"/>'
            for i, x in enumerate(range(260, 1500, 240))
        )
        + "</g>"
        + _floor("#7c2d12", 760, "#9a3412"),
    )
    add(
        "classroom-floor",
        _wall("cf", "#bae6fd", "#7dd3fc", 700)
        + '<g class="bg-mid"><rect x="200" y="150" width="1200" height="400" rx="20"'
        ' fill="#14532d" stroke="#78350f" stroke-width="18"/>'
        '<text x="800" y="400" text-anchor="middle" font-size="130" font-weight="bold"'
        ' font-family="Trebuchet MS,sans-serif" fill="#f8fafc" opacity=".9">'
        "up down left right</text></g>"
        + _floor("#a16207", 700, "#ca8a04"),
    )
    add(
        "near-far-map",
        _sky("nf", "#0f172a", "#1e3a8a")
        + _stars(46)
        + _map_lines()
        + _hills("#1e293b", "#334155"),
    )
    return out


BACKDROPS: dict[str, str] = _backdrops()


# --------------------------------------------------------------------------
# The storyboards
# --------------------------------------------------------------------------


def _n(en: str, es: str, fr: str, de: str, it: str, pt: str) -> dict[str, str]:
    return {"en": en, "es": es, "fr": fr, "de": de, "it": it, "pt": pt}


_WHEELS: tuple[Scene, ...] = (
    Scene(
        scene_id="wheels-1",
        title="Two friends at the bus stop",
        backdrop="town-morning",
        camera="push-in",
        start_line=1,
        end_line=4,
        narration=_n(
            "Two friends meet at the bus stop and say hello in the morning sun.",
            "Dos amigos se encuentran en la parada del autobús y se saludan bajo el sol de la mañana.",
            "Deux amis se retrouvent à l'arrêt de bus et se disent bonjour au soleil du matin.",
            "Zwei Freunde treffen sich an der Bushaltestelle und begrüßen sich in der Morgensonne.",
            "Due amici si incontrano alla fermata dell'autobus e si salutano al sole del mattino.",
            "Dois amigos se encontram na parada de ônibus e se cumprimentam ao sol da manhã.",
        ),
        cast=(
            Cast(kind="sun", x=86, y=14, scale=0.7, motion="shine"),
            Cast(kind="cloud", x=22, y=16, scale=0.8, motion="float"),
            Cast(kind="raincloud", x=62, y=22, scale=0.7, motion="fall", delay=0.5),
            Cast(kind="kid-teal", x=30, y=74, scale=1.0, motion="wave", label="Ana"),
            Cast(kind="kid-red", x=44, y=74, scale=0.95, motion="hop", flip=True, label="Ben"),
            Cast(kind="car", x=72, y=80, scale=0.8, motion="cross-right", delay=1.2),
        ),
    ),
    Scene(
        scene_id="wheels-2",
        title="The bus rolls through town",
        backdrop="town-street",
        camera="pan-right",
        start_line=5,
        end_line=8,
        narration=_n(
            "The bus drives through town. Its wheels go round and round and the door opens and shuts.",
            "El autobús cruza la ciudad. Sus ruedas giran y giran y la puerta se abre y se cierra.",
            "Le bus traverse la ville. Ses roues tournent et tournent et la porte s'ouvre et se ferme.",
            "Der Bus fährt durch die Stadt. Seine Räder drehen sich und die Tür öffnet und schließt sich.",
            "L'autobus attraversa la città. Le sue ruote girano e girano e la porta si apre e si chiude.",
            "O ônibus atravessa a cidade. Suas rodas giram e giram e a porta abre e fecha.",
        ),
        cast=(
            Cast(kind="bus", x=44, y=72, scale=1.5, motion="drive"),
            Cast(kind="tree", x=88, y=68, scale=0.7, motion="sway"),
            Cast(kind="tree", x=8, y=70, scale=0.6, motion="sway", delay=0.6),
        ),
    ),
    Scene(
        scene_id="wheels-3",
        title="Holding hands to the park",
        backdrop="park-path",
        camera="pull-out",
        start_line=9,
        end_line=12,
        narration=_n(
            "They ride to the park and walk hand in hand, fast and fast and slow.",
            "Van al parque y caminan de la mano, rápido, rápido y despacio.",
            "Ils vont au parc et marchent main dans la main, vite, vite et lentement.",
            "Sie fahren zum Park und gehen Hand in Hand, schnell, schnell und langsam.",
            "Vanno al parco e camminano mano nella mano, veloce, veloce e piano.",
            "Eles vão ao parque e andam de mãos dadas, rápido, rápido e devagar.",
        ),
        cast=(
            Cast(kind="grown-up", x=34, y=76, scale=1.1, motion="walk", label="Mum"),
            Cast(kind="kid-purple", x=45, y=78, scale=0.85, motion="walk", label="Mia"),
            Cast(kind="dog", x=58, y=84, scale=0.7, motion="hop"),
            Cast(kind="tree", x=80, y=64, scale=0.9, motion="sway"),
        ),
    ),
    Scene(
        scene_id="wheels-4",
        title="Round and round again",
        backdrop="town-street",
        camera="zoom-punch",
        start_line=13,
        end_line=16,
        narration=_n(
            "Everyone sings the chorus again while the wheels keep turning through the town.",
            "Todos cantan el estribillo otra vez mientras las ruedas siguen girando por la ciudad.",
            "Tout le monde chante le refrain encore une fois pendant que les roues tournent dans la ville.",
            "Alle singen den Refrain noch einmal, während die Räder weiter durch die Stadt rollen.",
            "Tutti cantano di nuovo il refrain mentre le ruote continuano a girare per la città.",
            "Todos cantam o refrão de novo enquanto as rodas continuam girando pela cidade.",
        ),
        cast=(
            Cast(kind="bus", x=52, y=70, scale=1.7, motion="spin"),
            Cast(kind="note", x=20, y=32, scale=0.5, motion="float"),
            Cast(kind="note", x=80, y=26, scale=0.4, motion="float", delay=0.8),
        ),
    ),
    Scene(
        scene_id="wheels-5",
        title="Inside the bus",
        backdrop="bus-interior",
        camera="dolly-shake",
        start_line=17,
        end_line=20,
        narration=_n(
            "Inside the bus people stand up and sit down, waving high and low while the horn beeps.",
            "Dentro del autobús la gente se levanta y se sienta, saludando arriba y abajo mientras suena la bocina.",
            "Dans le bus, les gens se lèvent et s'assoient, saluant en haut et en bas pendant que le klaxon sonne.",
            "Im Bus stehen die Leute auf und setzen sich, winken hoch und tief, während die Hupe tutet.",
            "Dentro l'autobus la gente si alza e si siede, salutando in alto e in basso mentre suona il clacson.",
            "Dentro do ônibus as pessoas levantam e sentam, acenando alto e baixo enquanto a buzina toca.",
        ),
        cast=(
            Cast(kind="kid-red", x=24, y=70, scale=1.0, motion="wave"),
            Cast(kind="kid-teal", x=48, y=72, scale=1.05, motion="hop"),
            Cast(kind="grown-up", x=72, y=68, scale=1.1, motion="wave", flip=True),
        ),
    ),
    Scene(
        scene_id="wheels-6",
        title="Off into the sunset",
        backdrop="town-sunset",
        camera="ken-burns",
        start_line=21,
        end_line=24,
        narration=_n(
            "The last chorus rolls by and the bus drives off into the evening light.",
            "Suena el último estribillo y el autobús se va con la luz de la tarde.",
            "Le dernier refrain passe et le bus s'en va dans la lumière du soir.",
            "Der letzte Refrain klingt und der Bus fährt ins Abendlicht davon.",
            "Arriva l'ultimo refrain e l'autobus parte nella luce della sera.",
            "Chega o último refrão e o ônibus vai embora na luz da tarde.",
        ),
        cast=(
            Cast(kind="bus", x=30, y=74, scale=1.3, motion="cross-right"),
            Cast(kind="kid-teal", x=76, y=76, scale=0.95, motion="wave"),
            Cast(kind="kid-red", x=86, y=76, scale=0.9, motion="wave", flip=True, delay=0.4),
        ),
    ),
)


_TRAVEL: tuple[Scene, ...] = (
    Scene(
        scene_id="travel-1",
        title="Off to work and school",
        backdrop="city-morning",
        camera="push-in",
        start_line=1,
        end_line=8,
        narration=_n(
            "The day starts in the city: work, school, the bank and the office.",
            "El día empieza en la ciudad: el trabajo, la escuela, el banco y la oficina.",
            "La journée commence en ville : le travail, l'école, la banque et le bureau.",
            "Der Tag beginnt in der Stadt: Arbeit, Schule, Bank und Büro.",
            "La giornata inizia in città: lavoro, scuola, banca e ufficio.",
            "O dia começa na cidade: trabalho, escola, banco e escritório.",
        ),
        cast=(
            Cast(kind="grown-up", x=28, y=76, scale=1.1, motion="walk", label="Sam"),
            Cast(kind="kid-teal", x=40, y=78, scale=0.85, motion="walk"),
            Cast(kind="sign-bank", x=72, y=62, scale=0.9, motion="bob"),
            Cast(kind="car", x=90, y=82, scale=0.7, motion="cross-left", delay=1.0),
        ),
    ),
    Scene(
        scene_id="travel-2",
        title="Walk to the store, walk to the bus",
        backdrop="street-walk",
        camera="pan-right",
        start_line=9,
        end_line=12,
        narration=_n(
            "We walk to the store, walk to the bus, pack a bag and bring a friend.",
            "Caminamos a la tienda, caminamos al autobús, hacemos la maleta y traemos a un amigo.",
            "Nous marchons au magasin, marchons au bus, préparons un sac et amenons un ami.",
            "Wir gehen zum Laden, gehen zum Bus, packen eine Tasche und nehmen einen Freund mit.",
            "Camminiamo al negozio, camminiamo all'autobus, prepariamo una borsa e portiamo un amico.",
            "Caminhamos até a loja, caminhamos até o ônibus, arrumamos a bolsa e trazemos um amigo.",
        ),
        cast=(
            Cast(kind="kid-purple", x=26, y=76, scale=1.0, motion="walk"),
            Cast(kind="bag", x=38, y=72, scale=0.5, motion="bob"),
            Cast(kind="sign-shop", x=64, y=60, scale=0.85, motion="bob"),
            Cast(kind="bus", x=88, y=76, scale=1.0, motion="drive"),
        ),
    ),
    Scene(
        scene_id="travel-3",
        title="Bank, supermarket, restaurant",
        backdrop="market-row",
        camera="ken-burns",
        start_line=13,
        end_line=20,
        narration=_n(
            "The chorus names the places we use every day, and the food we ask for politely.",
            "El estribillo nombra los lugares que usamos cada día y la comida que pedimos con amabilidad.",
            "Le refrain nomme les lieux que nous utilisons chaque jour et la nourriture que nous demandons poliment.",
            "Der Refrain nennt die Orte, die wir jeden Tag nutzen, und das Essen, das wir höflich bestellen.",
            "Il refrain nomina i luoghi che usiamo ogni giorno e il cibo che chiediamo con gentilezza.",
            "O refrão nomeia os lugares que usamos todos os dias e a comida que pedimos com educação.",
        ),
        cast=(
            Cast(kind="sign-bank", x=16, y=58, scale=0.8, motion="bob"),
            Cast(kind="sign-shop", x=42, y=56, scale=0.8, motion="bob", delay=0.4),
            Cast(kind="sign-food", x=68, y=58, scale=0.8, motion="bob", delay=0.8),
            Cast(kind="kid-red", x=88, y=78, scale=0.95, motion="wave"),
        ),
    ),
    Scene(
        scene_id="travel-4",
        title="Ticket, map and the airport",
        backdrop="airport-hall",
        camera="tilt-up",
        start_line=21,
        end_line=28,
        narration=_n(
            "At the airport we need a ticket and a map, we wait in line, then the hotel feels fine.",
            "En el aeropuerto necesitamos un billete y un mapa, esperamos en la fila y luego el hotel se siente bien.",
            "À l'aéroport, il faut un billet et une carte, on attend dans la file, puis l'hôtel est agréable.",
            "Am Flughafen brauchen wir ein Ticket und eine Karte, wir warten in der Schlange, dann ist das Hotel angenehm.",
            "All'aeroporto servono un biglietto e una mappa, aspettiamo in fila, poi l'hotel è piacevole.",
            "No aeroporto precisamos de um bilhete e um mapa, esperamos na fila e depois o hotel é agradável.",
        ),
        cast=(
            Cast(kind="ticket", x=24, y=52, scale=0.7, motion="float"),
            Cast(kind="grown-up", x=42, y=76, scale=1.05, motion="walk"),
            Cast(kind="kid-teal", x=54, y=78, scale=0.8, motion="walk", delay=0.3),
            Cast(kind="plane", x=80, y=26, scale=1.0, motion="cross-right"),
            Cast(kind="sign-hotel", x=88, y=64, scale=0.75, motion="bob"),
        ),
    ),
    Scene(
        scene_id="travel-5",
        title="Back on the street",
        backdrop="street-walk",
        camera="pull-out",
        start_line=29,
        end_line=32,
        narration=_n(
            "The walking verse comes back, so we practise the same words a second time.",
            "Vuelve la estrofa de caminar, así practicamos las mismas palabras una segunda vez.",
            "Le couplet de la marche revient, alors nous répétons les mêmes mots une deuxième fois.",
            "Die Geh-Strophe kommt zurück, so üben wir die gleichen Wörter ein zweites Mal.",
            "Torna la strofa del camminare, così ripetiamo le stesse parole una seconda volta.",
            "A estrofe de caminhar volta, então praticamos as mesmas palavras uma segunda vez.",
        ),
        cast=(
            Cast(kind="kid-purple", x=30, y=76, scale=1.0, motion="walk"),
            Cast(kind="kid-red", x=44, y=76, scale=0.95, motion="walk", delay=0.4),
            Cast(kind="bus", x=84, y=76, scale=1.0, motion="drive"),
        ),
    ),
    Scene(
        scene_id="travel-6",
        title="Market chorus",
        backdrop="market-row",
        camera="zoom-punch",
        start_line=33,
        end_line=40,
        narration=_n(
            "The market chorus returns louder, with please and thank you in every stall.",
            "El estribillo del mercado vuelve más fuerte, con por favor y gracias en cada puesto.",
            "Le refrain du marché revient plus fort, avec s'il vous plaît et merci à chaque étal.",
            "Der Marktrefrain kommt lauter zurück, mit bitte und danke an jedem Stand.",
            "Il refrain del mercato torna più forte, con per favore e grazie a ogni bancarella.",
            "O refrão do mercado volta mais forte, com por favor e obrigado em cada banca.",
        ),
        cast=(
            Cast(kind="kid-teal", x=22, y=78, scale=1.0, motion="hop"),
            Cast(kind="sandwich", x=48, y=54, scale=0.6, motion="float"),
            Cast(kind="sign-food", x=72, y=58, scale=0.85, motion="bob"),
            Cast(kind="note", x=88, y=30, scale=0.45, motion="float", delay=0.6),
        ),
    ),
    Scene(
        scene_id="travel-7",
        title="One sandwich, please",
        backdrop="cafe-table",
        camera="push-in",
        start_line=41,
        end_line=44,
        narration=_n(
            "At the cafe we order a sandwich and a cup of tea, then ask the price and ask for help.",
            "En el café pedimos un sándwich y una taza de té, luego preguntamos el precio y pedimos ayuda.",
            "Au café, nous commandons un sandwich et une tasse de thé, puis demandons le prix et de l'aide.",
            "Im Café bestellen wir ein Sandwich und eine Tasse Tee, dann fragen wir den Preis und um Hilfe.",
            "Al bar ordiniamo un panino e una tazza di tè, poi chiediamo il prezzo e chiediamo aiuto.",
            "No café pedimos um sanduíche e uma taça de chá, depois perguntamos o preço e pedimos ajuda.",
        ),
        cast=(
            Cast(kind="sandwich", x=32, y=70, scale=0.8, motion="bob"),
            Cast(kind="cup", x=52, y=70, scale=0.8, motion="bob", delay=0.4),
            Cast(kind="kid-red", x=74, y=74, scale=1.05, motion="wave"),
        ),
    ),
    Scene(
        scene_id="travel-8",
        title="Travel words, one more time",
        backdrop="market-row",
        camera="pull-out",
        start_line=45,
        end_line=52,
        narration=_n(
            "The last chorus puts every travel word together, and now we know them too.",
            "El último estribillo junta todas las palabras de viaje, y ahora también las conocemos.",
            "Le dernier refrain réunit tous les mots de voyage, et maintenant nous les connaissons aussi.",
            "Der letzte Refrain bringt alle Reisewörter zusammen, und jetzt kennen wir sie auch.",
            "L'ultimo refrain unisce tutte le parole del viaggio, e adesso le conosciamo anche noi.",
            "O último refrão junta todas as palavras de viagem, e agora nós também as conhecemos.",
        ),
        cast=(
            Cast(kind="kid-teal", x=26, y=78, scale=1.0, motion="wave"),
            Cast(kind="kid-purple", x=42, y=78, scale=0.95, motion="hop", delay=0.3),
            Cast(kind="kid-red", x=58, y=78, scale=0.95, motion="wave", flip=True, delay=0.6),
            Cast(kind="note", x=80, y=28, scale=0.5, motion="float"),
        ),
    ),
)


_WORDS: tuple[Scene, ...] = (
    Scene(
        scene_id="words-1",
        title="Morning song on the hill",
        backdrop="sunrise-hill",
        camera="push-in",
        start_line=1,
        end_line=4,
        narration=_n(
            "Morning on the hill: the sun is shining and everyone can sing along.",
            "Mañana en la colina: el sol brilla y todos pueden cantar juntos.",
            "Le matin sur la colline : le soleil brille et tout le monde peut chanter avec nous.",
            "Morgen auf dem Hügel: die Sonne scheint und alle können mitsingen.",
            "Mattina sulla collina: il sole brilla e tutti possono cantare insieme.",
            "Manhã na colina: o sol brilha e todos podem cantar juntos.",
        ),
        cast=(
            Cast(kind="sun", x=80, y=20, scale=0.9, motion="shine"),
            Cast(kind="kid-teal", x=34, y=74, scale=1.05, motion="wave", label="Lea"),
            Cast(kind="note", x=54, y=40, scale=0.45, motion="float"),
            Cast(kind="tree", x=14, y=66, scale=0.8, motion="sway"),
        ),
    ),
    Scene(
        scene_id="words-2",
        title="Up, down, left, right",
        backdrop="arrows-room",
        camera="pan-right",
        start_line=5,
        end_line=8,
        narration=_n(
            "Four arrows teach the directions: up, down, left and right, slowly.",
            "Cuatro flechas enseñan las direcciones: arriba, abajo, izquierda y derecha, despacio.",
            "Quatre flèches enseignent les directions : en haut, en bas, à gauche et à droite, lentement.",
            "Vier Pfeile zeigen die Richtungen: oben, unten, links und rechts, langsam.",
            "Quattro frecce insegnano le direzioni: su, giù, sinistra e destra, lentamente.",
            "Quatro setas ensinam as direções: para cima, para baixo, esquerda e direita, devagar.",
        ),
        cast=(
            Cast(kind="arrow", x=30, y=34, scale=0.6, motion="bob", rot=0),
            Cast(kind="arrow", x=30, y=66, scale=0.6, motion="bob", rot=180, delay=0.3),
            Cast(kind="arrow", x=64, y=50, scale=0.6, motion="bob", rot=270, delay=0.6),
            Cast(kind="arrow", x=80, y=50, scale=0.6, motion="bob", rot=90, delay=0.9),
            Cast(kind="kid-purple", x=48, y=76, scale=1.0, motion="point-up"),
        ),
    ),
    Scene(
        scene_id="words-3",
        title="Say it soft, say it loud",
        backdrop="stage-lights",
        camera="zoom-punch",
        start_line=9,
        end_line=15,
        narration=_n(
            "On the stage the chorus is sung soft and then loud, round and round.",
            "En el escenario el estribillo se canta suave y luego fuerte, dando vueltas y vueltas.",
            "Sur la scène, le refrain se chante doucement puis fort, en tournant encore et encore.",
            "Auf der Bühne wird der Refrain leise und dann laut gesungen, immer rundherum.",
            "Sul palco il refrain si canta piano e poi forte, girando e girando.",
            "No palco o refrão é cantado baixinho e depois alto, girando e girando.",
        ),
        cast=(
            Cast(kind="kid-teal", x=30, y=76, scale=1.1, motion="hop"),
            Cast(kind="kid-red", x=50, y=76, scale=1.1, motion="wave", delay=0.3),
            Cast(kind="kid-purple", x=70, y=76, scale=1.1, motion="turn", delay=0.6),
            Cast(kind="note", x=18, y=30, scale=0.5, motion="float"),
            Cast(kind="note", x=84, y=24, scale=0.4, motion="float", delay=0.7),
        ),
    ),
    Scene(
        scene_id="words-4",
        title="One hand, two feet",
        backdrop="classroom-floor",
        camera="ken-burns",
        start_line=16,
        end_line=19,
        narration=_n(
            "One hand points, two feet walk, we turn around, smile and ask for more.",
            "Una mano señala, dos pies caminan, damos la vuelta, sonreímos y pedimos más.",
            "Une main pointe, deux pieds marchent, on se retourne, on sourit et on en demande plus.",
            "Eine Hand zeigt, zwei Füße gehen, wir drehen uns um, lächeln und bitten um mehr.",
            "Una mano indica, due piedi camminano, ci giriamo, sorridiamo e chiediamo ancora.",
            "Uma mão aponta, dois pés caminham, nos viramos, sorrimos e pedimos mais.",
        ),
        cast=(
            Cast(kind="kid-red", x=34, y=76, scale=1.1, motion="point-up"),
            Cast(kind="kid-teal", x=56, y=76, scale=1.05, motion="walk", delay=0.4),
            Cast(kind="kid-purple", x=76, y=76, scale=1.0, motion="turn", delay=0.8),
        ),
    ),
    Scene(
        scene_id="words-5",
        title="Directions again",
        backdrop="arrows-room",
        camera="pull-out",
        start_line=20,
        end_line=23,
        narration=_n(
            "The direction verse returns so the four words settle in.",
            "Vuelve la estrofa de las direcciones para que las cuatro palabras se queden.",
            "Le couplet des directions revient pour que les quatre mots restent en mémoire.",
            "Die Richtungsstrophe kommt zurück, damit die vier Wörter sitzen.",
            "Torna la strofa delle direzioni così le quattro parole si fissano.",
            "A estrofe das direções volta para que as quatro palavras fiquem na memória.",
        ),
        cast=(
            Cast(kind="arrow", x=26, y=40, scale=0.55, motion="bob", rot=0),
            Cast(kind="arrow", x=44, y=62, scale=0.55, motion="bob", rot=180, delay=0.3),
            Cast(kind="arrow", x=62, y=40, scale=0.55, motion="bob", rot=270, delay=0.6),
            Cast(kind="arrow", x=80, y=62, scale=0.55, motion="bob", rot=90, delay=0.9),
            Cast(kind="kid-teal", x=14, y=78, scale=0.95, motion="point-down"),
        ),
    ),
    Scene(
        scene_id="words-6",
        title="Chorus under the lights",
        backdrop="stage-lights",
        camera="pan-left",
        start_line=24,
        end_line=30,
        narration=_n(
            "The whole class sings the chorus together under the stage lights.",
            "Toda la clase canta el estribillo junta bajo las luces del escenario.",
            "Toute la classe chante le refrain ensemble sous les lumières de la scène.",
            "Die ganze Klasse singt den Refrain gemeinsam unter den Bühnenlichtern.",
            "Tutta la classe canta il refrain insieme sotto le luci del palco.",
            "Toda a turma canta o refrão junta sob as luzes do palco.",
        ),
        cast=(
            Cast(kind="kid-purple", x=24, y=76, scale=1.05, motion="hop"),
            Cast(kind="kid-teal", x=42, y=76, scale=1.1, motion="wave", delay=0.2),
            Cast(kind="kid-red", x=60, y=76, scale=1.05, motion="hop", delay=0.5),
            Cast(kind="grown-up", x=80, y=74, scale=1.1, motion="wave", flip=True, delay=0.8),
        ),
    ),
    Scene(
        scene_id="words-7",
        title="Near and far",
        backdrop="near-far-map",
        camera="tilt-up",
        start_line=31,
        end_line=34,
        narration=_n(
            "This way, that way: words can take us near and far across the map.",
            "Por aquí, por allá: las palabras pueden llevarnos cerca y lejos por el mapa.",
            "Par ici, par là : les mots peuvent nous emmener près et loin sur la carte.",
            "Hier hin, dort hin: Wörter können uns nah und fern über die Karte tragen.",
            "Da questa parte, da quella: le parole possono portarci vicino e lontano sulla mappa.",
            "Por aqui, por ali: as palavras podem nos levar perto e longe pelo mapa.",
        ),
        cast=(
            Cast(kind="plane", x=44, y=36, scale=0.9, motion="cross-right"),
            Cast(kind="kid-teal", x=18, y=78, scale=0.95, motion="wave"),
            Cast(kind="kid-red", x=84, y=72, scale=0.9, motion="wave", flip=True, delay=0.5),
        ),
    ),
    Scene(
        scene_id="words-8",
        title="Round and round we go",
        backdrop="stage-lights",
        camera="pull-out",
        start_line=35,
        end_line=41,
        narration=_n(
            "The final chorus turns round and round, and the whole song is learned.",
            "El estribillo final da vueltas y vueltas, y la canción entera queda aprendida.",
            "Le refrain final tourne encore et encore, et toute la chanson est apprise.",
            "Der letzte Refrain dreht sich immer weiter, und das ganze Lied ist gelernt.",
            "Il refrain finale gira e gira, e tutta la canzone è imparata.",
            "O refrão final gira e gira, e toda a canção fica aprendida.",
        ),
        cast=(
            Cast(kind="kid-teal", x=28, y=76, scale=1.05, motion="turn"),
            Cast(kind="kid-red", x=46, y=76, scale=1.05, motion="turn", delay=0.3),
            Cast(kind="kid-purple", x=64, y=76, scale=1.05, motion="turn", delay=0.6),
            Cast(kind="note", x=82, y=30, scale=0.5, motion="float"),
            Cast(kind="note", x=16, y=26, scale=0.4, motion="float", delay=0.6),
        ),
    ),
)


STORYBOARDS: dict[str, tuple[Scene, ...]] = {
    "en-wheels-bus-audio-v1": _WHEELS,
    "en-travel-words-audio-v1": _TRAVEL,
    "en-words-this-way-audio-v1": _WORDS,
}


def safe_x(x: float) -> float:
    """Pull a cast member inside the frame the camera never crops.

    A push-in or ken-burns move zooms about the centre, so anything authored at
    the very edge slides out of shot exactly when the camera closes in. Film
    crews solve this with a title-safe area; SAFE_X_MIN/MAX is ours.
    """
    return round(min(SAFE_X_MAX, max(SAFE_X_MIN, float(x))), 2)


def has_storyboard(song_id: str) -> bool:
    return song_id in STORYBOARDS


def scene_count(song_id: str) -> int:
    return len(STORYBOARDS.get(song_id, ()))


def narration_for(scene: Scene, language: str) -> tuple[str, str]:
    """Return (text, language_actually_used) for a scene's narration."""
    text = scene.narration.get(language)
    if text:
        return text, language
    return scene.narration["en"], "en"


def storyboard_for(
    song: Song,
    *,
    language: str = "en",
    duration_sec: float | None = None,
) -> dict[str, Any]:
    """Resolve a song's storyboard into timed scenes plus the art they need."""
    scenes = STORYBOARDS.get(song.song_id, ())
    timings = timing.song_timings(song, duration_sec=duration_sec)
    rows = {row["line_no"]: row for row in timings["lines"]}
    out_scenes: list[dict[str, Any]] = []
    used_backdrops: dict[str, str] = {}
    used_sprites: dict[str, str] = {}
    for index, scene in enumerate(scenes):
        first = rows.get(scene.start_line)
        last = rows.get(scene.end_line)
        if not first or not last:
            continue
        text, narration_language = narration_for(scene, language)
        used_backdrops[scene.backdrop] = BACKDROPS[scene.backdrop]
        for member in scene.cast:
            used_sprites[member.kind] = SPRITES[member.kind]
        out_scenes.append(
            {
                "scene_id": scene.scene_id,
                "index": index,
                "title": scene.title,
                "backdrop": scene.backdrop,
                "camera": scene.camera,
                "start_line": scene.start_line,
                "end_line": scene.end_line,
                "start": round(float(first["start"]), 3),
                "end": round(float(last["end"]), 3),
                "duration": round(float(last["end"]) - float(first["start"]), 3),
                "narration": text,
                "narration_en": scene.narration["en"],
                "narration_language": narration_language,
                "narration_tier": "curated" if narration_language == language else "english",
                "line_numbers": list(range(scene.start_line, scene.end_line + 1)),
                "cast": [
                    {
                        **asdict(member),
                        "x": safe_x(member.x),
                        "height_pct": SPRITE_HEIGHT_PCT.get(member.kind, 20),
                    }
                    for member in scene.cast
                ],
            }
        )
    return {
        "song_id": song.song_id,
        "title": song.title_en,
        "language": language,
        "scene_count": len(out_scenes),
        "duration_sec": timings["duration_sec"],
        "narration_languages": ["en", *NARRATION_LANGUAGES],
        "cameras": sorted({row["camera"] for row in out_scenes}),
        "backdrops": used_backdrops,
        "sprites": used_sprites,
        "scenes": out_scenes,
    }


def scene_at(board: dict[str, Any], position_sec: float) -> dict[str, Any] | None:
    """Scene covering ``position_sec`` (clamped to the first/last scene)."""
    scenes = board.get("scenes") or []
    if not scenes:
        return None
    for row in scenes:
        if row["start"] <= position_sec < row["end"]:
            return row
    return scenes[0] if position_sec < scenes[0]["start"] else scenes[-1]
