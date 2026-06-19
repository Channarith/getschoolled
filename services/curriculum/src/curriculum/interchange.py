"""Content interchange / export (acquisition-ready, "Netflix-compatible").

Exports the course catalog into standards-based, widely-ingestible formats so a
large streamer / acquirer / CDN can onboard the library:
- a JSON content feed (titles + rich metadata + streaming manifest refs), and
- an MRSS (Media RSS) XML feed (media:content/title/description/thumbnail/rating).

The schema maps cleanly onto streaming-partner content specs (title, synopsis,
genres, language, audio + subtitle tracks, maturity rating, runtime, artwork, and
HLS/DASH manifests). Pure/offline-testable.
"""

from __future__ import annotations

from typing import Dict, List
from xml.sax.saxutils import escape

FEED_VERSION = "1.0"


def course_to_entry(c) -> Dict:
    """Normalize a Course into a portable content-feed entry."""
    cat = getattr(c, "category", "") or c.subject
    audio = [c.audio_language or c.language]
    return {
        "id": c.course_id,
        "type": "course",
        "title": c.title,
        "synopsis": c.preview or c.description,
        "genres": [cat, *([t for t in c.tags] if c.tags else [])],
        "language": c.language,
        "audioLanguages": audio,
        "subtitleLanguages": list(c.subtitle_languages),
        "maturityRating": c.maturity_rating,
        "level": c.level,
        "runtimeSeconds": int(c.duration_min) * 60,
        "handsOn": bool(c.hands_on),
        "artwork": c.thumbnail,
        "trailer": c.trailer_url,
        "media": {"hls": c.hls_url, "dash": c.dash_url},
        "accessTier": c.access_tier,
        "deliveryMode": c.delivery_mode.value,
        "provenance": {"validationStatus": c.validation_status,
                       "humanOfRecord": c.human_of_record},
    }


def catalog_json_feed(courses: List) -> Dict:
    return {
        "feedVersion": FEED_VERSION,
        "provider": "AOEP",
        "titleCount": len(courses),
        "titles": [course_to_entry(c) for c in courses],
    }


def _tag(name: str, value, *, ns: str = "") -> str:
    if value in (None, "", []):
        return ""
    return f"<{ns}{name}>{escape(str(value))}</{ns}{name}>"


def catalog_mrss(courses: List, *, channel_title: str = "AOEP Course Catalog") -> str:
    """Render an MRSS (Media RSS) XML feed - broadly ingestible by video platforms."""
    items: List[str] = []
    for c in courses:
        e = course_to_entry(c)
        media = e["media"]
        url = media.get("hls") or media.get("dash") or e.get("trailer") or ""
        parts = [
            _tag("title", e["title"]),
            _tag("description", e["synopsis"]),
            _tag("guid", e["id"]),
            _tag("category", e["genres"][0] if e["genres"] else ""),
            _tag("rating", e["maturityRating"], ns="media:"),
        ]
        if url:
            fmt = "application/x-mpegURL" if media.get("hls") else "application/dash+xml"
            parts.append(f'<media:content url="{escape(url)}" type="{fmt}" '
                         f'duration="{e["runtimeSeconds"]}" lang="{escape(e["language"])}"/>')
        if e["artwork"]:
            parts.append(f'<media:thumbnail url="{escape(str(e["artwork"]))}"/>')
        for sub in e["subtitleLanguages"]:
            parts.append(f'<media:subTitle type="application/ttml+xml" lang="{escape(sub)}"/>')
        items.append("<item>" + "".join(p for p in parts if p) + "</item>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">'
        f"<channel><title>{escape(channel_title)}</title>"
        f"<generator>AOEP/{FEED_VERSION}</generator>"
        + "".join(items)
        + "</channel></rss>"
    )
