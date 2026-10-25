// Triage log for the camera pages (/children-lab, /diag/vision). Local only: entries stay in this page's
// memory and localStorage, and leave the device only when the person taps Copy or Share. No frames, images or
// audio are ever recorded; only numbers, error names and timings.
const MAX_ENTRIES = 2000;
const MAX_MILESTONES = 200;
const KEY = "gs_vision_diag_v1";
const PREV_KEY = "gs_vision_diag_prev_v1";
const VERBOSE_KEY = "gs_diag_verbose";
const MEDIAPIPE_NOISE = /^[IWE]\d{4} \d{2}:\d{2}:\d{2}/;

const session = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
const startedAt = Date.now();
const entries = [];
const milestones = [];
let saveTimer = null;
let sentIndex = 0;
let noiseSeen = 0;
let exposed = {};
const videoCounts = {};
const frameWindow = { t0: 0, n: 0, face: 0, hands: 0, seg: 0, handsMax: 0, ms: { face: [], hands: [], seg: [] } };
const stats = { windows: [], totals: { frames: 0, faceFrames: 0, handFrames: 0, segRuns: 0 } };
const perms = {};
const tracks = [];
let battery = null;
let pressure = [];

function verbose() {
  try { return localStorage.getItem(VERBOSE_KEY) === "1" || /[?&]diag=verbose\b/.test(location.search); } catch (_) { return false; }
}

