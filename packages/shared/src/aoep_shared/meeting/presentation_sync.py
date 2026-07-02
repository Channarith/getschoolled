"""Synchronized slide deck + audio for the local AI presenter."""

from __future__ import annotations

import html
import json
import socket
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional

from .base import PresentationPlan, PresentationStep
from .presentation_assets import enrich_course_slides_for_deck, load_theme


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _slide_payload(
    step: PresentationStep,
    course_slide: Optional[dict] = None,
    *,
    native_pages: Optional[List[Path]] = None,
) -> dict:
    cs = course_slide or {}
    body = cs.get("body") or step.narration or ""
    bullets = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not bullets and body:
        bullets = [body[:240]]
    payload = {
        "order": step.order,
        "heading": step.heading,
        "bullets": bullets[:10],
        "category": cs.get("category", step.kind),
        "action": step.action,
        "media_url": cs.get("media_url", ""),
        "media_kind": cs.get("media_kind", ""),
        "audio_path": cs.get("audio_path", ""),
        "wallpaper_url": cs.get("wallpaper_url", ""),
        "accent_hex": cs.get("accent_hex", ""),
        "poster_url": cs.get("poster_url", ""),
        "slide_index": step.slide_index,
    }
    if native_pages:
        from .native_slides import page_for_step

        idx = page_for_step(step.slide_index, len(native_pages))
        payload["image"] = f"pages/{native_pages[idx].name}"
    return payload


def write_slide_deck_html(
    plan: PresentationPlan,
    *,
    out_path: Path,
    course_title: str,
    course_slides: Optional[List[dict]] = None,
    native_pages: Optional[List[Path]] = None,
    theme: Optional[dict] = None,
    course_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Path:
    """Build a fullscreen HTML deck that follows ``state.json`` step index."""
    course_slides = course_slides or []
    out_path = Path(out_path)
    root = out_path.parent
    if theme and course_slides:
        course_slides = enrich_course_slides_for_deck(
            course_slides,
            theme=theme,
            course_dir=course_dir or root,
            repo_root=repo_root or Path.cwd(),
            out_dir=root,
        )
    slides = []
    for step in plan.steps:
        cs = course_slides[step.slide_index] if step.slide_index < len(course_slides) else {}
        slides.append(_slide_payload(step, cs, native_pages=native_pages))

    deck_theme = theme or {}
    payload = json.dumps({
        "title": course_title,
        "slides": slides,
        "native": bool(native_pages),
        "theme": deck_theme,
    })
    if native_pages:
        doc = _native_deck_html(payload, course_title, deck_theme)
    else:
        doc = _rich_deck_html(payload, course_title, deck_theme)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def _rich_deck_html(payload: str, course_title: str, theme: dict) -> str:
    accent = html.escape(theme.get("accent_hex") or "#38bdf8")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{html.escape(course_title)} — AI Class</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{ --accent: {accent}; }}
  body {{ font-family: "SF Pro Display", "Segoe UI", system-ui, sans-serif;
          color: #f1f5f9; height: 100vh; overflow: hidden; }}
  #bg {{ position: fixed; inset: 0; background: #0b1220 center/cover no-repeat;
         transform: scale(1.05); transition: opacity 0.6s ease; z-index: 0; }}
  #bg.kb {{ animation: kenburns 18s ease-in-out infinite alternate; }}
  @keyframes kenburns {{
    from {{ transform: scale(1.05); }}
    to {{ transform: scale(1.12); }}
  }}
  #overlay {{ position: fixed; inset: 0; background: linear-gradient(135deg,
      rgba(11,18,32,0.88) 0%, rgba(11,18,32,0.55) 45%, rgba(11,18,32,0.82) 100%);
      z-index: 1; pointer-events: none; }}
  #deck {{ position: relative; z-index: 2; display: flex; flex-direction: column;
           height: 100vh; padding: 2rem 3rem; }}
  #bar {{ display: flex; justify-content: space-between; opacity: 0.9; font-size: 0.95rem;
          margin-bottom: 1rem; }}
  #layout {{ flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;
             align-items: center; min-height: 0; }}
  #layout.media-only {{ grid-template-columns: 1fr; }}
  #content {{ animation: fadeIn 0.45s ease; }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: none; }} }}
  #cat {{ display: inline-block; background: color-mix(in srgb, var(--accent) 35%, #1e293b);
          color: #e2e8f0; padding: 0.25rem 0.75rem; border-radius: 999px;
          font-size: 0.85rem; margin-bottom: 0.75rem; border: 1px solid var(--accent); }}
  #title {{ font-size: 2.2rem; font-weight: 700; line-height: 1.15; margin-bottom: 1rem;
            text-shadow: 0 2px 12px rgba(0,0,0,0.45); }}
  ul {{ list-style: none; font-size: 1.2rem; line-height: 1.5; max-height: 42vh; overflow-y: auto; }}
  li {{ margin: 0.5rem 0; padding-left: 1.1rem; position: relative; }}
  li::before {{ content: "•"; position: absolute; left: 0; color: var(--accent); }}
  #media-panel {{ display: flex; align-items: center; justify-content: center;
                  min-height: 0; animation: fadeIn 0.5s ease 0.1s both; }}
  #slide-video, #slide-gif {{ max-width: 100%; max-height: 48vh; border-radius: 12px;
              box-shadow: 0 12px 40px rgba(0,0,0,0.45); border: 2px solid color-mix(in srgb, var(--accent) 40%, transparent); }}
  #presenter {{ margin-top: auto; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.12);
                font-size: 0.95rem; color: #cbd5e1; max-height: 22vh; overflow-y: auto;
                background: rgba(11,18,32,0.55); border-radius: 8px; padding: 0.75rem 1rem; }}
  #presenter strong {{ color: #f8fafc; }}
  .hidden {{ display: none !important; }}
