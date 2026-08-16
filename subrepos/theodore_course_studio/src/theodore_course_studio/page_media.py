"""Offline SVG still pictures and animated motion cards for studio slides.

Shared by early-learning and certification-prep so every picture-led page works
without network media downloads. The "video" asset is an animated SVG motion
card that pairs with Theodore's narration.
"""

from __future__ import annotations

import html
import urllib.parse


def svg_data_url(
    *,
    title: str,
    symbol: str,
    color: str,
    animated: bool = False,
    bounce_px: int = 18,
    bounce_dur_s: float = 2.0,
) -> str:
    """Build a self-contained SVG data URL (still or looping motion)."""
    safe_title = html.escape((title or "")[:34])
    safe_symbol = html.escape((symbol or "?")[:24])
    safe_color = html.escape(color or "#2563eb")
    bounce = max(8, min(28, int(bounce_px)))
    dur = max(1.2, min(3.5, float(bounce_dur_s)))
    motion = (
        f"""
        <animateTransform attributeName="transform" type="translate"
          values="0 0;0 -{bounce};0 0" dur="{dur}s" repeatCount="indefinite"/>
        """
        if animated
        else ""
    )
    sparkles = (
        """
        <circle cx="80" cy="70" r="8" fill="#fff" opacity=".75">
          <animate attributeName="opacity" values=".2;1;.2" dur="1.4s"
            repeatCount="indefinite"/>
        </circle>
        <circle cx="720" cy="130" r="12" fill="#fff" opacity=".6">
          <animate attributeName="r" values="6;15;6" dur="1.8s"
            repeatCount="indefinite"/>
        </circle>
        <circle cx="100" cy="360" r="7" fill="#fff" opacity=".45">
          <animate attributeName="opacity" values=".15;.9;.15" dur="2.2s"
            repeatCount="indefinite"/>
        </circle>
        """
        if animated
        else ""
    )
    accent = (
        """
        <rect x="175" y="65" width="450" height="250" rx="36" fill="none"
          stroke="#38bdf8" stroke-width="6" opacity=".55">
          <animate attributeName="opacity" values=".25;.85;.25" dur="2.4s"
            repeatCount="indefinite"/>
        </rect>
        """
        if animated
        else ""
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450"
      viewBox="0 0 800 450" role="img" aria-label="{safe_title}">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="{safe_color}"/>
          <stop offset="1" stop-color="#172554"/>
        </linearGradient>
      </defs>
      <rect width="800" height="450" rx="32" fill="url(#bg)"/>
      {sparkles}
      <g transform="translate(0 0)">
        {motion}
        <rect x="175" y="65" width="450" height="250" rx="36"
          fill="#fff" opacity=".96"/>
        {accent}
        <text x="400" y="225" text-anchor="middle" font-family="Arial,sans-serif"
          font-size="108" font-weight="700" fill="#172554">{safe_symbol}</text>
      </g>
      <text x="400" y="382" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="42" font-weight="700" fill="#fff">{safe_title}</text>
    </svg>"""
    return "data:image/svg+xml," + urllib.parse.quote(svg, safe="")


def picture_data_url(*, title: str, symbol: str, color: str) -> str:
    return svg_data_url(title=title, symbol=symbol, color=color, animated=False)


def motion_data_url(
    *,
    title: str,
    symbol: str,
    color: str,
    bounce_px: int = 18,
    bounce_dur_s: float = 2.0,
) -> str:
    return svg_data_url(
        title=title,
        symbol=symbol,
        color=color,
        animated=True,
        bounce_px=bounce_px,
        bounce_dur_s=bounce_dur_s,
    )