export function redact(text) {
  return String(text ?? "")
    .replace(/eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}/g, "[jwt]")
    .replace(/Bearer\s+[\w.~+/=-]+/gi, "Bearer [redacted]")
    .replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, "[email]")
    .replace(/([?&#](?:token|access_token|id_token|key|api_key|secret|password|auth|code)=)[^&\s#]+/gi, "$1[redacted]");
}

function short(value, limit = 300) {
  let text;
  try {
    if (typeof value === "string") text = value;
    else if (value instanceof Error) text = `${value.name}: ${value.message}`;
    else if (value && typeof value === "object") text = JSON.stringify(value);
    else text = String(value);
  } catch (_) { text = String(value); }
  return redact(text).slice(0, limit);
}

function persist() {
  if (saveTimer) return;
  saveTimer = setTimeout(() => {
    saveTimer = null;
    const body = { s: session, startedAt, at: Date.now(), milestones, entries };
    try { localStorage.setItem(KEY, JSON.stringify(body)); }
    catch (_) {
      try { localStorage.setItem(KEY, JSON.stringify({ ...body, entries: entries.slice(-500) })); } catch (__) { /* storage full or blocked */ }
    }
  }, 1000);
}

export function log(kind, message, data) {
  const entry = { t: Date.now(), k: kind, m: short(message) };
  if (data !== undefined) entry.d = data;
  entries.push(entry);
  if (entries.length > MAX_ENTRIES + 100) entries.splice(0, entries.length - MAX_ENTRIES);
  if (kind === "init" || kind === "mp" || kind === "gum" || kind === "perm" || kind === "error" || kind === "env") {
    if (milestones.length < MAX_MILESTONES) milestones.push(entry);
  }
  persist();
  return entry;
}

function installConsole() {
  for (const level of ["log", "info", "warn", "error", "debug"]) {
    const original = console[level];
    if (typeof original !== "function" || original.__gsDiag) continue;
    const wrapped = function (...args) {
      try {
        const text = args.map((a) => short(a, 200)).join(" ");
        // MediaPipe prints hundreds of "I1025 ..." info lines; keep the first few and every warning or error.
        if (MEDIAPIPE_NOISE.test(text) && (level === "log" || level === "info")) {
          noiseSeen += 1;
          if (noiseSeen <= 12 || verbose()) log(`console.${level}`, text);
        } else log(`console.${level}`, text);
      } catch (_) { /* never break the page for a log */ }
      return original.apply(this, args);
    };
    wrapped.__gsDiag = true;
    console[level] = wrapped;
  }
}

function installErrors() {
  addEventListener("error", (event) => {
    log("error", `window.onerror: ${event.message || "error"} @ ${String(event.filename || "").split("/").pop()}:${event.lineno || 0}:${event.colno || 0}`);
  });
  addEventListener("unhandledrejection", (event) => {
    log("error", `unhandledrejection: ${short(event.reason)}`);
  });
}

function trackInfo(stream) {
  const out = [];
  for (const track of stream?.getTracks?.() || []) {
    const s = track.getSettings?.() || {};
    out.push({
      kind: track.kind, label: short(track.label || "", 60), state: track.readyState,
      width: s.width, height: s.height, fps: s.frameRate ? Math.round(s.frameRate * 10) / 10 : undefined,
      facing: s.facingMode, deviceId: s.deviceId ? "present" : undefined,
    });
  }
  return out;
}

function installGetUserMedia() {
  const md = navigator.mediaDevices;
  if (!md || typeof md.getUserMedia !== "function" || md.getUserMedia.__gsDiag) return;
  const original = md.getUserMedia.bind(md);
  const wrapped = async (constraints) => {
    const t0 = performance.now();
    log("gum", `request ${short(constraints, 160)}`);
    try {
      const stream = await original(constraints);
      const info = trackInfo(stream);
      tracks.splice(0, tracks.length, ...info);
      log("gum", `ok in ${Math.round(performance.now() - t0)} ms`, info);
      for (const track of stream.getTracks()) {
        track.addEventListener?.("ended", () => log("gum", `track ended (${track.kind})`));
        track.addEventListener?.("mute", () => log("gum", `track muted (${track.kind})`));
        track.addEventListener?.("unmute", () => log("gum", `track unmuted (${track.kind})`));
      }
      return stream;
    } catch (error) {
      log("gum", `FAILED ${error?.name || "Error"}: ${short(error?.message || "", 160)} after ${Math.round(performance.now() - t0)} ms`);
      log("error", `getUserMedia ${error?.name || "Error"}`);
      throw error;
    }
  };
  wrapped.__gsDiag = true;
  md.getUserMedia = wrapped;
}

function watchPermissions() {
  for (const name of ["camera", "microphone"]) {
    try {
      if (!navigator.permissions?.query) { perms[name] = "unsupported"; continue; }
      navigator.permissions.query({ name }).then((status) => {
        perms[name] = status.state;
        log("perm", `${name}: ${status.state}`);
        status.onchange = () => { perms[name] = status.state; log("perm", `${name} -> ${status.state}`); };
      }).catch((error) => { perms[name] = `unsupported (${error?.name || "error"})`; log("perm", `${name} query unsupported: ${error?.name || "error"}`); });
    } catch (error) { perms[name] = "unsupported"; }
  }
}

export function attachVideo(video) {
  if (!video || video.__gsDiag) return;
  video.__gsDiag = true;
  for (const type of ["loadedmetadata", "loadeddata", "canplay", "playing", "pause", "waiting", "stalled", "suspend", "emptied", "ended", "error", "resize"]) {
    video.addEventListener(type, () => {
      videoCounts[type] = (videoCounts[type] || 0) + 1;
      if (videoCounts[type] > 25 && !verbose()) return;
      log("video", `${type} ${video.videoWidth || 0}x${video.videoHeight || 0} ready=${video.readyState}${video.error ? ` err=${video.error.code}` : ""}`);
    });
  }
}

export function attachStream(stream) {
  const info = trackInfo(stream);
  tracks.splice(0, tracks.length, ...info);
}

export function begin(name, detail) {
  const t0 = performance.now();
  return (extra) => {
    const ms = Math.round(performance.now() - t0);
    log("mp", `${name} ${ms} ms`, { ms, ...(detail || {}), ...(extra || {}) });
    return ms;
  };
}

export function stage(name, data) { return log("mp", name, data); }

function percentile(sorted, p) {
  if (!sorted.length) return null;
  return Math.round(sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))] * 10) / 10;
}

