#!/usr/bin/env node
// Mobile machine-vision checks: does the camera, face, hand and body-outline stack load and work on phone-sized
// browsers, and do the overlays line up with the video?
//
//   scripts/mobile_vision_fixtures.sh                       # once: builds the fake-camera clips (needs ffmpeg)
//   node scripts/mobile_vision_check.mjs                    # against https://salareen.com
//   node scripts/mobile_vision_check.mjs --base http://127.0.0.1:8018 --lab-path /lab   # a local children-lab
//   node scripts/mobile_vision_check.mjs --only assets,detect --out report.json
//
// Engines: Chromium with phone profiles (Pixel 7, iPhone 14 viewport) and a fake camera fed from a video file, plus
// WebKit (the iPhone WebView engine) for the library-level check, because WebKit cannot take a fake camera.
// This is evidence from emulation. A real phone is still needed for the camera permission prompt, the GPU and heat.
import { createRequire } from "node:module";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const pw = createRequire(import.meta.url)(path.join(here, "..", "apps", "web", "node_modules", "playwright"));

const argv = process.argv.slice(2);
const opt = (name, fallback) => { const i = argv.indexOf(`--${name}`); return i >= 0 ? argv[i + 1] : fallback; };
const BASE = opt("base", "https://salareen.com").replace(/\/$/, "");
const LAB = opt("lab-path", "/children-lab");
const DIAG = opt("diag-path", "/diag/vision");
const ONLY = opt("only", "") ? opt("only", "").split(",") : null;
const OUT = opt("out", "");
const FX = process.env.GS_VISION_FIXTURES || path.join(os.homedir(), ".cache", "gs-vision-fixtures");
const results = [];

const FILES = [
  ["tasks-vision.mjs", /javascript/, 100_000], ["face_landmarker.task", /octet-stream/, 1_000_000],
  ["hand_landmarker.task", /octet-stream/, 1_000_000], ["selfie_segmenter.tflite", /octet-stream/, 100_000],
  ["wasm/vision_wasm_internal.wasm", /application\/wasm/, 5_000_000], ["wasm/vision_wasm_internal.js", /javascript/, 50_000],
  ["wasm/vision_wasm_nosimd_internal.wasm", /application\/wasm/, 5_000_000], ["wasm/vision_wasm_nosimd_internal.js", /javascript/, 50_000],
];

async function check(id, title, fn) {
  if (ONLY && !ONLY.includes(id)) return;
  const t0 = Date.now();
  let row;
  try {
    const r = (await fn()) || {};
    row = { id, title, status: r.status || "pass", detail: r.detail || "", data: r.data };
  } catch (error) {
    row = { id, title, status: "fail", detail: String(error?.message || error).split("\n")[0].slice(0, 400) };
  }
  row.ms = Date.now() - t0;
  results.push(row);
  const tag = { pass: "PASS", fail: "FAIL", warn: "WARN", skip: "SKIP" }[row.status];
  console.log(`${tag}  ${id.padEnd(14)} ${title}${row.detail ? `\n        ${row.detail}` : ""}`);
}

const need = (clip) => { if (!fs.existsSync(`${FX}/${clip}.y4m`)) throw new Error(`missing ${clip}.y4m: run scripts/mobile_vision_fixtures.sh`); };
const launch = (clip) => {
  need(clip);
  return pw.chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", `--use-file-for-fake-video-capture=${FX}/${clip}.y4m`, "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
};

async function openLab(browser, device, { permissions = ["camera"], viewport } = {}) {
  const ctx = await browser.newContext({ ...pw.devices[device], ...(viewport ? { viewport } : {}), permissions });
  const page = await ctx.newPage();
  const logs = [];
  page.on("console", (m) => { if (["error", "warning"].includes(m.type())) logs.push(`${m.type()}: ${m.text().slice(0, 160)}`); });
  page.on("pageerror", (e) => logs.push(`pageerror: ${String(e).slice(0, 160)}`));
  await page.goto(`${BASE}${LAB}?embed=mobile`, { waitUntil: "load", timeout: 60000 });
  await page.waitForSelector("#start", { timeout: 30000 });
  return { ctx, page, logs };
}

