// Camera check page (/diag/vision): camera -> MediaPipe load -> a few seconds of live detection -> verdict + report.
import {diag} from "./vision_diag.js";
import {loadVisionAssets} from "./vision_assets.js";
import {FACE_BLEND_VARIANT, buildLadders, createFace, createFeeder, createFirstWorking, createHands, createRecipeCache, detectEnv, memoryStorage, runVariantTest, variantOf} from "./vision_detectors.js";

const $ = (id) => document.getElementById(id);
const VISION = {
  module: "/vendor/vision/tasks-vision.mjs", wasm: "/vendor/vision/wasm",
  face: "/vendor/vision/face_landmarker.task", hand: "/vendor/vision/hand_landmarker.task",
  segment: "/vendor/vision/selfie_segmenter.tflite",
};
const SECONDS = Math.max(4, Math.min(60, Number(new URLSearchParams(location.search).get("seconds")) || 12));
const rows = new Map();
let running = false;
let stream = null;
let models = { face: null, hands: null, segmenter: null };
let result = null;
let detectCtx = null;
let modelVariants = { face: null, hands: null };
let variantTests = null;
const frameFor = createFeeder();
// The same device rules, ladders and recipe cache as the game: this page is the regression harness for the game, and a Hand test
// that finds a recipe that works writes it to the cache, so running the check also fixes the game on this phone.
const env = detectEnv();
const recipeCache = createRecipeCache((() => { try { return localStorage; } catch (_) { return memoryStorage(); } })());
let ladders = buildLadders(env, recipeCache.load(env));
const nextFrame = (video) => new Promise((resolve) => (video.requestVideoFrameCallback ? video.requestVideoFrameCallback(() => resolve()) : requestAnimationFrame(() => resolve())));

function setRow(key, label, value, level) {
  rows.set(key, { label, value, level: level || "" });
  const table = $("rows");
  table.innerHTML = [...rows.values()].map((r) => `<tr><td>${esc(r.label)}</td><td class="${r.level}">${esc(r.value)}</td></tr>`).join("");
}
function esc(text) { return String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
function status(text) { $("status").textContent = text; diag.log("init", `status: ${text}`); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function percentile(list, p) {
  if (!list.length) return null;
  const sorted = list.slice().sort((a, b) => a - b);
  return Math.round(sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))] * 10) / 10;
}

