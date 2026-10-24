/* Salareen listening lab. No network, no telemetry, no framework. All text is set with textContent. */
(() => {
'use strict';
const LAB = window.LAB_DATA || {candidates: [], sentences: {}, run: null};
const LANG_NAMES = {km: 'Khmer', vi: 'Vietnamese', th: 'Thai', es: 'Spanish', en: 'English', zh: 'Mandarin', sw: 'Swahili', hi: 'Hindi', bn: 'Bengali'};
const SID_RE = /^[SMLNDPVQ]\d{1,3}$/i;
const AUDIO_RE = /\.(wav|mp3|m4a|aac|ogg|opus|flac|webm)$/i;
const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? '' : String(v));
  }
  for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return e;
}

/* ---------- persistence (localStorage may be missing on file:// in Safari) ---------- */
const store = (() => {
  const mem = {};
  try { localStorage.setItem('__t', '1'); localStorage.removeItem('__t'); return {get: k => localStorage.getItem(k), set: (k, v) => localStorage.setItem(k, v)}; }
  catch (_) { return {get: k => (k in mem ? mem[k] : null), set: (k, v) => { mem[k] = v; }}; }
})();
const SAVED = (() => { try { return JSON.parse(store.get('ttslab.v1') || '{}'); } catch (_) { return {}; } })();

const state = {
  voices: new Map(),      // id -> {id, name, meta, dropped, cand}
  clips: new Map(),       // lang|sid|voice -> clip
  sentences: new Map(),   // lang -> Map(sid -> {id,text,ref_en,category,order})
  keyMaps: {},            // panel id -> {"id:label": voice} from panel/key.json
  external: [],           // ratings loaded from panel JSON files {lang, rater, sid, voice, nat, clr}
  lang: '', cat: '', hiddenVoices: new Set(),
  blind: !!SAVED.blind, seed: SAVED.seed ?? 7, norm: SAVED.norm !== false, wave: !!SAVED.wave, speed: SAVED.speed || 1,
  rater: SAVED.rater || '', ratings: SAVED.ratings || {},
  tab: 'grid', focus: {row: 0, col: 0}, now: null, queue: [], loop: null, rows: [], labelMaps: {},
};
function persist() {
  try { store.set('ttslab.v1', JSON.stringify({blind: state.blind, seed: state.seed, norm: state.norm, wave: state.wave, speed: state.speed, rater: state.rater, ratings: state.ratings})); } catch (_) { /* quota */ }
}
function say(msg) { $('#status').textContent = msg; }