async function startAndWait(page, maxSeconds = 120) {
  const t0 = Date.now();
  await page.click("#start");
  for (let i = 0; i < maxSeconds; i++) {
    await page.waitForTimeout(1000);
    const st = await page.evaluate(() => {
      const hook = window.__gsVision?.getVisionDiag?.();
      const text = document.getElementById("vision-status")?.textContent || "";
      return { hook, text };
    });
    if (st.hook && st.hook.face !== "pending" && st.hook.hands !== "pending" && st.hook.library !== "pending") return { seconds: (Date.now() - t0) / 1000, diag: st.hook };
    if (!st.hook && /ready|fallback|unavailable|Camera ready/i.test(st.text)) return { seconds: (Date.now() - t0) / 1000, text: st.text };
  }
  throw new Error(`vision did not become ready in ${maxSeconds}s`);
}

const hasHook = (page) => page.evaluate(() => Boolean(window.__gsVision?.getState));
const readout = (page) => page.evaluate(() => document.querySelector("#vision-readout")?.textContent || "");

async function waitFor(page, fn, arg, ms = 25000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    const value = await page.evaluate(fn, arg).catch(() => null);
    if (value) return value;
    await page.waitForTimeout(500);
  }
  return null;
}

// 1. Static files: reachable, correct type, cacheable.
await check("assets", "Vision files are served with the right type and a cache lifetime", async () => {
  const bad = []; const warn = [];
  for (const [file, type, min] of FILES) {
    const res = await fetch(`${BASE}/vendor/vision/${file}`, { cache: "no-store" });
    const ct = res.headers.get("content-type") || "";
    const len = Number(res.headers.get("content-length")) || (await res.arrayBuffer()).byteLength;
    const cc = res.headers.get("cache-control") || "";
    if (res.status !== 200) bad.push(`${file}: HTTP ${res.status}`);
    else {
      if (!type.test(ct)) bad.push(`${file}: content-type ${ct}`);
      if (len < min) bad.push(`${file}: only ${len} bytes`);
      const age = Number(/max-age=(\d+)/.exec(cc)?.[1] || 0);
      if (age < 86400) warn.push(`${file}: Cache-Control "${cc || "none"}"`);
    }
  }
  if (bad.length) throw new Error(bad.join("; "));
  if (warn.length) return { status: "fail", detail: `no cache lifetime, so a phone re-downloads ~21 MB per visit: ${warn.slice(0, 3).join("; ")}${warn.length > 3 ? ` (+${warn.length - 3} more)` : ""}` };
  return { detail: `${FILES.length} files, types ok, cacheable` };
});

await check("isolation", "WebAssembly SIMD and no-SIMD builds are both served; isolation is not required", async () => {
  const res = await fetch(`${BASE}${LAB}`);
  const coop = res.headers.get("cross-origin-opener-policy"); const coep = res.headers.get("cross-origin-embedder-policy");
  return { detail: `MediaPipe tasks-vision 0.10.14 runs single-threaded, so SharedArrayBuffer and COOP/COEP are not needed (COOP=${coop || "-"}, COEP=${coep || "-"}); the no-SIMD fallback files exist for older iPhones` };
});