function flushWindow(now) {
  const w = frameWindow;
  if (!w.n) { w.t0 = now; return; }
  const seconds = Math.max(0.25, (now - w.t0) / 1000);
  const row = {
    fps: Math.round((w.n / seconds) * 10) / 10, frames: w.n, face: w.face, handsMax: w.handsMax, handFrames: w.hands, seg: w.seg,
  };
  for (const key of ["face", "hands", "seg"]) {
    const sorted = w.ms[key].slice().sort((a, b) => a - b);
    row[`${key}P50`] = percentile(sorted, 0.5);
    row[`${key}P95`] = percentile(sorted, 0.95);
  }
  stats.windows.push(row);
  if (stats.windows.length > 120) stats.windows.shift();
  log("det", `${row.fps} fps · face ${row.face}/${row.frames} · hands max ${row.handsMax} · outline ${row.seg} · ms p50/p95 face ${row.faceP50}/${row.faceP95} hands ${row.handsP50}/${row.handsP95} outline ${row.segP50}/${row.segP95}`, row);
  w.t0 = now; w.n = 0; w.face = 0; w.hands = 0; w.seg = 0; w.handsMax = 0; w.ms = { face: [], hands: [], seg: [] };
}

export function frame(sample) {
  const now = performance.now();
  if (!frameWindow.t0) frameWindow.t0 = now;
  frameWindow.n += 1;
  stats.totals.frames += 1;
  if (sample?.face) { frameWindow.face += 1; stats.totals.faceFrames += 1; }
  const hands = Number(sample?.hands) || 0;
  if (hands) { frameWindow.hands += 1; stats.totals.handFrames += 1; }
  frameWindow.handsMax = Math.max(frameWindow.handsMax, hands);
  if (sample?.segRan) { frameWindow.seg += 1; stats.totals.segRuns += 1; }
  for (const key of ["face", "hands", "seg"]) {
    const ms = sample?.[`${key}Ms`];
    if (Number.isFinite(ms)) frameWindow.ms[key].push(ms);
  }
  if (now - frameWindow.t0 >= 1000) flushWindow(now);
}

export function webglInfo() {
  const out = { webgl2: false, webgl1: false };
  let canvas;
  try {
    canvas = document.createElement("canvas");
    let gl = canvas.getContext("webgl2");
    if (gl) out.webgl2 = true;
    else { gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl"); if (gl) out.webgl1 = true; }
    if (!gl) return out;
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    out.vendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
    out.renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
    out.maxTexture = gl.getParameter(gl.MAX_TEXTURE_SIZE);
    out.floatRender = Boolean(gl.getExtension("EXT_color_buffer_float") || gl.getExtension("WEBGL_color_buffer_float"));
    out.halfFloatRender = Boolean(gl.getExtension("EXT_color_buffer_half_float"));
    out.floatLinear = Boolean(gl.getExtension("OES_texture_float_linear"));
    out.software = /swiftshader|llvmpipe|software|basic render/i.test(String(out.renderer));
    gl.getExtension("WEBGL_lose_context")?.loseContext();
  } catch (error) { out.error = short(error, 80); }
  return out;
}

export function wasmInfo() {
  // Smallest module that uses a SIMD instruction: validates only where wasm SIMD works.
  const simdBytes = new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11]);
  let simd = false;
  try { simd = typeof WebAssembly === "object" && WebAssembly.validate(simdBytes); } catch (_) { simd = false; }
  return {
    webassembly: typeof WebAssembly === "object",
    simd,
    sharedArrayBuffer: typeof SharedArrayBuffer === "function",
    crossOriginIsolated: Boolean(self.crossOriginIsolated),
  };
}

