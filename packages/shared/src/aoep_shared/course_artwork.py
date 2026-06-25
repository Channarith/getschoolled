"""Subject-aware poster URLs for course cards (Netflix-style browse tiles).

Uses stable Unsplash CDN images keyed by category, title keywords, and format.
No API key required — URLs are deterministic for tests and offline resolution.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence

# Unsplash photo IDs (slug after photo-) — curated for education subjects.
_POSTERS: dict[str, str] = {
    "default": "1524995997473-0922192e7427",       # library / learning
    "mathematics": "1596495577885-7b0216313667",   # equations / math
    "science": "1532094349784-aa2b07712477",        # microscope / lab
    "technology": "1517694712202-8f3797902a10",    # laptop / code
    "languages": "1524995997473-0922192e7427",    # books / study
    "history": "1539650116574-8a991d6ac6d0",      # museum / artifacts
    "business": "1542744173-8c3279b9b0a8",         # office / teamwork
    "finance": "1611974789855-9c98a0f44d0a",      # charts / finance
    "wellness": "1506126613408-07c158377075",      # yoga / calm
    "cooking": "1556910103-1c02745aae4d",          # kitchen
    "geography": "1526778544-fe3699e2b0c0",        # globe / travel
    "sports": "1461896836934-ffe607f8210a",        # athletics
    "civics": "1577412647305-5365e4eee1d5",       # government / civic
    "mindfulness": "1544367567-0f2fcb009e0b",      # meditation
    "arcade": "1511512578047-dfb632b44527",       # gaming
    "audio": "1478737270239-5880992794b7",        # headphones
    "live_class": "1588196749598-0e4a0a5a9843",   # video classroom
    "ai": "1677442136019-21780ecad995",           # AI / neural
    "python": "1526374965328-7f61d4dc18c5",       # programming
    "fractions": "1635072833038-7c9468ee2294",    # math workbook
    "photosynthesis": "1416879595882-ce2fa732bc2c",  # plants / nature
    "english": "1456514295660-8ba4a0869efa",      # books / reading
    "spanish": "1481627834876-b7833e8f5570",       # language study
}

# (needle in haystack, poster key) — checked in order; first match wins.
_TITLE_RULES: Sequence[tuple[str, str]] = (
    ("photosynthesis", "photosynthesis"),
    ("fraction", "fractions"),
    ("python", "python"),
    ("ai fluency", "ai"),
    ("artificial intelligence", "ai"),
    ("machine learning", "ai"),
    ("english", "english"),
    ("spanish", "spanish"),
    ("french", "languages"),
    ("german", "languages"),
    ("japanese", "languages"),
    ("algebra", "mathematics"),
    ("calculus", "mathematics"),
    ("geometry", "mathematics"),
    ("chemistry", "science"),
    ("biology", "science"),
    ("physics", "science"),
    ("history", "history"),
    ("finance", "finance"),
    ("invest", "finance"),
    ("wellness", "wellness"),
    ("meditat", "mindfulness"),
    ("cook", "cooking"),
    ("geograph", "geography"),
    ("civic", "civics"),
    ("business", "business"),
    ("sport", "sports"),
)


def _unsplash_url(photo_id: str, *, width: int = 480, height: int = 270) -> str:
    return (
        f"https://images.unsplash.com/photo-{photo_id}"
        f"?w={width}&h={height}&fit=crop&q=80&auto=format"
    )


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _category_key(category: str, subject: str) -> str:
    blob = _norm(f"{category} {subject}")
    for key in (
        "mathematics", "math", "science", "technology", "language", "history",
        "business", "finance", "wellness", "cooking", "geography", "sport",
        "civic", "mindful",
    ):
        if key in blob:
            if key == "math":
                return "mathematics"
            if key == "language":
                return "languages"
            if key == "sport":
                return "sports"
            if key == "mindful":
                return "mindfulness"
            if key == "civic":
                return "civics"
            return key if key != "math" else "mathematics"
    return ""


def resolve_course_poster(
    *,
    title: str = "",
    category: str = "",
    subject: str = "",
    tags: Iterable[str] | None = None,
    format: str = "",
    thumbnail: Optional[str] = None,
) -> str:
    """Return a poster image URL for a course card."""
    if thumbnail and str(thumbnail).startswith(("http://", "https://", "/")):
        return str(thumbnail)

    hay = _norm(" ".join([title, category, subject, " ".join(tags or [])]))
    for needle, key in _TITLE_RULES:
        if needle in hay:
            return _unsplash_url(_POSTERS[key])

    cat_key = _category_key(category, subject)
    if cat_key and cat_key in _POSTERS:
        return _unsplash_url(_POSTERS[cat_key])

    fmt = _norm(format)
    if fmt == "audio":
        return _unsplash_url(_POSTERS["audio"])
    if fmt in ("live_class", "interactive"):
        return _unsplash_url(_POSTERS["live_class"])
    if fmt == "game":
        return _unsplash_url(_POSTERS["arcade"])

    return _unsplash_url(_POSTERS["default"])


def resolve_course_poster_from_mapping(item: Mapping[str, object]) -> str:
    """Convenience wrapper for catalog / learnable dicts."""
    tags_raw = item.get("tags")
    tags: Sequence[str] = tags_raw if isinstance(tags_raw, (list, tuple)) else ()
    thumb = item.get("thumbnail")
    return resolve_course_poster(
        title=str(item.get("title") or ""),
        category=str(item.get("category") or ""),
        subject=str(item.get("subject") or ""),
        tags=tags,
        format=str(item.get("format") or item.get("media_format") or ""),
        thumbnail=str(thumb) if thumb else None,
    )