// 2. Library-level check in the iPhone engine (WebKit) and Chromium: wasm + delegate + detection on a still photo.
const libraryCheck = (engineName) => async () => {
  need("face_p"); const photo = fs.readFileSync(`${FX}/woman_hands.jpg`).toString("base64");
  const browser = await pw[engineName].launch();
  try {
    const ctx = await browser.newContext({ ...pw.devices[engineName === "webkit" ? "iPhone 14" : "Pixel 7"] });
    const page = await ctx.newPage();
    await page.goto(`${BASE}${DIAG}`, { waitUntil: "load", timeout: 60000 });
    const out = await page.evaluate(async (b64) => {
      const r = { simd: WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11])) };
      const vision = await import("/vendor/vision/tasks-vision.mjs");
      const files = await vision.FilesetResolver.forVisionTasks("/vendor/vision/wasm");
      const blob = await (await fetch(`data:image/jpeg;base64,${b64}`)).blob();
      const bmp = await createImageBitmap(blob);
      const make = async (name, create, run) => {
        for (const delegate of ["GPU", "CPU"]) {
          try { const t = performance.now(); const model = await create(delegate); const load = Math.round(performance.now() - t);
            const t2 = performance.now(); const res = run(model); r[name] = { delegate, load, infer: Math.round(performance.now() - t2), found: res }; model.close?.(); return; }
          catch (e) { (r.errors ||= []).push(`${name} ${delegate}: ${String(e.message).slice(0, 100)}`); }
        }
        r[name] = { delegate: "none" };
      };
      await make("face", (d) => vision.FaceLandmarker.createFromOptions(files, { baseOptions: { modelAssetPath: "/vendor/vision/face_landmarker.task", delegate: d }, runningMode: "IMAGE", numFaces: 1 }), (m) => m.detect(bmp).faceLandmarks.length);
      await make("hands", (d) => vision.HandLandmarker.createFromOptions(files, { baseOptions: { modelAssetPath: "/vendor/vision/hand_landmarker.task", delegate: d }, runningMode: "IMAGE", numHands: 2 }), (m) => m.detect(bmp).landmarks.length);
      return r;
    }, photo);
    const problems = [];
    if (out.face?.delegate === "none") problems.push("face model failed");
    else if (!out.face.found) problems.push("face model loaded but found no face");
    if (out.hands?.delegate === "none") problems.push("hand model failed");
    else if (!out.hands.found) problems.push("hand model loaded but found no hand");
    const detail = `simd=${out.simd} face ${out.face?.delegate}(${out.face?.load}ms,found ${out.face?.found}) hands ${out.hands?.delegate}(${out.hands?.load}ms,found ${out.hands?.found})${out.errors ? ` fallbacks: ${out.errors.join(" | ")}` : ""}`;
    if (problems.length) throw new Error(`${problems.join(", ")}: ${detail}`);
    return { detail, status: out.face.delegate === "CPU" || out.hands.delegate === "CPU" ? "warn" : "pass", data: out };
  } finally { await browser.close(); }
};
await check("webkit", "iPhone engine (WebKit): library loads, wasm runs, face and hands are found in a photo", libraryCheck("webkit"));
await check("chromium-lib", "Android engine (Chromium): library loads, wasm runs, face and hands are found in a photo", libraryCheck("chromium"));

// 3. Real flow under a phone profile with the fake camera: detection, self-check, alignment, hand sides.
async function detectRun(clip, device, label) {
  const browser = await launch(clip);
  try {
    const { ctx, page, logs } = await openLab(browser, device);
    const ready = await startAndWait(page);
    await page.waitForTimeout(3500);
    const hook = await hasHook(page);
    const state = hook ? await page.evaluate(() => { const s = window.__gsVision.getState(); return { diag: s.visionDiag, face: Boolean(s.faceData), hands: s.handData.length }; }) : null;
    const text = await readout(page);
    return { ready, hook, state, text, logs, label };
  } finally { await browser.close(); }
}
await check("detect-face", "Pixel 7 + fake camera (face clip): the face model loads and finds the face", async () => {
  const r = await detectRun("face_p", "Pixel 7", "face");
  const face = r.hook ? r.state.face : /Face:\s*(?!none|—|-)/i.test(r.text);
  if (!face) throw new Error(`no face detected (readout "${r.text.slice(0, 80)}")`);
  return { detail: `ready in ${r.ready.seconds.toFixed(1)}s, ${r.hook ? `face ${r.state.diag.face}, hands ${r.state.diag.hands}` : "readout: " + r.text.slice(0, 70)}` };
});
await check("detect-hands", "Pixel 7 + fake camera (face + hands clip): both hands are found", async () => {
  const r = await detectRun("hands_p", "Pixel 7", "hands");
  const hands = r.hook ? r.state.hands : Number(/Hands:\s*(\d+)/i.exec(r.text)?.[1] || 0);
  if (!hands) throw new Error(`no hands detected (readout "${r.text.slice(0, 80)}")`);
  return { detail: `ready in ${r.ready.seconds.toFixed(1)}s, ${hands} hand(s) found${r.hook ? `, face ${r.state.diag.face}, hands ${r.state.diag.hands}` : ""}`, status: hands >= 2 ? "pass" : "warn" };
});
await check("detect-iphone", "iPhone 14 viewport + fake camera: same flow", async () => {
  const r = await detectRun("hands_p", "iPhone 14", "hands");
  const hands = r.hook ? r.state.hands : Number(/Hands:\s*(\d+)/i.exec(r.text)?.[1] || 0);
  if (!hands) throw new Error("no hands detected");
  return { detail: `ready in ${r.ready.seconds.toFixed(1)}s, ${hands} hand(s)` };
});

