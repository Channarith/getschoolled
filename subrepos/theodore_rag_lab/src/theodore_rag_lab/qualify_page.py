"""Embedded browser console for manually qualifying the RAG lab."""

from __future__ import annotations


def render_qualify_page() -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>Theodore RAG Lab</title>\n"
        "  <style>\n"
        + _CSS
        + "\n  </style>\n</head>\n<body>\n"
        + _HTML
        + "\n  <script>\n"
        + _JS
        + "\n  </script>\n</body>\n</html>\n"
    )


_CSS = """
  :root { --bg:#0b1220; --panel:#152036; --ink:#e8eefc; --muted:#93a4c3; --accent:#7dd3fc; --ok:#7dd3a8; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; color:var(--ink); font-family:"Trebuchet MS","Segoe UI",sans-serif;
    background: radial-gradient(900px 500px at 0% 0%, #0c4a6e 0%, transparent 55%),
                radial-gradient(700px 400px at 100% 10%, #1e3a5f 0%, transparent 50%), var(--bg); }
  header { padding:1.25rem 1.5rem .35rem; }
  header h1 { margin:0; font-size:1.7rem; letter-spacing:.01em; }
  header p { margin:.4rem 0 0; color:var(--muted); max-width:46rem; }
  .layout { display:grid; gap:1rem; padding:1rem 1.5rem 2rem; grid-template-columns:minmax(240px,320px) 1fr; }
  @media (max-width:900px){ .layout { grid-template-columns:1fr; } }
  .panel { background:color-mix(in srgb, var(--panel) 94%, black); border:1px solid #2a3b58; border-radius:16px; padding:1rem; }
  .panel h2 { margin:0 0 .75rem; font-size:1rem; color:var(--accent); }
  .row { display:flex; flex-wrap:wrap; gap:.45rem; margin-bottom:.65rem; }
  button, select, input { font:inherit; border-radius:10px; border:1px solid #3d5275; background:#0b1220; color:var(--ink); padding:.45rem .75rem; }
  button { cursor:pointer; }
  button.primary { background:#0369a1; border-color:var(--accent); font-weight:700; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  label { color:var(--muted); font-size:.85rem; display:flex; gap:.4rem; align-items:center; }
  .knobs { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.82rem; line-height:1.45; color:#d7e6ff; white-space:pre-wrap; }
  .out { margin:0; min-height:22rem; max-height:70vh; overflow:auto; padding:.85rem; border-radius:12px;
    background:#070d18; border:1px solid #2a3b58; color:#cfe3ff; font:12px/1.45 ui-monospace,Menlo,Consolas,monospace; white-space:pre-wrap; }
  .meta { color:var(--muted); font-size:.85rem; margin-top:.35rem; }
  .pill { display:inline-block; margin-right:.35rem; padding:.15rem .5rem; border-radius:999px; border:1px solid #3d5275; color:var(--ok); font-size:.75rem; }
"""

_HTML = """
  <header>
    <h1>Theodore RAG Lab</h1>
    <p>Manual qualification console for curriculum RAG tuning. Run eval, sweep presets,
       start a short bakeoff, and inspect champion + telemetry — all from the browser.</p>
    <div class="meta"><span class="pill">offline</span><span class="pill">port 8095</span><span class="pill">GET /</span></div>
  </header>
  <div class="layout">
    <aside class="panel">
      <h2>Actions</h2>
      <div class="row">
        <button class="primary" id="btn-eval" type="button">Run eval</button>
        <button id="btn-sweep" type="button">Sweep</button>
        <button id="btn-health" type="button">Health</button>
      </div>
      <div class="row">
        <label>Preset <select id="preset"></select></label>
        <button id="btn-preset" type="button">Apply</button>
      </div>
      <div class="row">
        <label>Hours <input id="hours" type="number" min="0.01" max="24" step="0.01" value="0.01" style="width:5rem" /></label>
        <button id="btn-block" type="button">Blocking bakeoff</button>
      </div>
      <div class="row">
        <button id="btn-start" type="button">Start train</button>
        <button id="btn-status" type="button">Status</button>
        <button id="btn-stop" type="button">Stop</button>
      </div>
      <div class="row">
        <button id="btn-champ" type="button">Champion</button>
        <button id="btn-tel" type="button">Telemetry</button>
        <button id="btn-tuning" type="button">Tuning</button>
      </div>
      <h2>Active knobs</h2>
      <div class="knobs" id="knobs">Loading…</div>
    </aside>
    <main class="panel">
      <h2>Result</h2>
      <pre class="out" id="out">Click an action to qualify the lab.</pre>
    </main>
  </div>
"""

_JS = """
  const out = document.getElementById('out');
  const knobs = document.getElementById('knobs');
  const preset = document.getElementById('preset');

  function show(data) {
    out.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  }

  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['content-type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = text; }
    if (!res.ok) throw new Error((data && data.detail) || text || res.statusText);
    return data;
  }

  async function refreshTuning() {
    const data = await api('GET', '/api/rag/tuning');
    knobs.textContent = JSON.stringify(data.knobs, null, 2);
    preset.innerHTML = '';
    (data.presets || []).forEach((name) => {
      const opt = document.createElement('option');
      opt.value = name; opt.textContent = name; preset.appendChild(opt);
    });
  }

  async function run(fn) {
    try {
      show(await fn());
      await refreshTuning();
    } catch (err) {
      show('Error: ' + (err && err.message ? err.message : err));
    }
  }

  document.getElementById('btn-health').onclick = () => run(() => api('GET', '/health'));
  document.getElementById('btn-eval').onclick = () => run(() => api('POST', '/api/rag/eval?details=false'));
  document.getElementById('btn-sweep').onclick = () => run(() => api('GET', '/api/rag/sweep'));
  document.getElementById('btn-tuning').onclick = () => run(() => api('GET', '/api/rag/tuning'));
  document.getElementById('btn-preset').onclick = () => run(() => api('POST', '/api/rag/tuning/preset/' + encodeURIComponent(preset.value)));
  document.getElementById('btn-block').onclick = () => run(() => api('POST', '/api/rag/train/run-blocking', { hours: Number(document.getElementById('hours').value) || 0.01 }));
  document.getElementById('btn-start').onclick = () => run(() => api('POST', '/api/rag/train/start', { hours: Number(document.getElementById('hours').value) || 1 }));
  document.getElementById('btn-status').onclick = () => run(() => api('GET', '/api/rag/train/status'));
  document.getElementById('btn-stop').onclick = () => run(() => api('POST', '/api/rag/train/stop'));
  document.getElementById('btn-champ').onclick = () => run(() => api('GET', '/api/rag/champion'));
  document.getElementById('btn-tel').onclick = () => run(() => api('GET', '/api/rag/telemetry'));

  refreshTuning().catch((err) => { knobs.textContent = String(err); });
"""
