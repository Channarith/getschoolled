"""Subject-aware poster URLs for course cards (Netflix-style browse tiles).

Uses stable Unsplash CDN images keyed by category, title keywords, and format.
No API key required — URLs are deterministic for tests and offline resolution.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence

# Unsplash photo IDs (slug after photo-) — verified HTTP 200 as of 2026-06.
_POSTERS: dict[str, str] = {
    "default": "1503676260728-1c00da094a0b",       # books / learning
    "mathematics": "1532012197267-da84d127e765",   # math notebook
    "science": "1582719471384-894fbb16e074",        # science lab
    "technology": "1516321318423-f06f85e504b3",    # laptop / code
    "languages": "1481627834876-b7833e8f5570",    # books / study
    "history": "1568667256549-094345857637",      # vintage books
    "business": "1522202176988-66273c2fd55f",         # office / teamwork
    "finance": "1554224155-6726b3ff858f",      # charts / finance
    "wellness": "1571019613454-1cb2f99b2d8b",      # fitness / calm
    "cooking": "1556909114-f6e7ad7d3136",          # kitchen
    "geography": "1469474968028-56623f02e42e",        # landscape
    "sports": "1571019613454-1cb2f99b2d8b",        # athletics
    "civics": "1522202176988-66273c2fd55f",       # meeting / civic
    "mindfulness": "1544367567-0f2fcb009e0b",      # meditation
    "arcade": "1611224923853-80b023f02d71",       # gaming
    "audio": "1493225457124-a3eb161ffa5f",        # headphones / music
    "live_class": "1509062522246-3755977927d7",   # classroom
    "ai": "1677442136019-21780ecad995",           # AI / neural
    "python": "1526374965328-7f61d4dc18c5",       # programming
    "fractions": "1554475901-4538ddfbccc2",    # chalkboard / math
    "photosynthesis": "1542601906990-b4d3fb778b09",  # plants / nature
    "english": "1503676260728-1c00da094a0b",      # books / reading
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


def _use_explicit_thumbnail(thumb: Optional[str]) -> bool:
    """Passthrough custom CDN paths only — re-resolve Unsplash (IDs go stale)."""
    if not thumb:
        return False
    s = str(thumb)
    if not s.startswith(("http://", "https://", "/")):
        return False
    if "images.unsplash.com/" in s:
        return False
    return True


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
    if _use_explicit_thumbnail(thumbnail):
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