await check("selfcheck", "The page's own camera check reports correctly (camera allowed, then camera blocked)", async () => {
  const browser = await launch("face_p");
  let okRows, badRows, blockedAdvice;
  try {
    const good = await openLab(browser, "Pixel 7");
    await startAndWait(good.page);
    await good.page.evaluate(() => document.getElementById("vision-check-open").click());   // the button hides with the setup panel once play starts
    await good.page.waitForSelector("#vision-check .vc-list");
    okRows = await good.page.locator("#vision-check .vc-ok").count();
    badRows = await good.page.locator("#vision-check .vc-bad").count();
    await good.ctx.close();
    const denied = await openLab(browser, "Pixel 7", { permissions: [] });
    await denied.page.evaluate(() => { navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("denied", "NotAllowedError")); });
    await denied.page.click("#start");
    await denied.page.waitForSelector("#vision-check .vc-advice", { timeout: 20000 });
    blockedAdvice = (await denied.page.locator("#vision-check .vc-advice").innerText()).toLowerCase();
  } finally { await browser.close(); }
  if (badRows > 1) throw new Error(`healthy phone shows ${badRows} red rows`);
  if (!/blocked|allow/.test(blockedAdvice)) throw new Error(`blocked camera advice missing: "${blockedAdvice.slice(0, 100)}"`);
  return { detail: `healthy: ${okRows} green / ${badRows} red rows; blocked camera advises: "${blockedAdvice.slice(0, 70)}"` };
});

