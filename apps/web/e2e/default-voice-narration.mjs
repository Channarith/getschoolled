// Narration with the published default voice (Sage): a visitor who never chose gets Sage's pre-rendered clip for a line it has; an edge voice
// picked on purpose wins; a line with no clip, a withdrawn voice and a missing voices.json all fall back to the live voice (never silent);
// and the old automatic voice ("default") migrates to Sage. Drives the hidden On the Go demo with everything outside the page stubbed.
//   node apps/web/e2e/default-voice-narration.mjs http://localhost:3127
import { createRequire } from "node:module";
import assert from "node:assert/strict";

import { clipHash } from "../app/lib/cloneVoice.ts";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://localhost:3127";

const ROW = ["audio-intro-to-machine-learning", "Intro to Machine Learning (audio)", "Technology"];
const row = ([id, title, category]) => ({ id, title, category, subject: category, level: "beginner", duration_min: 5, tags: [], format: "audio", visual_required: false, drive_safe: true, segments: 2 });
const SEGS = [1, 2].map((n) => ({ heading: `Part ${n}`, text: `Intro to Machine Learning part ${n}. A short explanation about technology and how it works in practice.` }));
const FIRST_LINE = `${SEGS[0].heading}. ${SEGS[0].text}`;
const SAGE = { id: "stock-f-young-warm", label: "Sage (designed)", name: "Sage", ai_label: "AI-generated voice (designed with VoxCPM2)", active: true, default: true, gender: "female", primary_lang: "en", kind: "stock" };
const MP3 = Buffer.from("//uQxAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYYoRBqpAAAAAAD/+xDEAAPAAAGkAAAAIAAANIAAAAQAAAAATEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV", "base64");

const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"] });
const errors = [];

async function run(name, { store = {}, voices = [SAGE], clips = { en: [clipHash("en", FIRST_LINE)] }, voicesStatus = 200, expect }) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, permissions: ["camera", "microphone"] });
  await ctx.addInitScript((s) => {
    for (const [k, val] of Object.entries(s)) localStorage.setItem(k, val);
    window.__spoken = [];
    const synth = {
      speaking: false, pending: false, paused: false, getVoices: () => [], addEventListener() {}, removeEventListener() {},
      cancel() { this.__cur = null; }, pause() {}, resume() {},
      speak(u) { window.__spoken.push(String(u.text)); this.__cur = u; setTimeout(() => { if (this.__cur === u) { this.__cur = null; u.onend && u.onend({}); } }, 150); },
    };
    Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
    window.SpeechSynthesisUtterance = function (text) { this.text = text; };
    window.webkitSpeechRecognition = window.SpeechRecognition = function () { this.start = () => {}; this.stop = () => {}; this.abort = () => {}; };
  }, store);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(`${name}: ${e.message.slice(0, 160)}`));
  const clipRequests = [];
  const serverTts = [];
  await page.route(/\/audio\/courses\/[^/?]+(\?.*)?$/, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...row(ROW), body_locale: "en", segments: SEGS }) }));
  await page.route(/\/audio\/courses(\?.*)?$/, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total: 1, offset: 0, limit: 300, courses: [row(ROW)] }) }));
  await page.route("**/tts/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ available: true }) }));
  await page.route("**/tts/voices", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ groups: [] }) }));
  await page.route("**/tts", async (r) => { try { serverTts.push(JSON.parse(r.request().postData() || "{}")); } catch { /* ignore */ } await r.fulfill({ status: 501, body: "" }); });
  await page.route("**/vendor/vision/tasks-vision.mjs", (r) => r.fulfill({ status: 200, contentType: "text/javascript", body: "export const FilesetResolver={forVisionTasks:async()=>({})};export const FaceLandmarker={createFromOptions:async()=>({detectForVideo:()=>({faceLandmarks:[[{x:.5,y:.5,z:0}]]}),close(){}})};" }));
  await page.route("**/voice-assets/voices.json", (r) => voicesStatus === 200
    ? r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ voices }) })
    : r.fulfill({ status: voicesStatus, body: "" }));
  await page.route("**/voice-assets/*/index.json", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ext: "mp3", clips }) }));
  await page.route("**/voice-assets/**/*.mp3", (r) => { clipRequests.push(new URL(r.request().url()).pathname); return r.fulfill({ status: 200, contentType: "audio/mpeg", body: MP3 }); });
  await page.goto(`${BASE}/demo/on-the-go`, { waitUntil: "domcontentloaded" });
  for (let i = 0; i < 3; i += 1) { await page.keyboard.press("Escape").catch(() => {}); await page.waitForTimeout(150); }
  await page.getByTestId("on-the-go-picker").waitFor({ state: "visible", timeout: 30000 });
  await page.getByRole("button", { name: /^(start|.*pause)$/i }).first().click();
  await page.waitForTimeout(4000);
  const spoken = await page.evaluate(() => window.__spoken);
  try { await expect({ clipRequests, spoken, serverTts }); console.log(`PASS ${name}`); } catch (e) { console.log(`FAIL ${name}: ${String(e.message).split("\n")[0]}`); process.exitCode = 1; }
  await ctx.close();
}