/* ---------- seeded shuffle ---------- */
function hash32(s) { let x = 2166136261; for (let i = 0; i < s.length; i++) { x ^= s.charCodeAt(i); x = Math.imul(x, 16777619); } return x >>> 0; }
function rng32(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function shuffled(arr, seedStr) { const a = arr.slice(), r = rng32(hash32(seedStr)); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }

/* ---------- voices, badges ---------- */
function candidateFor(id) {
  const norm = x => String(x || '').toLowerCase().replace(/[-\s]+/g, '_');
  return (LAB.candidates || []).find(c => norm(c.adapter) === norm(id) || norm(c.id) === norm(id)) || null;
}
function badgeOf(voice) {
  const c = voice.cand;
  if (!c) return {cls: 'b-unk', text: 'UNKNOWN LICENSE', title: 'Not in the license matrix: do not assume it can ship.'};
  if (c.label === 'SHIPPABLE') return {cls: 'b-ok', text: 'SHIPPABLE', title: 'Code and weights allow commercial use (license matrix).'};
  if (c.label === 'NOT SHIPPABLE') return {cls: 'b-no', text: 'NOT SHIPPABLE', title: 'Internal reference only: license forbids commercial use.'};
  return {cls: 'b-chk', text: 'CHECK LICENSE', title: 'Open license questions: not counted as shippable.'};
}
function ensureVoice(id, meta) {
  let v = state.voices.get(id);
  if (!v) { v = {id, name: id, meta: meta || {}, cand: candidateFor(id), dropped: !meta}; state.voices.set(id, v); }
  else if (meta) { v.meta = meta; v.dropped = false; }
  if (v.cand && v.cand.name) v.name = v.cand.name;
  return v;
}
function addSentence(lang, sid, text, extra) {
  let m = state.sentences.get(lang);
  if (!m) { m = new Map(); state.sentences.set(lang, m); }
  const cur = m.get(sid) || {id: sid, text: '', ref_en: '', category: '', order: m.size};
  if (text) cur.text = text;
  Object.assign(cur, extra || {}, {text: text || cur.text});
  m.set(sid, cur);
  return cur;
}
(function seedSentences() {
  for (const [lang, rows] of Object.entries(LAB.sentences || {})) rows.forEach((r, i) => addSentence(lang, r.id, r.text, {ref_en: r.ref_en, category: r.category, order: i}));
})();

/* ---------- ingest (served listing, folder picker, drag and drop) ---------- */
const segs = p => p.split('/').filter(Boolean);
function entryFromFile(file, path) { return {path: (path || file.webkitRelativePath || file.name).replace(/\\/g, '/').replace(/^\.?\//, ''), name: file.name, size: file.size, file, url: null}; }
async function readText(e) { return e.file ? e.file.text() : fetch(e.url).then(r => r.text()); }
function urlOf(e) { if (!e.url) e.url = URL.createObjectURL(e.file); return e.url; }
function parseJsonl(text) { return text.split('\n').filter(l => l.trim()).map(l => { try { return JSON.parse(l); } catch (_) { return null; } }).filter(Boolean); }

function inferFromPath(path) {
  const s = segs(path), name = s[s.length - 1] || '', stem = name.replace(/\.[^.]+$/, '');
  let model = '', lang = '', sid = '';
  if (SID_RE.test(stem)) sid = stem.toUpperCase();
  const langs = Object.keys(LANG_NAMES);
  if (s.length >= 3 && SID_RE.test(stem) && langs.includes(s[s.length - 2])) { lang = s[s.length - 2]; model = s[s.length - 3]; }
  else if (s.length >= 2 && SID_RE.test(stem) && langs.includes(s[s.length - 2])) { lang = s[s.length - 2]; }
  else {
    const parts = stem.split(/[_\-.\s]+/);
    const li = parts.findIndex(p => langs.includes(p.toLowerCase()));
    const si = parts.findIndex(p => SID_RE.test(p));
    if (li >= 0) lang = parts[li].toLowerCase();
    if (si >= 0) sid = parts[si].toUpperCase();
    if (li > 0) model = parts.slice(0, li).join('-');
    else if (s.length >= 2) model = s[s.length - 2];
  }
  return {model, lang, sid};
}

async function ingest(entries) {
  entries = entries.filter(e => e && e.path);
  const byLast = new Map();
  for (const e of entries) { const p = segs(e.path); for (const n of [2, 3]) if (p.length >= n) { const k = p.slice(-n).join('/'); (byLast.get(k) || byLast.set(k, []).get(k)).push(e); } }
  const used = new Set();
  let added = 0;
  const manifests = entries.filter(e => e.name === 'manifest.jsonl');
  for (const mf of manifests) {
    const dir = segs(mf.path).slice(0, -1), model = dir[dir.length - 1] || 'voice';
    const sibling = n => entries.find(e => e.name === n && segs(e.path).slice(0, -1).join('/') === dir.join('/'));
    let meta = {};
    try { const m = sibling('meta.json'); if (m) meta = JSON.parse(await readText(m)); } catch (_) { /* optional */ }
    const scores = new Map();
    try { const s = sibling('scores.jsonl'); if (s) for (const r of parseJsonl(await readText(s))) scores.set(`${r.lang}|${r.id}`, r); } catch (_) { /* optional */ }
    const voice = ensureVoice(model, meta);
    for (const r of parseJsonl(await readText(mf))) {
      if (r.status !== 'ok' || !r.wav) continue;
      const p = segs(r.wav), cands = byLast.get(p.slice(-3).join('/')) || byLast.get(p.slice(-2).join('/')) || [];
      const e = cands[0];
      if (!e) continue;
      used.add(e);
      addSentence(r.lang, r.id, r.text);
      state.clips.set(`${r.lang}|${r.id}|${voice.id}`, {voice: voice.id, lang: r.lang, sid: r.id, entry: e, dur: r.duration_s, score: scores.get(`${r.lang}|${r.id}`) || null, rms: null, peaks: null});
      added++;
    }
  }
  for (const e of entries) {
    if (used.has(e) || !AUDIO_RE.test(e.name)) continue;
    const g = inferFromPath(e.path);
    if (g.model && g.lang && g.sid) { addClipEntry(e, g.model, g.lang, g.sid); added++; }
    else pendingLabel.push({e, guess: g});
  }
  for (const e of entries) {
    if (!/\.json$/i.test(e.name) || !/(ratings|key)/i.test(e.name) || (e.size || 0) > 5e6) continue;
    try { loadRatingsJson(JSON.parse(await readText(e))); } catch (_) { /* not a ratings file */ }
  }
  if (pendingLabel.length) openLabelDialog();
  refreshAll();
  say(added ? `Loaded ${added} clip${added === 1 ? '' : 's'}: ${state.voices.size} voice(s).` : (pendingLabel.length ? 'Label the clips to add them.' : 'No clips found in that selection.'));
}
const pendingLabel = [];
function addClipEntry(e, model, lang, sid, dropped = true) {
  const v = ensureVoice(model, dropped ? null : undefined);
  addSentence(lang, sid, '');
  state.clips.set(`${lang}|${sid}|${v.id}`, {voice: v.id, lang, sid, entry: e, dur: null, score: null, rms: null, peaks: null});
}
function loadRatingsJson(data) {
  if (data && data.panels && typeof data.panels === 'object') { Object.assign(state.keyMaps, data.panels); return; }
  if (!data || !Array.isArray(data.ratings)) return;
  const map = data.key || state.keyMaps[data.panel] || {};
  for (const r of data.ratings) {
    const voice = map[`${r.id}:${r.label}`] || r.voice;
    if (!voice) continue;
    state.external.push({lang: data.lang, rater: data.rater || 'anonymous', sid: r.id, voice, nat: r.naturalness, clr: r.clarity});
  }
}

/* ---------- label dialog ---------- */
function openLabelDialog() {
  const box = $('#label-rows'); box.replaceChildren();
  box.append(h('b', {text: 'File'}), h('b', {text: 'Voice name'}), h('b', {text: 'Language'}), h('b', {text: 'Sentence'}));
  pendingLabel.forEach((p, i) => {
    const sel = h('select', {'aria-label': 'language', 'data-i': i}, h('option', {value: '', text: '?'}), ...Object.keys(LANG_NAMES).map(l => h('option', {value: l, text: l, selected: l === p.guess.lang})));
    box.append(h('span', {text: p.e.path}), h('input', {'data-f': 'model', 'data-i': i, value: p.guess.model || '', 'aria-label': 'voice name'}), sel, h('input', {'data-f': 'sid', 'data-i': i, value: p.guess.sid || '', 'aria-label': 'sentence id', placeholder: 'S01'}));
  });
  $('#label-dlg').hidden = false;
  $('#label-rows input').focus();
}
function closeLabel() { $('#label-dlg').hidden = true; pendingLabel.length = 0; }
$('#label-skip').addEventListener('click', () => { closeLabel(); refreshAll(); });
$('#label-apply').addEventListener('click', () => {
  let n = 0;
  pendingLabel.forEach((p, i) => {
    const model = $(`input[data-f=model][data-i="${i}"]`).value.trim(), lang = $(`select[data-i="${i}"]`).value, sid = $(`input[data-f=sid][data-i="${i}"]`).value.trim().toUpperCase();
    if (model && lang && sid) { addClipEntry(p.e, model, lang, sid); n++; }
  });
  closeLabel(); refreshAll(); say(`Added ${n} labelled clip(s).`);
});

/* ---------- loading UI ---------- */
$('#open-folder').addEventListener('change', e => { ingest(Array.from(e.target.files).map(f => entryFromFile(f))); e.target.value = ''; });
$('#add-files').addEventListener('change', e => { ingest(Array.from(e.target.files).map(f => entryFromFile(f))); e.target.value = ''; });
$('#load-ratings').addEventListener('change', async e => {
  for (const f of e.target.files) { try { loadRatingsJson(JSON.parse(await f.text())); } catch (_) { say(`${f.name}: not a ratings file`); } }
  e.target.value = ''; renderSummary(); say(`Loaded ratings: ${state.external.length} external rating(s).`);
});
for (const id of ['open-folder-label', 'add-files-label']) $('#' + id).addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('input', e.currentTarget).click(); } });
let dragDepth = 0;
window.addEventListener('dragenter', e => { e.preventDefault(); dragDepth++; $('#drop').hidden = false; });
window.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; $('#drop').hidden = true; } });
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', async e => {
  e.preventDefault(); dragDepth = 0; $('#drop').hidden = true;
  const items = Array.from(e.dataTransfer.items || []);
  const out = [];
  async function walk(entry, prefix) {
    if (entry.isFile) { const f = await new Promise((res, rej) => entry.file(res, rej)); out.push(entryFromFile(f, prefix + entry.name)); }
    else if (entry.isDirectory) {
      const rd = entry.createReader();
      for (;;) { const batch = await new Promise((res, rej) => rd.readEntries(res, rej)); if (!batch.length) break; for (const c of batch) await walk(c, prefix + entry.name + '/'); }
    }
  }
  const roots = items.map(i => (i.webkitGetAsEntry ? i.webkitGetAsEntry() : null)).filter(Boolean);
  if (roots.length) for (const r of roots) await walk(r, ''); else for (const f of e.dataTransfer.files) out.push(entryFromFile(f));
  ingest(out);
});