// 4. Overlay alignment: the app's mapping must match where the browser really draws the video.
await check("alignment", "Overlays line up with the video at phone sizes, portrait and landscape, mirrored", async () => {
  const worst = [];
  for (const clip of ["face_p", "face_l"]) {
    const browser = await launch(clip);
    try {
      const { page } = await openLab(browser, "Pixel 7");
      await startAndWait(page);
      await page.waitForTimeout(1500);
      for (const [name, w, h] of [["Pixel 7 portrait", 412, 915], ["Pixel 7 landscape", 915, 412], ["iPhone 14 portrait", 390, 844], ["iPhone 14 landscape", 844, 390]]) {
        await page.setViewportSize({ width: w, height: h });
        await page.waitForTimeout(700);
        const g = await page.evaluate(async () => {
          const vm = await import("/static/vision_math.js");
          const stage = document.getElementById("stage"), video = document.getElementById("camera"), canvas = document.getElementById("overlay");
          const sr = stage.getBoundingClientRect(), vr = video.getBoundingClientRect(), cr = canvas.getBoundingClientRect();
          const cs = getComputedStyle(video);
          const mirrored = cs.transform !== "none" && new DOMMatrix(cs.transform).a < 0;
          const vw = video.videoWidth, vh = video.videoHeight, fit = cs.objectFit;
          const W = vr.width, H = vr.height;
          const scale = fit === "cover" ? Math.max(W / vw, H / vh) : fit === "contain" ? Math.min(W / vw, H / vh) : null;
          const frame = vm.coverFrame(sr.width, sr.height, vw, vh);
          let worstPx = 0; let compared = 0;
          if (scale) {
            const dw = vw * scale, dh = vh * scale, ox = (W - dw) / 2, oy = (H - dh) / 2;
            for (let px = 0.05; px <= 0.951; px += 0.15) for (let py = 0.05; py <= 0.951; py += 0.15) {
              const app = vm.mapMirroredLandmark({ x: px, y: py }, frame);
              let ex = ox + px * dw; if (mirrored) ex = W - ex;
              const ey = oy + py * dh;
              worstPx = Math.max(worstPx, Math.hypot(app.x - (ex + vr.left - sr.left), app.y - (ey + vr.top - sr.top))); compared += 1;
            }
          }
          const dpr = Math.min(2, window.devicePixelRatio || 1);
          return { mirrored, fit, vw, vh, stage: [Math.round(sr.width), Math.round(sr.height)], videoDelta: Math.max(Math.abs(vr.left - sr.left), Math.abs(vr.top - sr.top), Math.abs(vr.width - sr.width), Math.abs(vr.height - sr.height)),
            canvasDelta: Math.max(Math.abs(cr.left - sr.left), Math.abs(cr.top - sr.top), Math.abs(cr.width - sr.width), Math.abs(cr.height - sr.height)),
            canvasBackingOk: Math.abs(canvas.width - Math.round(sr.width * dpr)) <= 1 && Math.abs(canvas.height - Math.round(sr.height * dpr)) <= 1, worstPx: Math.round(worstPx * 100) / 100, compared };
        });
        const issues = [];
        if (!g.mirrored) issues.push("video is not mirrored in CSS but the overlay assumes it is");
        if (g.fit !== "cover") issues.push(`object-fit is ${g.fit}, overlay assumes cover`);
        if (g.worstPx > 1.5) issues.push(`landmark mapping off by up to ${g.worstPx}px`);
        if (g.videoDelta > 1.5) issues.push(`video box differs from the stage by ${g.videoDelta.toFixed(1)}px`);
        if (g.canvasDelta > 1.5) issues.push(`overlay canvas differs from the stage by ${g.canvasDelta.toFixed(1)}px`);
        if (!g.canvasBackingOk) issues.push("overlay canvas backing size does not match the stage x devicePixelRatio");
        worst.push({ clip, name, issues, g });
      }
    } finally { await browser.close(); }
  }
  const failing = worst.filter((w) => w.issues.length);
  if (failing.length) throw new Error(failing.slice(0, 4).map((w) => `${w.clip}@${w.name}: ${w.issues.join(", ")}`).join(" | "));
  const maxPx = Math.max(...worst.map((w) => w.g.worstPx));
  return { detail: `${worst.length} viewport/camera combinations, worst landmark error ${maxPx}px`, data: { worstPx: maxPx } };
});

await check("face-pixels", "The face overlay lands on the face in the rendered video (checked on real pixels)", async () => {
  const browser = await launch("face_p");
  try {
    const { page } = await openLab(browser, "Pixel 7");
    await startAndWait(page);
    if (!(await hasHook(page))) return { status: "skip", detail: "needs the vision_diag test hook (deploy this change first)" };
    const gotFace = await waitFor(page, () => Boolean(window.__gsVision.getState().faceData?.points?.length), null, 25000);
    if (!gotFace) throw new Error("no face landmarks within 25 s");
    await page.evaluate(() => { for (const id of ["show-hands", "show-outline", "show-trail", "show-guide", "show-measures", "show-readout"]) { const el = document.getElementById(id); if (el) el.checked = false; } });
    await page.waitForTimeout(800);
    // Hide everything above the video, screenshot the stage, and find the face in that picture.
    await page.addStyleTag({ content: "#stage > *:not(#camera){visibility:hidden!important} [role=dialog],dialog,.gt-scrim,.vc-overlay{visibility:hidden!important}" });
    await page.waitForTimeout(300);
    const png = (await page.locator("#stage").screenshot({ type: "png", animations: "disabled" })).toString("base64");
    const r = await page.evaluate(async (b64) => {
      const vm = await import("/static/vision_math.js");
      const s = window.__gsVision.getState(); const video = window.__gsVision.getVideo();
      const sr = document.getElementById("stage").getBoundingClientRect();
      const frame = vm.coverFrame(sr.width, sr.height, video.videoWidth, video.videoHeight);
      const expected = s.faceData.points.map((p) => vm.mapMirroredLandmark(p, frame));
      const box = (pts) => ({ x: Math.min(...pts.map((p) => p.x)), X: Math.max(...pts.map((p) => p.x)), y: Math.min(...pts.map((p) => p.y)), Y: Math.max(...pts.map((p) => p.y)) });
      const e = box(expected);
      const bmp = await createImageBitmap(await (await fetch(`data:image/png;base64,${b64}`)).blob());
      const vision = await import("/vendor/vision/tasks-vision.mjs");
      const files = await vision.FilesetResolver.forVisionTasks("/vendor/vision/wasm");
      const model = await vision.FaceLandmarker.createFromOptions(files, { baseOptions: { modelAssetPath: "/vendor/vision/face_landmarker.task", delegate: "CPU" }, runningMode: "IMAGE", numFaces: 1 });
      const found = model.detect(bmp).faceLandmarks[0]; model.close();
      if (!found) return { found: false };
      const fb = box(found.map((p) => ({ x: p.x * sr.width, y: p.y * sr.height })));
      const center = (b) => ({ x: (b.x + b.X) / 2, y: (b.y + b.Y) / 2 });
      const a = center(e), b = center(fb);
      return { found: true, dx: Math.round(a.x - b.x), dy: Math.round(a.y - b.y), faceW: Math.round(fb.X - fb.x), stageW: Math.round(sr.width) };
    }, png);
    if (!r.found) return { status: "warn", detail: "face not found in the stage screenshot; overlay comparison inconclusive" };
    const tol = Math.max(6, r.faceW * 0.12);
    if (Math.abs(r.dx) > tol || Math.abs(r.dy) > tol) throw new Error(`overlay centre is off the visible face by (${r.dx}, ${r.dy}) px (face ${r.faceW}px wide)`);
    return { detail: `overlay centre vs visible face: dx ${r.dx}px, dy ${r.dy}px (face ${r.faceW}px wide, tolerance ${tol.toFixed(0)}px)` };
  } finally { await browser.close(); }
});