export function env() {
  const ua = navigator.userAgent || "";
  const android = /Android (\d+(?:\.\d+)*)/.exec(ua)?.[1];
  const ios = /OS (\d+(?:[_.]\d+)*) like Mac OS X/.exec(ua)?.[1]?.replace(/_/g, ".");
  const chrome = /(?:Chrome|CriOS)\/([\d.]+)/.exec(ua)?.[1];
  const conn = navigator.connection || {};
  const mem = performance.memory;
  return {
    userAgent: redact(ua),
    platform: android ? `Android ${android}` : ios ? `iOS ${ios}` : navigator.platform || "unknown",
    chromeVersion: chrome,
    androidWebView: /; wv\)/.test(ua) || (/Android/.test(ua) && /Version\/\d/.test(ua)),
    inApp: Boolean(window.ReactNativeWebView),
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemoryGB: navigator.deviceMemory,
    screen: `${screen.width}x${screen.height}`,
    viewport: `${innerWidth}x${innerHeight}`,
    devicePixelRatio: window.devicePixelRatio,
    orientation: `${screen.orientation?.type || (innerWidth > innerHeight ? "landscape" : "portrait")} ${screen.orientation?.angle ?? ""}`.trim(),
    secureContext: window.isSecureContext !== false,
    connection: conn.effectiveType ? `${conn.effectiveType} ${conn.downlink ?? "?"}Mbps rtt ${conn.rtt ?? "?"}ms${conn.saveData ? " saveData" : ""}` : "unknown",
    jsHeapMB: mem ? { used: Math.round(mem.usedJSHeapSize / 1048576), total: Math.round(mem.totalJSHeapSize / 1048576), limit: Math.round(mem.jsHeapSizeLimit / 1048576) } : undefined,
    language: navigator.language,
    battery,
    pressure: pressure.length ? pressure.slice(-3) : undefined,
    thermal: pressure.length ? undefined : "no browser API (Compute Pressure not available)",
  };
}

function resourceTimings() {
  try {
    return performance.getEntriesByType("resource")
      .filter((r) => /vendor\/vision|vision-models|face_landmarker|hand_landmarker|selfie_segmenter|tasks-vision|vision_wasm/.test(r.name))
      .map((r) => ({
        file: r.name.split("/").slice(-1)[0].split("?")[0], ms: Math.round(r.duration), start: Math.round(r.startTime),
        bytes: r.encodedBodySize || r.decodedBodySize || 0, fromCache: r.transferSize === 0 && (r.encodedBodySize || 0) > 0,
      }));
  } catch (_) { return []; }
}

export function report({ tail = 300 } = {}) {
  const state = exposed.getVisionDiag?.() || null;
  return {
    tool: "salareen-vision-diag/1",
    session,
    generatedAt: new Date().toISOString(),
    page: redact(location.pathname + location.search),
    uptimeSec: Math.round((Date.now() - startedAt) / 1000),
    env: env(),
    webgl: webglInfo(),
    wasm: wasmInfo(),
    permissions: { ...perms },
    tracks: tracks.slice(),
    video: { ...videoCounts },
    mediapipe: { state, resources: resourceTimings(), noiseLinesSkipped: Math.max(0, noiseSeen - 12) },
    stats: { totals: { ...stats.totals }, recent: stats.windows.slice(-10) },
    counts: {
      entries: entries.length,
      errors: entries.filter((e) => e.k === "error" || e.k === "console.error").length,
      warnings: entries.filter((e) => e.k === "console.warn").length,
    },
    milestones: milestones.slice(),
    tail: entries.slice(-tail),
  };
}

function line(entry) {
  const time = new Date(entry.t).toISOString().slice(11, 23);
  return `${time} ${entry.k.padEnd(13)} ${entry.m}`;
}