</style>
</head>
<body>
<div id="bg"></div>
<div id="overlay"></div>
<div id="deck">
  <div id="bar"><span id="course">{html.escape(course_title)}</span><span id="progress"></span></div>
  <div id="layout">
    <div id="content">
      <div id="cat"></div>
      <div id="title"></div>
      <ul id="bullets"></ul>
    </div>
    <div id="media-panel" class="hidden">
      <video id="slide-video" class="hidden" playsinline muted loop controls></video>
      <img id="slide-gif" class="hidden" alt="demo"/>
    </div>
  </div>
  <div id="presenter"><strong>Presenter:</strong> <span id="caption"></span></div>
</div>
<script>
const DECK = {payload};
let lastStep = -1;
function setBg(url) {{
  const bg = document.getElementById('bg');
  if (url) {{
    bg.style.backgroundImage = "url('" + url + "')";
    bg.classList.add('kb');
  }} else {{
    bg.style.backgroundImage = 'none';
    bg.classList.remove('kb');
  }}
}}
function setAccent(hex) {{
  if (hex) document.documentElement.style.setProperty('--accent', hex);
}}
function showMedia(s) {{
  const panel = document.getElementById('media-panel');
  const vid = document.getElementById('slide-video');
  const gif = document.getElementById('slide-gif');
  const layout = document.getElementById('layout');
  vid.classList.add('hidden'); gif.classList.add('hidden'); panel.classList.add('hidden');
  layout.classList.remove('media-only');
  const url = s.media_url || '';
  if (!url) return;
  panel.classList.remove('hidden');
  const kind = (s.media_kind || '').toLowerCase();
  if (kind === 'image' || url.endsWith('.gif') || url.endsWith('.png') || url.endsWith('.jpg')) {{
    gif.src = url; gif.classList.remove('hidden');
  }} else {{
    vid.src = url; vid.classList.remove('hidden'); vid.play().catch(() => {{}});
  }}
  if ((s.bullets || []).length <= 2) layout.classList.add('media-only');
}}
async function refresh() {{
  try {{
    const r = await fetch('state.json?_=' + Date.now());
    const st = await r.json();
    const i = st.step ?? 0;
    if (i === lastStep && st.caption === document.getElementById('caption').textContent) return;
    lastStep = i;
    const s = DECK.slides[i] || DECK.slides[0] || {{}};
    document.getElementById('progress').textContent =
      'Slide ' + (i + 1) + ' / ' + DECK.slides.length;
    setBg(s.wallpaper_url || (DECK.theme && DECK.theme.wallpaper_url) || '');
    setAccent(s.accent_hex || (DECK.theme && DECK.theme.accent_hex) || '');
    document.getElementById('cat').textContent = (s.category || 'segment') +
      (s.action && s.action !== 'speak' ? ' · ' + s.action : '');
    document.getElementById('title').textContent = s.heading || DECK.title;
    const ul = document.getElementById('bullets');
    ul.innerHTML = '';
    (s.bullets || []).forEach(b => {{
      const li = document.createElement('li');
      li.textContent = b;
      ul.appendChild(li);
    }});
    showMedia(s);
    document.getElementById('caption').textContent = st.caption || '';
    const content = document.getElementById('content');
    content.style.animation = 'none';
    void content.offsetWidth;
    content.style.animation = '';
  }} catch (e) {{ /* wait for state */ }}
}}
setInterval(refresh, 120);
refresh();
</script>
</body>
</html>
"""


def _bullet_deck_html(payload: str, course_title: str) -> str:
    """Legacy alias — rich deck is default for bullet mode."""
    try:
        data = json.loads(payload)
        theme = data.get("theme") or {}
    except json.JSONDecodeError:
        theme = {}
    return _rich_deck_html(payload, course_title, theme)


def _native_deck_html(payload: str, course_title: str, theme: Optional[dict] = None) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{html.escape(course_title)} — AI Class</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "SF Pro Display", "Segoe UI", system-ui, sans-serif;
          background: #000; color: #f1f5f9; height: 100vh; overflow: hidden; }}
  #wrap {{ display: flex; flex-direction: column; height: 100vh; }}
  #bar {{ display: flex; justify-content: space-between; padding: 0.75rem 1.25rem;
          background: rgba(0,0,0,0.55); font-size: 0.9rem; position: absolute;
          top: 0; left: 0; right: 0; z-index: 2; }}
  #stage {{ flex: 1; display: flex; align-items: center; justify-content: center;
            background: #111; position: relative; min-height: 0; }}
  #slide-img {{ max-width: 100%; max-height: 100vh; object-fit: contain; }}
  #presenter {{ padding: 0.85rem 1.25rem; background: rgba(11,18,32,0.92);
                border-top: 1px solid #1e293b; font-size: 0.95rem; color: #94a3b8;
                max-height: 22vh; overflow-y: auto; }}
  #presenter strong {{ color: #e2e8f0; }}
</style>
</head>
<body>
<div id="wrap">
  <div id="stage">
    <div id="bar"><span id="course">{html.escape(course_title)}</span><span id="progress"></span></div>
    <img id="slide-img" alt="slide"/>
  </div>
  <div id="presenter"><strong>Presenter:</strong> <span id="caption"></span></div>
</div>
<script>
const DECK = {payload};
let lastStep = -1;
async function refresh() {{
  try {{
    const r = await fetch('state.json?_=' + Date.now());
    const st = await r.json();
    const i = st.step ?? 0;
    if (i === lastStep && st.caption === document.getElementById('caption').textContent) return;
    lastStep = i;
    const s = DECK.slides[i] || DECK.slides[0] || {{}};
    document.getElementById('progress').textContent =
      'Slide ' + (i + 1) + ' / ' + DECK.slides.length;
    const img = document.getElementById('slide-img');
    if (s.image) {{
      img.src = s.image + '?_=' + Date.now();
      img.style.display = 'block';
    }} else {{
      img.style.display = 'none';
    }}
    document.getElementById('caption').textContent = st.caption || '';
  }} catch (e) {{ /* wait for state */ }}
}}
setInterval(refresh, 120);
refresh();
</script>
</body>
</html>
"""