const SAGE_CLIP = `/voice-assets/stock-f-young-warm/en/${clipHash("en", FIRST_LINE)}.mp3`;

await run("no saved choice: Sage's clip is requested for the first line", {
  expect: ({ clipRequests }) => assert.ok(clipRequests.includes(SAGE_CLIP), JSON.stringify(clipRequests)),
});
await run("the old automatic voice ('default') migrates to Sage", {
  store: { aoep_demo_voice: "default", aoep_drive_voice: "" },
  expect: ({ clipRequests }) => assert.ok(clipRequests.includes(SAGE_CLIP), JSON.stringify(clipRequests)),
});
await run("an accent voice the app wrote itself is not a choice: Sage still speaks", {
  store: { aoep_drive_voice: "en_gb_f" },
  expect: ({ clipRequests }) => assert.ok(clipRequests.includes(SAGE_CLIP), JSON.stringify(clipRequests)),
});
await run("an edge voice picked on purpose wins: no Sage clip", {
  store: { aoep_demo_voice: "default", aoep_drive_voice: "en-GB-RyanNeural", aoep_voice_explicit: "1" },
  expect: ({ clipRequests, spoken, serverTts }) => {
    assert.deepEqual(clipRequests, []);
    assert.ok(spoken.length > 0 || serverTts.length > 0, "the live voice speaks");
  },
});
await run("a tone means the live edge voice, not the plain pre-rendered Sage", {
  store: { aoep_demo_tone: "anime" },
  expect: ({ clipRequests, spoken, serverTts }) => {
    assert.deepEqual(clipRequests, [], "no pre-rendered clip: the tone is applied by the live voice");
    assert.ok(spoken.length > 0 || serverTts.length > 0, "the live voice speaks");
  },
});
await run("a line Sage has no clip for falls back to the live voice (never silent)", {
  clips: { en: [] },
  expect: ({ clipRequests, spoken, serverTts }) => {
    assert.deepEqual(clipRequests, []);
    assert.ok(spoken.some((t) => /Intro to Machine Learning part 1/.test(t)) || serverTts.some((b) => /Intro to Machine Learning part 1/.test(b.text || "")), "the line is still spoken");
  },
});
await run("voices.json missing: the live voice speaks, nothing breaks", {
  voicesStatus: 404,
  expect: ({ clipRequests, spoken, serverTts }) => {
    assert.deepEqual(clipRequests, []);
    assert.ok(spoken.length > 0 || serverTts.length > 0);
  },
});
await run("a withdrawn voice chosen earlier falls back to the default (Sage), not to silence", {
  store: { aoep_demo_voice: "gone-voice" },
  expect: ({ clipRequests }) => assert.ok(clipRequests.includes(SAGE_CLIP), JSON.stringify(clipRequests)),
});
await run("the Salane Voice picked on purpose after an edge voice: Sage again", {
  store: { aoep_demo_voice: "default", aoep_drive_voice: "en-GB-RyanNeural", aoep_voice_explicit: "0" },
  expect: ({ clipRequests }) => assert.ok(clipRequests.includes(SAGE_CLIP), JSON.stringify(clipRequests)),
});

assert.deepEqual(errors, []);
await browser.close();
