"""Topic-matched slide themes, wallpapers, and templates for harvested courses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from ..course_artwork import resolve_course_poster

# Accent colors per subject family (hex) for slide templates.
_ACCENT: Dict[str, str] = {
    "mathematics": "#2563eb",
    "science": "#059669",
    "technology": "#7c3aed",
    "ai": "#6366f1",
    "history": "#b45309",
    "languages": "#db2777",
    "business": "#0d9488",
    "civics": "#1d4ed8",
    "general": "#334155",
}

_TEMPLATE_BY_FMT: Dict[str, str] = {
    "lecture": "title_body",
    "hands_on": "lab",
    "tutorial": "step_by_step",
    "video": "cinema",
    "article": "reader",
}


@dataclass
class SlideTheme:
    poster_url: str
    wallpaper_url: str
    accent_hex: str
    template: str
    font_pair: str = "system"

    def to_dict(self) -> Dict:
        return {
            "poster_url": self.poster_url,
            "wallpaper_url": self.wallpaper_url,
            "accent_hex": self.accent_hex,
            "template": self.template,
            "font_pair": self.font_pair,
        }


def _accent(subject: str, title: str) -> str:
    hay = f"{subject} {title}".lower()
    for key, color in _ACCENT.items():
        if key in hay:
            return color
    if any(k in hay for k in ("math", "algebra", "calculus")):
        return _ACCENT["mathematics"]
    if any(k in hay for k in ("ml", "machine", "neural", "ai")):
        return _ACCENT["ai"]
    return _ACCENT["general"]


def resolve_slide_theme(
    *,
    title: str = "",
    subject: str = "general",
    tags: Optional[Iterable[str]] = None,
    fmt: str = "lecture",
) -> SlideTheme:
    """RAG-friendly theme record: poster + wallpaper + accent + template name."""
    poster = resolve_course_poster(
        title=title,
        subject=subject,
        tags=list(tags or ()),
        format=fmt,
    )
    # Wallpaper = larger crop of same Unsplash asset for slide backgrounds.
    wallpaper = poster.replace("w=480", "w=1920").replace("h=270", "h=1080")
    return SlideTheme(
        poster_url=poster,
        wallpaper_url=wallpaper,
        accent_hex=_accent(subject, title),
        template=_TEMPLATE_BY_FMT.get(fmt, "title_body"),
    )