await check("hand-sides", "Pop Quiz Toss: the hand on the left of the screen throws at the left answer, right at right", async () => {
  const out = [];
  for (const clip of ["hands_p", "hands_p_flip"]) {
    const browser = await launch(clip);
    try {
      const { page } = await openLab(browser, "Pixel 7");
      await startAndWait(page);
      if (!(await hasHook(page))) return { status: "skip", detail: "needs the vision_diag test hook (deploy this change first)" };
      const two = await waitFor(page, () => window.__gsVision.getState().handData.length >= 1, null, 25000);
      if (!two) throw new Error(`${clip}: no hands found`);
      await page.waitForTimeout(1200);
      const r = await page.evaluate(async () => {
        const Q = await import("/static/pop_quiz.js");
        const s = window.__gsVision.getState();
        const w = document.getElementById("stage").getBoundingClientRect().width;
        const hands = s.handData.map((h) => ({ wrist: h.wrist, label: h.label }));
        const sided = Q.assignHandSides(hands, w);
        const targets = [{ x: 0.25 * w, id: "A" }, { x: 0.75 * w, id: "B" }];
        return { w, sided: sided.map((e) => ({ x: Math.round(e.hand.wrist.x), frac: +(e.hand.wrist.x / w).toFixed(2), side: e.side, label: e.hand.label, target: Q.targetForSide(e.side, targets)?.id })) };
      });
      out.push({ clip, ...r });
      for (const h of r.sided) {
        const expectSide = h.frac < 0.38 ? "left" : h.frac > 0.62 ? "right" : null;
        if (expectSide && h.side !== expectSide) throw new Error(`${clip}: hand at ${Math.round(h.frac * 100)}% of the screen got side "${h.side}"`);
        if (h.side === "left" && h.target !== "A") throw new Error(`${clip}: left hand maps to target ${h.target}`);
        if (h.side === "right" && h.target !== "B") throw new Error(`${clip}: right hand maps to target ${h.target}`);
      }
      if (r.sided.length >= 2 && r.sided[0].side === r.sided[1].side) throw new Error(`${clip}: two hands both got "${r.sided[0].side}"`);
    } finally { await browser.close(); }
  }
  return { detail: out.map((o) => `${o.clip}: ${o.sided.map((h) => `${Math.round(h.frac * 100)}%→${h.side}/${h.target}`).join(", ")}`).join(" | ") };
});

