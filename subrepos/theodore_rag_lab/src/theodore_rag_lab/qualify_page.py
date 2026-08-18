"""Embedded browser console for the RAG lab — tuning, dictionary, dialects, drills."""

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
  :root { --bg:#0f172a; --panel:#1e293b; --ink:#f1f5f9; --muted:#94a3b8; --accent:#38bdf8;
    --ok:#4ade80; --line:#334155; --warn:#fbbf24; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; color:var(--ink); font-family:"IBM Plex Sans","Segoe UI",sans-serif;
    background:
      linear-gradient(160deg, rgba(15,23,42,.92), rgba(15,23,42,.97)),
      radial-gradient(800px 420px at 10% 0%, #164e63 0%, transparent 55%),
      radial-gradient(600px 360px at 100% 0%, #1e3a5f 0%, transparent 50%),
      var(--bg); }
  header { padding:1.2rem 1.5rem .4rem; }
  header h1 { margin:0; font-size:1.65rem; font-weight:700; letter-spacing:-.02em; }
  header p { margin:.35rem 0 0; color:var(--muted); max-width:52rem; line-height:1.45; }
  .tabs { display:flex; flex-wrap:wrap; gap:.35rem; padding:.5rem 1.5rem 0; }
  .tabs button { border:1px solid var(--line); background:#0b1220; color:var(--muted);
    border-radius:999px; padding:.4rem .9rem; cursor:pointer; font:inherit; }
  .tabs button.active { color:var(--ink); border-color:var(--accent); background:#0c4a6e; font-weight:700; }
  .layout { display:grid; gap:1rem; padding:1rem 1.5rem 2rem; grid-template-columns:minmax(260px,340px) 1fr; }
  @media (max-width:960px){ .layout { grid-template-columns:1fr; } }
  .panel { background:color-mix(in srgb, var(--panel) 92%, black); border:1px solid var(--line); border-radius:14px; padding:1rem; }
  .panel h2 { margin:0 0 .75rem; font-size:.95rem; color:var(--accent); text-transform:uppercase; letter-spacing:.04em; }
  .row { display:flex; flex-wrap:wrap; gap:.45rem; margin-bottom:.65rem; align-items:center; }
  button, select, input, textarea { font:inherit; border-radius:10px; border:1px solid var(--line);
    background:#0b1220; color:var(--ink); padding:.45rem .75rem; }
  textarea { width:100%; min-height:4.5rem; resize:vertical; }
  button { cursor:pointer; }
  button.primary { background:#0369a1; border-color:var(--accent); font-weight:700; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  label { color:var(--muted); font-size:.85rem; display:flex; gap:.4rem; align-items:center; }
  .knobs, .out, .list { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.8rem; line-height:1.45; }
  .knobs { color:#d7e6ff; white-space:pre-wrap; }
  .out { margin:0; min-height:20rem; max-height:68vh; overflow:auto; padding:.85rem; border-radius:12px;
    background:#070d18; border:1px solid var(--line); color:#cfe3ff; white-space:pre-wrap; }
  .meta { color:var(--muted); font-size:.85rem; margin-top:.35rem; }
  .pill { display:inline-block; margin:.1rem .3rem .1rem 0; padding:.15rem .5rem; border-radius:999px;
    border:1px solid var(--line); color:var(--ok); font-size:.75rem; }
  .card { border:1px solid var(--line); border-radius:12px; padding:.75rem; margin-bottom:.55rem; background:#0b1220; }
  .card strong { color:var(--accent); }
  .hidden { display:none !important; }
  .score-ok { color:var(--ok); font-weight:700; }
  .score-bad { color:var(--warn); font-weight:700; }
"""

_HTML = """
  <header>
    <h1>Theodore RAG Lab</h1>
    <p>Tune curriculum RAG, browse an extensive slang/idiom dictionary, rehearse world dialects
       (Southern, NYC, New England, California, Canadian, British, Australian, Singaporean,
       Beijing, Shanghai, Guangzhou Cantonese, Fujianese, and more), run regurgitation drills,
       and grow the lexicon with feedback learning.</p>
    <div class="meta" id="meta-pills"><span class="pill">offline</span><span class="pill">port 8095</span></div>
  </header>
  <nav class="tabs" id="tabs">
    <button type="button" data-tab="rag" class="active">RAG tuning</button>
    <button type="button" data-tab="dict">Dictionary</button>
    <button type="button" data-tab="dialect">Dialects</button>
    <button type="button" data-tab="drill">Regurgitation</button>
    <button type="button" data-tab="feedback">Feedback learning</button>
  </nav>

  <div class="layout tab-panel" id="panel-rag">
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
      <pre class="out" id="out-rag">Click an action to qualify RAG tuning.</pre>
    </main>
  </div>

  <div class="layout tab-panel hidden" id="panel-dict">
    <aside class="panel">
      <h2>Search dictionary</h2>
      <div class="row"><input id="dict-q" placeholder="phrase or meaning" style="flex:1;min-width:10rem" /></div>
      <div class="row">
        <label>Lang <input id="dict-lang" placeholder="en/zh" style="width:4rem" /></label>
        <label>Region <input id="dict-region" placeholder="us-south" style="width:7rem" /></label>
        <label>Kind <select id="dict-kind"><option value="">any</option><option>idiom</option><option>slang</option></select></label>
      </div>
      <div class="row">
        <button class="primary" id="btn-dict-search" type="button">Search</button>
        <button id="btn-dict-browse" type="button">Browse stats</button>
      </div>
      <div class="meta">More idioms and slang → more mature tutoring.</div>
    </aside>
    <main class="panel">
      <h2>Entries</h2>
      <div id="out-dict" class="list"></div>
    </main>
  </div>

  <div class="layout tab-panel hidden" id="panel-dialect">
    <aside class="panel">
      <h2>Dialect probe</h2>
      <div class="row"><label>Dialect <select id="dialect-id"></select></label></div>
      <div class="row"><textarea id="dialect-text">Welcome! We will walk through the lesson. Take your time. Nice work.</textarea></div>
      <div class="row">
        <button class="primary" id="btn-dialect-probe" type="button">Humanize</button>
        <button id="btn-dialect-catalog" type="button">Catalog</button>
      </div>
      <div class="meta">Test Southern, NYC, New England, California, Canadian, British, Australian, Singaporean, Beijing, Shanghai, Cantonese, Fujianese, and more.</div>
    </aside>
    <main class="panel">
      <h2>Output</h2>
      <pre class="out" id="out-dialect">Pick a dialect and probe narration tone + matched voices.</pre>
    </main>
  </div>

  <div class="layout tab-panel hidden" id="panel-drill">
    <aside class="panel">
      <h2>Regurgitation deck</h2>
      <div class="row"><label>Dialect <select id="drill-dialect"></select></label></div>
      <div class="row">
        <label>Cards <input id="drill-n" type="number" min="3" max="20" value="6" style="width:4rem" /></label>
        <button class="primary" id="btn-drill-deal" type="button">Deal deck</button>
      </div>
      <div class="meta">Recall the plain meaning. Hits reinforce feedback learning.</div>
      <div id="drill-card" class="card hidden">
        <div><strong id="drill-phrase"></strong></div>
        <div class="meta" id="drill-meta"></div>
        <div class="row" style="margin-top:.6rem"><input id="drill-answer" placeholder="Your meaning…" style="flex:1;min-width:12rem" /></div>
        <div class="row">
          <button class="primary" id="btn-drill-grade" type="button">Grade</button>
          <button id="btn-drill-next" type="button">Next</button>
        </div>
        <div id="drill-result" class="meta"></div>
      </div>
    </aside>
    <main class="panel">
      <h2>Deck</h2>
      <pre class="out" id="out-drill">Deal a deck to start regurgitation practice.</pre>
    </main>
  </div>

  <div class="layout tab-panel hidden" id="panel-feedback">
    <aside class="panel">
      <h2>Teach the dictionary</h2>
      <div class="row"><input id="fb-phrase" placeholder="phrase" style="flex:1;min-width:8rem" /></div>
      <div class="row"><input id="fb-meaning" placeholder="plain meaning" style="flex:1;min-width:8rem" /></div>
      <div class="row">
        <label>Lang <input id="fb-lang" value="en" style="width:3.5rem" /></label>
        <label>Region <input id="fb-region" value="global" style="width:6rem" /></label>
        <label>Action <select id="fb-action"><option>correct</option><option>confirm</option><option>reject</option></select></label>
      </div>
      <div class="row">
        <button class="primary" id="btn-fb-submit" type="button">Submit feedback</button>
        <button id="btn-fb-refresh" type="button">Refresh</button>
      </div>
    </aside>
    <main class="panel">
      <h2>Learned</h2>
      <pre class="out" id="out-feedback">Feedback learning folds corrections into the live lexicon.</pre>
    </main>
  </div>
"""

_JS = """
  const tabs = document.getElementById('tabs');
  const knobs = document.getElementById('knobs');
  const preset = document.getElementById('preset');
  let drillCards = [];
  let drillIdx = 0;
  let featured = [];

  function show(el, data) {
    el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
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

  function switchTab(name) {
    document.querySelectorAll('.tabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('hidden', p.id !== 'panel-' + name));
  }
  tabs.onclick = (e) => {
    const b = e.target.closest('button[data-tab]');
    if (b) switchTab(b.dataset.tab);
  };

  async function refreshTuning() {
    const data = await api('GET', '/api/rag/tuning');
    knobs.textContent = JSON.stringify(data.knobs, null, 2);
    preset.innerHTML = '';
    (data.presets || []).forEach((name) => {
      const opt = document.createElement('option');
      opt.value = name; opt.textContent = name; preset.appendChild(opt);
    });
  }

  async function run(el, fn) {
    try { show(el, await fn()); await refreshTuning().catch(()=>{}); }
    catch (err) { show(el, 'Error: ' + (err && err.message ? err.message : err)); }
  }

  const outRag = document.getElementById('out-rag');
  document.getElementById('btn-health').onclick = () => run(outRag, () => api('GET', '/health'));
  document.getElementById('btn-eval').onclick = () => run(outRag, () => api('POST', '/api/rag/eval?details=false'));
  document.getElementById('btn-sweep').onclick = () => run(outRag, () => api('GET', '/api/rag/sweep'));
  document.getElementById('btn-tuning').onclick = () => run(outRag, () => api('GET', '/api/rag/tuning'));
  document.getElementById('btn-preset').onclick = () => run(outRag, () => api('POST', '/api/rag/tuning/preset/' + encodeURIComponent(preset.value)));
  document.getElementById('btn-block').onclick = () => run(outRag, () => api('POST', '/api/rag/train/run-blocking', { hours: Number(document.getElementById('hours').value) || 0.01 }));
  document.getElementById('btn-start').onclick = () => run(outRag, () => api('POST', '/api/rag/train/start', { hours: Number(document.getElementById('hours').value) || 1 }));
  document.getElementById('btn-status').onclick = () => run(outRag, () => api('GET', '/api/rag/train/status'));
  document.getElementById('btn-stop').onclick = () => run(outRag, () => api('POST', '/api/rag/train/stop'));
  document.getElementById('btn-champ').onclick = () => run(outRag, () => api('GET', '/api/rag/champion'));
  document.getElementById('btn-tel').onclick = () => run(outRag, () => api('GET', '/api/rag/telemetry'));

  function renderEntries(payload) {
    const box = document.getElementById('out-dict');
    const stats = payload.stats || {};
    const entries = payload.entries || payload.sample || [];
    let html = '<div class="meta">total=' + (stats.total || '?') +
      ' packs=' + (stats.from_packs || '?') + ' learned=' + (stats.learned || 0) + '</div>';
    entries.forEach((e) => {
      html += '<div class="card"><strong>' + e.phrase + '</strong> · ' + e.kind +
        ' · <span class="pill">' + e.language + '/' + e.region + '</span><div>' + e.meaning + '</div></div>';
    });
    box.innerHTML = html || '<div class="meta">No hits.</div>';
  }

  document.getElementById('btn-dict-search').onclick = async () => {
    try {
      const q = new URLSearchParams({
        q: document.getElementById('dict-q').value || '',
        language: document.getElementById('dict-lang').value || '',
        region: document.getElementById('dict-region').value || '',
        kind: document.getElementById('dict-kind').value || '',
        limit: '60',
      });
      renderEntries(await api('GET', '/api/dictionary?' + q.toString()));
    } catch (err) { document.getElementById('out-dict').textContent = String(err); }
  };
  document.getElementById('btn-dict-browse').onclick = async () => {
    try { renderEntries(await api('GET', '/api/dictionary?limit=40')); }
    catch (err) { document.getElementById('out-dict').textContent = String(err); }
  };

  function fillDialectSelects(list) {
    ['dialect-id', 'drill-dialect'].forEach((id) => {
      const sel = document.getElementById(id);
      sel.innerHTML = '';
      (list || []).forEach((d) => {
        const opt = document.createElement('option');
        opt.value = d.id; opt.textContent = d.label + ' (' + d.id + ')';
        sel.appendChild(opt);
      });
    });
    if (featured.length) {
      const prefer = featured[0];
      const d1 = document.getElementById('dialect-id');
      const d2 = document.getElementById('drill-dialect');
      if ([...d1.options].some((o) => o.value === prefer)) d1.value = prefer;
      if ([...d2.options].some((o) => o.value === prefer)) d2.value = prefer;
    }
  }

  document.getElementById('btn-dialect-catalog').onclick = () => run(document.getElementById('out-dialect'), () => api('GET', '/api/dialects'));
  document.getElementById('btn-dialect-probe').onclick = () => run(document.getElementById('out-dialect'), () => api('POST', '/api/dialects/probe', {
    dialect: document.getElementById('dialect-id').value,
    text: document.getElementById('dialect-text').value,
    language: 'en',
    title: 'Practice',
  }));

  function showDrillCard() {
    const card = drillCards[drillIdx];
    const wrap = document.getElementById('drill-card');
    if (!card) { wrap.classList.add('hidden'); return; }
    wrap.classList.remove('hidden');
    document.getElementById('drill-phrase').textContent = card.phrase;
    document.getElementById('drill-meta').textContent = (card.language || '') + '/' + (card.region || '') + ' · ' + (card.kind || '') + ' · card ' + (drillIdx+1) + '/' + drillCards.length;
    document.getElementById('drill-answer').value = '';
    document.getElementById('drill-result').textContent = '';
  }

  document.getElementById('btn-drill-deal').onclick = async () => {
    try {
      const dialect = document.getElementById('drill-dialect').value;
      const n = Number(document.getElementById('drill-n').value) || 6;
      const data = await api('GET', '/api/regurgitate/deck?dialect=' + encodeURIComponent(dialect) + '&n=' + n);
      drillCards = data.cards || [];
      drillIdx = 0;
      show(document.getElementById('out-drill'), data);
      showDrillCard();
    } catch (err) { show(document.getElementById('out-drill'), String(err)); }
  };
  document.getElementById('btn-drill-next').onclick = () => {
    if (!drillCards.length) return;
    drillIdx = (drillIdx + 1) % drillCards.length;
    showDrillCard();
  };
  document.getElementById('btn-drill-grade').onclick = async () => {
    const card = drillCards[drillIdx];
    if (!card) return;
    try {
      const res = await api('POST', '/api/regurgitate/grade', {
        phrase: card.phrase,
        answer: document.getElementById('drill-answer').value,
        language: card.language,
        region: card.region,
        dialect: document.getElementById('drill-dialect').value,
        learn: true,
      });
      const el = document.getElementById('drill-result');
      el.className = res.ok ? 'score-ok' : 'score-bad';
      el.textContent = (res.ok ? 'OK ' : 'MISS ') + 'score=' + res.score + ' · ' + res.detail + ' · expected: ' + res.expected;
    } catch (err) {
      document.getElementById('drill-result').textContent = String(err);
    }
  };

  document.getElementById('btn-fb-refresh').onclick = () => run(document.getElementById('out-feedback'), () => api('GET', '/api/feedback'));
  document.getElementById('btn-fb-submit').onclick = () => run(document.getElementById('out-feedback'), () => api('POST', '/api/feedback', {
    phrase: document.getElementById('fb-phrase').value,
    meaning: document.getElementById('fb-meaning').value,
    language: document.getElementById('fb-lang').value || 'en',
    region: document.getElementById('fb-region').value || 'global',
    action: document.getElementById('fb-action').value,
    kind: 'idiom',
  }));

  (async function boot() {
    try {
      const health = await api('GET', '/health');
      const pills = document.getElementById('meta-pills');
      pills.innerHTML = '<span class="pill">offline</span><span class="pill">port 8095</span>' +
        '<span class="pill">lexicon ' + (health.lexicon_total || 0) + '</span>' +
        '<span class="pill">dialects ' + (health.dialects || 0) + '</span>';
      const cat = await api('GET', '/api/dialects');
      featured = cat.featured_dialects || [];
      fillDialectSelects(cat.dialects || []);
      await refreshTuning();
      renderEntries(await api('GET', '/api/dictionary?limit=24'));
    } catch (err) {
      knobs.textContent = String(err);
    }
  })();
"""