async function openCamera() {
  const attempts = [
    { video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
    { video: true, audio: false },
  ];
  let last = null;
  for (const constraints of attempts) {
    try { return await navigator.mediaDevices.getUserMedia(constraints); }
    catch (error) {
      last = error;
      if (error?.name === "NotAllowedError" || error?.name === "SecurityError") break;
    }
  }
  throw last || new Error("no camera");
}

async function measureFps(video, ms = 1500) {
  let frames = 0;
  const t0 = performance.now();
  await new Promise((resolve) => {
    const tick = () => {
      frames += 1;
      if (performance.now() - t0 >= ms) resolve(); else schedule();
    };
    const schedule = () => (video.requestVideoFrameCallback ? video.requestVideoFrameCallback(tick) : requestAnimationFrame(tick));
    schedule();
    setTimeout(resolve, ms + 1500);
  });
  return Math.round((frames / ((performance.now() - t0) / 1000)) * 10) / 10;
}

async function loadContext() {
  const timings = {};
  const endLib = diag.begin("library import");
  const vision = await import(VISION.module);
  timings.library = endLib();
  const lowMemory = Number(navigator.deviceMemory) > 0 && Number(navigator.deviceMemory) <= 2;
  let assets = null;
  const endAssets = diag.begin("asset cache");
  try {
    assets = await loadVisionAssets({ segment: !lowMemory });
    timings.assets = endAssets({ backend: assets.stats.backend, hits: assets.stats.hits, misses: assets.stats.misses, networkMB: Math.round(assets.stats.networkBytes / 104857.6) / 10 });
  } catch (error) { timings.assets = endAssets({ ok: false, reason: String(error?.message || error).slice(0, 120) }); }
  const endWasm = diag.begin("wasm fileset");
  const files = assets ? assets.files : await vision.FilesetResolver.forVisionTasks(VISION.wasm);
  timings.wasm = endWasm();
  const modelBase = (key, path, delegate) => (assets?.models?.[key] ? { modelAssetBuffer: assets.models[key].slice(), delegate } : { modelAssetPath: path, delegate });
  return { ctx: { vision, files, modelBase, source: VISION }, timings, lowMemory, assets: assets?.stats || null };
}

// Same builders and recipe ladders as the games (vision_detectors.js): this page is the regression harness for the game.
async function loadModels() {
  const loaded = await loadContext();
  detectCtx = loaded.ctx;
  const { ctx, timings, lowMemory } = loaded;
  const make = async (name, list, create) => {
    const end = diag.begin(`${name} model`);
    const run = await createFirstWorking(list, create, { note: (variant, error) => diag.log("error", `${name} ${variant.id}: ${String(error?.message || error).slice(0, 120)}`) });
    const ms = end({ ok: Boolean(run.model), variant: run.variant?.id || "", reason: run.errors.slice(-1)[0] || "" });
    return run.model
      ? { model: run.model, delegate: run.variant.delegate, variant: run.variant.id, index: run.index, ms, fellBack: run.index > 0 }
      : { model: null, delegate: "none", variant: "", index: -1, ms: 0 };
  };
  ladders = buildLadders(env, recipeCache.load(env));
  diag.log("env", `renderer=${env.renderer.slice(0, 90)} browser=${env.browser} mobile=${env.mobile} rules=[${env.rules.join("; ")}] remembered=${JSON.stringify(recipeCache.load(env))} ignored=${JSON.stringify(ladders.ignored)}`);
  const face = await make("face", ladders.face, (variant) => createFace(ctx, variant));
  const hands = await make("hand", ladders.hands, (variant) => createHands(ctx, variant));
  modelVariants = { face: variantOf(ladders.face, face.index), hands: variantOf(ladders.hands, hands.index) };
  const segment = lowMemory
    ? { model: null, delegate: "skipped (low memory)", ms: 0 }
    : await (async () => {
      for (const delegate of ["GPU", "CPU"]) {
        const end = diag.begin(`outline model ${delegate}`);
        try {
          const model = await ctx.vision.ImageSegmenter.createFromOptions(ctx.files, {
            baseOptions: ctx.modelBase("segment", VISION.segment, delegate), runningMode: "VIDEO", outputCategoryMask: true, outputConfidenceMasks: false });
          return { model, delegate, ms: end({ ok: true, delegate }), fellBack: delegate === "CPU" };
        } catch (error) { end({ ok: false, delegate, reason: String(error?.message || error).slice(0, 160) }); }
      }
      return { model: null, delegate: "none", ms: 0 };
    })();
  return { timings, face, hands, segment, assets: loaded.assets };
}

async function runDetection(video, seconds) {
  const stats = { frames: 0, faceFrames: 0, handFrames: 0, handsMax: 0, segRuns: 0, faceMs: [], handsMs: [], segMs: [] };
  const end = performance.now() + seconds * 1000;
  let lastTs = 0;
  while (performance.now() < end && running) {
    await nextFrame(video);
    if (video.readyState < 2) continue;
    const ts = Math.max(lastTs + 1, performance.now());
    lastTs = ts;
    const sample = {};
    stats.frames += 1;
    try {
      if (models.face) {
        const t = performance.now();
        const r = models.face.detectForVideo(frameFor(video, modelVariants.face), ts);
        sample.faceMs = performance.now() - t;
        sample.face = Boolean(r.faceLandmarks?.[0]);
        stats.faceMs.push(sample.faceMs);
        if (sample.face) stats.faceFrames += 1;
      }
      if (models.hands) {
        const t = performance.now();
        const r = models.hands.detectForVideo(frameFor(video, modelVariants.hands), ts);
        sample.handsMs = performance.now() - t;
        sample.hands = r.landmarks?.length || 0;
        stats.handsMs.push(sample.handsMs);
        if (sample.hands) stats.handFrames += 1;
        stats.handsMax = Math.max(stats.handsMax, sample.hands);
      }
      if (models.segmenter && stats.frames % 3 === 0) {
        const t = performance.now();
        const r = models.segmenter.segmentForVideo(video, ts);
        r?.categoryMask?.close?.();
        sample.segMs = performance.now() - t; sample.segRan = true;
        stats.segMs.push(sample.segMs); stats.segRuns += 1;
      }
    } catch (error) {
      diag.log("error", `detect frame failed: ${error?.name || "Error"} ${String(error?.message || "").slice(0, 120)}`);
    }
    diag.frame(sample);
    if (stats.frames % 5 === 0) {
      setRow("live", "Seeing now", `face ${sample.face ? "yes" : "no"} · hands ${sample.hands ?? 0} · ${stats.frames} frames`, sample.face || sample.hands ? "ok" : "warn");
    }
  }
  return stats;
}

function verdict(r) {
  const advice = [];
  let level = "ok";
  const bump = (to) => { if (to === "bad" || (to === "warn" && level === "ok")) level = to; };
  if (r.cameraError) { bump("bad"); advice.push(adviceForCamera(r.cameraError)); }
  if (!r.cameraError && !r.face?.model && !r.hands?.model) { bump("bad"); advice.push("The face and hand models could not start. Close other apps and tabs, check your connection, and try again."); }
  if (!r.cameraError && r.face?.model && r.stats.faceFrames === 0) { bump("warn"); advice.push("No face was found. Face the screen in good light and keep your whole face in view."); }
  if (!r.cameraError && r.hands?.model && r.stats.handFrames === 0) { bump("warn"); advice.push("No hand was found. Hold one open hand in front of the camera, about arm's length away."); }
  if (r.face?.fellBack || r.hands?.fellBack) { bump("warn"); advice.push("The graphics chip was not used (the check fell back to the CPU). Games will run, but slower."); }
  if (r.gl?.software) { bump("warn"); advice.push("This device only has software graphics. Expect slow hand tracking."); }
  if (r.wasm && !r.wasm.simd) { bump("warn"); advice.push("This browser lacks fast WebAssembly (SIMD). Update the system WebView or browser."); }
  const p95 = percentile(r.stats.handsMs.concat(r.stats.faceMs), 0.95);
  if (p95 && p95 > 120) { bump("warn"); advice.push(`Detection is slow on this device (95th percentile ${p95} ms per frame).`); }
  if (r.fps && r.fps < 12) { bump("warn"); advice.push(`The camera delivers only ${r.fps} frames per second.`); }
  if (!advice.length) advice.push("Everything looks fine. If a game still misbehaves, copy the report and send it to us.");
  return { level, advice };
}

function adviceForCamera(name) {
  if (/NotAllowed|Security/.test(name)) return "The camera is blocked. Allow the camera for Salareen in your phone's Settings (or tap Allow in the pop-up), then run the check again.";
  if (/NotFound|Overconstrained/.test(name)) return "No camera was found on this device.";
  if (/NotReadable|Abort/.test(name)) return "Another app is using the camera. Close it and try again.";
  return `The camera could not start (${name}).`;
}

function renderReport() {
  const summary = result ? [
    "== Camera check result",
    `verdict: ${result.verdict.level.toUpperCase()}`,
    ...result.verdict.advice.map((a) => `- ${a}`),
    `camera: ${result.cameraError || "ok"} ${result.resolution || ""} ${result.fps ? `${result.fps} fps` : ""}`,
    `face: ${result.face?.delegate || "-"} (${result.face?.ms ?? "-"} ms)  hands: ${result.hands?.delegate || "-"} (${result.hands?.ms ?? "-"} ms)  outline: ${result.segment?.delegate || "-"} (${result.segment?.ms ?? "-"} ms)`,
    `detected: face ${result.stats.faceFrames}/${result.stats.frames} frames, hands ${result.stats.handFrames}/${result.stats.frames} (max ${result.stats.handsMax}), inference p50/p95 face ${percentile(result.stats.faceMs, 0.5)}/${percentile(result.stats.faceMs, 0.95)} hands ${percentile(result.stats.handsMs, 0.5)}/${percentile(result.stats.handsMs, 0.95)}`,
    "",
  ].join("\n") : "";
  const tests = variantTests ? [
    "== Hand / face setting test",
    `device rules: ${env.rules.join("; ") || "none"}   renderer: ${env.renderer.slice(0, 80) || "?"}   browser: ${env.browser}${env.ios ? "   (iOS: Safari engine)" : ""}`,
    ...[variantTests.face, variantTests.hands].flatMap((t) => t.rows.map((r) => `${t.kind} ${r.id}: ${r.created ? `${r.withHit}/${r.frames} frames, max ${r.max}` : "could not start"} (${r.delegate}, conf ${r.conf}, feed ${r.feed}${r.error ? `, ${r.error}` : ""})`)),
    `winner: face ${variantTests.face.winner || "none"}, hands ${variantTests.hands.winner || "none"}`,
    "",
  ].join("\n") : "";
  const full = summary + tests + diag.text({ tail: 200 });
  $("report").value = full;
  if (window.ReactNativeWebView?.postMessage) {
    try { window.ReactNativeWebView.postMessage(JSON.stringify({ type: "salareen-diag-report", text: full, level: result?.verdict.level || "unknown" })); } catch (_) { /* app closing */ }
  }
  return full;
}

// Tries every face and hand recipe (delegate, thresholds, blendshapes, frame feed) on live frames and reports which one sees you,
// so ONE pasted report identifies the working configuration for this phone.
async function variantTest() {
  if (running) return;
  running = true;
  $("handtest").disabled = true; $("start").disabled = true; $("stop").disabled = false;
  try {
    status("Hand test: hold ONE open hand in front of the camera, palm toward the screen, about an arm's length away, and keep your face in view.");
    const video = $("preview");
    if (!stream) {
      stream = await openCamera();
      diag.attachVideo(video); diag.attachStream(stream);
      video.hidden = false; video.srcObject = stream;
      try { await video.play(); } catch (_) { /* autoplay muted normally works */ }
    }
    if (!detectCtx) detectCtx = (await loadContext()).ctx;
    const show = (label) => (row) => setRow(`vt-${row.kind}-${row.id}`, `${label}: ${row.id}`,
      row.created ? `${row.withHit}/${row.frames} frames saw one${row.error ? ` (${row.error})` : ""}` : `could not start (${row.error || "unknown"})`, row.withHit ? "ok" : "warn");
    ladders = buildLadders(env, {});   // test in the platform's preference order (first working one wins), ignoring what was remembered
    const face = await runVariantTest({ kind: "face", ctx: detectCtx, video, seconds: 3, nextFrame, variants: [...ladders.face, FACE_BLEND_VARIANT], onProgress: show("Face setting") });   // each variant is warmed up before timing (the first inference compiles shaders), so order does not confound; the opt-in blendshape recipe is never the winner
    const hands = await runVariantTest({ kind: "hands", ctx: detectCtx, video, seconds: 4, nextFrame, variants: ladders.hands, onProgress: show("Hand setting") });   // 4 s each: the first frames after a model is built can be slow (iOS)
    variantTests = { face, hands };
    window.__gsDiagVariantTests = variantTests;
    for (const t of [face, hands]) for (const row of t.rows) diag.log("variant-test", `${t.kind} ${row.id} delegate=${row.delegate} conf=${row.conf} feed=${row.feed}${row.blendshapes !== undefined ? ` blend=${row.blendshapes}` : ""}: ${row.withHit}/${row.frames} frames, max ${row.max}, create ${row.ms} ms${row.error ? ` error=${row.error}` : ""}`);
    diag.log("variant-test", `winner face=${face.winner || "none"} hands=${hands.winner || "none"}`);
    // Remember what worked on THIS device (keyed by GPU renderer + browser version) so the game starts on it next time.
    const saved = [];
    if (face.winner) { recipeCache.save(env, "face", face.winner); saved.push(`face=${face.winner}`); }
    if (hands.winner) { recipeCache.save(env, "hands", hands.winner); saved.push(`hands=${hands.winner}`); }
    diag.log("variant-test", saved.length ? `saved to this device's recipe cache: ${saved.join(", ")}` : "nothing saved (no setting saw a face or hand)");
    if (saved.length) setRow("vt-saved", "Remembered for the game", saved.join(", "), "ok");
    setRow("vt-winner", "Hand setting that worked", hands.saw ? hands.winner : "none saw a hand", hands.saw ? "ok" : "bad");
    status(hands.saw ? `Done. Hands were seen with the "${hands.winner}" setting.` : "Done. No setting saw a hand: if an open hand was in view, please send this report.");
  } catch (error) {
    diag.log("error", `variant test failed: ${error?.name || "Error"} ${String(error?.message || "").slice(0, 120)}`);
    setRow("vt-error", "Hand test", String(error?.name || error?.message || "failed"), "bad");
  }
  stop(false);
  $("handtest").disabled = false; $("start").disabled = false;
  renderReport();
}

async function start() {
  if (running) return;
  running = true;
  rows.clear(); result = null;
  $("start").disabled = true; $("stop").disabled = false;
  $("verdict").textContent = "Running…"; $("verdict").className = ""; $("advice").innerHTML = "";
  const gl = diag.webglInfo(); const wasm = diag.wasmInfo(); const env = diag.env();
  setRow("secure", "Secure page (https)", env.secureContext ? "yes" : "NO: the camera needs https", env.secureContext ? "ok" : "bad");
  setRow("device", "Device", `${env.platform}${env.androidWebView ? " WebView" : ""}${env.chromeVersion ? ` · Chrome ${env.chromeVersion}` : ""}${env.inApp ? " · in the Salareen app" : ""}`);
  setRow("hw", "Cores / memory", `${env.hardwareConcurrency ?? "?"} cores · ${env.deviceMemoryGB ?? "?"} GB`);
  setRow("gl", "Graphics", gl.webgl2 || gl.webgl1 ? `${gl.renderer || "WebGL"}${gl.software ? " (software)" : ""}` : "no WebGL", gl.webgl2 || gl.webgl1 ? (gl.software ? "warn" : "ok") : "bad");
  setRow("wasm", "WebAssembly SIMD", wasm.simd ? "yes" : "no (slower)", wasm.simd ? "ok" : "warn");
  const out = { stats: { frames: 0, faceFrames: 0, handFrames: 0, handsMax: 0, faceMs: [], handsMs: [], segMs: [] }, gl, wasm };
  try {
    status("Asking for the camera. Tap Allow if your phone asks.");
    stream = await openCamera();
    const video = $("preview");
    diag.attachVideo(video); diag.attachStream(stream);
    video.hidden = false; video.srcObject = stream;
    try { await video.play(); } catch (_) { /* autoplay muted normally works */ }
    const track = stream.getVideoTracks()[0];
    const s = track?.getSettings?.() || {};
    out.resolution = `${video.videoWidth || s.width || "?"}x${video.videoHeight || s.height || "?"}`;
    out.fps = await measureFps(video);
    setRow("cam", "Camera", `${out.resolution} · ${out.fps} fps measured${s.facingMode ? ` · ${s.facingMode}` : ""}`, out.fps >= 12 ? "ok" : "warn");
    status("Loading the face, hand and outline models…");
    const loaded = await loadModels();
    models = { face: loaded.face.model, hands: loaded.hands.model, segmenter: loaded.segment.model };
    Object.assign(out, { face: loaded.face, hands: loaded.hands, segment: loaded.segment, loadMs: loaded.timings });
    const lvl = (m) => (m.model ? (m.fellBack ? "warn" : "ok") : "bad");
    setRow("lib", "MediaPipe library", `${loaded.timings.library} ms import · ${loaded.timings.wasm} ms wasm`, "ok");
    if (loaded.assets) {
      const a = loaded.assets;
      setRow("assets", "Model files", `${(a.bytes / 1048576).toFixed(1)} MB · ${a.hits} from saved copy, ${a.misses} downloaded (${(a.networkBytes / 1048576).toFixed(1)} MB) · ${a.backend} · ${a.ms} ms`, a.backend === "none" ? "warn" : "ok");
    } else setRow("assets", "Model files", "loaded straight from the site (no saved copy possible)", "warn");
    setRow("face", "Face model", m(loaded.face), lvl(loaded.face));
    setRow("hands", "Hand model", m(loaded.hands), lvl(loaded.hands));
    setRow("seg", "Body outline model", loaded.segment.model ? m(loaded.segment) : loaded.segment.delegate === "none" ? "unavailable" : loaded.segment.delegate, loaded.segment.model ? lvl(loaded.segment) : "warn");
    status(`Detecting for ${SECONDS} seconds: keep your face and one open hand in view.`);
    out.stats = await runDetection(video, SECONDS);
  } catch (error) {
    out.cameraError = String(error?.name || error?.message || "error");
    diag.log("error", `camera check failed: ${out.cameraError} ${String(error?.message || "").slice(0, 120)}`);
    setRow("cam", "Camera", out.cameraError, "bad");
  }
  stop(false);
  const v = verdict(out);
  result = { ...out, verdict: v };
  const stats = out.stats;
  setRow("det", "Detection", `face ${stats.faceFrames}/${stats.frames} frames · hands ${stats.handFrames}/${stats.frames} (max ${stats.handsMax})`, stats.faceFrames || stats.handFrames ? "ok" : "warn");
  setRow("speed", "Speed (p50 / p95 ms)", `face ${percentile(stats.faceMs, 0.5) ?? "-"} / ${percentile(stats.faceMs, 0.95) ?? "-"} · hands ${percentile(stats.handsMs, 0.5) ?? "-"} / ${percentile(stats.handsMs, 0.95) ?? "-"}`);
  $("verdict").textContent = { ok: "Looks good", warn: "Works, with warnings", bad: "Problem found" }[v.level];
  $("verdict").className = v.level;
  $("advice").innerHTML = v.advice.map((a) => `<li>${esc(a)}</li>`).join("");
  status(v.level === "ok" ? "Done." : "Done. See the notes above.");
  renderReport();
  window.__gsDiagResult = { level: v.level, advice: v.advice, face: out.face?.delegate, hands: out.hands?.delegate, stats: { frames: stats.frames, faceFrames: stats.faceFrames, handFrames: stats.handFrames, handsMax: stats.handsMax }, cameraError: out.cameraError || "" };
}

function m(loaded) { return `${loaded.delegate} · ${loaded.ms} ms`; }

function stop(rerender = true) {
  running = false;
  try { stream?.getTracks().forEach((t) => t.stop()); } catch (_) { /* already stopped */ }
  stream = null;
  for (const model of Object.values(models)) { try { model?.close?.(); } catch (_) { /* closed */ } }
  models = { face: null, hands: null, segmenter: null };
  $("start").disabled = false; $("stop").disabled = true;
  if (rerender) { status("Stopped."); renderReport(); }
}

async function copyReport() {
  const text = renderReport();
  try { await navigator.clipboard.writeText(text); status("Report copied. Paste it into a message to us."); return; } catch (_) { /* fall through */ }
  const area = $("report");
  area.focus(); area.select();
  try { document.execCommand("copy"); status("Report copied."); } catch (_) { status("Select the text in the box and copy it."); }
}

$("start").addEventListener("click", () => { void start(); });
$("stop").addEventListener("click", () => stop(true));
$("handtest").addEventListener("click", () => { void variantTest(); });
$("copy").addEventListener("click", () => { void copyReport(); });
if (window.ReactNativeWebView?.postMessage) {
  $("share").hidden = false;
  $("share").addEventListener("click", () => {
    const text = renderReport();
    window.ReactNativeWebView.postMessage(JSON.stringify({ type: "salareen-diag-share", text }));
  });
}
diag.log("init", "camera check page ready");
renderReport();