export function text({ tail = 300 } = {}) {
  const r = report({ tail });
  const lines = [];
  lines.push(`Salareen camera diagnostics (${r.tool})`, `generated ${r.generatedAt}  page ${r.page}  uptime ${r.uptimeSec}s  session ${r.session}`, "");
  lines.push("== Device", ...Object.entries(r.env).filter(([, v]) => v !== undefined).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`), "");
  lines.push("== WebGL", JSON.stringify(r.webgl), "== WebAssembly", JSON.stringify(r.wasm), "");
  lines.push("== Permissions", JSON.stringify(r.permissions), "== Camera tracks", JSON.stringify(r.tracks), "== Video events", JSON.stringify(r.video), "");
  lines.push("== MediaPipe", JSON.stringify(r.mediapipe.state), ...r.mediapipe.resources.map((x) => `${x.file}  ${x.ms} ms  ${x.bytes} bytes${x.fromCache ? "  (cache)" : ""}`), "");
  lines.push("== Detection (last windows)", ...r.stats.recent.map((w) => `${w.fps} fps  face ${w.face}/${w.frames}  hands max ${w.handsMax}  ms p50/p95 face ${w.faceP50}/${w.faceP95} hands ${w.handsP50}/${w.handsP95} outline ${w.segP50}/${w.segP95}`), `totals ${JSON.stringify(r.stats.totals)}`, "");
  lines.push(`== Log (${r.counts.entries} entries, ${r.counts.errors} errors, ${r.counts.warnings} warnings; last ${r.tail.length})`, ...r.tail.map(line));
  return redact(lines.join("\n"));
}

export function previousSession() {
  try { return JSON.parse(localStorage.getItem(PREV_KEY) || "null"); } catch (_) { return null; }
}

export function clear() { entries.length = 0; milestones.length = 0; sentIndex = 0; persist(); }

// Test and diagnostics hook: the page hands over read-only getters; nothing here changes behaviour.
export function expose(hooks) {
  exposed = { ...exposed, ...hooks };
  window.__gsVision = exposed;
}

function startBridge() {
  const bridge = window.ReactNativeWebView;
  if (!bridge || typeof bridge.postMessage !== "function") return;
  setInterval(() => {
    if (sentIndex > entries.length) sentIndex = 0;
    const fresh = entries.slice(sentIndex, sentIndex + 100);
    if (!fresh.length) return;
    sentIndex += fresh.length;
    try { bridge.postMessage(JSON.stringify({ type: "salareen-diag", session, entries: fresh })); } catch (_) { /* the app may be closing */ }
  }, 2000);
}

function startExtras() {
  try {
    navigator.getBattery?.().then((b) => { battery = { level: Math.round(b.level * 100), charging: b.charging }; }).catch(() => {});
  } catch (_) { /* no battery API */ }
  try {
    if (typeof PressureObserver === "function") {
      const observer = new PressureObserver((records) => { for (const r of records) { pressure.push(`${r.source}:${r.state}`); log("env", `pressure ${r.source} ${r.state}`); } });
      observer.observe("cpu", { sampleInterval: 2000 }).catch(() => {});
    }
  } catch (_) { /* Compute Pressure needs a permissions policy; not available here */ }
}

function boot() {
  if (window.__gsDiagBooted) return;
  window.__gsDiagBooted = true;
  try {
    const old = localStorage.getItem(KEY);
    if (old) localStorage.setItem(PREV_KEY, old);   // keep the last session across a crash or reload
  } catch (_) { /* storage blocked */ }
  installConsole();
  installErrors();
  installGetUserMedia();
  watchPermissions();
  startExtras();
  startBridge();
  const e = env();
  log("env", `${e.platform} · ${e.androidWebView ? "WebView" : "browser"}${e.chromeVersion ? ` ${e.chromeVersion}` : ""} · ${e.screen} dpr ${e.devicePixelRatio} · cores ${e.hardwareConcurrency ?? "?"} mem ${e.deviceMemoryGB ?? "?"}GB · ${e.connection}`);
  const gl = webglInfo(); const wasm = wasmInfo();
  log("env", `WebGL ${gl.webgl2 ? "2" : gl.webgl1 ? "1" : "none"} ${gl.renderer || ""}${gl.software ? " (software)" : ""} · wasm simd ${wasm.simd} · SAB ${wasm.sharedArrayBuffer} · isolated ${wasm.crossOriginIsolated}`);
  addEventListener("pagehide", () => { saveTimer = null; try { localStorage.setItem(KEY, JSON.stringify({ s: session, startedAt, at: Date.now(), milestones, entries })); } catch (_) { /* full */ } });
  addEventListener("orientationchange", () => log("env", `orientation ${screen.orientation?.type || ""} ${innerWidth}x${innerHeight}`));
  document.addEventListener("visibilitychange", () => log("env", `visibility ${document.visibilityState}`));
  window.__gsDiag = { log, report, text, previousSession, clear, redact, session };
}

boot();
export const diag = { log, begin, stage, frame, attachVideo, attachStream, expose, report, text, redact, webglInfo, wasmInfo, env, previousSession, clear, verbose };