async function loadServed() {
  if (!LAB.run || !LAB.run.base) return;
  const sub = new URLSearchParams(location.search).get('run') || '';
  try {
    const r = await fetch('/api/run' + (sub ? '?sub=' + encodeURIComponent(sub) : '')).then(x => x.json());
    const base = LAB.run.base + (sub ? sub.replace(/^\/+|\/+$/g, '') + '/' : '');
    const entries = (r.files || []).map(f => ({path: f.path, name: f.path.split('/').pop(), size: f.size, file: null, url: base + f.path.split('/').map(encodeURIComponent).join('/')}));
    if (entries.length) await ingest(entries); else say('The served run folder has no audio yet.');
  } catch (err) { say('Could not list the run folder: ' + err.message); }
}

/* ---------- filters ---------- */
function languagesWithClips() { const s = new Set(); for (const c of state.clips.values()) s.add(c.lang); return Object.keys(LANG_NAMES).filter(l => s.has(l)).concat(Array.from(s).filter(l => !LANG_NAMES[l])); }
function voicesFor(lang) { return Array.from(state.voices.values()).filter(v => !state.hiddenVoices.has(v.id) && hasAnyClip(lang, v.id)).sort((a, b) => a.name.localeCompare(b.name)); }
function hasAnyClip(lang, voice) { for (const c of state.clips.values()) if (c.lang === lang && c.voice === voice) return true; return false; }
function sentenceList(lang) {
  const m = state.sentences.get(lang) || new Map();
  const vs = voicesFor(lang);
  return Array.from(m.values()).filter(s => (!state.cat || s.category === state.cat) && vs.some(v => state.clips.has(`${lang}|${s.id}|${v.id}`))).sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
}
function labelMapFor(lang, sid) {
  const k = `${lang}|${sid}|${state.seed}`;
  if (!state.labelMaps[k]) {
    const present = Array.from(state.voices.values()).filter(v => state.clips.has(`${lang}|${sid}|${v.id}`)).map(v => v.id).sort();
    const order = shuffled(present, `${state.seed}:${lang}:${sid}`);
    const byVoice = {}, byLabel = {};
    order.forEach((vid, i) => { byVoice[vid] = LETTERS[i] || '?'; byLabel[LETTERS[i] || '?'] = vid; });
    state.labelMaps[k] = {order, byVoice, byLabel};
  }
  return state.labelMaps[k];
}

function refreshFilters() {
  const langs = languagesWithClips(), sel = $('#f-lang');
  if (!langs.includes(state.lang)) state.lang = langs.includes('km') ? 'km' : (langs[0] || '');
  sel.replaceChildren(...langs.map(l => h('option', {value: l, text: `${LANG_NAMES[l] || l} (${l})`, selected: l === state.lang})));
  const cats = new Set(); (state.sentences.get(state.lang) || new Map()).forEach(s => { if (s.category) cats.add(s.category); });
  $('#f-cat').replaceChildren(h('option', {value: '', text: 'all'}), ...Array.from(cats).map(c => h('option', {value: c, text: c, selected: c === state.cat})));
  const box = $('#f-models'); box.replaceChildren();
  if (state.blind) box.append(h('span', {class: 'chip', text: 'names hidden in blind mode'}));
  else for (const v of Array.from(state.voices.values()).sort((a, b) => a.name.localeCompare(b.name))) {
    if (!hasAnyClip(state.lang, v.id)) continue;
    const b = badgeOf(v);
    const cb = h('input', {type: 'checkbox', checked: !state.hiddenVoices.has(v.id), 'data-v': v.id, onchange: e => { e.target.checked ? state.hiddenVoices.delete(v.id) : state.hiddenVoices.add(v.id); renderGrid(); renderSamples(); }});
    box.append(h('label', {title: b.title}, cb, ' ', v.name, ' ', h('span', {class: 'badge ' + b.cls, text: b.text})));
  }
  $('#banner-demo').hidden = !Array.from(state.voices.values()).some(v => v.meta && v.meta.demo);
  $('#banner-nodata').hidden = !window.__noLabData;
  $('#t-blind').checked = state.blind; $('#t-seed').value = state.seed; $('#t-norm').checked = state.norm; $('#t-wave').checked = state.wave; $('#t-speed').value = String(state.speed); $('#t-rater').value = state.rater;
}

