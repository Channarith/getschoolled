"""Stage course theme + media files for the local slide-show HTTP server."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional


def _resolve_source(path_str: str, *, course_dir: Path, repo_root: Path) -> Optional[Path]:
    if not path_str or path_str.startswith(("http://", "https://", "data:")):
        return None
    p = Path(path_str)
    if p.is_file():
        return p
    for base in (course_dir, repo_root):
        cand = base / path_str
        if cand.is_file():
            return cand
    return None


def stage_asset(
    path_str: str,
    *,
    assets_dir: Path,
    course_dir: Path,
    repo_root: Path,
) -> str:
    """Copy a local media file into ``assets_dir``; return web-relative URL."""
    if not path_str:
        return ""
    if path_str.startswith(("http://", "https://")):
        return path_str
    src = _resolve_source(path_str, course_dir=course_dir, repo_root=repo_root)
    if src is None:
        return path_str
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / src.name
    if not dest.is_file() or dest.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, dest)
    return f"assets/{dest.name}"


def load_theme(
    course_dir: Path,
    *,
    course_title: str = "",
    subject: str = "general",
    fmt: str = "lecture",
    tags: Optional[List[str]] = None,
) -> dict:
    """Load theme from course JSON or resolve a fresh one."""
    for name in ("*.course.json", "course.json"):
        for path in sorted(course_dir.glob(name)):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("theme"):
                    return dict(data["theme"])
            except (json.JSONDecodeError, OSError):
                continue
    from ..harvest.themes import resolve_slide_theme

    return resolve_slide_theme(
        title=course_title, subject=subject, tags=tags or (), fmt=fmt,
    ).to_dict()


def enrich_course_slides_for_deck(
    course_slides: List[dict],
    *,
    theme: dict,
    course_dir: Path,
    repo_root: Path,
    out_dir: Path,
) -> List[dict]:
    """Attach staged wallpaper/media URLs for the HTML presenter."""
    assets_dir = out_dir / "assets"
    enriched: List[dict] = []
    wallpaper = theme.get("wallpaper_url") or theme.get("poster_url") or ""
    accent = theme.get("accent_hex") or "#334155"
    manifest: dict = {}
    mf = course_dir / "media_manifest.json"
    if mf.is_file():
        try:
            manifest = json.loads(mf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    manifest_by_index = {s.get("index", i): s for i, s in enumerate(manifest.get("slides") or [])}

    for i, slide in enumerate(course_slides):
        row = dict(slide)
        row["wallpaper_url"] = wallpaper
        row["accent_hex"] = accent
        row["poster_url"] = theme.get("poster_url") or wallpaper

        mf_row = manifest_by_index.get(i) or manifest_by_index.get(row.get("slide_index", i)) or {}
        media_url = row.get("media_url") or mf_row.get("media_url") or ""
        media_kind = row.get("media_kind") or mf_row.get("media_kind") or ""
        audio_path = row.get("audio_path") or mf_row.get("audio") or ""

        if media_url:
            row["media_url"] = stage_asset(
                media_url, assets_dir=assets_dir, course_dir=course_dir, repo_root=repo_root,
            )
            row["media_kind"] = media_kind or (
                "video" if str(media_url).lower().endswith((".mp4", ".webm", ".mov")) else
                "image" if str(media_url).lower().endswith((".gif", ".png", ".jpg", ".jpeg", ".webp")) else
                "video"
            )
        if audio_path:
            row["audio_path"] = stage_asset(
                audio_path, assets_dir=assets_dir, course_dir=course_dir, repo_root=repo_root,
            )
        enriched.append(row)
    return enriched
