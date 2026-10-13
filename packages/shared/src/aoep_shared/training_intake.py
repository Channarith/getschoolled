"""Drop links, media, and databases into one training intake.

The RAG lab Drop training tab and ``scripts/training_drop.py`` both call
``drop_training``. YouTube and Vimeo (videos, channels, playlists) become the
voice queue. Other links, notes, and database rows become RAG text. Rows that
already look like question/answer pairs also land in an LLM JSONL file.
"""

from __future__ import annotations

import csv
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import urlparse

from aoep_shared.cosyvoice_ingest.urls import is_allowed_media_url

MEDIA_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".mp4", ".webm", ".mkv", ".mov"}
TEXT_EXTS = {".txt", ".md", ".rst", ".html", ".htm"}
TABLE_EXTS = {".json", ".jsonl", ".csv", ".tsv", ".sqlite", ".sqlite3", ".db", ".sql"}
MAX_MEDIA_BYTES = 512 * 1024 * 1024
MAX_TEXT_BYTES = 32 * 1024 * 1024
MAX_TABLE_ROWS = 200
MAX_DOC_CHARS = 8000

_URL_KEYS = {"url", "link", "href", "video", "audio", "source_url", "webpage_url"}
_TEXT_KEYS = {
    "text",
    "title",
    "content",
    "body",
    "transcript",
    "narration",
    "question",
    "answer",
    "instruction",
    "response",
    "meaning",
    "gloss",
    "description",
}
_TAG_RE = re.compile(r"(?is)<(script|style).*?>.*?</\1>|<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


ExpandFn = Callable[[str, int], list[str]]


def intake_root(root: Optional[Path] = None) -> Path:
    if root is not None:
        return Path(root)
    env = os.environ.get("AOEP_TRAINING_INTAKE", "").strip()
    if env:
        return Path(env)
    from aoep_shared.cosyvoice_ingest.queue import repo_root

    return repo_root() / "output" / "intake"


def _slug(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")[:40]
    return f"{stem or 'item'}_{digest}"


def safe_filename(name: str) -> str:
    base = Path(name or "upload").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return (cleaned or "upload")[:80]


def _plain(text: str) -> str:
    stripped = _TAG_RE.sub(" ", text or "")
    return _SPACE_RE.sub(" ", stripped).strip()


def _split_links(blob: str) -> list[str]:
    found: list[str] = []
    for line in (blob or "").replace(",", "\n").splitlines():
        for part in line.split():
            text = part.strip().strip("<>\"'")
            if text:
                found.append(text)
    return found


def _is_collection(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    if "list=" in query or "/playlist" in path:
        return True
    if host in {"youtube.com", "youtube-nocookie.com"}:
        if path.startswith(("/@", "/channel/", "/c/", "/user/", "/videos")):
            return True
        if path.rstrip("/").endswith("/videos") or path.rstrip("/").endswith("/shorts"):
            return True
        return False
    if host in {"vimeo.com", "player.vimeo.com"}:
        return any(bit in path for bit in ("/channels/", "/groups/", "/showcase/", "/album/"))
    return False


def _normalize_link(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("@") and " " not in text:
        return f"https://www.youtube.com/{text}/videos"
    return text


def host_is_public(host: str) -> bool:
    """False for loopback, private, and link-local hosts."""
    name = (host or "").strip().lower().rstrip(".")
    if not name or name in {"localhost", "localhost.localdomain"}:
        return False
    if name.endswith(".local") or name.endswith(".internal"):
        return False
    try:
        ip = ipaddress.ip_address(name)
    except ValueError:
        ip = None
    if ip is not None:
        return not _blocked_ip(ip)
    try:
        infos = socket.getaddrinfo(name, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if _blocked_ip(addr):
            return False
    return True


def _blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def expand_media_source(url: str, limit: int) -> list[str]:
    """List up to ``limit`` watch URLs for a channel or playlist. Empty if yt-dlp is missing."""
    if limit <= 0:
        return []
    binary = os.environ.get("YT_DLP_BIN", "yt-dlp")
    if shutil.which(binary) is None:
        return []
    cmd = [
        binary,
        "--flat-playlist",
        "--ignore-errors",
        "--playlist-end",
        str(limit),
        "--print",
        "%(webpage_url)s",
        "--no-warnings",
        url,
    ]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        return []
    urls: list[str] = []
    for line in (proc.stdout or "").splitlines():
        text = line.strip()
        if is_allowed_media_url(text):
            urls.append(text)
    return urls


def _append_unique(path: Path, lines: Iterable[str]) -> int:
    existing: list[str] = []
    if path.is_file():
        existing = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = set(existing)
    added = 0
    for line in lines:
        text = line.strip()
        if not text or text in seen:
            continue
        existing.append(text)
        seen.add(text)
        added += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(("\n".join(existing) + "\n") if existing else "", encoding="utf-8")
    return added


def _write_rag(root: Path, key: str, title: str, body: str) -> str:
    text = _plain(body)[:MAX_DOC_CHARS]
    if not text:
        return ""
    dest = root / "rag" / f"{_slug(key)}.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"{title}\n\n{text}\n", encoding="utf-8")
    return str(dest)


def _append_llm(root: Path, rows: list[dict]) -> int:
    if not rows:
        return 0
    dest = root / "llm" / "dropped_rag.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def _append_manifest(root: Path, rows: list[dict]) -> None:
    dest = root / "manifest.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _store_voice_urls(root: Path, urls: list[str]) -> int:
    return _append_unique(root / "voice" / "urls.txt", urls)


def _store_resource(root: Path, url: str, *, fetch_pages: bool) -> dict:
    _append_unique(root / "resources" / "links.txt", [url])
    body = url
    fetched = False
    parsed = urlparse(url)
    if fetch_pages and parsed.scheme in {"http", "https"} and host_is_public(parsed.hostname or ""):
        page = _fetch_text(url)
        if page:
            body = page
            fetched = True
    stored = _write_rag(root, url, url, body)
    return {
        "kind": "resource_url",
        "source": url,
        "stored": stored,
        "fetched": fetched,
    }


def _fetch_text(url: str) -> str:
    import urllib.request

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "aoep-training-drop"})
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read(200_000)
            charset = response.headers.get_content_charset() or "utf-8"
        return _plain(raw.decode(charset, errors="replace"))
    except Exception:
        return ""


def _rows_from_mapping(row: dict) -> tuple[list[str], str, list[dict]]:
    urls: list[str] = []
    bits: list[str] = []
    for key, value in row.items():
        if isinstance(value, (dict, list)):
            continue
        text = str(value or "").strip()
        if not text:
            continue
        key_name = str(key).lower()
        if key_name in _URL_KEYS or text.startswith(("http://", "https://", "@")):
            urls.extend(_split_links(text) if " " in text or "\n" in text else [text])
        elif key_name in _TEXT_KEYS or len(text) >= 40:
            bits.append(text)
    question = str(row.get("question") or row.get("instruction") or "").strip()
    answer = str(row.get("answer") or row.get("response") or "").strip()
    llm: list[dict] = []
    if question and answer:
        llm.append(
            {
                "question": question[:500],
                "answer": answer[:MAX_DOC_CHARS],
                "topic": str(row.get("topic") or row.get("title") or "dropped")[:120],
                "language": str(row.get("language") or "")[:16],
            }
        )
    return urls, "\n".join(bits), llm


def _iter_table_rows(name: str, data: bytes) -> list[dict]:
    suffix = Path(name).suffix.lower()
    if suffix == ".sql":
        return [{"text": data.decode("utf-8", errors="replace")[:MAX_DOC_CHARS]}]
    if suffix in {".sqlite", ".sqlite3", ".db"}:
        return _sqlite_rows(data)
    text = data.decode("utf-8", errors="replace")
    if suffix == ".jsonl":
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
            if len(rows) >= MAX_TABLE_ROWS:
                break
        return rows
    if suffix == ".json":
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            return [{"text": text[:MAX_DOC_CHARS]}]
        if isinstance(item, list):
            return [row for row in item if isinstance(row, dict)][:MAX_TABLE_ROWS]
        if isinstance(item, dict):
            for key in ("records", "items", "videos", "rows", "data"):
                nested = item.get(key)
                if isinstance(nested, list):
                    return [row for row in nested if isinstance(row, dict)][:MAX_TABLE_ROWS]
            return [item]
        return []
    if suffix in {".csv", ".tsv"}:
        sample = text[:4096]
        delimiter = "\t" if suffix == ".tsv" or "\t" in sample else ","
        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        return [dict(row) for i, row in zip(range(MAX_TABLE_ROWS), reader)]
    return []


def _sqlite_rows(data: bytes) -> list[dict]:
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        conn = sqlite3.connect(f"file:{tmp.name}?mode=ro", uri=True)
    except sqlite3.Error:
        Path(tmp.name).unlink(missing_ok=True)
        return []
    rows: list[dict] = []
    try:
        names = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if row and row[0] and not str(row[0]).startswith("sqlite_")
        ]
        for name in names:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(name)):
                continue
            try:
                cursor = conn.execute(f'SELECT * FROM "{name}" LIMIT {MAX_TABLE_ROWS}')
            except sqlite3.Error:
                continue
            columns = [col[0] for col in cursor.description or []]
            for record in cursor:
                rows.append({str(columns[i]): record[i] for i in range(len(columns))})
                if len(rows) >= MAX_TABLE_ROWS:
                    return rows
    finally:
        conn.close()
        Path(tmp.name).unlink(missing_ok=True)
    return rows


def _accept_links(
    root: Path,
    links: list[str],
    *,
    expand_limit: int,
    fetch_pages: bool,
    expand: ExpandFn,
) -> list[dict]:
    accepted: list[dict] = []
    voice: list[str] = []
    for raw in links:
        url = _normalize_link(raw)
        if url.startswith("@"):
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            accepted.append({"kind": "skipped", "source": raw, "detail": "only http(s) links"})
            continue
        if is_allowed_media_url(url):
            expanded = expand(url, expand_limit) if _is_collection(url) else []
            chosen = expanded or [url]
            voice.extend(chosen)
            accepted.append(
                {
                    "kind": "voice_url",
                    "source": raw,
                    "stored": str(root / "voice" / "urls.txt"),
                    "videos": len(chosen),
                    "expanded": bool(expanded),
                }
            )
            continue
        accepted.append(_store_resource(root, url, fetch_pages=fetch_pages))
    if voice:
        _store_voice_urls(root, voice)
    return accepted


def _accept_bytes(
    root: Path,
    name: str,
    data: bytes,
    *,
    expand_limit: int,
    fetch_pages: bool,
    expand: ExpandFn,
) -> list[dict]:
    filename = safe_filename(name)
    suffix = Path(filename).suffix.lower()
    if suffix in MEDIA_EXTS:
        if len(data) > MAX_MEDIA_BYTES:
            return [{"kind": "skipped", "source": filename, "detail": "media file is too large"}]
        dest = root / "voice" / "media" / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return [{"kind": "media", "source": filename, "stored": str(dest), "bytes": len(data)}]
    if len(data) > MAX_TEXT_BYTES:
        return [{"kind": "skipped", "source": filename, "detail": "file is too large"}]
    if suffix in TEXT_EXTS or suffix == "":
        text = data.decode("utf-8", errors="replace")
        links = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
        urlish = [line for line in links if line.startswith(("http://", "https://", "@"))]
        if links and len(urlish) >= max(1, int(len(links) * 0.6)):
            accepted = _accept_links(
                root, urlish, expand_limit=expand_limit, fetch_pages=fetch_pages, expand=expand
            )
            for row in accepted:
                row["source"] = filename
            return accepted or [{"kind": "skipped", "source": filename, "detail": "no links kept"}]
        stored = _write_rag(root, filename + text[:80], filename, text)
        if not stored:
            return [{"kind": "skipped", "source": filename, "detail": "no text kept"}]
        return [{"kind": "rag_text", "source": filename, "stored": stored}]
    if suffix in TABLE_EXTS:
        return _accept_table(root, filename, data, expand_limit=expand_limit, fetch_pages=fetch_pages, expand=expand)
    return [{"kind": "skipped", "source": filename, "detail": f"unsupported type {suffix or 'unknown'}"}]


def _accept_table(
    root: Path,
    filename: str,
    data: bytes,
    *,
    expand_limit: int,
    fetch_pages: bool,
    expand: ExpandFn,
) -> list[dict]:
    rows = _iter_table_rows(filename, data)
    voice: list[str] = []
    llm_rows: list[dict] = []
    docs = 0
    for index, row in enumerate(rows):
        urls, text, llm = _rows_from_mapping(row)
        for url in urls:
            normalized = _normalize_link(url)
            if is_allowed_media_url(normalized) or normalized.startswith("https://www.youtube.com/@"):
                voice.append(normalized)
            elif normalized.startswith(("http://", "https://")):
                _store_resource(root, normalized, fetch_pages=fetch_pages)
        if text:
            if _write_rag(root, f"{filename}:{index}", filename, text):
                docs += 1
        llm_rows.extend(llm)
    if voice:
        collected: list[str] = []
        for url in voice:
            if _is_collection(url):
                collected.extend(expand(url, expand_limit) or [url])
            else:
                collected.append(url)
        _store_voice_urls(root, collected)
    llm_count = _append_llm(root, llm_rows)
    return [
        {
            "kind": "table",
            "source": filename,
            "rows": len(rows),
            "rag_docs": docs,
            "voice_urls": len(voice),
            "llm_rows": llm_count,
            "stored": str(root),
        }
    ]


def drop_training(
    *,
    links: Optional[Iterable[str]] = None,
    files: Optional[Iterable[tuple[str, bytes]]] = None,
    paths: Optional[Iterable[Path]] = None,
    language: str = "en",
    expand_limit: int = 20,
    fetch_pages: bool = False,
    root: Optional[Path] = None,
    expand: Optional[ExpandFn] = None,
) -> dict:
    """Stage dropped links and files. Does not download media."""
    base = intake_root(root)
    base.mkdir(parents=True, exist_ok=True)
    (base / "language.txt").write_text((language or "en").strip() or "en", encoding="utf-8")
    expander = expand or expand_media_source
    accepted: list[dict] = []
    flat_links: list[str] = []
    for blob in links or []:
        flat_links.extend(_split_links(blob))
    if flat_links:
        accepted.extend(
            _accept_links(
                base,
                flat_links,
                expand_limit=expand_limit,
                fetch_pages=fetch_pages,
                expand=expander,
            )
        )
    for name, data in files or []:
        accepted.extend(
            _accept_bytes(
                base,
                name,
                data,
                expand_limit=expand_limit,
                fetch_pages=fetch_pages,
                expand=expander,
            )
        )
    for path in paths or []:
        accepted.extend(
            _accept_path(
                base,
                Path(path),
                expand_limit=expand_limit,
                fetch_pages=fetch_pages,
                expand=expander,
            )
        )
    for row in accepted:
        row["language"] = language or "en"
    _append_manifest(base, accepted)
    summary = intake_summary(base)
    summary["accepted"] = accepted
    summary["cli"] = "python3 scripts/training_drop.py " + " ".join(
        item for item in flat_links[:8]
    )
    return summary


def _accept_path(
    root: Path,
    path: Path,
    *,
    expand_limit: int,
    fetch_pages: bool,
    expand: ExpandFn,
) -> list[dict]:
    if not path.exists():
        return [{"kind": "skipped", "source": str(path), "detail": "path not found"}]
    if path.is_dir():
        accepted: list[dict] = []
        files = [item for item in sorted(path.rglob("*")) if item.is_file() and not item.name.startswith(".")]
        for item in files[:200]:
            accepted.extend(
                _accept_path(
                    root,
                    item,
                    expand_limit=expand_limit,
                    fetch_pages=fetch_pages,
                    expand=expand,
                )
            )
        return accepted
    if path.stat().st_size > (MAX_MEDIA_BYTES if path.suffix.lower() in MEDIA_EXTS else MAX_TEXT_BYTES):
        return [{"kind": "skipped", "source": str(path), "detail": "file is too large"}]
    return _accept_bytes(
        root,
        path.name,
        path.read_bytes(),
        expand_limit=expand_limit,
        fetch_pages=fetch_pages,
        expand=expand,
    )


def intake_summary(root: Optional[Path] = None) -> dict:
    base = intake_root(root)
    voice = base / "voice" / "urls.txt"
    voice_count = 0
    if voice.is_file():
        voice_count = sum(1 for line in voice.read_text(encoding="utf-8").splitlines() if line.strip())
    media = base / "voice" / "media"
    media_count = len([item for item in media.glob("*") if item.is_file()]) if media.is_dir() else 0
    rag = base / "rag"
    rag_count = len(list(rag.glob("*.txt"))) if rag.is_dir() else 0
    resources = base / "resources" / "links.txt"
    resource_count = 0
    if resources.is_file():
        resource_count = sum(1 for line in resources.read_text(encoding="utf-8").splitlines() if line.strip())
    llm = base / "llm" / "dropped_rag.jsonl"
    llm_count = 0
    if llm.is_file():
        llm_count = sum(1 for line in llm.read_text(encoding="utf-8").splitlines() if line.strip())
    language = "en"
    lang_path = base / "language.txt"
    if lang_path.is_file():
        language = lang_path.read_text(encoding="utf-8").strip() or "en"
    recent: list[dict] = []
    manifest = base / "manifest.jsonl"
    if manifest.is_file():
        lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
        for line in lines[-12:]:
            try:
                recent.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {
        "root": str(base),
        "language": language,
        "voice_urls": voice_count,
        "media_files": media_count,
        "rag_docs": rag_count,
        "resource_links": resource_count,
        "llm_rows": llm_count,
        "recent": recent,
    }


def iter_rag_texts(root: Optional[Path] = None) -> list[tuple[str, str, str]]:
    """(doc_id, title, text) for dropped notes, pages, and database rows."""
    rag = intake_root(root) / "rag"
    if not rag.is_dir():
        return []
    docs = []
    for path in sorted(rag.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")
        title = text.splitlines()[0].strip() if text.strip() else path.stem
        docs.append((f"intake/{path.name}", title, text))
    return docs


def train_dropped(
    *,
    language: str = "",
    max_urls: Optional[int] = None,
    root: Optional[Path] = None,
    run_ingest=None,
) -> dict:
    """Ingest only the dropped voice URLs and media files."""
    from aoep_shared.cosyvoice_ingest.pipeline import IngestConfig
    from aoep_shared.cosyvoice_ingest.pipeline import run_ingest as default_run

    base = intake_root(root)
    lang = language or "en"
    lang_path = base / "language.txt"
    if not language and lang_path.is_file():
        lang = lang_path.read_text(encoding="utf-8").strip() or "en"
    runner = run_ingest or default_run
    urls = base / "voice" / "urls.txt"
    media = base / "voice" / "media"
    has_urls = urls.is_file() and any(line.strip() for line in urls.read_text(encoding="utf-8").splitlines())
    has_media = media.is_dir() and any(item.is_file() for item in media.iterdir())
    if not has_urls and not has_media:
        return {"ok": False, "detail": "nothing dropped to train", "root": str(base)}
    reports = []
    out = base / "voice_run"
    if has_urls:
        reports.append(
            runner(
                IngestConfig(
                    urls_file=urls,
                    output_dir=out,
                    language=lang,
                    max_urls=max_urls,
                    speaker="dropped",
                )
            ).to_dict()
        )
    if has_media:
        reports.append(
            runner(
                IngestConfig(
                    media_dir=media,
                    output_dir=out / "local_media",
                    language=lang,
                    skip_download=True,
                    speaker="dropped_local",
                )
            ).to_dict()
        )
    ok = all(row.get("ok") for row in reports)
    return {"ok": ok, "language": lang, "root": str(base), "reports": reports}