/* ---------- audio engine ---------- */
const player = new Audio();
player.preload = 'auto';
let actx = null;
function audioCtx() { if (!actx) { const C = window.AudioContext || window.webkitAudioContext; actx = C ? new C() : null; } return actx; }
async function decodeClip(clip) {
  if (clip.peaks || clip.failed) return clip;
  const e = clip.entry;
  if ((e.size || 0) > 30e6) { clip.failed = true; return clip; }
  try {
    const buf = await (e.file ? e.file.arrayBuffer() : fetch(urlOf(e)).then(r => r.arrayBuffer()));
    const ctx = audioCtx(); if (!ctx) { clip.failed = true; return clip; }
    const ab = await new Promise((res, rej) => { const p = ctx.decodeAudioData(buf, res, rej); if (p && p.then) p.then(res, rej); });
    const x = ab.getChannelData(0), bins = 160, step = Math.max(1, Math.floor(x.length / bins));
    const peaks = new Array(bins).fill(0); let sum = 0, cnt = 0;
    for (let i = 0; i < x.length; i++) { const a = Math.abs(x[i]); const b = Math.min(bins - 1, Math.floor(i / step)); if (a > peaks[b]) peaks[b] = a; if (a > 0.01) { sum += a * a; cnt++; } }
    clip.rms = cnt ? Math.sqrt(sum / cnt) : 0.001; clip.peaks = peaks; clip.dur = clip.dur || ab.duration;
    drawWave(clip);
  } catch (_) { clip.failed = true; }
  return clip;
}
function drawWave(clip) {
  const c = clip.canvas; if (!c || !clip.peaks) return;
  const w = c.width = c.clientWidth * (window.devicePixelRatio || 1) || 160, hgt = c.height = c.clientHeight * (window.devicePixelRatio || 1) || 30, g = c.getContext('2d');
  g.clearRect(0, 0, w, hgt); g.fillStyle = '#8fa0d8';
  const n = clip.peaks.length, bw = w / n;
  clip.peaks.forEach((p, i) => { const bh = Math.max(1, p * hgt * 0.95); g.fillRect(i * bw, (hgt - bh) / 2, Math.max(1, bw - 1), bh); });
}
async function volumeFor(clip) {
  if (!state.norm) return 1;
  const sibs = Array.from(state.voices.values()).map(v => state.clips.get(`${clip.lang}|${clip.sid}|${v.id}`)).filter(Boolean);
  await Promise.all(sibs.map(decodeClip));
  const rs = sibs.map(c => c.rms).filter(r => r > 0);
  if (!clip.rms || !rs.length) return 1;
  return Math.min(1, Math.min(...rs) / clip.rms);
}
function keyOf(c) { return `${c.lang}|${c.sid}|${c.voice}`; }
function setPlayingUI() {
  $$('.cell.playing').forEach(c => c.classList.remove('playing'));
  $$('.cell .play').forEach(b => { b.textContent = '▶'; b.setAttribute('aria-pressed', 'false'); });
  if (state.now && !player.paused) {
    const cell = $(`.cell[data-key="${CSS.escape(state.now)}"]`);
    if (cell) { cell.classList.add('playing'); const b = $('.play', cell); b.textContent = '❚❚'; b.setAttribute('aria-pressed', 'true'); }
  }
}
async function play(key, opts = {}) {
  const clip = state.clips.get(key); if (!clip) return;
  if (state.now === key && !player.paused && !opts.restart) { player.pause(); setPlayingUI(); return; }
  if (!opts.keepQueue) { state.queue = []; state.loop = null; }
  if (state.now !== key || opts.restart) { player.src = urlOf(clip.entry); state.now = key; }
  player.playbackRate = state.speed; player.preservesPitch = true;
  // Start inside the user gesture (Safari rejects play() after an await); match loudness a moment later.
  player.volume = !state.norm ? 1 : (clip.rms ? 1 : 0.5);
  try { await player.play(); } catch (err) { say('Playback was blocked or failed: ' + err.message); }
  setPlayingUI();
  volumeFor(clip).then(v => { if (state.now === key) player.volume = v; });
}
function stopAll() { state.queue = []; state.loop = null; player.pause(); setPlayingUI(); }
player.addEventListener('ended', () => {
  if (state.loop) { state.loop.i = (state.loop.i + 1) % state.loop.keys.length; play(state.loop.keys[state.loop.i], {keepQueue: true, restart: true}); return; }
  if (state.queue.length) { play(state.queue.shift(), {keepQueue: true, restart: true}); return; }
  setPlayingUI();
});
player.addEventListener('timeupdate', () => {
  if (!state.now || !player.duration) return;
  const cell = $(`.cell[data-key="${CSS.escape(state.now)}"]`); if (!cell) return;
  $('.prog', cell).style.width = (100 * player.currentTime / player.duration) + '%';
});
player.addEventListener('play', setPlayingUI); player.addEventListener('pause', setPlayingUI);
function rowKeys(row) { return state.blind ? labelMapFor(state.lang, row.id).order.filter(v => !state.hiddenVoices.has(v)).map(v => `${state.lang}|${row.id}|${v}`) : voicesFor(state.lang).map(v => `${state.lang}|${row.id}|${v.id}`).filter(k => state.clips.has(k)); }
function playRowAll(row) { const keys = rowKeys(row); if (!keys.length) return; state.queue = keys.slice(1); state.loop = null; play(keys[0], {keepQueue: true, restart: true}); }
function loopAB(row) { const keys = rowKeys(row).slice(0, 2); if (keys.length < 2) { say('Need at least two voices to loop A vs B.'); return; } state.queue = []; state.loop = {keys, i: 0}; play(keys[0], {keepQueue: true, restart: true}); say('Looping A vs B: press any key or Esc to stop.'); }

