"""The camera check page served at /diag/vision.

Public on purpose: a person whose camera games fail can run it without signing in. It opens the camera, loads
the same self-hosted MediaPipe files the games use, runs face, hand and outline detection for a few seconds, and
prints what happened with timings. Camera frames stay in this browser; nothing is uploaded. The report text is
what the person copies or shares.
"""
from __future__ import annotations

DIAG_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>Camera check · Salareen</title>
<style>
:root{color-scheme:dark;--bg:#0b1020;--card:#141b34;--line:#2c3558;--text:#f4e9d8;--muted:#9aa5c4;--ok:#5eead4;--warn:#fbbf24;--bad:#fb7185;--gold:#d4af37}
*{box-sizing:border-box}
body{margin:0;padding:calc(12px + env(safe-area-inset-top,0px)) 14px calc(24px + env(safe-area-inset-bottom,0px));background:var(--bg);color:var(--text);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
h1{font-size:1.25rem;margin:0 0 2px}
p.sub{margin:0 0 12px;color:var(--muted);font-size:.9rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;margin:10px 0}
button{font:inherit;min-height:46px;padding:0 16px;border-radius:12px;border:1px solid var(--gold);background:transparent;color:var(--text)}
button.primary{background:var(--gold);color:#1a1405;font-weight:700}
button:disabled{opacity:.5}
.row{display:flex;gap:8px;flex-wrap:wrap}
table{width:100%;border-collapse:collapse;font-size:.92rem}
td{padding:5px 4px;border-bottom:1px solid var(--line);vertical-align:top}
td:first-child{color:var(--muted);width:42%}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
video{width:100%;max-height:34vh;border-radius:12px;background:#000;transform:scaleX(-1);object-fit:cover}
#verdict{font-size:1.1rem;font-weight:700}
#advice li{margin:4px 0}
textarea{width:100%;height:9rem;background:#0a0f1f;color:var(--muted);border:1px solid var(--line);border-radius:10px;font:12px/1.35 ui-monospace,Menlo,monospace}
.small{font-size:.8rem;color:var(--muted)}
</style>
</head>
<body>
<h1>Camera check</h1>
<p class="sub">Tests the camera, face, hand and outline detection on this device. Camera frames stay on this device. Nothing is uploaded.</p>
<div class="card">
  <div class="row"><button id="start" class="primary">Start the check</button><button id="stop" disabled>Stop</button><button id="handtest">Hand test</button></div>
  <p class="small">Hand test: if the check shows hands 0, press this and hold ONE open hand in front of the camera (about 40 seconds). It tries every face and hand setting and reports which one sees you.</p>
  <p id="status" class="small" role="status">Press Start, allow the camera, then keep your face and one open hand in view for a few seconds.</p>
  <video id="preview" autoplay playsinline muted hidden></video>
</div>
<div class="card"><div id="verdict">Not run yet</div><ul id="advice"></ul></div>
<div class="card"><table id="rows"></table></div>
<div class="card">
  <div class="row"><button id="copy">Copy report</button><button id="share" hidden>Share report</button></div>
  <p class="small">The report has numbers, error names and timings only: no pictures, no audio. Review it before you send it.</p>
  <textarea id="report" readonly aria-label="Diagnostic report"></textarea>
</div>
<script type="module" src="/static/vision_diag_page.js__ASSET_TAG__"></script>
</body>
</html>
"""


def render_diag_page(asset_tag: str) -> str:
    return DIAG_HTML.replace("__ASSET_TAG__", f"?v={asset_tag}" if asset_tag else "")