// 5. The new camera check page, end to end with the fake camera.
await check("diag-page", "/diag/vision runs the whole check and reports (face + hands clip)", async () => {
  const browser = await launch("hands_p");
  try {
    const ctx = await browser.newContext({ ...pw.devices["Pixel 7"], permissions: ["camera"] });
    const page = await ctx.newPage();
    const res = await page.goto(`${BASE}${DIAG}?seconds=8`, { waitUntil: "load", timeout: 60000 });
    if (!res || res.status() !== 200) throw new Error(`HTTP ${res?.status()} for ${DIAG}`);
    await page.click("#start");
    const done = await waitFor(page, () => window.__gsDiagResult || null, null, 120000);
    if (!done) throw new Error("the check did not finish in 120 s");
    const report = await page.inputValue("#report");
    const verdictText = await page.textContent("#verdict");
    const missing = ["== Device", "== WebGL", "== MediaPipe", "== Log", "Camera check result"].filter((s) => !report.includes(s));
    if (missing.length) throw new Error(`report is missing sections: ${missing.join(", ")}`);
    if (/eyJ[\w-]{10,}\.[\w-]{10,}|[\w.+-]+@[\w-]+\.[a-z]{2,}/i.test(report)) throw new Error("report contains something that looks like a token or an email");
    if (done.cameraError) throw new Error(`camera error ${done.cameraError}`);
    if (!done.stats.faceFrames && !done.stats.handFrames) throw new Error("no face or hand detected during the check");
    return { detail: `"${verdictText}", face ${done.face}, hands ${done.hands}, ${done.stats.faceFrames}/${done.stats.frames} face frames, ${done.stats.handFrames} hand frames, report ${report.length} chars`, status: done.level === "bad" ? "fail" : done.level === "warn" ? "warn" : "pass" };
  } finally { await browser.close(); }
});

// 6. Cold and warm load under a mid-range phone's conditions (4G, 4x slower CPU).
await check("throttled", "Cold vs warm model load on throttled 4G with a 4x slower CPU", async () => {
  const browser = await launch("hands_p");
  try {
    const ctx = await browser.newContext({ ...pw.devices["Pixel 7"], permissions: ["camera"] });
    const timings = [];
    for (const pass of ["cold", "warm"]) {
      const page = await ctx.newPage();
      const cdp = await ctx.newCDPSession(page);
      await cdp.send("Network.enable");
      await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 120, downloadThroughput: (4 * 1024 * 1024) / 8, uploadThroughput: (1 * 1024 * 1024) / 8 });
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
      let bytes = 0;
      page.on("response", async (r) => { if (/vendor\/vision/.test(r.url())) { try { bytes += (await r.body()).length; } catch (_) { /* streamed */ } } });
      await page.goto(`${BASE}${LAB}?embed=mobile`, { waitUntil: "load", timeout: 120000 });
      await page.waitForSelector("#start");
      const t = await startAndWait(page, 240);
      const fetched = await page.evaluate(() => performance.getEntriesByType("resource").filter((r) => /vendor\/vision/.test(r.name)).reduce((n, r) => n + (r.transferSize || 0), 0));
      timings.push({ pass, seconds: Math.round(t.seconds * 10) / 10, transferredMB: Math.round(fetched / 1048576 * 10) / 10 });
      await page.close();
    }
    const [cold, warm] = timings;
    const detail = `cold ${cold.seconds}s (${cold.transferredMB} MB over the network), warm ${warm.seconds}s (${warm.transferredMB} MB over the network)`;
    if (warm.transferredMB > 5) return { status: "fail", detail: `${detail}: the second visit downloads the models again (no effective cache)`, data: timings };
    return { detail, status: cold.seconds > 60 ? "warn" : "pass", data: timings };
  } finally { await browser.close(); }
});

// Report
const counts = results.reduce((m, r) => ({ ...m, [r.status]: (m[r.status] || 0) + 1 }), {});
console.log(`\n${results.length} checks: ${Object.entries(counts).map(([k, v]) => `${v} ${k}`).join(", ")}  (base ${BASE})`);
if (OUT) fs.writeFileSync(OUT, JSON.stringify({ base: BASE, generatedAt: new Date().toISOString(), results }, null, 2));
process.exit(counts.fail ? 1 : 0);
