"""Embedded Music Lab player — featured songs with audio, lyrics, animation."""

from __future__ import annotations


def render_music_page() -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>Theodore Music Lab</title>\n"
        "  <style>\n"
        + _CSS
        + "\n  </style>\n</head>\n<body>\n"
        + _HTML
        + "\n  <script>\n"
        + _JS
        + "\n  </script>\n</body>\n</html>\n"
    )


_CSS = """
  :root { --bg:#0f172a; --panel:#1e293b; --ink:#f8fafc; --muted:#94a3b8; --accent:#38bdf8; --warm:#fbbf24; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; color:var(--ink); font-family:"Trebuchet MS","Segoe UI",sans-serif;
    background: radial-gradient(1200px 600px at 10% -10%, #1d4ed6 0%, transparent 55%),
                radial-gradient(900px 500px at 100% 0%, #0ea5e9 0%, transparent 50%), var(--bg); }
  header { padding:1.25rem 1.5rem .5rem; }
  header h1 { margin:0; font-size:1.75rem; }
  header p { margin:.35rem 0 0; color:var(--muted); max-width:42rem; }
  .layout { display:grid; gap:1rem; padding:1rem 1.5rem 2rem; grid-template-columns:minmax(220px,280px) 1fr; }
  @media (max-width:900px){ .layout { grid-template-columns:1fr; } }
  .panel { background:color-mix(in srgb, var(--panel) 92%, black); border:1px solid #334155; border-radius:18px; padding:1rem; }
  .panel h2 { margin:0 0 .75rem; font-size:1rem; color:var(--accent); }
  .song-card { display:block; width:100%; text-align:left; margin:0 0 .55rem; padding:.75rem .85rem;
    border-radius:12px; cursor:pointer; background:#0f172a; border:1px solid #334155; color:var(--ink); }
  .song-card.active { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }
  .song-card strong { display:block; }
  .song-card span { color:var(--muted); font-size:.8rem; }
  .stage { position:relative; overflow:hidden; border-radius:18px; min-height:220px;
    background:linear-gradient(160deg,#0c4a6e,#1e293b 55%,#0f172a); border:1px solid #334155;
    display:grid; place-items:center; }
  .stage[data-anim="travel"]{ background:linear-gradient(160deg,#0369a1,#0f766e 60%,#0f172a); }
  .stage[data-anim="bus"]{ background:linear-gradient(160deg,#b45309,#ea580c 45%,#0f172a); }
  .stage[data-anim="words"]{ background:linear-gradient(160deg,#7c3aed,#2563eb 55%,#0f172a); }
  .orb { width:120px; height:120px; border-radius:50%;
    background:radial-gradient(circle at 30% 30%,#fff,var(--accent) 45%,transparent 70%); opacity:.85; }
  .stage.playing .orb { animation:bounce 1.1s ease-in-out infinite; }
  .stage.playing[data-anim="bus"] .orb { animation:spin 2.4s linear infinite; }
  .stage.playing[data-anim="travel"] .orb { animation:slide 2s ease-in-out infinite; }
  .stage.playing[data-anim="words"] .orb { animation:pulse 1.4s ease-in-out infinite; }
  .symbol { position:absolute; font-size:4rem; text-shadow:0 8px 24px rgba(0,0,0,.35); }
  .stage.playing .symbol { animation:bob 1.2s ease-in-out infinite; }
  @keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-18px)} }
  @keyframes spin { to { transform:rotate(360deg) } }
  @keyframes slide { 0%,100%{transform:translateX(-24px)} 50%{transform:translateX(24px)} }
  @keyframes pulse { 0%,100%{transform:scale(1);opacity:.75} 50%{transform:scale(1.18);opacity:1} }
  @keyframes bob { 0%,100%{transform:translateY(0) scale(1)} 50%{transform:translateY(-10px) scale(1.05)} }
  .controls { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; margin-top:.85rem; }
  button, select { font:inherit; border-radius:10px; border:1px solid #475569; background:#0f172a; color:var(--ink); padding:.45rem .8rem; cursor:pointer; }
  button.primary { background:#0284c7; border-color:#38bdf8; font-weight:700; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  audio { width:100%; margin-top:.65rem; }
  .lyrics { margin-top:.85rem; max-height:280px; overflow:auto; padding:.75rem; border-radius:14px; background:#0f172a; border:1px solid #334155; }
  .line { padding:.35rem .5rem; border-radius:8px; color:var(--muted); transition:background .2s,color .2s,transform .2s; }
  .line.active { background:color-mix(in srgb, var(--warm) 22%, transparent); color:var(--ink); font-weight:700; transform:scale(1.01); }
  .line .section { font-size:.7rem; text-transform:uppercase; letter-spacing:.06em; color:var(--accent); }
  .meaning { margin-top:.75rem; padding:.75rem .9rem; border-radius:12px; background:#122033; border:1px solid #334155; min-height:3rem; }
  .meta { color:var(--muted); font-size:.85rem; margin-top:.35rem; }
  .toast { position:fixed; right:1rem; bottom:1rem; display:none; background:#0f766e; border:1px solid #5eead4; padding:.7rem .9rem; border-radius:10px; }
  .toast.show { display:block; }
"""

