// Camera check page (/diag/vision): camera -> MediaPipe load -> a few seconds of live detection -> verdict + report.
import {diag} from "./vision_diag.js";
import {loadVisionAssets} from "./vision_assets.js";

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

async function loadModels() {
  const timings = {};
  let vision;
  const endLib = diag.begin("library import");
  vision = await import(VISION.module);
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
  const base = (key, path, delegate) => (assets?.models?.[key] ? { modelAssetBuffer: assets.models[key].slice(), delegate } : { modelAssetPath: path, delegate });
  const make = async (name, create) => {
    for (const delegate of ["GPU", "CPU"]) {
      const end = diag.begin(`${name} model ${delegate}`);
      try {
        const model = await create(delegate);
        const ms = end({ ok: true, delegate });
        return { model, delegate, ms, fellBack: delegate === "CPU" };
      } catch (error) {
        end({ ok: false, delegate, reason: String(error?.message || error).slice(0, 160) });
      }
    }
    return { model: null, delegate: "none", ms: 0 };
  };
  const face = await make("face", (delegate) => vision.FaceLandmarker.createFromOptions(files, {
    baseOptions: base("face", VISION.face, delegate), runningMode: "VIDEO", numFaces: 1, outputFaceBlendshapes: false }));
  const hands = await make("hand", (delegate) => vision.HandLandmarker.createFromOptions(files, {
    baseOptions: base("hand", VISION.hand, delegate), runningMode: "VIDEO", numHands: 2 }));
  const segment = lowMemory
    ? { model: null, delegate: "skipped (low memory)", ms: 0 }
    : await make("outline", (delegate) => vision.ImageSegmenter.createFromOptions(files, {
      baseOptions: base("segment", VISION.segment, delegate), runningMode: "VIDEO", outputCategoryMask: true, outputConfidenceMasks: false }));
  return { timings, face, hands, segment, assets: assets?.stats || null };
}

async function runDetection(video, seconds) {
  const stats = { frames: 0, faceFrames: 0, handFrames: 0, handsMax: 0, segRuns: 0, faceMs: [], handsMs: [], segMs: [] };
  const end = performance.now() + seconds * 1000;
  let lastTs = 0;
  while (performance.now() < end && running) {
    await new Promise((resolve) => (video.requestVideoFrameCallback ? video.requestVideoFrameCallback(() => resolve()) : requestAnimationFrame(() => resolve())));
    if (video.readyState < 2) continue;
    const ts = Math.max(lastTs + 1, performance.now());
    lastTs = ts;
    const sample = {};
    stats.frames += 1;
    try {
      if (models.face) {
        const t = performance.now();
        const r = models.face.detectForVideo(video, ts);
        sample.faceMs = performance.now() - t;
        sample.face = Boolean(r.faceLandmarks?.[0]);
        stats.faceMs.push(sample.faceMs);
        if (sample.face) stats.faceFrames += 1;
      }
      if (models.hands) {
        const t = performance.now();
        const r = models.hands.detectForVideo(video, ts);
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
  const full = summary + diag.text({ tail: 200 });
  $("report").value = full;
  if (window.ReactNativeWebView?.postMessage) {
    try { window.ReactNativeWebView.postMessage(JSON.stringify({ type: "salareen-diag-report", text: full, level: result?.verdict.level || "unknown" })); } catch (_) { /* app closing */ }
  }
  return full;
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
