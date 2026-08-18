"""Landing page that seeds a demo session and opens the live monitor."""

from __future__ import annotations


def render_landing_page(default_session_id: str = "demo-session") -> str:
    import json as _json

    # The id lands in BOTH an HTML attribute and a JS string. JS-escaping alone
    # (\" is not an HTML escape) does not protect the attribute, and neither
    # neutralizes </script> — JSON-encode for the JS context (safe inside
    # <script> once < is escaped) and HTML-escape for the attribute.
    sid_js = _json.dumps(default_session_id).replace("<", "\\u003c")
    sid_attr = (
        default_session_id.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Theodore Webcam Lab</title>
  <style>
    :root {{ --bg:#0b1220; --ink:#e8eefc; --muted:#93a4c3; --accent:#7dd3fc; }}
    body {{ margin:0; min-height:100vh; color:var(--ink); font-family:"Trebuchet MS","Segoe UI",sans-serif;
      display:grid; place-items:center; background:
      radial-gradient(900px 500px at 10% 0%, #1d4ed6 0%, transparent 55%), var(--bg); }}
    .card {{ max-width:32rem; padding:1.5rem 1.75rem; border:1px solid #2a3b58; border-radius:16px;
      background:#152036; }}
    h1 {{ margin:0 0 .5rem; font-size:1.6rem; }}
    p {{ margin:.35rem 0; color:var(--muted); line-height:1.45; }}
    .row {{ display:flex; flex-wrap:wrap; gap:.5rem; margin-top:1rem; }}
    button, a.btn {{ font:inherit; border-radius:10px; border:1px solid #3d5275; background:#0b1220;
      color:var(--ink); padding:.55rem .9rem; cursor:pointer; text-decoration:none; display:inline-block; }}
    button.primary, a.btn.primary {{ background:#0369a1; border-color:var(--accent); font-weight:700; }}
    #status {{ margin-top:.85rem; font:12px/1.4 ui-monospace,Menlo,Consolas,monospace; color:#cfe3ff;
      white-space:pre-wrap; min-height:3rem; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Theodore Webcam Lab</h1>
    <p>Manual qualification entry. Seed a demo session, then open the live monitor
       (owner face lock, multi-face integrity, lesson actions).</p>
    <div class="row">
      <button class="primary" id="btn-open" type="button">Seed + open monitor</button>
      <a class="btn" id="link-monitor" href="/theodore/webcam/live-monitor/{sid_attr}">Open monitor only</a>
      <button id="btn-health" type="button">Health</button>
    </div>
    <div id="status">Ready.</div>
  </div>
  <script>
    const SESSION = {sid_js};
    const status = document.getElementById('status');
    async function seedAndOpen() {{
      status.textContent = 'Seeding demo session…';
      try {{
        const res = await fetch('/api/theodore/webcam/demo/seed', {{
          method: 'POST',
          headers: {{ 'content-type': 'application/json' }},
          body: JSON.stringify({{ session_id: SESSION, frames: 3, scenario: 'solo' }}),
        }});
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || res.statusText);
        status.textContent = JSON.stringify(data, null, 2);
        const path = data.monitor_path || ('/theodore/webcam/live-monitor/' + SESSION);
        window.location.href = path;
      }} catch (err) {{
        status.textContent = 'Error: ' + (err && err.message ? err.message : err);
      }}
    }}
    document.getElementById('btn-open').onclick = seedAndOpen;
    document.getElementById('btn-health').onclick = async () => {{
      const res = await fetch('/health');
      status.textContent = JSON.stringify(await res.json(), null, 2);
    }};
  </script>
</body>
</html>
"""