_HTML = """
  <header>
    <h1>Theodore Music Lab</h1>
    <p>Play featured learning songs with animation and line-by-line lyrics.
       Pick a meaning language (26+) to see educational glosses while you listen.</p>
  </header>
  <div class="layout">
    <aside class="panel">
      <h2>Featured songs</h2>
      <div id="song-list">Loading…</div>
      <div class="meta" id="catalog-meta"></div>
    </aside>
    <main class="panel">
      <h2 id="now-title">Choose a song</h2>
      <div class="meta" id="now-meta"></div>
      <div class="stage" id="stage" data-anim="pulse">
        <div class="orb" aria-hidden="true"></div>
        <div class="symbol" id="stage-symbol">♪</div>
      </div>
      <div class="controls">
        <button class="primary" id="btn-play" type="button" disabled>Play</button>
        <button id="btn-pause" type="button" disabled>Pause</button>
        <button id="btn-restart" type="button" disabled>Restart</button>
        <label>Meaning <select id="meaning-lang"></select></label>
      </div>
      <audio id="player" controls preload="metadata"></audio>
      <div class="lyrics" id="lyrics"></div>
      <div class="meaning" id="meaning">Meaning / translation will appear here.</div>
    </main>
  </div>
  <div class="toast" id="toast"></div>
"""

