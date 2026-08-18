"""Compose a Scene into an animated SVG (data URL + inline HTML)."""

from __future__ import annotations

import html
import re
from base64 import b64encode
from urllib.parse import quote

from .art import BACKDROPS, SPRITE_WIDTH, SPRITES
from .types import Scene

_CAMERAS = {
    "static": "",
    "push-in": "cam-push-in 12s ease-in-out infinite alternate",
    "pull-out": "cam-pull-out 12s ease-in-out infinite alternate",
    "pan-right": "cam-pan-right 14s ease-in-out infinite alternate",
    "pan-left": "cam-pan-left 14s ease-in-out infinite alternate",
    "ken-burns": "cam-ken-burns 16s ease-in-out infinite alternate",
    "zoom-punch": "cam-zoom-punch 0.9s ease-out 1",
    "tilt-up": "cam-tilt-up 10s ease-in-out infinite alternate",
    "dolly-shake": "cam-dolly-shake 0.35s linear infinite",
}

_MOTIONS = {
    "static": "",
    "bob": "bob 2.4s ease-in-out infinite",
    "sway": "sway 3s ease-in-out infinite",
    "walk": "walk-bob 0.55s ease-in-out infinite",
    "drive": "drive-bob 0.9s ease-in-out infinite",
    "cross-right": "cross-right 8s linear infinite",
    "cross-left": "cross-left 8s linear infinite",
    "hop": "hop 1.1s ease-in-out infinite",
    "spin": "spin 4s linear infinite",
    "pulse": "pulse 1.6s ease-in-out infinite",
    "flash": "flash 1.2s steps(2) infinite",
    "approach": "approach 6s ease-in-out infinite alternate",
}


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _sprite_px(kind: str) -> float:
    """SPRITE_WIDTH values are % of the 960-wide stage."""
    return float(SPRITE_WIDTH.get(kind, 12)) / 100.0 * 960.0


def _sized_sprite(kind: str, eid: str) -> str | None:
    art = SPRITES.get(kind)
    if not art:
        return None
    sw = _sprite_px(kind)
    sh = sw * 0.65
    art = re.sub(
        r"<svg\b",
        f'<svg id="{eid}" width="{sw:.1f}" height="{sh:.1f}"',
        art,
        count=1,
    )
    return art


