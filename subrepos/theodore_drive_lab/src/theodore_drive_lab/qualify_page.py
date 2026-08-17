"""Embedded browser console for manually qualifying the Drive Mode lab."""

from __future__ import annotations


def render_qualify_page() -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>Theodore Drive Lab</title>\n"
        "  <style>\n"
        + _CSS
        + "\n  </style>\n</head>\n<body>\n"
        + _HTML
        + "\n  <script>\n"
        + _JS
        + "\n  </script>\n</body>\n</html>\n"
    )


_CSS = """
  :root { --bg:#120e08; --panel:#241c12; --ink:#f7efe2; --muted:#b9a789; --accent:#d6a84b; --ok:#7dd3a8; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; color:var(--ink); font-family:"Trebuchet MS","Segoe UI",sans-serif;
    background: radial-gradient(900px 500px at 5% -5%, #7c4a12 0%, transparent 55%),
                radial-gradient(700px 400px at 100% 0%, #3f2a12 0%, transparent 50%), var(--bg); }
  header { padding:1.25rem 1.5rem .35rem; }
  header h1 { margin:0; font-size:1.7rem; }
  header p { margin:.4rem 0 0; color:var(--muted); max-width:46rem; }
  .layout { display:grid; gap:1rem; padding:1rem 1.5rem 2rem; grid-template-columns:minmax(240px,340px) 1fr; }
  @media (max-width:900px){ .layout { grid-template-columns:1fr; } }
  .panel { background:color-mix(in srgb, var(--panel) 94%, black); border:1px solid #4a3a22; border-radius:16px; padding:1rem; }
  .panel h2 { margin:0 0 .75rem; font-size:1rem; color:var(--accent); }
  .row { display:flex; flex-wrap:wrap; gap:.45rem; margin-bottom:.65rem; }
  button, select, input, textarea { font:inherit; border-radius:10px; border:1px solid #6a5430; background:#1a140c; color:var(--ink); padding:.45rem .75rem; }
  button { cursor:pointer; }
  button.primary { background:#92610f; border-color:var(--accent); font-weight:700; }
  textarea { width:100%; min-height:4.5rem; resize:vertical; }
  .knobs { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.82rem; line-height:1.45; white-space:pre-wrap; }
  .out { margin:0; min-height:22rem; max-height:70vh; overflow:auto; padding:.85rem; border-radius:12px;
    background:#0c0905; border:1px solid #4a3a22; color:#f0e2c4; font:12px/1.45 ui-monospace,Menlo,Consolas,monospace; white-space:pre-wrap; }
  .meta { color:var(--muted); font-size:.85rem; margin-top:.35rem; }
  .pill { display:inline-block; margin-right:.35rem; padding:.15rem .5rem; border-radius:999px; border:1px solid #6a5430; color:var(--ok); font-size:.75rem; }
"""

_HTML = """
  <header>
    <h1>Theodore Drive Lab</h1>
    <p>Manual qualification console for Drive Mode wake / echo / TTS / Q&amp;A tuning.
       Parse a wake utterance, run fixture evals, and bakeoff champions from the browser.</p>
    <div class="meta"><span class="pill">offline fixtures</span><span class="pill">port 8096</span><span class="pill">GET /</span></div>
  </header>
  <div class="layout">
    <aside class="panel">
      <h2>Actions</h2>
      <div class="row">
        <button class="primary" id="btn-wake" type="button">Wake eval</button>
        <button id="btn-answer" type="button">Answer eval</button>
        <button id="btn-health" type="button">Health</button>
      </div>
      <div class="row">
        <label>Preset <select id="preset"></select></label>
        <button id="btn-preset" type="button">Apply</button>
      </div>
      <div class="row">
        <label>Rounds <input id="rounds" type="number" min="1" max="100" value="8" style="width:4.5rem" /></label>
        <button id="btn-bake" type="button">Bakeoff</button>
      </div>
      <div class="row">
        <button id="btn-champ" type="button">Champion</button>
        <button id="btn-tel" type="button">Telemetry</button>
        <button id="btn-tuning" type="button">Tuning</button>
      </div>
      <h2>Wake parse</h2>
      <textarea id="utterance" placeholder="Hey Sala, pause the lesson"></textarea>
      <div class="row" style="margin-top:.55rem">
        <button id="btn-parse" type="button">Parse utterance</button>
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
  document.getElementById('utterance').value = 'Hey Sala, pause the lesson';

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
    const data = await api('GET', '/api/drive/tuning');
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
  document.getElementById('btn-wake').onclick = () => run(() => api('POST', '/api/drive/wake/eval'));
  document.getElementById('btn-answer').onclick = () => run(() => api('POST', '/api/drive/answer/eval'));
  document.getElementById('btn-tuning').onclick = () => run(() => api('GET', '/api/drive/tuning'));
  document.getElementById('btn-preset').onclick = () => run(() => api('POST', '/api/drive/tuning/preset/' + encodeURIComponent(preset.value)));
  document.getElementById('btn-bake').onclick = () => run(() => api('POST', '/api/drive/bakeoff', { rounds: Number(document.getElementById('rounds').value) || 8 }));
  document.getElementById('btn-champ').onclick = () => run(() => api('GET', '/api/drive/champion'));
  document.getElementById('btn-tel').onclick = () => run(() => api('GET', '/api/drive/telemetry'));
  document.getElementById('btn-parse').onclick = () => run(() => api('POST', '/api/drive/wake/parse', { text: document.getElementById('utterance').value || 'Hey Sala' }));

  refreshTuning().catch((err) => { knobs.textContent = String(err); });
"""
