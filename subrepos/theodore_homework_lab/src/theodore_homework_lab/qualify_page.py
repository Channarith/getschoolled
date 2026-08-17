"""Embedded browser console for manually qualifying the homework lab."""

from __future__ import annotations


def render_qualify_page() -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>Theodore Homework Lab</title>\n"
        "  <style>\n"
        + _CSS
        + "\n  </style>\n</head>\n<body>\n"
        + _HTML
        + "\n  <script>\n"
        + _JS
        + "\n  </script>\n</body>\n</html>\n"
    )


_CSS = """
  :root { --bg:#0b1512; --panel:#13261f; --ink:#e8f7f0; --muted:#93b8a8; --accent:#7dd3a8; --warm:#fbbf24; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; color:var(--ink); font-family:"Trebuchet MS","Segoe UI",sans-serif;
    background: radial-gradient(900px 500px at 0% 0%, #14532d 0%, transparent 55%),
                radial-gradient(700px 400px at 100% 0%, #0f3d2e 0%, transparent 50%), var(--bg); }
  header { padding:1.25rem 1.5rem .35rem; }
  header h1 { margin:0; font-size:1.7rem; }
  header p { margin:.4rem 0 0; color:var(--muted); max-width:48rem; }
  .layout { display:grid; gap:1rem; padding:1rem 1.5rem 2rem; grid-template-columns:minmax(250px,340px) 1fr; }
  @media (max-width:980px){ .layout { grid-template-columns:1fr; } }
  .panel { background:color-mix(in srgb, var(--panel) 94%, black); border:1px solid #2a4a3c; border-radius:16px; padding:1rem; }
  .panel h2 { margin:0 0 .75rem; font-size:1rem; color:var(--accent); }
  .row { display:flex; flex-wrap:wrap; gap:.45rem; margin-bottom:.65rem; }
  button, select, input, textarea { font:inherit; border-radius:10px; border:1px solid #3d6a55; background:#0b1512; color:var(--ink); padding:.45rem .75rem; }
  button { cursor:pointer; }
  button.primary { background:#15803d; border-color:var(--accent); font-weight:700; }
  textarea { width:100%; min-height:4rem; resize:vertical; }
  .methods { max-height:14rem; overflow:auto; font-size:.82rem; line-height:1.4; border:1px solid #2a4a3c; border-radius:10px; padding:.55rem; background:#0a120e; }
  .methods .m { margin:.25rem 0; color:var(--muted); }
  .methods .m strong { color:var(--ink); }
  .item { margin:0 0 .75rem; padding:.7rem .8rem; border-radius:12px; border:1px solid #2a4a3c; background:#0a120e; }
  .item .qid { color:var(--accent); font-size:.75rem; text-transform:uppercase; letter-spacing:.04em; }
  .item .prompt { margin:.25rem 0 .45rem; }
  .item input, .item select { width:100%; }
  .out { margin:0; min-height:10rem; max-height:28vh; overflow:auto; padding:.85rem; border-radius:12px;
    background:#070f0c; border:1px solid #2a4a3c; color:#d7f5e6; font:12px/1.45 ui-monospace,Menlo,Consolas,monospace; white-space:pre-wrap; }
  .meta { color:var(--muted); font-size:.85rem; margin-top:.35rem; }
  .pill { display:inline-block; margin-right:.35rem; padding:.15rem .5rem; border-radius:999px; border:1px solid #3d6a55; color:var(--warm); font-size:.75rem; }
  .score { font-size:1.1rem; color:var(--accent); font-weight:700; margin:.35rem 0 .75rem; }
"""

_HTML = """
  <header>
    <h1>Theodore Homework Lab</h1>
    <p>Manual qualification UI for 75+ generate/grade methodologies. List methods,
       generate a short assignment, answer in the browser, then grade — or run the gold battery.</p>
    <div class="meta"><span class="pill">75 methods</span><span class="pill">port 8098</span><span class="pill">GET /</span></div>
  </header>
  <div class="layout">
    <aside class="panel">
      <h2>Actions</h2>
      <div class="row">
        <button class="primary" id="btn-gen" type="button">Generate</button>
        <button id="btn-battery" type="button">Full battery</button>
        <button id="btn-gold" type="button">Gold eval</button>
      </div>
      <div class="row">
        <button id="btn-methods" type="button">List methods</button>
        <button id="btn-health" type="button">Health</button>
        <button id="btn-tel" type="button">Telemetry</button>
      </div>
      <div class="row">
        <label>Preset <select id="preset"></select></label>
        <button id="btn-preset" type="button">Apply</button>
      </div>
      <label>Passage</label>
      <textarea id="passage">photosynthesis: plants make food using light water and carbon dioxide</textarea>
      <div class="row" style="margin-top:.55rem">
        <label>Max items <input id="max-items" type="number" min="1" max="40" value="6" style="width:4rem" /></label>
        <label>Difficulty
          <select id="difficulty">
            <option>easy</option>
            <option selected>medium</option>
            <option>hard</option>
          </select>
        </label>
      </div>
      <h2>Methodologies</h2>
      <div class="methods" id="methods">Loading…</div>
    </aside>
    <main class="panel">
      <h2>Assignment</h2>
      <div class="score" id="score"></div>
      <div id="items"><p class="meta">Generate an assignment to answer and grade here.</p></div>
      <div class="row">
        <button class="primary" id="btn-grade" type="button" disabled>Grade answers</button>
      </div>
      <h2>Raw result</h2>
      <pre class="out" id="out">Ready.</pre>
    </main>
  </div>
"""

