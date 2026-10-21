"""Short lesson clips for the video modality.

A clip is either a playable reference the platform already knows how to store
(YouTube id or another allowed online URL: start, end, title, source url) or a
deterministic SVG title card written locally. This module never downloads
media files.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import parse_qs, quote, urlparse

_MIN_SEC = 15
_MAX_SEC = 60
_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIMEO_ID = re.compile(r"^\d{6,12}$")
_CLOCK = re.compile(r"(\d+)([hms])")


def clamp_clip_seconds(seconds: object, *, default: int = 30) -> int:
    """Keep a requested clip inside the short-lesson window (15–60 seconds)."""
    try:
        value = int(seconds)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        value = default
    if value < _MIN_SEC:
        return _MIN_SEC
    if value > _MAX_SEC:
        return _MAX_SEC
    return value


def svg_data_url(svg: str) -> str:
    """Browser-playable URL for an SVG document. No file is required."""
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


def build_lesson_clips(
    *,
    topic: str,
    language: str = "en",
    duration_sec: int = 30,
    source_url: str = "",
    references: Optional[Iterable[dict]] = None,
    out_dir: Optional[str | Path] = None,
    repo_root: Optional[str | Path] = None,
) -> dict:
    """Select or create one short clip list for a lesson topic.

    Remote YouTube / Vimeo references stay metadata. When none is playable in
    a browser, a generated title-card SVG is included and ``trailer_url``
    points at it (data URL, or a ``/lesson-clips/...`` path when the file is
    written under a web ``public`` directory). An on-disk harvest demo that
    matches the topic is appended as an extra reference and is not copied.
    """
    duration = clamp_clip_seconds(duration_sec)
    title = (topic or "").strip() or "Lesson"
    lang = (language or "en").strip() or "en"
    remote = _select_remote(
        topic=title,
        language=lang,
        duration=duration,
        source_url=source_url,
        references=references,
    )
    clips: list[dict] = []
    if remote is not None:
        clips.append(remote)
    else:
        demo = _select_demo(title, repo_root, duration)
        generated = _generate_clip(title, lang, duration, out_dir)
        if demo is not None:
            clips.append(demo)
            if not _browser_url(demo):
                clips.insert(0, generated)
        else:
            clips.append(generated)
    trailer = ""
    for clip in clips:
        trailer = _browser_url(clip)
        if trailer:
            break
    return {
        "topic": title,
        "language": lang,
        "media_format": "video",
        "trailer_url": trailer,
        "clips": clips,
    }


def apply_lesson_clips(payload: dict, built: dict) -> dict:
    """Point a course or generated-lesson dict at ``built`` clips.

    Sets ``trailer_url`` and ``media_format``, and the first slide that does
    not already have ``media_url``. Does not download anything.
    """
    updated = dict(payload or {})
    trailer = str(built.get("trailer_url") or "")
    if trailer:
        updated["trailer_url"] = trailer
    updated["media_format"] = "video"
    slides = updated.get("slides")
    if isinstance(slides, list):
        copied = [dict(slide) if isinstance(slide, dict) else slide for slide in slides]
        url = trailer
        if not url and built.get("clips"):
            url = str(built["clips"][0].get("how") or "")
        for slide in copied:
            if isinstance(slide, dict) and not str(slide.get("media_url") or "").strip():
                slide["media_url"] = url
                slide["media_kind"] = "video"
                break
        updated["slides"] = copied
    return updated


def _browser_url(clip: dict) -> str:
    how = str(clip.get("how") or "")
    if how.startswith(("https://", "http://", "/", "data:")):
        return how
    svg = str((clip.get("play") or {}).get("svg") or "")
    if svg:
        return svg_data_url(svg)
    return ""


def _clip(
    source: str,
    title: str,
    duration: int,
    *,
    kind: str,
    url: str,
    video_id: str = "",
    start_sec: int = 0,
    end_sec: int = 0,
    source_url: str = "",
    embed_url: str = "",
    path: str = "",
    svg: str = "",
    reused: bool = False,
) -> dict:
    play = {
        "kind": kind,
        "reused": reused,
        "video_id": video_id,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "source_url": source_url,
        "embed_url": embed_url,
        "url": url,
        "path": path,
        "svg": svg,
    }
    return {
        "source": source,
        "title": title,
        "duration": duration,
        "how": url,
        "play": play,
    }


def _select_remote(
    *,
    topic: str,
    language: str,
    duration: int,
    source_url: str,
    references: Optional[Iterable[dict]],
) -> Optional[dict]:
    direct = _reference_from_url(source_url, title=topic, duration=duration)
    if direct is not None:
        return direct
    primary = language.split("-")[0].lower()
    for item in references or []:
        if not isinstance(item, dict):
            continue
        item_lang = str(item.get("language") or "")
        if item_lang and item_lang.split("-")[0].lower() != primary:
            continue
        keys = item.get("topics") or item.get("keywords") or []
        item_title = str(item.get("title") or topic)
        if not _keyword_hit(topic, keys, item_title):
            continue
        url = str(item.get("url") or item.get("source_url") or "")
        clip = _reference_from_url(
            url,
            title=item_title,
            duration=duration,
            start_sec=_optional_int(item.get("start_sec")),
            end_sec=_optional_int(item.get("end_sec")),
        )
        if clip is not None:
            return clip
    return _from_music_packs(topic, language, duration)


def _from_music_packs(topic: str, language: str, duration: int) -> Optional[dict]:
    try:
        from aoep_shared.content_packs import load_records
    except Exception:
        return None
    primary = language.split("-")[0].lower()
    try:
        records = load_records("music_videos")
    except Exception:
        return None
    for rec in records:
        if str(rec.get("language") or "").split("-")[0].lower() != primary:
            continue
        title = str(rec.get("title_en") or rec.get("title") or topic)
        if not _keyword_hit(topic, [], title):
            continue
        for key in ("media_url", "source_url"):
            clip = _reference_from_url(str(rec.get(key) or ""), title=title, duration=duration)
            if clip is not None:
                return clip
    return None


def _select_demo(topic: str, repo_root: Optional[str | Path], duration: int) -> Optional[dict]:
    if repo_root is None:
        return None
    from aoep_shared.harvest.media import pick_demo_video

    root = Path(repo_root)
    rel = pick_demo_video(subject=topic, title=topic, repo_root=root)
    if not rel or "platform_walkthrough" in rel.replace("\\", "/"):
        return None
    path = root / rel
    if not path.is_file():
        return None
    posix = Path(rel).as_posix()
    return _clip(
        "generated",
        topic,
        duration,
        kind="file",
        url=posix,
        start_sec=0,
        end_sec=duration,
        source_url=posix,
        path=str(path),
        reused=True,
    )


def _reference_from_url(
    url: str,
    *,
    title: str,
    duration: int,
    start_sec: Optional[int] = None,
    end_sec: Optional[int] = None,
) -> Optional[dict]:
    raw = (url or "").strip()
    if not raw:
        return None
    if _YT_ID.match(raw):
        raw = f"https://www.youtube.com/watch?v={raw}"
    from aoep_shared.cosyvoice_ingest.urls import is_allowed_media_url

    if not is_allowed_media_url(raw):
        return None
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    qs = parse_qs(parsed.query)
    start = start_sec if start_sec is not None else _start_from_url(parsed, qs)
    end = end_sec if end_sec is not None else _optional_seconds(qs.get("end", [""])[0])
    start, end = _window(start or 0, duration, end)
    span = end - start
    if "youtube" in host or host == "youtu.be":
        video_id = _youtube_id(parsed)
        if not video_id:
            return None
        source = f"https://www.youtube.com/watch?v={video_id}&t={start}"
        embed = (
            f"https://www.youtube.com/embed/{video_id}"
            f"?start={start}&end={end}&rel=0"
        )
        return _clip(
            "youtube",
            title,
            span,
            kind="embed",
            url=embed,
            video_id=video_id,
            start_sec=start,
            end_sec=end,
            source_url=source,
            embed_url=embed,
        )
    video_id = _vimeo_id(parsed)
    if not video_id:
        return None
    source = f"https://vimeo.com/{video_id}"
    embed = f"https://player.vimeo.com/video/{video_id}#t={start}s"
    return _clip(
        "online",
        title,
        span,
        kind="embed",
        url=embed,
        video_id=video_id,
        start_sec=start,
        end_sec=end,
        source_url=source,
        embed_url=embed,
    )


def _generate_clip(topic: str, language: str, duration: int, out_dir: Optional[str | Path]) -> dict:
    svg = render_title_card(topic, language, duration)
    url = svg_data_url(svg)
    path = ""
    if out_dir is not None:
        dest = Path(out_dir)
        dest.mkdir(parents=True, exist_ok=True)
        file_path = dest / f"{_slug(topic)}-{_slug(language)}.svg"
        file_path.write_text(svg, encoding="utf-8")
        path = str(file_path)
        public = _public_url(file_path)
        if public:
            url = public
    return _clip(
        "generated",
        topic,
        duration,
        kind="svg",
        url=url,
        start_sec=0,
        end_sec=duration,
        source_url="",
        path=path,
        svg=svg,
    )


def render_title_card(topic: str, language: str, duration_sec: int) -> str:
    """Deterministic animated SVG: a title plus a few moving shapes."""
    duration = clamp_clip_seconds(duration_sec)
    label = (topic or "Lesson").strip() or "Lesson"
    if len(label) > 48:
        label = label[:45].rstrip() + "..."
    lang = (language or "en").strip() or "en"
    digest = hashlib.sha256(f"{label}|{lang}|{duration}".encode("utf-8")).digest()

    def color(index: int) -> str:
        red = 36 + digest[index] % 190
        green = 36 + digest[index + 1] % 190
        blue = 36 + digest[index + 2] % 190
        return f"#{red:02x}{green:02x}{blue:02x}"

    dur = f"{duration}s"
    safe_title = _xml(label)
    safe_lang = _xml(lang)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" '
        'width="640" height="360" role="img">'
        f"<title>{safe_title}</title>"
        f'<rect width="640" height="360" fill="{color(0)}"/>'
        f'<circle cx="90" cy="180" r="34" fill="{color(3)}">'
        f'<animate attributeName="cx" values="90;540;90" dur="{dur}" '
        'repeatCount="indefinite"/>'
        f'<animate attributeName="cy" values="180;70;180" dur="{dur}" '
        'repeatCount="indefinite"/>'
        "</circle>"
        f'<rect x="250" y="48" width="42" height="42" fill="{color(6)}">'
        f'<animate attributeName="y" values="48;250;48" dur="{dur}" '
        'repeatCount="indefinite"/>'
        "</rect>"
        f'<circle cx="500" cy="90" r="18" fill="{color(9)}">'
        f'<animate attributeName="r" values="14;36;14" dur="{dur}" '
        'repeatCount="indefinite"/>'
        "</circle>"
        '<text x="320" y="176" text-anchor="middle" fill="#f8fafc" '
        'font-size="32" font-family="Georgia, serif">'
        f"{safe_title}</text>"
        '<text x="320" y="208" text-anchor="middle" fill="#e2e8f0" '
        'font-size="16" font-family="Georgia, serif">'
        f"{safe_lang} · {duration}s</text>"
        "</svg>"
    )


def _public_url(path: Path) -> str:
    parts = path.resolve().parts
    if "public" not in parts:
        return ""
    idx = len(parts) - 1 - list(reversed(parts)).index("public")
    rel = "/".join(parts[idx + 1 :])
    if not rel:
        return ""
    return "/" + rel


def _window(start: int, duration: int, end: Optional[int]) -> tuple[int, int]:
    start = max(0, int(start))
    if end is None or end <= start:
        end = start + duration
    if end - start < _MIN_SEC:
        end = start + duration
    if end - start > _MAX_SEC:
        end = start + _MAX_SEC
    return start, end


def _start_from_url(parsed, qs: dict) -> Optional[int]:
    for key in ("start", "t"):
        values = qs.get(key) or []
        if values:
            parsed_value = _optional_seconds(values[0])
            if parsed_value is not None:
                return parsed_value
    frag = parsed.fragment or ""
    if frag.startswith("t="):
        return _optional_seconds(frag[2:])
    return None


def _optional_seconds(value: str) -> Optional[int]:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("s") and text[:-1].isdigit():
        return int(text[:-1])
    if text.isdigit():
        return int(text)
    total = 0
    found = False
    for amount, unit in _CLOCK.findall(text):
        found = True
        scale = {"h": 3600, "m": 60, "s": 1}[unit]
        total += int(amount) * scale
    return total if found else None


def _optional_int(value: object) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _youtube_id(parsed) -> str:
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host == "youtu.be":
        cand = parsed.path.strip("/").split("/")[0]
    else:
        qs = parse_qs(parsed.query)
        if qs.get("v"):
            cand = qs["v"][0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            cand = ""
            if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live", "v"}:
                cand = parts[1]
    return cand if _YT_ID.match(cand or "") else ""


def _vimeo_id(parsed) -> str:
    parts = [part for part in parsed.path.split("/") if part]
    for part in reversed(parts):
        if _VIMEO_ID.match(part):
            return part
    return ""


def _keyword_hit(topic: str, keys, title: str) -> bool:
    topic_l = (topic or "").lower()
    for key in keys or []:
        word = str(key).strip().lower()
        if len(word) >= 3 and word in topic_l:
            return True
    topic_words = [w for w in re.split(r"[^0-9A-Za-z]+", topic_l) if len(w) >= 4]
    title_l = (title or "").lower()
    if any(word in title_l for word in topic_words):
        return True
    title_words = [w for w in re.split(r"[^0-9A-Za-z]+", title_l) if len(w) >= 4]
    return any(word in topic_l for word in title_words)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:48] or "clip")


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