/* ---------- grid ---------- */
const io = 'IntersectionObserver' in window ? new IntersectionObserver(entries => { for (const en of entries) if (en.isIntersecting) { fillRow(en.target); io.unobserve(en.target); } }, {rootMargin: '700px 0px'}) : null;
function fmtDur(s) { return s ? `${s.toFixed(1)}s` : ''; }
function scoreChips(clip) {
  const s = clip.score, chips = [];
  if (!s) return chips;
  if (s.error && typeof s.error.value === 'number') chips.push(h('span', {class: 'chip', title: 'ASR round-trip error: lower is better. Intelligibility only.', text: `${String(s.error.metric || 'err').toUpperCase()} ${(100 * s.error.value).toFixed(1)}%`}));
  const a = s.audio || {};
  if (typeof a.rate_per_s === 'number') chips.push(h('span', {class: 'chip', title: 'speaking rate over the voiced span', text: `${a.rate_per_s.toFixed(1)}/s`}));
  for (const f of a.flags || []) chips.push(h('span', {class: 'chip warn', text: '⚠ ' + String(f).replace(/_/g, ' ')}));
  if (s.scoring_error) chips.push(h('span', {class: 'chip warn', text: 'scoring failed'}));
  return chips;
}
function ratingOf(key) { return state.ratings[key] || (state.ratings[key] = {}); }
function buildCell(row, ri, voiceId, ci) {
  const key = `${state.lang}|${row.id}|${voiceId}`, clip = state.clips.get(key);
  if (!clip) return h('div', {class: 'cell empty', 'data-key': key, tabindex: '-1', text: '—'});
  const v = state.voices.get(voiceId), lm = labelMapFor(state.lang, row.id), label = lm.byVoice[voiceId], b = badgeOf(v);
  const cell = h('div', {class: 'cell', tabindex: ci === 0 && ri === 0 ? '0' : '-1', 'data-key': key, 'data-row': ri, 'data-col': ci, role: 'group', 'aria-label': `${state.blind ? 'voice ' + label : v.name}, sentence ${row.id}`});
  const head = h('div', {class: 'cellhead'}, h('span', {class: 'lbl', text: label}));
  if (!state.blind) head.append(h('span', {class: 'vname', text: v.name}), h('span', {class: 'badge ' + b.cls, title: b.title, text: b.text}));
  const canvas = h('canvas', {'aria-hidden': 'true'});
  clip.canvas = canvas;
  const bar = h('div', {class: 'bar', title: 'click to seek', onclick: e => { const r = bar.getBoundingClientRect(), f = (e.clientX - r.left) / r.width; if (state.now === key && player.duration) player.currentTime = f * player.duration; else play(key).then(() => { if (player.duration) player.currentTime = f * player.duration; }); }}, canvas, h('div', {class: 'prog'}));
  const playBtn = h('button', {class: 'play', type: 'button', 'aria-label': `Play ${state.blind ? 'voice ' + label : v.name}`, 'aria-pressed': 'false', text: '▶', onclick: () => { selectCell(ri, ci, false); play(key); }});
  const dur = h('span', {class: 'dur', text: fmtDur(clip.dur)});
  const rate = state.ratings[key] || {};
  const mkScale = field => { const kids = [1, 2, 3, 4, 5].map(n => h('button', {type: 'button', 'aria-label': `${field === 'nat' ? 'naturalness' : 'clarity'} ${n}`, 'aria-pressed': String(rate[field] === n), text: n, onclick: () => setRating(key, field, n, cell)})); return h('div', {class: 'line'}, h('span', {class: 'k', text: field === 'nat' ? 'Natural' : 'Clear'}), ...kids); };
  const best = h('button', {type: 'button', class: 'star', 'aria-label': 'best of this sentence', 'aria-pressed': String(!!rate.best), text: '★ best', style: 'width:auto;padding:0 .4rem', onclick: () => setRating(key, 'best', !ratingOf(key).best, cell)});
  const note = h('input', {type: 'text', placeholder: 'note', maxlength: '200', 'aria-label': 'note', value: rate.note || '', oninput: e => { ratingOf(key).note = e.target.value; persist(); }});
  cell.append(head, h('div', {class: 'player'}, playBtn, bar, dur), h('div', {class: 'chips'}, ...scoreChips(clip)), h('div', {class: 'rate'}, mkScale('nat'), mkScale('clr'), h('div', {class: 'line'}, best, note)));
  cell.addEventListener('focus', () => { state.focus = {row: ri, col: ci}; });
  if (state.wave || clip.peaks) { decodeClip(clip).then(() => drawWave(clip)); }
  if (clip.peaks) requestAnimationFrame(() => drawWave(clip));
  if (!clip.dur) { const t = new Audio(); t.preload = 'metadata'; t.src = urlOf(clip.entry); t.addEventListener('loadedmetadata', () => { clip.dur = t.duration; dur.textContent = fmtDur(clip.dur); }); }
  return cell;
}
function setRating(key, field, val, cell) {
  const r = ratingOf(key); r[field] = (field === 'best') ? !!val : (r[field] === val ? undefined : val);
  persist();
  if (cell) { for (const b of $$('.rate .line button:not(.star)', cell)) { const f = b.getAttribute('aria-label').startsWith('natural') ? 'nat' : 'clr'; b.setAttribute('aria-pressed', String(r[f] === +b.textContent)); } $('.star', cell).setAttribute('aria-pressed', String(!!r.best)); }
}
function fillRow(rowEl) {
  if (rowEl.dataset.filled) return; rowEl.dataset.filled = '1';
  const ri = +rowEl.dataset.ri, row = state.rows[ri]; if (!row) return;
  const cells = $('.cells', rowEl); cells.replaceChildren();
  const order = state.blind ? labelMapFor(state.lang, row.id).order.filter(v => !state.hiddenVoices.has(v)) : voicesFor(state.lang).map(v => v.id);
  order.forEach((vid, ci) => cells.append(buildCell(row, ri, vid, ci)));
}
function renderGrid() {
  const host = $('#grid'); host.replaceChildren();
  state.rows = state.lang ? sentenceList(state.lang) : [];
  if (!state.rows.length) { host.append(h('p', {class: 'status', text: state.voices.size ? 'No clips match these filters.' : 'No audio loaded yet. Use “Open run folder” or drop files here.'})); return; }
  state.rows.forEach((row, ri) => {
    const sent = h('div', {class: 'sent'}, h('div', {}, h('span', {class: 'id', text: row.id}), h('span', {class: 'cat', text: row.category})),
      h('div', {class: 'txt', text: row.text || '(text unknown)', dir: 'auto', lang: state.lang}), row.ref_en ? h('div', {class: 'ref', text: row.ref_en}) : null,
      h('div', {class: 'acts'}, h('button', {class: 'btn small', type: 'button', text: 'Play all', onclick: () => playRowAll(row)}), h('button', {class: 'btn small', type: 'button', text: 'A/B loop', onclick: () => loopAB(row)})));
    const el = h('div', {class: 'row-s', 'data-ri': ri, 'data-sid': row.id}, sent, h('div', {class: 'cells'}));
    host.append(el);
    if (io) io.observe(el); else fillRow(el);
  });
  const n0 = $('.row-s'); if (n0) fillRow(n0);
}
function selectCell(ri, ci, focus = true) {
  const rowEl = $(`.row-s[data-ri="${ri}"]`); if (!rowEl) return;
  fillRow(rowEl);
  const cell = $(`.cell[data-row="${ri}"][data-col="${ci}"]`, rowEl); if (!cell) return;
  $$('.cell.sel').forEach(c => c.classList.remove('sel')); $$('.row-s.active').forEach(c => c.classList.remove('active'));
  cell.classList.add('sel'); rowEl.classList.add('active'); cell.tabIndex = 0;
  state.focus = {row: ri, col: ci};
  if (focus) { cell.focus({preventScroll: true}); cell.scrollIntoView({block: 'nearest'}); }
}