_JS = """
  const out = document.getElementById('out');
  const methodsEl = document.getElementById('methods');
  const itemsEl = document.getElementById('items');
  const scoreEl = document.getElementById('score');
  const preset = document.getElementById('preset');
  const gradeBtn = document.getElementById('btn-grade');
  let assignment = null;

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

  function genBody() {
    return {
      title: 'Browser qualification homework',
      passages: [document.getElementById('passage').value || 'practice passage'],
      subject: 'science',
      max_items: Number(document.getElementById('max-items').value) || 6,
      difficulty: document.getElementById('difficulty').value || 'medium',
    };
  }

  function renderAssignment(data) {
    assignment = data.assignment || data;
    const items = assignment.items || [];
    scoreEl.textContent = items.length + ' items ready — fill answers then grade';
    itemsEl.innerHTML = '';
    items.forEach((it, idx) => {
      const wrap = document.createElement('div');
      wrap.className = 'item';
      const mid = it.methodology_id || it.type || ('item-' + idx);
      const prompt = it.prompt || it.question || it.stem || '(no prompt)';
      wrap.innerHTML = '<div class="qid">' + mid + '</div><div class="prompt"></div>';
      wrap.querySelector('.prompt').textContent = prompt;
      const input = document.createElement('input');
      input.dataset.idx = String(idx);
      input.placeholder = 'Your answer';
      if (Array.isArray(it.choices) && it.choices.length) {
        const sel = document.createElement('select');
        sel.dataset.idx = String(idx);
        const blank = document.createElement('option');
        blank.value = ''; blank.textContent = 'Select…';
        sel.appendChild(blank);
        it.choices.forEach((c) => {
          const o = document.createElement('option');
          o.value = typeof c === 'string' ? c : (c.id || c.label || JSON.stringify(c));
          o.textContent = typeof c === 'string' ? c : (c.label || c.id || o.value);
          sel.appendChild(o);
        });
        wrap.appendChild(sel);
      } else {
        wrap.appendChild(input);
      }
      itemsEl.appendChild(wrap);
    });
    gradeBtn.disabled = items.length === 0;
  }

  function collectAnswers() {
    const answers = [];
    itemsEl.querySelectorAll('[data-idx]').forEach((el) => {
      answers.push(el.value);
    });
    return answers;
  }

  async function loadMethods() {
    const data = await api('GET', '/api/homework/methodologies');
    methodsEl.innerHTML = '<div class="m"><strong>' + data.count + '</strong> shown / '
      + data.total_registered + ' registered</div>';
    (data.methodologies || []).slice(0, 40).forEach((m) => {
      const row = document.createElement('div');
      row.className = 'm';
      row.innerHTML = '<strong></strong> · ';
      row.querySelector('strong').textContent = m.id;
      row.appendChild(document.createTextNode(m.family + ' — ' + m.label));
      methodsEl.appendChild(row);
    });
    if ((data.methodologies || []).length > 40) {
      const more = document.createElement('div');
      more.className = 'm';
      more.textContent = '… and ' + (data.methodologies.length - 40) + ' more';
      methodsEl.appendChild(more);
    }
  }

  async function loadTuning() {
    const data = await api('GET', '/api/homework/tuning');
    preset.innerHTML = '';
    (data.presets || []).forEach((name) => {
      const opt = document.createElement('option');
      opt.value = name; opt.textContent = name; preset.appendChild(opt);
    });
  }

  async function run(fn) {
    try {
      const data = await fn();
      show(data);
      return data;
    } catch (err) {
      show('Error: ' + (err && err.message ? err.message : err));
      throw err;
    }
  }

  document.getElementById('btn-health').onclick = () => run(() => api('GET', '/health'));
  document.getElementById('btn-methods').onclick = () => run(async () => { await loadMethods(); return api('GET', '/api/homework/methodologies'); });
  document.getElementById('btn-tel').onclick = () => run(() => api('GET', '/api/homework/telemetry'));
  document.getElementById('btn-preset').onclick = () => run(() => api('POST', '/api/homework/tuning/preset/' + encodeURIComponent(preset.value)));
  document.getElementById('btn-gold').onclick = () => run(() => api('POST', '/api/homework/eval/gold'));
  document.getElementById('btn-gen').onclick = () => run(async () => {
    const data = await api('POST', '/api/homework/generate', genBody());
    renderAssignment(data);
    return data;
  });
  document.getElementById('btn-battery').onclick = () => run(async () => {
    const data = await api('POST', '/api/homework/generate/battery', genBody());
    renderAssignment(data);
    return data;
  });
  document.getElementById('btn-grade').onclick = () => run(async () => {
    if (!assignment) throw new Error('Generate an assignment first');
    const data = await api('POST', '/api/homework/grade', { assignment, answers: collectAnswers() });
    const pct = data.report && typeof data.report.percentage === 'number'
      ? data.report.percentage + '%'
      : (data.report && typeof data.report.score === 'number'
        ? Math.round(data.report.score * 100) + '%'
        : 'see report');
    scoreEl.textContent = 'Grade result: ' + pct;
    return data;
  });

  loadMethods().catch((err) => { methodsEl.textContent = String(err); });
  loadTuning().catch(() => {});
"""