_JS = r"""
  const $ = (id) => document.getElementById(id);
  const SYMBOLS = { travel: "✈️", bus: "🚌", words: "🔤", pulse: "♪" };
  let featured = [];
  let current = null;
  let lineTimers = [];

  function toast(msg) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2200);
  }
  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
  function clearLineTimers() {
    lineTimers.forEach((t) => clearTimeout(t));
    lineTimers = [];
  }
  function esc(s) {
    return String(s || "").replace(/[&<>"']/g, (c) => (
      ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[c]
    ));
  }
  function renderSongList() {
    const box = $("song-list");
    box.innerHTML = featured.map((s) => `
      <button type="button" class="song-card ${current && current.song_id === s.song_id ? "active" : ""}"
        data-id="${s.song_id}">
        <strong>${esc(s.title_en)}</strong>
        <span>${esc(s.topic)} · ${s.line_count} lines · MP3</span>
      </button>`).join("") || "<div class='meta'>No featured songs found.</div>";
    box.querySelectorAll(".song-card").forEach((btn) => {
      btn.onclick = () => selectSong(btn.getAttribute("data-id"));
    });
  }
  async function selectSong(songId) {
    clearLineTimers();
    const player = $("player");
    player.pause();
    current = await api("/api/music/songs/" + encodeURIComponent(songId));
    $("now-title").textContent = current.title_en;
    $("now-meta").textContent = `${current.topic} · ${current.lines.length} lines · ${current.license}`;
    const anim = current.animation || "pulse";
    $("stage").dataset.anim = anim;
    $("stage").classList.remove("playing");
    $("stage-symbol").textContent = SYMBOLS[anim] || "♪";
    player.src = current.audio_url || "";
    $("btn-play").disabled = !player.src;
    $("btn-pause").disabled = !player.src;
    $("btn-restart").disabled = !player.src;
    renderLyrics(0);
    await refreshMeaning(1);
    renderSongList();
    toast("Loaded " + current.title_en);
  }
  function renderLyrics(activeNo) {
    if (!current) return;
    $("lyrics").innerHTML = current.lines.map((line) => `
      <div class="line ${line.line_no === activeNo ? "active" : ""}" data-no="${line.line_no}">
        ${line.section ? `<div class="section">${esc(line.section)}</div>` : ""}
        ${esc(line.text)}
      </div>`).join("");
    const active = $("lyrics").querySelector(".line.active");
    if (active) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  async function refreshMeaning(lineNo) {
    if (!current) return;
    const lang = $("meaning-lang").value || "en";
    const line = current.lines.find((l) => l.line_no === lineNo) || current.lines[0];
    if (!line) return;
    try {
      const data = await api("/api/music/meaning", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ song_id: current.song_id, line_no: line.line_no, target_lang: lang }),
      });
      const m = data.meaning || {};
      $("meaning").textContent = `${m.target_language_name || lang}: ${m.text || line.meaning_en || line.text}`;
    } catch (_) {
      $("meaning").textContent = line.meaning_en || line.text;
    }
  }
  function scheduleLineHighlights() {
    clearLineTimers();
    if (!current || !current.lines.length) return;
    const player = $("player");
    const duration = (Number.isFinite(player.duration) && player.duration > 0)
      ? player.duration
      : (current.duration_hint_sec || Math.max(30, current.lines.length * 2.2));
    const slice = duration / current.lines.length;
    const start = player.currentTime || 0;
    current.lines.forEach((line, idx) => {
      const delay = Math.max(0, (idx * slice - start) * 1000);
      lineTimers.push(setTimeout(() => {
        renderLyrics(line.line_no);
        refreshMeaning(line.line_no);
      }, delay));
    });
  }
  $("btn-play").onclick = async () => {
    const player = $("player");
    if (!player.src) return;
    try {
      await player.play();
      $("stage").classList.add("playing");
      scheduleLineHighlights();
    } catch (_) {
      toast("Could not play audio — click Play again after interacting");
    }
  };
  $("btn-pause").onclick = () => {
    $("player").pause();
    $("stage").classList.remove("playing");
    clearLineTimers();
  };
  $("btn-restart").onclick = async () => {
    const player = $("player");
    player.currentTime = 0;
    clearLineTimers();
    renderLyrics(1);
    await refreshMeaning(1);
    await player.play();
    $("stage").classList.add("playing");
    scheduleLineHighlights();
  };
  $("player").addEventListener("ended", () => { $("stage").classList.remove("playing"); clearLineTimers(); });
  $("player").addEventListener("pause", () => { if (!$("player").ended) $("stage").classList.remove("playing"); });
  $("player").addEventListener("play", () => { $("stage").classList.add("playing"); });
  $("meaning-lang").onchange = () => {
    const active = $("lyrics").querySelector(".line.active");
    refreshMeaning(active ? +active.getAttribute("data-no") : 1);
  };
  (async function boot() {
    const langs = await api("/api/music/languages");
    $("meaning-lang").innerHTML = (langs.languages || []).map((code) =>
      `<option value="${esc(code)}">${esc(code)}</option>`).join("");
    $("meaning-lang").value = "es";
    const data = await api("/api/music/featured");
    featured = data.songs || [];
    $("catalog-meta").textContent =
      `${featured.length} featured with audio · ${data.meaning_language_count || 26}+ meaning languages`;
    renderSongList();
    if (featured[0]) await selectSong(featured[0].song_id);
  })().catch((e) => toast(String(e.message || e)));
"""