/* ---------- keyboard ---------- */
document.addEventListener('keydown', e => {
  const t = e.target;
  if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) && !(t.type === 'checkbox')) return;
  if (!$('#help-dlg').hidden || !$('#label-dlg').hidden) { if (e.key === 'Escape') { $('#help-dlg').hidden = true; } return; }
  if (e.ctrlKey || e.metaKey) return;
  if (state.loop && e.key !== 'l') { stopAll(); if (e.key === 'Escape') return; }
  const rows = state.rows, f = state.focus, row = rows[f.row];
  const colCount = row ? rowKeys(row).length : 0;
  const move = (dr, dc) => { e.preventDefault(); const nr = Math.max(0, Math.min(rows.length - 1, f.row + dr)); const rr = rows[nr]; const nc = Math.max(0, Math.min((rr ? rowKeys(rr).length : 1) - 1, f.col + dc)); selectCell(nr, nc); };
  if (e.key === 'ArrowRight') return move(0, 1);
  if (e.key === 'ArrowLeft') return move(0, -1);
  if (e.key === 'ArrowDown') return move(1, 0);
  if (e.key === 'ArrowUp') return move(-1, 0);
  if (e.key === ' ') { if (state.tab !== 'grid') return; e.preventDefault(); if (!$('.cell.sel')) selectCell(f.row, f.col, false); const key = rowKeys(row || {id: ''})[f.col]; if (key) play(key); return; }
  if (/^Digit[1-5]$/.test(e.code) && row) { const key = rowKeys(row)[f.col]; if (key) { setRating(key, e.altKey ? 'clr' : 'nat', +e.code.slice(5), $(`.cell[data-key="${CSS.escape(key)}"]`)); e.preventDefault(); } return; }
  if (e.shiftKey && e.code === 'KeyN') return move(-1, 0);
  if (e.shiftKey && /^Key[A-Z]$/.test(e.code) && row) { const idx = LETTERS.indexOf(e.code.slice(3)); const keys = rowKeys(row); if (idx < keys.length) { e.preventDefault(); selectCell(f.row, idx); play(keys[idx]); } return; }
  if (e.key === 'b') { $('#t-blind').click(); return; }
  if (e.key === 'n') return move(1, 0);
  if (e.key === 'N') return move(-1, 0);
  if (e.key === 'p' && row) { playRowAll(row); return; }
  if (e.key === 'l' && row) { if (state.loop) stopAll(); else loopAB(row); return; }
  if (e.key === '?') { $('#help-dlg').hidden = false; $('#help-close').focus(); return; }
  if (e.key === 'Escape') { stopAll(); }
  void colCount;
});
$('#help-btn').addEventListener('click', () => { $('#help-dlg').hidden = false; $('#help-close').focus(); });
$('#help-close').addEventListener('click', () => { $('#help-dlg').hidden = true; });