def render_scene_svg(scene: Scene, *, width: int = 960, height: int = 540) -> str:
    """Return a self-contained animated SVG for ``scene``."""
    backdrop = BACKDROPS.get(scene.backdrop, BACKDROPS["intersection"])
    cam = _CAMERAS.get(scene.camera, "")
    cast_parts: list[str] = []
    for i, c in enumerate(scene.cast):
        art = _sized_sprite(c.kind, f"c{i}")
        if not art:
            continue
        sw = _sprite_px(c.kind) * c.scale
        sh = sw * 0.65
        cx = c.x - sw / 2
        cy = c.y - sh / 2
        motion = _MOTIONS.get(c.motion, "")
        delay = f"animation-delay:{c.delay}s;" if c.delay else ""
        flip_attr = ' transform="scale(-1,1)"' if c.flip else ""
        # Keep placement on the OUTER <g> — CSS motion keyframes also set
        # ``transform``, which would wipe an attribute on the same element.
        inner_style = delay
        if motion:
            inner_style += f"animation:{motion};"
        cast_parts.append(
            f'<g transform="translate({cx:.1f},{cy:.1f}) scale({c.scale})">'
            f'<g class="cast" style="{inner_style}"{flip_attr}>{art}</g></g>'
        )

    callouts: list[str] = []
    for i, o in enumerate(scene.objects):
        callouts.append(
            f'<g class="callout" style="animation:callout-pop 0.6s ease-out {0.3 + i * 0.15}s both">'
            f'<rect x="{o.x}" y="{o.y}" width="220" height="36" rx="8" fill="#0f172a" opacity="0.88"/>'
            f'<text x="{o.x + 12}" y="{o.y + 23}" font-family="system-ui,sans-serif" '
            f'font-size="13" font-weight="700" fill="#f8fafc">{_esc(o.label)}</text></g>'
        )

    title = _esc(scene.title)
    caption = _esc(scene.caption)
    cam_style = f"animation:{cam};transform-origin:50% 50%;" if cam else "transform-origin:50% 50%;"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" width="{width}" height="{height}" role="img" aria-label="{title}">
  <defs>
    <style><![CDATA[
      @keyframes cam-push-in {{ from {{ transform: scale(1); }} to {{ transform: scale(1.12); }} }}
      @keyframes cam-pull-out {{ from {{ transform: scale(1.1); }} to {{ transform: scale(1); }} }}
      @keyframes cam-pan-right {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-40px); }} }}
      @keyframes cam-pan-left {{ from {{ transform: translateX(0); }} to {{ transform: translateX(40px); }} }}
      @keyframes cam-ken-burns {{ from {{ transform: scale(1) translate(0,0); }} to {{ transform: scale(1.15) translate(-20px,-10px); }} }}
      @keyframes cam-zoom-punch {{ 0% {{ transform: scale(1); }} 40% {{ transform: scale(1.18); }} 100% {{ transform: scale(1.05); }} }}
      @keyframes cam-tilt-up {{ from {{ transform: translateY(12px); }} to {{ transform: translateY(-8px); }} }}
      @keyframes cam-dolly-shake {{ 0%,100% {{ transform: translate(0,0); }} 25% {{ transform: translate(2px,-1px); }} 75% {{ transform: translate(-2px,1px); }} }}
      @keyframes bob {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-8px); }} }}
      @keyframes sway {{ 0%,100% {{ transform: rotate(-3deg); }} 50% {{ transform: rotate(3deg); }} }}
      @keyframes walk-bob {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-4px); }} }}
      @keyframes drive-bob {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-3px); }} }}
      @keyframes cross-right {{ from {{ transform: translateX(-80px); }} to {{ transform: translateX(80px); }} }}
      @keyframes cross-left {{ from {{ transform: translateX(80px); }} to {{ transform: translateX(-80px); }} }}
      @keyframes hop {{ 0%,100% {{ transform: translateY(0); }} 40% {{ transform: translateY(-18px); }} }}
      @keyframes spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
      @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.55; }} }}
      @keyframes flash {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.2; }} }}
      @keyframes approach {{ from {{ transform: scale(0.85) translateY(20px); }} to {{ transform: scale(1.05) translateY(0); }} }}
      @keyframes callout-pop {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
      @keyframes title-in {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
      .hud {{ font-family: system-ui, sans-serif; }}
    ]]></style>
  </defs>
  <g class="camera" style="{cam_style}">
    {backdrop}
    {"".join(cast_parts)}
    {"".join(callouts)}
  </g>
  <rect x="0" y="0" width="960" height="64" fill="#0f172a" opacity="0.72"/>
  <text class="hud" x="24" y="28" font-size="18" font-weight="800" fill="#f8fafc" style="animation:title-in 0.5s ease-out both">{title}</text>
  <text class="hud" x="24" y="50" font-size="13" fill="#cbd5e1">{caption}</text>
  <rect x="0" y="500" width="960" height="40" fill="#0f172a" opacity="0.65"/>
  <text class="hud" x="24" y="525" font-size="12" fill="#94a3b8">Storyboard · animated scenario</text>
</svg>"""


def scene_data_url(scene: Scene, *, width: int = 960, height: int = 540) -> str:
    svg = render_scene_svg(scene, width=width, height=height)
    return "data:image/svg+xml;utf8," + quote(svg, safe="")


def scene_data_url_b64(scene: Scene, *, width: int = 960, height: int = 540) -> str:
    svg = render_scene_svg(scene, width=width, height=height)
    return "data:image/svg+xml;base64," + b64encode(svg.encode("utf-8")).decode("ascii")


def render_scene_html(scene: Scene, *, width: int = 960, height: int = 540) -> str:
    """Inline HTML wrapper for embedding in Course Studio decks / ClassRoom."""
    svg = render_scene_svg(scene, width=width, height=height)
    audio = ""
    if scene.narration:
        audio = (
            f'<p class="sb-audio-cue" data-audio-cue="{_esc(scene.narration)}">'
            f"🔊 {_esc(scene.narration)}</p>"
        )
    return (
        f'<figure class="cert-storyboard" data-scene="{_esc(scene.scene_id)}" '
        f'style="margin:0;width:100%;max-width:{width}px">'
        f"{svg}{audio}"
        f'<figcaption style="font:12px system-ui;color:#64748b;margin-top:6px">'
        f"{_esc(scene.caption)}</figcaption></figure>"
    )
