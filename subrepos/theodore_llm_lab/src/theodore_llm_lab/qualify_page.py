"""Browser console for the all-in-one LLM training lab."""

from __future__ import annotations


def render_qualify_page() -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>Theodore LLM Lab</title>\n"
        "  <style>\n"
        + _CSS
        + "\n  </style>\n</head>\n<body>\n"
        + _HTML
        + "\n  <script>\n"
        + _JS
        + "\n  </script>\n</body>\n</html>\n"
    )


_CSS = """
  :root { --bg:#0b1020; --panel:#121a2e; --ink:#e8eeff; --muted:#9aa6c1; --accent:#7dd3fc; --warm:#fbbf24; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; color:var(--ink); font-family:"Segoe UI",sans-serif;
    background: radial-gradient(900px 500px at 0% 0%, #1e3a5f 0%, transparent 55%),
                radial-gradient(700px 400px at 100% 0%, #312e81 0%, transparent 50%), var(--bg); }
  header { padding:1.25rem 1.5rem .35rem; }
  header h1 { margin:0; font-size:1.7rem; }
  header p { margin:.4rem 0 0; color:var(--muted); max-width:52rem; }
  .layout { display:grid; gap:1rem; padding:1rem 1.5rem 2rem; grid-template-columns:minmax(260px,360px) 1fr; }
  @media (max-width:980px){ .layout { grid-template-columns:1fr; } }
  .panel { background:color-mix(in srgb, var(--panel) 94%, black); border:1px solid #2a3755; border-radius:16px; padding:1rem; }
  .panel h2 { margin:0 0 .75rem; font-size:1rem; color:var(--accent); }
  .row { display:flex; flex-wrap:wrap; gap:.45rem; margin-bottom:.65rem; }
  button { font:inherit; border-radius:10px; border:1px solid #3d547a; background:#0b1020; color:var(--ink); padding:.45rem .75rem; cursor:pointer; }
  button.primary { background:#075985; border-color:var(--accent); font-weight:700; }
  label { display:flex; gap:.4rem; align-items:center; color:var(--muted); font-size:.9rem; }
  .counts { display:grid; grid-template-columns:1fr 1fr; gap:.4rem; font-size:.88rem; }
  .counts div { background:#0a0f1c; border-radius:10px; padding:.45rem .6rem; border:1px solid #1f2a42; }
  .counts b { color:var(--accent); }
  pre { margin:0; white-space:pre-wrap; word-break:break-word; font-size:.78rem; line-height:1.45; background:#0a0f1c; border-radius:12px; padding:.8rem; min-height:16rem; max-height:28rem; overflow:auto; border:1px solid #1f2a42; }
  .ok { color:#86efac; }
  .bad { color:#fca5a5; }
"""

_HTML = """
  <header>
    <p class="eyebrow" style="letter-spacing:.12em;font-size:.72rem;color:var(--accent);margin:0 0 .35rem;">THEODORE LLM LAB</p>
    <h1>Train our own portable education LLM</h1>
    <p>Fold the course library, pedagogical profiles, and webcam / audio / game / RAG learning signals into one custom model, then export a GGUF + ONNX pack a humanoid can run offline. GPU fine-tune is optional and happens on a separate CUDA host; this console never ships identity, race, or names into the weights.</p>
  </header>
  <div class="layout">
    <section class="panel">
      <h2>Corpus</h2>
      <label><input id="curriculum" type="checkbox" /> also scan sample-curriculum</label>
      <div class="row" style="margin-top:.8rem">
        <button class="primary" id="assemble">Assemble</button>
        <button id="check">Validate JSONL</button>
        <button id="pack">Robot pack</button>
        <button id="robot">Mock robot turn</button>
      </div>
      <div class="counts" id="counts"></div>
    </section>
    <section class="panel">
      <h2>Report</h2>
      <pre id="out">Ready. Assemble the bundled fixtures to preview examples.</pre>
    </section>
  </div>
"""

_JS = """
  const out = document.getElementById('out');
  const counts = document.getElementById('counts');
  function show(data) {
    out.textContent = JSON.stringify(data, null, 2);
    out.className = data && data.ok === false ? 'bad' : 'ok';
    const by = (data && (data.by_source || (data.pack && data.pack.sources))) || {};
    counts.innerHTML = Object.keys(by).map(k => '<div>' + k + ' <b>' + by[k] + '</b></div>').join('');
  }
  async function post(url, body) {
    const res = await fetch(url, {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(body || {})});
    const data = await res.json();
    show(data);
  }
  function body() {
    return { include_curriculum: document.getElementById('curriculum').checked };
  }
  document.getElementById('assemble').onclick = () => post('/api/llm/assemble', body());
  document.getElementById('check').onclick = () => post('/api/llm/check', body());
  document.getElementById('pack').onclick = () => post('/api/llm/robot-pack', body());
  document.getElementById('robot').onclick = () => post('/api/llm/robot-turn', {text:'Today we learn fractions together.'});
  if (window.__THEODORE_LIVE_AUDIO_ACTIVE__) { /* native audio owns speech */ }
  window.addEventListener('theodore-live-audio', () => {});
"""
