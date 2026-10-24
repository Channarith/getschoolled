"""Local listening lab: load bake-off runs (and any other voice clips) and compare them by ear.

  python3 -m tts_bakeoff.lab --out runs/2026-10-24            # serve the run and open the browser
  python3 -m tts_bakeoff.lab --demo                           # synthetic 3-voice run, no GPU or model needed
  python3 -m tts_bakeoff.lab --export lab-standalone          # static copy that opens from disk (index.html)

Serves 127.0.0.1 only. No network access, no telemetry. The page itself is static (static/index.html, lab.js, lab.css);
this module only serves it, streams the audio with Range support, and embeds the license matrix and sentence set.
"""
from __future__ import annotations

import http.server
import json
import mimetypes
import re
import shutil
import socketserver
import threading
import urllib.parse
from pathlib import Path

from .. import schema
from ..build_sentences import load as load_sentences

STATIC = Path(__file__).resolve().parent / "static"
LANGS = ("km", "vi", "th", "es", "en", "zh", "sw", "hi", "bn")
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".opus", ".aac"}
LISTED_EXT = AUDIO_EXT | {".json", ".jsonl"}
MAX_LISTED = 20000

MIME = {
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".ogg": "audio/ogg",
    ".opus": "audio/ogg", ".flac": "audio/flac", ".webm": "audio/webm",
    ".json": "application/json", ".jsonl": "application/x-ndjson",
    ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8",
}


def content_type(path: Path | str) -> str:
    ext = Path(path).suffix.lower()
    return MIME.get(ext) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def lab_data() -> dict:
    """License matrix (with the shippable label) and the fixed sentence set, embedded in the page as window.LAB_DATA."""
    cands = []
    for c in schema.candidates().values():
        cands.append({
            "id": c["id"], "name": c.get("name", c["id"]), "adapter": c.get("adapter"), "role": c.get("role"),
            "kind": c.get("kind"), "label": schema.label(c), "languages": [str(x) for x in c.get("languages", [])],
        })
    sentences: dict[str, list[dict]] = {}
    for lang in LANGS:
        try:
            rows = load_sentences(lang, None)
        except Exception:  # noqa: BLE001 - a missing language file must not stop the lab
            continue
        sentences[lang] = [{"id": r["id"], "text": r["text"], "category": r.get("category", ""), "ref_en": r.get("ref_en", "")} for r in rows]
    return {"version": 1, "candidates": cands, "sentences": sentences, "run": None}


def lab_data_js(run_base: str | None) -> str:
    data = lab_data()
    data["run"] = {"base": run_base} if run_base else None
    return "window.LAB_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n"


def safe_join(root: Path, rel: str) -> Path | None:
    """Resolve rel under root; None for traversal, absolute paths, NULs or symlinks that leave root."""
    rel = urllib.parse.unquote(rel)
    if not rel or "\x00" in rel or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel):
        return None
    if any(part == ".." for part in re.split(r"[\\/]", rel)):
        return None
    root_r = root.resolve()
    target = (root_r / rel).resolve()
    try:
        target.relative_to(root_r)
    except ValueError:
        return None
    return target


def list_run(root: Path, sub: str = "") -> dict:
    base = safe_join(root, sub) if sub else root.resolve()
    if base is None or not base.is_dir():
        return {"files": [], "error": "not a directory"}
    files = []
    for p in sorted(base.rglob("*")):
        if len(files) >= MAX_LISTED:
            break
        if p.is_file() and p.suffix.lower() in LISTED_EXT and not any(part.startswith(".") for part in p.relative_to(base).parts):
            files.append({"path": p.relative_to(base).as_posix(), "size": p.stat().st_size})
    return {"files": files, "root": (sub or "").strip("/"), "truncated": len(files) >= MAX_LISTED}


def parse_range(header: str | None, size: int) -> tuple[int, int] | None | str:
    """(start, end) inclusive; None for no header; 'bad' for an unsatisfiable or malformed range."""
    if not header:
        return None
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not m or (m.group(1) == "" and m.group(2) == ""):
        return "bad"
    if m.group(1) == "":
        n = int(m.group(2))
        if n == 0:
            return "bad"
        return (max(0, size - n), size - 1)
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else size - 1
    if start >= size or end < start:
        return "bad"
    return (start, min(end, size - 1))


def make_handler(out_dir: Path | None):
    root = out_dir.resolve() if out_dir else None

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "SalareenListeningLab/1"

        def log_message(self, fmt, *args):  # quiet by default
            return

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None, head: bool = False):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def _file(self, path: Path, head: bool):
            if not path.is_file():
                return self._send(404, b"not found", "text/plain; charset=utf-8", head=head)
            size = path.stat().st_size
            rng = parse_range(self.headers.get("Range"), size)
            ctype = content_type(path)
            if rng == "bad":
                return self._send(416, b"", ctype, {"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"}, head=True)
            start, end = (0, size - 1) if rng is None else rng
            length = end - start + 1 if size else 0
            self.send_response(200 if rng is None else 206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            if rng is not None:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if head or not size:
                return
            with path.open("rb") as fh:
                fh.seek(start)
                left = length
                while left > 0:
                    chunk = fh.read(min(64 * 1024, left))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    left -= len(chunk)

        def _route(self, head: bool):
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)
            if path in ("/", "/index.html"):
                return self._file(STATIC / "index.html", head)
            if path in ("/lab.js", "/lab.css"):
                return self._file(STATIC / path.lstrip("/"), head)
            if path == "/lab_data.js":
                return self._send(200, lab_data_js("/run/" if root else None).encode("utf-8"), MIME[".js"], head=head)
            if path == "/api/run":
                if root is None:
                    return self._send(200, b'{"files": []}', MIME[".json"], head=head)
                data = list_run(root, (query.get("sub") or [""])[0])
                return self._send(200, json.dumps(data).encode("utf-8"), MIME[".json"], head=head)
            if path.startswith("/run/") and root is not None:
                target = safe_join(root, path[len("/run/"):])
                if target is None:
                    return self._send(403, b"forbidden", "text/plain; charset=utf-8", head=head)
                return self._file(target, head)
            return self._send(404, b"not found", "text/plain; charset=utf-8", head=head)

        def do_GET(self):  # noqa: N802
            self._route(False)

        def do_HEAD(self):  # noqa: N802
            self._route(True)

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(out_dir: Path | None, port: int = 8765, host: str = "127.0.0.1") -> Server:
    return Server((host, port), make_handler(out_dir))


def serve_in_thread(out_dir: Path | None, port: int = 0) -> tuple[Server, threading.Thread]:
    srv = serve(out_dir, port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, t


def export_standalone(dest: Path) -> Path:
    """Copy the page plus lab_data.js so index.html opens from disk (file://) and the folder picker loads the audio."""
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "lab.js", "lab.css"):
        shutil.copyfile(STATIC / name, dest / name)
    (dest / "lab_data.js").write_text(lab_data_js(None), encoding="utf-8")
    return dest