/* ---------- toolbar wiring ---------- */
$('#f-lang').addEventListener('change', e => { state.lang = e.target.value; state.cat = ''; refreshAll(); });
$('#f-cat').addEventListener('change', e => { state.cat = e.target.value; renderGrid(); renderSamples(); });
$('#t-blind').addEventListener('change', e => { state.blind = e.target.checked; persist(); refreshAll(); stopAll(); say(state.blind ? 'Blind mode: voices are hidden and shuffled per sentence.' : 'Blind mode off.'); });
$('#t-seed').addEventListener('change', e => { state.seed = Math.max(0, parseInt(e.target.value || '7', 10) || 0); state.labelMaps = {}; persist(); refreshAll(); });
$('#t-norm').addEventListener('change', e => { state.norm = e.target.checked; persist(); });
$('#t-wave').addEventListener('change', e => { state.wave = e.target.checked; persist(); if (state.wave) renderGrid(); });
$('#t-speed').addEventListener('change', e => { state.speed = parseFloat(e.target.value) || 1; player.playbackRate = state.speed; persist(); });
$('#t-rater').addEventListener('input', e => { state.rater = e.target.value; persist(); });
$$('.tabs button').forEach(b => b.addEventListener('click', () => { state.tab = b.dataset.tab; $$('.tabs button').forEach(x => x.setAttribute('aria-selected', String(x === b))); for (const id of ['grid', 'summary', 'samples']) $('#' + id).hidden = id !== state.tab; if (state.tab === 'summary') renderSummary(); if (state.tab === 'samples') renderSamples(); }));

/* ---------- ratings: collect, export, summary ---------- */
function ownRatings() {
  const out = [];
  for (const [key, r] of Object.entries(state.ratings)) {
    if (!r || (r.nat == null && r.clr == null && !r.best && !r.note)) continue;
    const [lang, sid, voice] = key.split('|');
    out.push({lang, sid, voice, nat: r.nat, clr: r.clr, best: !!r.best, note: r.note || '', rater: state.rater || 'anonymous'});
  }
  return out;
}
function download(name, text, type) { const a = h('a', {href: URL.createObjectURL(new Blob([text], {type})), download: name}); document.body.append(a); a.click(); a.remove(); }
function exportJson() {
  const mine = ownRatings(), langs = Array.from(new Set(mine.map(r => r.lang)));
  if (!langs.length) { say('Nothing rated yet.'); return; }
  const rater = state.rater || 'anonymous';
  for (const lang of langs) {
    const key = {}, ratings = [];
    for (const r of mine.filter(x => x.lang === lang)) {
      const label = labelMapFor(lang, r.sid).byVoice[r.voice]; if (!label) continue;
      key[`${r.sid}:${label}`] = r.voice;
      if (r.nat != null && r.clr != null) { const o = {id: r.sid, label, naturalness: r.nat, clarity: r.clr}; if (r.best) o.best = true; if (r.note) o.note = r.note; ratings.push(o); }
    }
    download(`ratings_lab_${lang}_${rater.replace(/[^a-z0-9]+/gi, '_')}.json`, JSON.stringify({panel: `lab-${lang}-${state.seed}`, lang, rater, ratings, key, exported: new Date().toISOString()}, null, 1), 'application/json');
  }
  say(`Exported ${langs.length} file(s). The embedded key lets “panel aggregate” resolve the labels.`);
}
function exportCsv() {
  const rows = ownRatings(); if (!rows.length) { say('Nothing rated yet.'); return; }
  const esc = s => `"${String(s ?? '').replace(/"/g, '""')}"`;
  const lines = ['lang,sentence,voice,label,naturalness,clarity,best,note,rater'].concat(rows.map(r => [r.lang, r.sid, r.voice, labelMapFor(r.lang, r.sid).byVoice[r.voice] || '', r.nat ?? '', r.clr ?? '', r.best ? 1 : 0, esc(r.note), esc(r.rater)].join(',')));
  download('ratings_lab.csv', lines.join('\n'), 'text/csv');
}
$('#x-json').addEventListener('click', exportJson); $('#x-csv').addEventListener('click', exportCsv);

