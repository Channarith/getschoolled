"""Embedded Music Lab player.

Featured MP3s with a karaoke bouncing ball, word-level highlighting, a
per-line translation always visible in any of the 26+ languages, an Ask-AI box
that works while the track plays, short lyric clips, and curated lyric videos.
"""

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
  :root { --bg:#0f172a; --panel:#1e293b; --ink:#f8fafc; --muted:#94a3b8; --accent:#38bdf8;
          --warm:#fbbf24; --good:#34d399; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; color:var(--ink); font-family:"Trebuchet MS","Segoe UI",sans-serif;
    background: radial-gradient(1200px 600px at 10% -10%, #1d4ed6 0%, transparent 55%),
                radial-gradient(900px 500px at 100% 0%, #0ea5e9 0%, transparent 50%), var(--bg); }
  header { padding:1.25rem 1.5rem .5rem; }
  header h1 { margin:0; font-size:1.75rem; }
  header p { margin:.35rem 0 0; color:var(--muted); max-width:46rem; }
  .layout { display:grid; gap:1rem; padding:1rem 1.5rem 2rem; grid-template-columns:minmax(230px,290px) 1fr; }
  .layout > .stack { display:grid; gap:1rem; align-content:start; }
  .bottom { display:grid; gap:1rem; grid-template-columns:1fr 1fr; }
  @media (max-width:980px){ .layout { grid-template-columns:1fr; } .bottom { grid-template-columns:1fr; } }
  .panel { background:color-mix(in srgb, var(--panel) 92%, black); border:1px solid #334155;
    border-radius:18px; padding:1rem; }
  .panel h2 { margin:0 0 .75rem; font-size:1rem; color:var(--accent); }
  .song-card { display:block; width:100%; text-align:left; margin:0 0 .55rem; padding:.75rem .85rem;
    border-radius:12px; cursor:pointer; background:#0f172a; border:1px solid #334155; color:var(--ink); }
  .song-card.active { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }
  .song-card strong { display:block; }
  .song-card span { color:var(--muted); font-size:.8rem; }
  .stage { position:relative; overflow:hidden; border-radius:18px; min-height:180px;
    background:linear-gradient(160deg,#0c4a6e,#1e293b 55%,#0f172a); border:1px solid #334155;
    display:grid; place-items:center; }
  .stage[data-anim="travel"]{ background:linear-gradient(160deg,#0369a1,#0f766e 60%,#0f172a); }
  .stage[data-anim="bus"]{ background:linear-gradient(160deg,#b45309,#ea580c 45%,#0f172a); }
  .stage[data-anim="words"]{ background:linear-gradient(160deg,#7c3aed,#2563eb 55%,#0f172a); }
  .orb { width:110px; height:110px; border-radius:50%;
    background:radial-gradient(circle at 30% 30%,#fff,var(--accent) 45%,transparent 70%); opacity:.85; }
  .stage.playing .orb { animation:bounce 1.1s ease-in-out infinite; }
  .stage.playing[data-anim="bus"] .orb { animation:spin 2.4s linear infinite; }
  .stage.playing[data-anim="travel"] .orb { animation:slide 2s ease-in-out infinite; }
  .stage.playing[data-anim="words"] .orb { animation:pulse 1.4s ease-in-out infinite; }
  .symbol { position:absolute; font-size:3.4rem; text-shadow:0 8px 24px rgba(0,0,0,.35); }
  .stage.playing .symbol { animation:bob 1.2s ease-in-out infinite; }
  @keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-18px)} }
  @keyframes spin { to { transform:rotate(360deg) } }
  @keyframes slide { 0%,100%{transform:translateX(-24px)} 50%{transform:translateX(24px)} }
  @keyframes pulse { 0%,100%{transform:scale(1);opacity:.75} 50%{transform:scale(1.18);opacity:1} }
  @keyframes bob { 0%,100%{transform:translateY(0) scale(1)} 50%{transform:translateY(-10px) scale(1.05)} }
  @keyframes ballhop { 0%,100%{transform:translateY(0) scale(1)} 45%{transform:translateY(-9px) scale(1.12)} }
  .controls { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; margin-top:.85rem; }
  .controls label { color:var(--muted); font-size:.85rem; display:inline-flex; gap:.35rem; align-items:center; }
  button, select, input[type=text] { font:inherit; border-radius:10px; border:1px solid #475569;
    background:#0f172a; color:var(--ink); padding:.45rem .8rem; }
  button { cursor:pointer; }
  button.primary { background:#0284c7; border-color:#38bdf8; font-weight:700; }
  button.ghost { padding:.3rem .6rem; font-size:.8rem; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  audio { width:100%; margin-top:.65rem; }
  .lyrics { position:relative; margin-top:.85rem; max-height:320px; overflow:auto; padding:1.6rem .75rem .75rem;
    border-radius:14px; background:#0f172a; border:1px solid #334155; }
  .line { padding:.4rem .5rem .3rem; border-radius:10px; transition:background .2s; }
  .line.active { background:color-mix(in srgb, var(--accent) 14%, transparent); }
  .line .section { font-size:.66rem; text-transform:uppercase; letter-spacing:.08em; color:var(--accent); opacity:.8; }
  .line .words { color:var(--muted); font-size:1.05rem; line-height:1.9; }
  .line.active .words { color:var(--ink); }
  .w { padding:.05rem .18rem; border-radius:6px; transition:color .15s, background .15s; }
  .w.sung { color:var(--warm); }
  .w.now { background:var(--warm); color:#0f172a; font-weight:800; }
  .line.done .words { color:color-mix(in srgb, var(--warm) 70%, #64748b); }
  .line .tr { font-size:.9rem; color:var(--good); margin-top:.1rem; }
  .line .tr:empty { display:none; }
  #ball { position:absolute; left:0; top:0; width:18px; height:18px; pointer-events:none; opacity:0;
    transition:transform .16s ease-out, opacity .2s; }
  #ball .dot { width:18px; height:18px; border-radius:50%; animation:ballhop .5s ease-in-out infinite;
    background:radial-gradient(circle at 32% 30%, #fff, var(--warm) 60%, #b45309);
    box-shadow:0 0 12px rgba(251,191,36,.7); }
  #ball.on { opacity:1; }
  .now-line { padding:.65rem .8rem; border-radius:12px; background:#122033; border:1px solid #334155; }
  .now-line .en { font-weight:700; }
  .now-line .target { color:var(--good); font-size:1.05rem; margin-top:.2rem; }
  .badge { display:inline-block; font-size:.68rem; text-transform:uppercase; letter-spacing:.06em;
    padding:.12rem .45rem; border-radius:999px; border:1px solid #475569; color:var(--muted); margin-left:.4rem; }
  .badge.curated { color:#a7f3d0; border-color:#34d399; }
  .badge.llm, .badge.cached { color:#bfdbfe; border-color:#60a5fa; }
  .badge.lexicon { color:#fde68a; border-color:#fbbf24; }
  .chips { display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.55rem; }
  .chip { font-size:.8rem; padding:.25rem .55rem; border-radius:999px; background:#0f172a; border:1px solid #475569; }
  .chip b { color:var(--good); font-weight:700; }
  .examples { margin:.6rem 0 0; padding-left:1.1rem; color:var(--muted); font-size:.88rem; }
  .examples li { margin:.15rem 0; }
  .ask-row { display:flex; gap:.5rem; margin-top:.5rem; }
  .ask-row input { flex:1; }
  .answer { margin-top:.65rem; padding:.7rem .85rem; border-radius:12px; background:#0f172a;
    border:1px solid #334155; white-space:pre-wrap; min-height:3rem; }
  .clip { display:block; width:100%; text-align:left; margin:0 0 .45rem; padding:.55rem .7rem;
    border-radius:10px; background:#0f172a; border:1px solid #334155; color:var(--ink); cursor:pointer; }
  .clip strong { display:block; font-size:.92rem; }
  .clip span { color:var(--muted); font-size:.76rem; }
  .clip.active { border-color:var(--warm); box-shadow:0 0 0 1px var(--warm); }
  .videos { display:grid; gap:.6rem; }
  .video { padding:.7rem .85rem; border-radius:12px; background:#0f172a; border:1px solid #334155; }
  .video strong { display:block; }
  .video p { margin:.25rem 0 .5rem; color:var(--muted); font-size:.85rem; }
  .video a { color:var(--accent); margin-right:.9rem; }
  .video iframe { width:100%; aspect-ratio:16/9; border:0; border-radius:10px; margin-top:.5rem; }
  .meta { color:var(--muted); font-size:.85rem; margin-top:.35rem; }
  .toast { position:fixed; right:1rem; bottom:1rem; display:none; background:#0f766e;
    border:1px solid #5eead4; padding:.7rem .9rem; border-radius:10px; }
  .toast.show { display:block; }
"""

_HTML = """
  <header>
    <h1>Theodore Music Lab</h1>
    <p>Follow the bouncing ball, watch each word light up as it is sung, and read the
       translation of every line in any of 26+ languages. Ask the AI about a line at
       any time — while the song is still playing.</p>
  </header>
  <div class="layout">
    <div class="stack">
      <aside class="panel">
        <h2>Featured songs</h2>
        <div id="song-list">Loading…</div>
        <div class="meta" id="catalog-meta"></div>
      </aside>
      <aside class="panel">
        <h2>Short lyric clips</h2>
        <div id="clip-list" class="meta">Loading…</div>
      </aside>
    </div>
    <div class="stack">
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
          <label>Translation <select id="meaning-lang"></select></label>
          <label><input type="checkbox" id="show-inline" checked /> Show every line</label>
          <label>Sync
            <button class="ghost" id="sync-back" type="button">−0.25s</button>
            <span id="sync-value">0.00s</span>
            <button class="ghost" id="sync-fwd" type="button">+0.25s</button>
          </label>
        </div>
        <audio id="player" controls preload="metadata"></audio>
        <div class="lyrics" id="lyrics">
          <div id="ball"><div class="dot"></div></div>
        </div>
        <div class="meta" id="tier-meta"></div>
      </main>
      <div class="bottom">
        <section class="panel">
          <h2>This line, translated</h2>
          <div class="now-line" id="now-line">Press play — the current line and its
            translation appear here.</div>
          <div class="chips" id="now-vocab"></div>
          <ul class="examples" id="now-examples"></ul>
        </section>
        <section class="panel">
          <h2>Ask the AI about the lyrics</h2>
          <div class="meta" id="ask-context">No line selected yet.</div>
          <div class="ask-row">
            <input type="text" id="ask-input" placeholder="e.g. Why does it say 'go round and round'?" />
            <button class="primary" id="ask-send" type="button">Ask</button>
          </div>
          <div class="chips" id="ask-quick"></div>
          <div class="answer" id="ask-answer">Answers stay grounded in the lyrics of the
            line you are on.</div>
        </section>
      </div>
      <section class="panel">
        <h2>Lyric videos</h2>
        <div class="videos" id="video-list">Loading…</div>
      </section>
    </div>
  </div>
  <div class="toast" id="toast"></div>
"""

_JS = r"""
  const $ = (id) => document.getElementById(id);
  const SYMBOLS = { travel: "\u2708\uFE0F", bus: "\uD83D\uDE8C", words: "\uD83D\uDD24", pulse: "\u266A" };
  const QUICK_ASKS = [
    "What does this line mean?",
    "How do I say this in my language?",
    "Why is it worded this way?",
    "How do I pronounce it?",
  ];

  let featured = [];
  let current = null;
  let timings = null;
  let translation = null;
  let clips = [];
  let syncOffset = 0;
  let activeLineNo = 0;
  let activeWordKey = "";
  let activeClip = null;
  let rafId = 0;
  const trCache = new Map();

  function toast(msg) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2400);
  }
  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
  function post(path, body) {
    return api(path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
  }
  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, (c) => (
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
    ));
  }
  function lang() { return $("meaning-lang").value || "en"; }
  function trRow(lineNo) {
    if (!translation) return null;
    return translation.lines.find((r) => r.line_no === lineNo) || null;
  }

  /* ---------- rendering ---------- */

  function renderSongList() {
    const box = $("song-list");
    box.innerHTML = featured.map((s) => `
      <button type="button" class="song-card ${current && current.song_id === s.song_id ? "active" : ""}"
        data-id="${esc(s.song_id)}">
        <strong>${esc(s.title_en)}</strong>
        <span>${esc(s.topic)} \u00b7 ${s.line_count} lines \u00b7 MP3</span>
      </button>`).join("") || "<div class='meta'>No featured songs found.</div>";
    box.querySelectorAll(".song-card").forEach((btn) => {
      btn.onclick = () => selectSong(btn.getAttribute("data-id"));
    });
  }

  function renderLyrics() {
    if (!current || !timings) return;
    const inline = $("show-inline").checked;
    const rows = timings.lines.map((row) => {
      const words = row.words.map((w) =>
        `<span class="w" data-no="${row.line_no}" data-i="${w.index}">${esc(w.text)}</span>`
      ).join(" ");
      const tr = inline ? esc((trRow(row.line_no) || {}).translation || "") : "";
      return `<div class="line" data-no="${row.line_no}">
        ${row.section ? `<div class="section">${esc(row.section)}</div>` : ""}
        <div class="words">${words}</div>
        <div class="tr">${tr}</div>
      </div>`;
    }).join("");
    const box = $("lyrics");
    box.innerHTML = `<div id="ball"><div class="dot"></div></div>` + rows;
    box.querySelectorAll(".line").forEach((el) => {
      el.onclick = () => {
        const no = Number(el.getAttribute("data-no"));
        const row = timings.lines.find((r) => r.line_no === no);
        if (row) $("player").currentTime = Math.max(0, row.start - syncOffset);
        setActiveLine(no, true);
      };
    });
    activeLineNo = 0;
    activeWordKey = "";
  }

  function renderTierMeta() {
    if (!translation) { $("tier-meta").textContent = ""; return; }
    const t = translation.tiers || {};
    const parts = Object.keys(t).map((k) => `${t[k]} ${k}`);
    const review = translation.needs_native_review ? " \u00b7 pending native review" : "";
    const llm = translation.llm_available ? "" : " \u00b7 set XAI_API_KEY for full-sentence machine translation";
    $("tier-meta").textContent =
      `${translation.language_name}: ${translation.line_count} lines translated (${parts.join(", ")})${review}${llm}`;
  }

  function renderNowLine(lineNo) {
    const row = trRow(lineNo);
    const timed = timings ? timings.lines.find((r) => r.line_no === lineNo) : null;
    if (!row || !timed) return;
    const tier = row.tier || "english";
    $("now-line").innerHTML =
      `<div class="en">${esc(row.text)}<span class="badge ${esc(tier)}">${esc(tier)}</span></div>
       <div class="target">${esc(row.translation)}</div>
       <div class="meta">${esc(row.note || "")}</div>`;
    const vocab = (row.vocabulary || []).filter((v) => v.target);
    $("now-vocab").innerHTML = vocab.map((v) =>
      `<span class="chip">${esc(v.en)} = <b>${esc(v.target)}</b></span>`).join("");
    const examples = (row.vocabulary || []).filter((v) => v.example_en).slice(0, 3);
    $("now-examples").innerHTML = examples.map((v) =>
      `<li>${esc(v.example_en)}</li>`).join("");
    $("ask-context").textContent = `Asking about line ${lineNo}: "${row.text}"`;
  }

  function renderClips() {
    const box = $("clip-list");
    if (!clips.length) { box.textContent = "No clips for this song."; return; }
    box.innerHTML = clips.map((c) => `
      <button type="button" class="clip ${activeClip && activeClip.clip_id === c.clip_id ? "active" : ""}"
        data-id="${esc(c.clip_id)}">
        <strong>${esc(c.title)}</strong>
        <span>${esc(c.focus)} \u00b7 ${Math.round(c.duration_sec)}s</span>
      </button>`).join("");
    box.querySelectorAll(".clip").forEach((btn) => {
      btn.onclick = () => playClip(btn.getAttribute("data-id"));
    });
  }

  function renderVideos(rows) {
    const box = $("video-list");
    if (!rows.length) { box.textContent = "No videos configured."; return; }
    box.innerHTML = rows.map((v) => `
      <div class="video" data-id="${esc(v.video_id)}">
        <strong>${esc(v.title)}<span class="badge">${esc(v.kind)}</span></strong>
        <p>${esc(v.note)}</p>
        <a href="${esc(v.url)}" target="_blank" rel="noopener">Watch on ${esc(v.provider)}</a>
        ${v.lyrics_url ? `<a href="${esc(v.lyrics_url)}" target="_blank" rel="noopener">Printed lyrics</a>` : ""}
        ${v.embed_url ? `<button class="ghost" type="button" data-embed="${esc(v.embed_url)}">Play here</button>` : ""}
        <div class="slot"></div>
      </div>`).join("");
    box.querySelectorAll("button[data-embed]").forEach((btn) => {
      btn.onclick = () => {
        const slot = btn.parentElement.querySelector(".slot");
        slot.innerHTML = `<iframe src="${btn.getAttribute("data-embed")}" allowfullscreen
          title="Lyric video" loading="lazy"></iframe>`;
        btn.disabled = true;
      };
    });
  }

  /* ---------- karaoke loop ---------- */

  /* Word classes are painted per frame for the active line only, so every line
     change must re-settle the others — otherwise jumping backwards leaves later
     lines looking already sung. */
  function repaintLineStates(lineNo, t) {
    const box = $("lyrics");
    box.querySelectorAll(".line").forEach((el) => {
      const no = Number(el.getAttribute("data-no"));
      const row = timings ? timings.lines.find((r) => r.line_no === no) : null;
      el.classList.toggle("active", no === lineNo);
      el.classList.toggle("done", !!row && no !== lineNo && row.end <= t);
      if (no !== lineNo) {
        el.querySelectorAll(".w").forEach((s) => s.classList.remove("now", "sung"));
      }
    });
  }

  function setActiveLine(lineNo, scroll) {
    if (lineNo === activeLineNo) return;
    activeLineNo = lineNo;
    const player = $("player");
    repaintLineStates(lineNo, player.currentTime + syncOffset);
    const el = $("lyrics").querySelector(`.line[data-no="${lineNo}"]`);
    if (el && scroll !== false) el.scrollIntoView({ block: "center", behavior: "smooth" });
    renderNowLine(lineNo);
  }

  function moveBall(span) {
    const ball = $("ball");
    if (!span) { ball.classList.remove("on"); return; }
    const x = span.offsetLeft + span.offsetWidth / 2 - 9;
    const y = span.offsetTop - 20;
    ball.style.transform = `translate(${x}px, ${y}px)`;
    ball.classList.add("on");
  }

  function paintWords(row, t) {
    const box = $("lyrics");
    let activeSpan = null;
    let key = "";
    row.words.forEach((w) => {
      const span = box.querySelector(`.w[data-no="${row.line_no}"][data-i="${w.index}"]`);
      if (!span) return;
      const isNow = t >= w.start && t < w.end;
      span.classList.toggle("now", isNow);
      span.classList.toggle("sung", t >= w.end);
      if (isNow) { activeSpan = span; key = `${row.line_no}:${w.index}`; }
    });
    if (!activeSpan && row.words.length) {
      const last = row.words[row.words.length - 1];
      if (t >= last.end) {
        activeSpan = box.querySelector(`.w[data-no="${row.line_no}"][data-i="${last.index}"]`);
        key = `${row.line_no}:${last.index}`;
      }
    }
    if (key !== activeWordKey) {
      activeWordKey = key;
      moveBall(activeSpan);
    }
  }

  function clearWordPaint() {
    const box = $("lyrics");
    box.querySelectorAll(".w").forEach((s) => s.classList.remove("now", "sung"));
    box.querySelectorAll(".line.done").forEach((el) => el.classList.remove("done"));
    activeWordKey = "";
    $("ball").classList.remove("on");
  }

  function tick() {
    const player = $("player");
    if (!timings) return;
    const t = player.currentTime + syncOffset;
    if (activeClip && player.currentTime >= activeClip.end_sec) {
      player.pause();
      activeClip = null;
      renderClips();
    }
    let row = timings.lines.find((r) => t >= r.start && t < r.end);
    if (!row && timings.lines.length) {
      row = t < timings.lines[0].start ? null : timings.lines[timings.lines.length - 1];
    }
    if (row) {
      setActiveLine(row.line_no, true);
      paintWords(row, t);
    } else {
      clearWordPaint();
    }
    if (!player.paused && !player.ended) rafId = requestAnimationFrame(tick);
  }

  function startLoop() {
    cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(tick);
  }

  /* ---------- data loading ---------- */

  async function loadTranslation() {
    if (!current) return;
    const key = `${current.song_id}|${lang()}`;
    if (trCache.has(key)) {
      translation = trCache.get(key);
    } else {
      translation = await post("/api/music/translate", {
        song_id: current.song_id, target_lang: lang(), allow_llm: true,
      });
      trCache.set(key, translation);
    }
    renderTierMeta();
  }

  async function loadClips() {
    if (!current) return;
    const data = await api(`/api/music/clips?song_id=${encodeURIComponent(current.song_id)}` +
      `&target_lang=${encodeURIComponent(lang())}`);
    clips = data.clips || [];
    renderClips();
  }

  async function loadTimings() {
    if (!current) return;
    const player = $("player");
    const duration = Number.isFinite(player.duration) && player.duration > 0 ? player.duration : 0;
    timings = await api(`/api/music/timing/${encodeURIComponent(current.song_id)}` +
      (duration ? `?duration=${duration.toFixed(2)}` : ""));
  }

  async function selectSong(songId) {
    const player = $("player");
    player.pause();
    cancelAnimationFrame(rafId);
    activeClip = null;
    current = await api("/api/music/songs/" + encodeURIComponent(songId));
    $("now-title").textContent = current.title_en;
    $("now-meta").textContent =
      `${current.topic} \u00b7 ${current.lines.length} lines \u00b7 ${current.license}`;
    const anim = current.animation || "pulse";
    $("stage").dataset.anim = anim;
    $("stage").classList.remove("playing");
    $("stage-symbol").textContent = SYMBOLS[anim] || "\u266A";
    player.src = current.audio_url || "";
    ["btn-play", "btn-pause", "btn-restart"].forEach((id) => { $(id).disabled = !player.src; });
    await loadTimings();
    await loadTranslation();
    renderLyrics();
    setActiveLine(current.lines[0] ? current.lines[0].line_no : 0, false);
    renderSongList();
    await Promise.all([loadClips(), loadVideos()]);
  }

  async function loadVideos() {
    const id = current ? current.song_id : "";
    const data = await api(`/api/music/videos?song_id=${encodeURIComponent(id)}`);
    renderVideos(data.videos || []);
  }

  async function playClip(clipId) {
    const clip = clips.find((c) => c.clip_id === clipId);
    if (!clip) return;
    const player = $("player");
    activeClip = clip;
    renderClips();
    player.currentTime = Math.max(0, clip.start_sec - syncOffset);
    try {
      await player.play();
      startLoop();
      toast(`Clip: ${clip.title}`);
    } catch (_) {
      toast("Tap play once, then choose the clip again");
    }
  }

  /* ---------- ask AI ---------- */

  async function askAI(question) {
    if (!current) return;
    const q = (question || $("ask-input").value || "").trim();
    if (!q) { toast("Type a question first"); return; }
    $("ask-answer").textContent = "Thinking\u2026";
    try {
      const data = await post("/api/music/ask", {
        song_id: current.song_id,
        question: q,
        line_no: activeLineNo || 1,
        target_lang: lang(),
      });
      const source = data.provider === "xai" ? "Grok" : "offline teacher";
      $("ask-answer").innerHTML = `${esc(data.answer)}
        <div class="meta">${esc(source)} \u00b7 grounded in lines ${data.cited_lines.join(", ")}</div>`;
    } catch (e) {
      $("ask-answer").textContent = String(e.message || e);
    }
  }

  /* ---------- wiring ---------- */

  $("btn-play").onclick = async () => {
    const player = $("player");
    if (!player.src) return;
    activeClip = null;
    try {
      await player.play();
      startLoop();
    } catch (_) {
      toast("Could not play audio \u2014 press Play again");
    }
  };
  $("btn-pause").onclick = () => { $("player").pause(); };
  $("btn-restart").onclick = async () => {
    const player = $("player");
    activeClip = null;
    player.currentTime = 0;
    clearWordPaint();
    try { await player.play(); startLoop(); } catch (_) { /* user gesture needed */ }
  };
  $("player").addEventListener("play", () => { $("stage").classList.add("playing"); startLoop(); });
  $("player").addEventListener("pause", () => {
    $("stage").classList.remove("playing");
    cancelAnimationFrame(rafId);
  });
  $("player").addEventListener("ended", () => {
    $("stage").classList.remove("playing");
    cancelAnimationFrame(rafId);
    clearWordPaint();
  });
  $("player").addEventListener("seeked", () => {
    activeWordKey = "";
    repaintLineStates(activeLineNo, $("player").currentTime + syncOffset);
    tick();
  });
  $("player").addEventListener("loadedmetadata", async () => {
    await loadTimings();
    renderLyrics();
    if (activeLineNo) { const no = activeLineNo; activeLineNo = 0; setActiveLine(no, false); }
  });
  $("meaning-lang").onchange = async () => {
    await loadTranslation();
    renderLyrics();
    const no = activeLineNo || (current && current.lines[0] ? current.lines[0].line_no : 0);
    activeLineNo = 0;
    if (no) setActiveLine(no, false);
    await loadClips();
  };
  $("show-inline").onchange = () => {
    const no = activeLineNo;
    renderLyrics();
    if (no) setActiveLine(no, false);
  };
  function setSync(delta) {
    syncOffset = Math.round((syncOffset + delta) * 100) / 100;
    $("sync-value").textContent = `${syncOffset >= 0 ? "" : "\u2212"}${Math.abs(syncOffset).toFixed(2)}s`;
    activeWordKey = "";
    repaintLineStates(activeLineNo, $("player").currentTime + syncOffset);
    tick();
  }
  $("sync-back").onclick = () => setSync(-0.25);
  $("sync-fwd").onclick = () => setSync(0.25);
  $("ask-send").onclick = () => askAI();
  $("ask-input").addEventListener("keydown", (e) => { if (e.key === "Enter") askAI(); });

  (async function boot() {
    $("ask-quick").innerHTML = QUICK_ASKS.map((q) =>
      `<button class="chip" type="button" data-q="${esc(q)}">${esc(q)}</button>`).join("");
    $("ask-quick").querySelectorAll("button").forEach((b) => {
      b.onclick = () => askAI(b.getAttribute("data-q"));
    });
    const langs = await api("/api/music/languages");
    const cat = langs.catalog || [];
    $("meaning-lang").innerHTML = cat.map((row) =>
      `<option value="${esc(row.code)}">${esc(row.name)}${row.curated ? " \u2713" : ""}</option>`).join("");
    $("meaning-lang").value = "es";
    const data = await api("/api/music/featured");
    featured = data.songs || [];
    $("catalog-meta").textContent =
      `${featured.length} featured with audio \u00b7 ${langs.count || 26} translation languages`;
    renderSongList();
    if (featured[0]) await selectSong(featured[0].song_id);
  })().catch((e) => toast(String(e.message || e)));
"""
