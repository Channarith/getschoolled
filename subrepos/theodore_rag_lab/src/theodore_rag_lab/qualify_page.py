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
  label.stack { display:flex; flex-direction:column; align-items:stretch; gap:.3rem; width:100%; }
  label.stack select { width:100%; }
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
  .drop-zone { border:1px dashed var(--accent); border-radius:12px; min-height:7rem; padding:1rem;
    color:var(--muted); display:flex; align-items:center; justify-content:center; text-align:center; }
  .drop-zone.hot { background:#0c4a6e; color:var(--ink); }
  .layout.voice-layout { grid-template-columns:minmax(300px,460px) 1fr; }
  .pool-list { max-height:24rem; overflow:auto; border:1px solid var(--line); border-radius:12px;
    padding:.2rem .45rem; margin-bottom:.75rem; background:#0b1220; }
  .pool-list label { color:var(--ink); width:100%; padding:.4rem .15rem; margin:0; border-bottom:1px solid var(--line); }
  .pool-list label:last-child { border-bottom:0; }
  .pool-list .count { margin-left:auto; color:var(--muted); white-space:nowrap; font-size:.78rem; }
  #vq-amount { flex:1; min-width:14rem; }
  #vq-status-line { color:var(--ink); font-size:1.02rem; line-height:1.45; margin:0 0 .8rem; }
  details.more { margin:.15rem 0 .8rem; }
  details.more summary { cursor:pointer; color:var(--muted); }
"""

_HTML = """
  <header>
    <h1>Theodore RAG Lab</h1>
    <p>Tune curriculum RAG, grow the dictionary corpus, queue multi-language YouTube voice
       training, practice read-aloud pronunciation, browse slang/idioms, rehearse world dialects,
       run regurgitation drills, and export dictionary rows into the LLM training assemble path.
       Drop links, media, and databases on the Drop training tab, or pass the same
       paths to the command line. Voice training uses that intake too.</p>
    <div class="meta" id="meta-pills"><span class="pill">offline</span><span class="pill">port 8095</span></div>
  </header>
  <nav class="tabs" id="tabs">
    <button type="button" data-tab="rag" class="active">RAG tuning</button>
    <button type="button" data-tab="corpus">Corpus + read-aloud</button>
    <button type="button" data-tab="voice">Voice training</button>
    <button type="button" data-tab="drop">Drop training</button>
    <button type="button" data-tab="current">Current awareness</button>
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

  <div class="layout tab-panel hidden" id="panel-corpus">
    <aside class="panel">
      <h2>Dictionary corpus</h2>
      <div class="row">
        <button class="primary" id="btn-corpus-stats" type="button">Stats</button>
        <button id="btn-corpus-update" type="button">Train-update</button>
      </div>
      <div class="row">
        <button id="btn-corpus-review" type="button">Review queue</button>
        <button id="btn-corpus-export-llm" type="button">Export LLM JSONL</button>
      </div>
      <div class="meta">Ingest baselines, route hard rows, rebuild sentences, clean audio. Feeds llm_training.assemble (dictionary source).</div>
      <h2>Read-aloud</h2>
      <div class="row">
        <label class="stack">Language
          <select id="ra-lang" class="lang-select"><option>Loading languages…</option></select>
        </label>
        <button class="primary" id="btn-ra-next" type="button">Next sentence</button>
      </div>
      <div class="card" id="ra-card">
        <div id="ra-sentence" class="meta">Press Next sentence after train-update.</div>
        <div class="row" style="margin-top:.6rem"><input id="ra-heard" placeholder="Type what you said…" style="flex:1;min-width:12rem" /></div>
        <div class="row"><button class="primary" id="btn-ra-score" type="button">Score</button></div>
        <div id="ra-result" class="meta"></div>
      </div>
    </aside>
    <main class="panel">
      <h2>Corpus / score output</h2>
      <pre class="out" id="out-corpus">Run train-update to seed the dictionary corpus.</pre>
    </main>
  </div>

  <div class="layout voice-layout tab-panel hidden" id="panel-voice">
    <aside class="panel">
      <h2>Languages</h2>
      <div class="row">
        <button id="btn-vq-all" type="button">Check all</button>
        <button id="btn-vq-none" type="button">Clear</button>
      </div>
      <div id="vq-pools" class="pool-list"></div>
      <h2>How much</h2>
      <div class="row">
        <select id="vq-amount">
          <option value="sample" selected>A sample — 2 videos from 1 channel</option>
          <option value="channel">One full channel per language</option>
          <option value="all">Every video in the checked languages</option>
        </select>
      </div>
      <p class="meta" id="vq-amount-note">Downloads 2 videos from the first channel of each language you checked.</p>
      <div class="row">
        <label><input id="vq-news" type="checkbox" /> Include large news channels</label>
      </div>
      <details class="more">
        <summary>Parallel downloads</summary>
        <div class="row" style="margin-top:.45rem">
          <label>At once <input id="vq-workers" type="number" min="1" max="12" value="1" style="width:4rem" /></label>
        </div>
      </details>
      <div class="row">
        <button class="primary" id="btn-vq-start" type="button">Start training</button>
        <button id="btn-vq-stop" type="button">Stop</button>
      </div>
    </aside>
    <main class="panel">
      <h2>Progress</h2>
      <p id="vq-status-line">Open this tab to choose languages.</p>
      <pre class="out" id="out-voice">Progress from each channel appears here.</pre>
    </main>
  </div>

  <div class="layout tab-panel hidden" id="panel-drop">
    <aside class="panel">
      <h2>Drop into training</h2>
      <div id="drop-zone" class="drop-zone">Drop links, videos, audio, channel lists, Vimeo, news pages, notes, or databases here</div>
      <div class="row" style="margin-top:.7rem">
        <textarea id="drop-links" placeholder="Or paste links, one per line&#10;https://www.youtube.com/@channel&#10;https://vimeo.com/123&#10;https://example.com/news"></textarea>
      </div>
      <div class="row">
        <label class="stack">Language
          <select id="drop-lang" class="lang-select"><option>Loading languages…</option></select>
        </label>
        <label>Channel cap <input id="drop-expand" type="number" min="0" max="500" value="20" style="width:4.5rem" /></label>
        <label><input id="drop-fetch" type="checkbox" /> Read page text</label>
      </div>
      <div class="row">
        <input id="drop-file" type="file" multiple />
      </div>
      <div class="row">
        <button class="primary" id="btn-drop-add" type="button">Add to training</button>
        <button id="btn-drop-status" type="button">Status</button>
        <button id="btn-drop-train" type="button">Train dropped voice</button>
      </div>
      <div class="meta">YouTube and Vimeo, including a channel or playlist, go to the voice list. News links, notes, CSV, JSON, and SQLite go to RAG. Drag the same files onto the shell: python3 scripts/training_drop.py &lt;paths and links&gt;</div>
    </aside>
    <main class="panel">
      <h2>Intake</h2>
      <pre class="out" id="out-drop">Drop something to stage it. Nothing is downloaded until Train dropped voice.</pre>
    </main>
  </div>

  <div class="layout tab-panel hidden" id="panel-current">
    <aside class="panel">
      <h2>Research a current question</h2>
      <div class="row">
        <textarea id="current-question">Who is the current president of the United States?</textarea>
      </div>
      <div class="row">
        <button class="primary" id="btn-current-research" type="button">Search trusted sources</button>
      </div>
      <div class="meta">Live-only: trusted pages are read transiently, checked for independent corroboration, and never stored in the long-lived RAG corpus.</div>
    </aside>
    <main class="panel">
      <h2>Fresh evidence and citations</h2>
      <pre class="out" id="out-current">Ask about current leaders, global events, announcements, or recent sports results.</pre>
    </main>
  </div>

  <div class="layout tab-panel hidden" id="panel-dict">
    <aside class="panel">
      <h2>Search dictionary</h2>
      <div class="row"><input id="dict-q" placeholder="phrase or meaning" style="flex:1;min-width:10rem" /></div>
      <div class="row">
        <label class="stack">Language
          <select id="dict-lang" class="lang-select" data-any="1"><option>Loading languages…</option></select>
        </label>
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
      <div class="row"><label class="stack">Language and dialect <select id="dialect-id"></select></label></div>
      <div class="row"><label class="stack">Speaker voice <select id="dialect-voice"></select></label></div>
      <div class="row"><textarea id="dialect-text">Welcome! We will walk through the lesson. Take your time. Nice work.</textarea></div>
      <div class="row">
        <button class="primary" id="btn-dialect-listen" type="button">Listen</button>
        <button id="btn-sala-listen" type="button">Hear Sala</button>
        <button id="btn-dialect-stop" type="button">Stop</button>
      </div>
      <div class="row">
        <button id="btn-dialect-probe" type="button">Humanize</button>
        <button id="btn-dialect-catalog" type="button">Catalog</button>
      </div>
      <div class="meta" id="dialect-audio-state">Listen plays this line on your speakers in the selected dialect voice. Hear Sala plays a local Sala preview. The microphone chip does not open an xAI session.</div>
      <div class="meta">Test Southern, NYC, New England, California, Canadian, British, Australian, Singaporean, Beijing, Shanghai, Cantonese, Fujianese, and more. British, Australian, and Cantonese use different neural voices. US regions share American neural voices and change the wording.</div>
    </aside>
    <main class="panel">
      <h2>Output</h2>
      <pre class="out" id="out-dialect">Pick a dialect and probe narration tone + matched voices.</pre>
    </main>
  </div>

  <div class="layout tab-panel hidden" id="panel-drill">
    <aside class="panel">
      <h2>Regurgitation deck</h2>
      <div class="row"><label class="stack">Language and dialect <select id="drill-dialect"></select></label></div>
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
        <label class="stack">Language
          <select id="fb-lang" class="lang-select"><option>Loading languages…</option></select>
        </label>
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
  let voiceGroups = [];
  let previewAudio = null;

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
    if (name === 'voice') loadVoiceCatalog().catch((err) => {
      const line = document.getElementById('vq-status-line');
      if (line) line.textContent = err && err.message ? err.message : String(err);
    });
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
  const outCurrent = document.getElementById('out-current');
  document.getElementById('btn-current-research').onclick = () => run(
    outCurrent,
    () => api('POST', '/api/current-awareness/research', {
      question: document.getElementById('current-question').value,
    }),
  );

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = String(s ?? '');
    return d.innerHTML;
  }

  function renderEntries(payload) {
    const box = document.getElementById('out-dict');
    const stats = payload.stats || {};
    const entries = payload.entries || payload.sample || [];
    let html = '<div class="meta">total=' + (stats.total || '?') +
      ' packs=' + (stats.from_packs || '?') + ' learned=' + (stats.learned || 0) + '</div>';
    entries.forEach((e) => {
      html += '<div class="card"><strong>' + esc(e.phrase) + '</strong> · ' + esc(e.kind) +
        ' · <span class="pill">' + esc(e.language) + '/' + esc(e.region) + '</span><div>' + esc(e.meaning) + '</div></div>';
    });
    box.innerHTML = html || '<div class="meta">No hits.</div>';
  }

  document.getElementById('btn-dict-search').onclick = async () => {
    try {
      const q = new URLSearchParams({
        q: document.getElementById('dict-q').value || '',
        language: chosenLanguage('dict-lang', 'language'),
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

  let languageCatalog = [];
  function varietyByDialect(dialectId) {
    return languageCatalog.find((row) => row.dialect && row.dialect === dialectId);
  }
  function chosenLanguage(id, field) {
    const sel = document.getElementById(id);
    const opt = sel && sel.selectedOptions && sel.selectedOptions[0];
    if (!opt) return field === 'language' ? '' : 'en';
    if (field === 'whisper') return opt.dataset.whisper || opt.dataset.language || 'en';
    if (field === 'dialect') return opt.dataset.dialect || '';
    return opt.dataset.language || '';
  }
  function fillLanguageSelects(list) {
    languageCatalog = list || [];
    document.querySelectorAll('select.lang-select').forEach((sel) => {
      const previous = sel.value;
      sel.innerHTML = '';
      if (sel.dataset.any === '1') {
        const any = document.createElement('option');
        any.value = '';
        any.dataset.language = '';
        any.dataset.whisper = '';
        any.dataset.dialect = '';
        any.textContent = 'Any language';
        sel.appendChild(any);
      }
      languageCatalog.forEach((row) => {
        const opt = document.createElement('option');
        opt.value = row.id;
        opt.dataset.language = row.language || '';
        opt.dataset.whisper = row.whisper || row.language || '';
        opt.dataset.dialect = row.dialect || '';
        opt.textContent = row.label;
        sel.appendChild(opt);
      });
      const known = previous && [...sel.options].some((opt) => opt.value === previous);
      if (known) sel.value = previous;
      else if (sel.dataset.any === '1') sel.value = '';
      else if ([...sel.options].some((opt) => opt.value === 'en_us')) sel.value = 'en_us';
    });
  }
  function fillDialectSelects(list) {
    ['dialect-id', 'drill-dialect'].forEach((id) => {
      const sel = document.getElementById(id);
      sel.innerHTML = '';
      (list || []).forEach((d) => {
        const named = varietyByDialect(d.id);
        const opt = document.createElement('option');
        opt.value = d.id;
        opt.dataset.language = (named && named.language) || d.language || 'en';
        opt.textContent = (named && named.label) || d.label;
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
    fillVoiceSelect();
  }
  function fillVoiceSelect() {
    const dialect = document.getElementById('dialect-id').value;
    const language = document.getElementById('dialect-id').selectedOptions[0]?.dataset.language || 'en';
    const all = voiceGroups.flatMap((group) => group.voices || []);
    let rows = all.filter((voice) => voice.dialect === dialect);
    if (!rows.length) rows = all.filter((voice) => voice.language === language).slice(0, 4);
    const sel = document.getElementById('dialect-voice');
    const previous = sel.value;
    sel.innerHTML = '';
    rows.forEach((voice) => {
      const opt = document.createElement('option');
      opt.value = voice.id;
      opt.dataset.locale = voice.locale || '';
      opt.textContent = voice.label;
      sel.appendChild(opt);
    });
    if ([...sel.options].some((opt) => opt.value === previous)) sel.value = previous;
  }
  function stopPreview() {
    window.speechSynthesis?.cancel();
    if (previewAudio) {
      previewAudio.pause();
      try { URL.revokeObjectURL(previewAudio.src); } catch (_) {}
      previewAudio = null;
    }
  }
  function deviceSpeak(text, locale) {
    const stateEl = document.getElementById('dialect-audio-state');
    if (!window.speechSynthesis) {
      stateEl.textContent = 'No speaker voice is available in this browser.';
      return;
    }
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = locale || 'en-US';
    const voices = window.speechSynthesis.getVoices() || [];
    const want = utter.lang.toLowerCase();
    const match = voices.find((voice) => (voice.lang || '').toLowerCase() === want)
      || voices.find((voice) => (voice.lang || '').toLowerCase().startsWith(want.slice(0, 2)));
    if (match) utter.voice = match;
    utter.onend = () => { stateEl.textContent = 'Finished on the device speaker.'; };
    window.speechSynthesis.speak(utter);
    stateEl.textContent = 'Playing on the device speaker (' + utter.lang + ').';
  }
  async function listenDialect(kind) {
    const stateEl = document.getElementById('dialect-audio-state');
    const text = document.getElementById('dialect-text').value.trim();
    if (!text) { stateEl.textContent = 'Type a line to hear.'; return; }
    stopPreview();
    const dialect = document.getElementById('dialect-id').value;
    const language = document.getElementById('dialect-id').selectedOptions[0]?.dataset.language || 'en';
    const voiceSel = document.getElementById('dialect-voice');
    const voice = kind === 'sala' ? 'sala' : (voiceSel.value || '');
    const locale = kind === 'sala' ? 'en-US' : (voiceSel.selectedOptions[0]?.dataset.locale || 'en-US');
    const label = kind === 'sala' ? 'Salane Voice' : (voiceSel.selectedOptions[0]?.textContent || 'dialect voice');
    let spoken = text;
    stateEl.textContent = 'Preparing ' + label + '…';
    try {
      if (kind !== 'sala') {
        const probe = await api('POST', '/api/dialects/probe', {
          dialect, text, language, title: 'Practice',
        });
        spoken = (probe.humanized || text).trim();
        show(document.getElementById('out-dialect'), probe);
      }
      const res = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          text: spoken,
          language: kind === 'sala' ? 'en' : language,
          voice,
        }),
      });
      if (res.ok) {
        const engine = res.headers.get('X-TTS-Engine') || 'server';
        const note = res.headers.get('X-TTS-Note') || '';
        const blob = await res.blob();
        previewAudio = new Audio(URL.createObjectURL(blob));
        previewAudio.onended = () => { stateEl.textContent = label + ' finished.'; };
        stateEl.textContent = 'Playing ' + label + ' · ' + engine + (note ? ' · ' + note : '');
        await previewAudio.play();
        return;
      }
      let detail = '';
      try { detail = (await res.json()).detail || ''; } catch (_) {}
      stateEl.textContent = (detail || 'Server voice unavailable.') + ' Using the device speaker.';
    } catch (err) {
      stateEl.textContent = 'Server voice unavailable. Using the device speaker.';
    }
    deviceSpeak(spoken, locale);
  }

  document.getElementById('dialect-id').addEventListener('change', fillVoiceSelect);
  document.getElementById('btn-dialect-listen').onclick = () => listenDialect('dialect');
  document.getElementById('btn-sala-listen').onclick = () => listenDialect('sala');
  document.getElementById('btn-dialect-stop').onclick = () => {
    stopPreview();
    document.getElementById('dialect-audio-state').textContent = 'Stopped.';
  };
  document.getElementById('btn-dialect-catalog').onclick = () => run(document.getElementById('out-dialect'), () => api('GET', '/api/dialects'));
  document.getElementById('btn-dialect-probe').onclick = () => run(document.getElementById('out-dialect'), () => api('POST', '/api/dialects/probe', {
    dialect: document.getElementById('dialect-id').value,
    text: document.getElementById('dialect-text').value,
    language: document.getElementById('dialect-id').selectedOptions[0]?.dataset.language || 'en',
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
    language: chosenLanguage('fb-lang', 'language') || 'en',
    dialect: chosenLanguage('fb-lang', 'dialect'),
    region: document.getElementById('fb-region').value || 'global',
    action: document.getElementById('fb-action').value,
    kind: 'idiom',
  }));

  const outVoice = document.getElementById('out-voice');
  const poolLabels = {};
  let voicePoolKey = '';
  let voiceTimer = null;
  function selectedPools() {
    return Array.from(document.querySelectorAll('#vq-pools input:checked')).map((el) => el.value);
  }
  function voiceStartBody() {
    const amount = document.getElementById('vq-amount').value;
    const body = {
      pools: selectedPools(),
      workers: Number(document.getElementById('vq-workers').value) || 1,
      max_urls: null,
      max_channels: null,
      include_news: document.getElementById('vq-news').checked,
    };
    if (amount === 'sample') {
      body.max_urls = 2;
      body.max_channels = 1;
    } else if (amount === 'channel') {
      body.max_channels = 1;
    }
    return body;
  }
  function languageNames(ids) {
    if (!ids || !ids.length) return 'the languages you checked';
    return ids.map((id) => poolLabels[id] || id).join(', ');
  }
  function describeQueue(data) {
    const q = (data && data.queue) || {};
    const names = languageNames(q.pools || []);
    if (q.running && q.phase === 'discover') return 'Finding channels for ' + names + '.';
    if (q.running) {
      const now = (q.current || []).join(', ');
      let line = 'Training ' + names + '. ' + (q.done || 0) + ' of ' + (q.queued || 0) + ' channels done.';
      if (now) line += ' Working on ' + now + '.';
      return line;
    }
    if (q.stopped) return 'Stopped after ' + (q.ok || 0) + ' channels. ' + (q.failed || 0) + ' failed.';
    if (q.done) {
      return 'Finished ' + (q.ok || 0) + ' of ' + (q.queued || 0) + ' channels.' + (q.failed ? ' ' + q.failed + ' failed.' : '');
    }
    return 'Check the languages you want, then start training.';
  }
  function renderVoice(data) {
    document.getElementById('vq-status-line').textContent = describeQueue(data);
    const log = (((data || {}).queue || {}).log || []).slice(-12);
    outVoice.textContent = log.length ? log.join('\\n') : 'Progress from each channel appears here.';
  }
  function renderPoolList(pools) {
    const box = document.getElementById('vq-pools');
    const keep = new Set(selectedPools());
    box.innerHTML = '';
    pools.forEach((pool) => {
      poolLabels[pool.pool_id] = pool.label || pool.pool_id;
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = pool.pool_id;
      input.checked = keep.has(pool.pool_id);
      const name = document.createElement('span');
      name.textContent = pool.label || pool.pool_id;
      const count = document.createElement('span');
      count.className = 'count';
      const videos = pool.videos == null ? '—' : Number(pool.videos).toLocaleString();
      count.textContent = videos + ' videos';
      label.appendChild(input);
      label.appendChild(name);
      label.appendChild(count);
      box.appendChild(label);
    });
    if (!pools.length) box.textContent = 'No language lists found.';
  }
  async function loadVoiceCatalog() {
    const data = await api('GET', '/api/voice/queue');
    const key = (data.pools || []).map((pool) => pool.pool_id + ':' + pool.videos + ':' + pool.channels).join('|');
    if (key !== voicePoolKey) {
      voicePoolKey = key;
      renderPoolList(data.pools || []);
    }
    renderVoice(data);
    if (data.queue && data.queue.running) watchVoice();
    else if (voiceTimer) { clearInterval(voiceTimer); voiceTimer = null; }
    return data;
  }
  function watchVoice() {
    if (voiceTimer) return;
    voiceTimer = setInterval(() => {
      const panel = document.getElementById('panel-voice');
      if (!panel || panel.classList.contains('hidden')) return;
      loadVoiceCatalog().catch(() => {});
    }, 3000);
  }
  const amountNotes = {
    sample: 'Downloads 2 videos from the first channel of each language you checked.',
    channel: 'Downloads every video from the first channel of each language you checked.',
    all: 'Downloads every video from every channel in the languages you checked. This can be millions of videos.',
  };
  document.getElementById('vq-amount').onchange = () => {
    document.getElementById('vq-amount-note').textContent = amountNotes[document.getElementById('vq-amount').value] || '';
  };
  document.getElementById('btn-vq-all').onclick = () => {
    document.querySelectorAll('#vq-pools input').forEach((el) => { el.checked = true; });
  };
  document.getElementById('btn-vq-none').onclick = () => {
    document.querySelectorAll('#vq-pools input').forEach((el) => { el.checked = false; });
  };
  document.getElementById('btn-vq-start').onclick = async () => {
    const line = document.getElementById('vq-status-line');
    if (!selectedPools().length) {
      line.textContent = 'Check at least one language. Starting does not train every language.';
      return;
    }
    const btn = document.getElementById('btn-vq-start');
    btn.disabled = true;
    try {
      await api('POST', '/api/voice/queue/start', voiceStartBody());
      await loadVoiceCatalog();
    } catch (err) {
      line.textContent = err && err.message ? err.message : String(err);
    } finally {
      btn.disabled = false;
    }
  };
  document.getElementById('btn-vq-stop').onclick = async () => {
    const line = document.getElementById('vq-status-line');
    try {
      await api('POST', '/api/voice/queue/stop');
      await loadVoiceCatalog();
    } catch (err) {
      line.textContent = err && err.message ? err.message : String(err);
    }
  };

  const outDrop = document.getElementById('out-drop');
  const dropZone = document.getElementById('drop-zone');
  function dropOptions() {
    return {
      language: chosenLanguage('drop-lang', 'whisper') || 'en',
      expand_limit: Number(document.getElementById('drop-expand').value || '20'),
      fetch_pages: document.getElementById('drop-fetch').checked,
    };
  }
  async function submitDrop(fileList, linkText) {
    const opts = dropOptions();
    const files = Array.from(fileList || []);
    const text = (linkText || '').trim();
    if (!files.length) {
      const links = text.split(/\\s+/).filter(Boolean);
      if (!links.length) throw new Error('Drop a file or paste a link first.');
      return api('POST', '/api/training/drop', Object.assign({ links }, opts));
    }
    const body = new FormData();
    body.append('links', text);
    body.append('language', opts.language);
    body.append('expand_limit', String(opts.expand_limit));
    body.append('fetch_pages', opts.fetch_pages ? 'true' : 'false');
    files.forEach((file) => body.append('files', file, file.name));
    const res = await fetch('/api/training/drop/upload', { method: 'POST', body });
    const raw = await res.text();
    let data;
    try { data = JSON.parse(raw); } catch { data = raw; }
    if (!res.ok) throw new Error((data && data.detail) || raw || res.statusText);
    return data;
  }
  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('hot'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('hot'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('hot');
    const text = e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain') || '';
    const pasted = document.getElementById('drop-links').value;
    run(outDrop, () => submitDrop(e.dataTransfer.files, [text, pasted].filter(Boolean).join('\\n')));
  });
  document.getElementById('btn-drop-add').onclick = () => run(outDrop, () => submitDrop(
    document.getElementById('drop-file').files,
    document.getElementById('drop-links').value
  ));
  document.getElementById('btn-drop-status').onclick = () => run(outDrop, () => api('GET', '/api/training/drop'));
  document.getElementById('btn-drop-train').onclick = () => run(outDrop, () => api('POST', '/api/training/drop/train'));

  let raPrompt = null;
  const outCorpus = document.getElementById('out-corpus');
  document.getElementById('btn-corpus-stats').onclick = () => run(outCorpus, () => api('GET', '/api/corpus/stats'));
  document.getElementById('btn-corpus-update').onclick = () => run(outCorpus, () => api('POST', '/api/corpus/train-update', { force: false, language: 'en' }));
  document.getElementById('btn-corpus-review').onclick = () => run(outCorpus, () => api('GET', '/api/corpus/review?limit=30'));
  document.getElementById('btn-corpus-export-llm').onclick = () => run(outCorpus, () => api('POST', '/api/corpus/export-llm'));
  document.getElementById('btn-ra-next').onclick = async () => {
    try {
      raPrompt = await api('POST', '/api/read-aloud/next', {
        language: chosenLanguage('ra-lang', 'language') || 'en',
        learner_id: 'lab',
      });
      document.getElementById('ra-sentence').textContent = '[' + (raPrompt.difficulty || '?') + '] ' + (raPrompt.sentence || '');
      document.getElementById('ra-heard').value = '';
      document.getElementById('ra-result').textContent = (raPrompt.targets || []).map((t) => t.form).join(', ');
      show(outCorpus, raPrompt);
    } catch (err) { show(outCorpus, 'Error: ' + (err && err.message ? err.message : err)); }
  };
  document.getElementById('btn-ra-score').onclick = async () => {
    if (!raPrompt) { show(outCorpus, 'Get a sentence first.'); return; }
    try {
      const forms = (raPrompt.targets || []).map((t) => t.form);
      const res = await api('POST', '/api/read-aloud/score', {
        sentence: raPrompt.sentence,
        heard: document.getElementById('ra-heard').value,
        target_forms: forms,
        language: chosenLanguage('ra-lang', 'language') || 'en',
        learner_id: 'lab',
      });
      const el = document.getElementById('ra-result');
      el.className = res.score >= 60 ? 'score-ok' : 'score-bad';
      el.textContent = 'score=' + res.score + ' · ' + (res.feedback || '');
      show(outCorpus, res);
    } catch (err) { show(outCorpus, 'Error: ' + (err && err.message ? err.message : err)); }
  };

  (async function boot() {
    try {
      const health = await api('GET', '/health');
      const pills = document.getElementById('meta-pills');
      const corp = health.corpus || {};
      const en = (corp.languages && corp.languages.en) || {};
      pills.innerHTML = '<span class="pill">offline tuning</span><span class="pill">port 8095</span>' +
        '<span class="pill">current awareness ' + (health.current_awareness_live ? 'live' : 'needs search key') + '</span>' +
        '<span class="pill">lexicon ' + (health.lexicon_total || 0) + '</span>' +
        '<span class="pill">corpus en ' + (en.total || 0) + '</span>' +
        '<span class="pill">dialects ' + (health.dialects || 0) + '</span>';
      const cat = await api('GET', '/api/dialects');
      featured = cat.featured_dialects || [];
      voiceGroups = cat.voices || [];
      fillLanguageSelects(cat.languages || []);
      fillDialectSelects(cat.dialects || []);
      window.speechSynthesis?.getVoices();
      await refreshTuning();
      renderEntries(await api('GET', '/api/dictionary?limit=24'));
    } catch (err) {
      knobs.textContent = String(err);
    }
  })();
"""