function renderSummary() {
  const host = $('#summary'); host.replaceChildren();
  if (state.blind) {
    host.append(h('p', {class: 'status', text: 'Blind mode is on, so voice names are hidden. Finish rating, then reveal to see the results per voice.'}),
      h('button', {class: 'btn', type: 'button', id: 'reveal', text: 'Reveal voices (turn blind mode off)', onclick: () => $('#t-blind').click()}));
    return;
  }
  const all = ownRatings().map(r => ({...r})).concat(state.external.map(r => ({...r, best: false})));
  if (!all.length) { host.append(h('p', {class: 'status', text: 'No ratings yet. Rate clips in the Compare tab (keys 1-5), or load panel rating files.'})); return; }
  const langs = Array.from(new Set(all.map(r => r.lang)));
  for (const lang of langs) {
    const rs = all.filter(r => r.lang === lang), agg = new Map();
    for (const r of rs) { const a = agg.get(r.voice) || {n: 0, nat: [], clr: [], best: 0, raters: new Set()}; if (r.nat != null) a.nat.push(r.nat); if (r.clr != null) a.clr.push(r.clr); a.n++; if (r.best) a.best++; a.raters.add(r.rater); agg.set(r.voice, a); }
    const mean = a => a.length ? (a.reduce((x, y) => x + y, 0) / a.length) : null;
    const tbl = h('table', {class: 'sum'}, h('tr', {}, ...['Voice', 'License', 'Rated clips', 'Raters', 'Naturalness', 'Clarity', 'Best picks'].map(x => h('th', {text: x}))));
    const rowsAgg = Array.from(agg.entries()).map(([vid, a]) => ({vid, a, v: ensureVoice(vid), nat: mean(a.nat), clr: mean(a.clr)})).sort((x, y) => ((y.nat || 0) + (y.clr || 0)) - ((x.nat || 0) + (x.clr || 0)));
    for (const r of rowsAgg) { const b = badgeOf(r.v); tbl.append(h('tr', {}, h('td', {text: r.v.name}), h('td', {}, h('span', {class: 'badge ' + b.cls, text: b.text})), h('td', {text: r.a.n}), h('td', {text: r.a.raters.size}), h('td', {text: r.nat == null ? '-' : r.nat.toFixed(2)}), h('td', {text: r.clr == null ? '-' : r.clr.toFixed(2)}), h('td', {text: r.a.best}))); }
    /* head to head: same rater + sentence, compare naturalness+clarity */
    const voices = rowsAgg.map(r => r.vid), wins = {};
    for (const a of voices) for (const b of voices) if (a !== b) wins[`${a}>${b}`] = 0;
    const bySent = new Map(); for (const r of rs) { if (r.nat == null || r.clr == null) continue; const k = `${r.rater}|${r.sid}`; (bySent.get(k) || bySent.set(k, []).get(k)).push(r); }
    for (const list of bySent.values()) for (const x of list) for (const y of list) if (x.voice !== y.voice && x.nat + x.clr > y.nat + y.clr) wins[`${x.voice}>${y.voice}`]++;
    const h2h = h('table', {class: 'sum'}, h('tr', {}, h('th', {text: 'wins (row beat column)'}), ...voices.map(v => h('th', {text: ensureVoice(v).name}))));
    for (const a of voices) h2h.append(h('tr', {}, h('th', {text: ensureVoice(a).name}), ...voices.map(b => h('td', {text: a === b ? '·' : wins[`${a}>${b}`]}))));
    const best = rowsAgg[0], shippable = rowsAgg.find(r => r.v.cand && r.v.cand.label === 'SHIPPABLE');
    const asrNote = rowsAgg.map(r => { const errs = Array.from(state.clips.values()).filter(c => c.lang === lang && c.voice === r.vid && c.score && c.score.error).map(c => c.score.error.value); return errs.length ? `${r.v.name}: ASR error ${(100 * errs.reduce((x, y) => x + y, 0) / errs.length).toFixed(1)}%` : null; }).filter(Boolean).join('; ');
    const text = [`Language: ${LANG_NAMES[lang] || lang} (${lang})`, `Listeners: ${new Set(rs.map(r => r.rater)).size}; rated clips: ${rs.length}`,
      best ? `Best by ear: ${best.v.name} (naturalness ${best.nat?.toFixed(2) ?? '-'}, clarity ${best.clr?.toFixed(2) ?? '-'}) [${badgeOf(best.v).text}]` : '',
      shippable ? `Best shippable: ${shippable.v.name} (naturalness ${shippable.nat?.toFixed(2) ?? '-'}, clarity ${shippable.clr?.toFixed(2) ?? '-'})` : 'Best shippable: none rated yet (only SHIPPABLE voices can be chosen for the product)',
      best && best.v.cand && best.v.cand.label === 'NOT SHIPPABLE' ? 'NOTE: the best-sounding voice is NOT SHIPPABLE: internal reference only.' : '', asrNote ? `ASR round trip: ${asrNote}` : 'ASR round trip: not loaded', 'Native-speaker check done: yes / no', 'Decision: ____________', 'Notes: '].filter(Boolean).join('\n');
    host.append(h('h2', {text: `${LANG_NAMES[lang] || lang} (${lang})`}), tbl, h('h3', {text: 'Head to head'}), h2h, h('h3', {text: 'Verdict template'}), h('textarea', {class: 'verdict', 'aria-label': 'verdict template', text}), h('p', {}, h('button', {class: 'btn small', type: 'button', text: 'Copy', onclick: e => { const ta = e.target.parentElement.previousElementSibling; navigator.clipboard && navigator.clipboard.writeText(ta.value); say('Copied.'); }})));
  }
}

/* ---------- quick samples ---------- */
function renderSamples() {
  const host = $('#samples'); host.replaceChildren();
  const lang = state.lang; if (!lang) { host.append(h('p', {class: 'status', text: 'Nothing loaded yet.'})); return; }
  const sents = Array.from((state.sentences.get(lang) || new Map()).values()).sort((a, b) => a.order - b.order);
  const vs = voicesFor(lang), picks = sents.filter(s => vs.some(v => state.clips.has(`${lang}|${s.id}|${v.id}`))).slice(0, 3);
  host.append(h('h2', {text: `First impressions: ${LANG_NAMES[lang] || lang}`}), h('p', {class: 'status', text: 'The first three sentences for each voice. Play them in a row for a quick first impression.'}));
  const order = state.blind ? shuffled(vs.map(v => v.id), `${state.seed}:samples:${lang}`) : vs.map(v => v.id);
  const all = [];
  order.forEach((vid, i) => {
    const v = state.voices.get(vid), b = badgeOf(v), keys = picks.map(s => `${lang}|${s.id}|${vid}`).filter(k => state.clips.has(k));
    all.push(...keys);
    host.append(h('div', {class: 'sampbox'}, h('b', {text: state.blind ? `Voice ${LETTERS[i]}` : v.name}), state.blind ? null : h('span', {class: 'badge ' + b.cls, text: b.text}),
      ...keys.map((k, j) => h('button', {class: 'btn small', type: 'button', text: `▶ ${k.split('|')[1]}`, title: picks[j] && picks[j].text, onclick: () => play(k)})),
      h('button', {class: 'btn small', type: 'button', text: 'Play these 3', onclick: () => { state.queue = keys.slice(1); state.loop = null; play(keys[0], {keepQueue: true, restart: true}); }})));
  });
  host.append(h('p', {}, h('button', {class: 'btn', type: 'button', text: 'Play every voice, one after another', onclick: () => { if (!all.length) return; state.queue = all.slice(1); state.loop = null; play(all[0], {keepQueue: true, restart: true}); }}), ' ', h('button', {class: 'btn', type: 'button', text: 'Stop', onclick: stopAll})));
}

function refreshAll() { refreshFilters(); renderGrid(); if (state.tab === 'summary') renderSummary(); if (state.tab === 'samples') renderSamples(); }
window.__lab = {state, player, ingest, play, stopAll, counts: () => ({voices: state.voices.size, clips: state.clips.size, cells: $$('.cell:not(.empty)').length, rows: state.rows.length})};
refreshAll();
loadServed();
})();