class SyncedSlideShow:
    """Local HTTP slide deck + state file kept in sync with spoken narration."""

    def __init__(self, root: Path, *, port: int = 0) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.port = port or _free_port()
        self.state_path = self.root / "state.json"
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._browser_opened = False
        self._native_pages: List[Path] = []

    def build(
        self,
        plan: PresentationPlan,
        *,
        title: str,
        course_slides: Optional[List[dict]] = None,
        slide_source: Optional[str | Path] = None,
        theme: Optional[dict] = None,
        course_dir: Optional[Path] = None,
        repo_root: Optional[Path] = None,
    ) -> Path:
        native_pages: Optional[List[Path]] = None
        if slide_source:
            from .native_slides import prepare_native_slides

            self._native_pages = prepare_native_slides(Path(slide_source), self.root)
            native_pages = self._native_pages
        if theme is None and course_dir:
            theme = load_theme(Path(course_dir), course_title=title)
        html_path = self.root / "slide_deck.html"
        write_slide_deck_html(
            plan,
            out_path=html_path,
            course_title=title,
            course_slides=course_slides,
            native_pages=native_pages,
            theme=theme,
            course_dir=course_dir or self.root,
            repo_root=repo_root,
        )
        self.state_path.write_text(json.dumps({"step": 0, "caption": ""}), encoding="utf-8")
        return html_path

    def start(self, *, open_browser: bool = True) -> str:
        root = str(self.root.resolve())

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=root, **kwargs)

            def log_message(self, fmt, *args):
                return

        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        url = f"http://127.0.0.1:{self.port}/slide_deck.html"
        if open_browser and not self._browser_opened:
            try:
                webbrowser.open(url)
            except Exception:
                pass
            self._browser_opened = True
        return url

    def show_step(self, step: PresentationStep, *, caption: str = "") -> None:
        self.state_path.write_text(
            json.dumps({"step": step.order, "caption": caption[:2000]}),
            encoding="utf-8",
        )

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        self._thread = None


def open_meeting_url(url: str) -> None:
    """Open Zoom / Meet / Teams join link in the default browser."""
    if not url or url.startswith("local://"):
        return
    try:
        webbrowser.open(url)
    except Exception:
        pass
