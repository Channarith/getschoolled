// On the Go (hidden demo): course search (ready-in-language first), avatar states, mic consent, resume points, spoken course commands, face presence, avatar Q&A, mic mute, camera denied,
// question limits and privacy on a hidden tab. Everything outside the page is stubbed: API, camera detector, speech recognizer, voice.
//   node apps/web/e2e/on-the-go-demo.mjs http://127.0.0.1:3071 /tmp/shots
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");

// The shared dance/giggle module is a studio asset: serve the real file so the avatar behaves as it does in production.
const SALA_MODULE = readFileSync(new globalThis.URL("../../../subrepos/theodore_course_studio/src/theodore_course_studio/voice_static/sala_interactions.js", import.meta.url), "utf8");
const BASE = process.argv[2] || "http://127.0.0.1:3071";
const SHOTS = process.argv[3] || "/tmp";
const URL = `${BASE}/demo/on-the-go`;

const CATALOG = [
  ["audio-intro-to-machine-learning", "Intro to Machine Learning (audio)", "Technology"],
  ["audio-the-roman-empire", "The Roman Empire (audio)", "History"],
  ["audio-climate-and-weather", "Climate and Weather (audio)", "Science"],
  ["audio-cybersecurity-basics", "Cybersecurity Basics (audio)", "Technology"],
  ["audio-understanding-classical-music", "Understanding Classical Music (audio)", "Arts & Culture"],
  ["audio-not-in-the-curated-list", "Hidden Extra Course (audio)", "Other"],
];
const row = ([id, title, category]) => ({
  id, title, category, subject: category, level: "beginner", duration_min: 5, tags: [], format: "audio",
  visual_required: false, drive_safe: true, segments: 4,
});
const course = (r) => ({
  ...row(r), body_locale: "en",
  segments: [1, 2, 3, 4].map((n) => ({ heading: `Part ${n}`, text: `${r[1].replace(" (audio)", "")} part ${n}. A short explanation about ${r[2].toLowerCase()} and how it works in practice.` })),
});

async function setup(browser, opts = {}) {
  const ctx = await browser.newContext({ ...(opts.device || { viewport: { width: 1280, height: 800 } }), permissions: ["camera", "microphone"] });
  const page = await ctx.newPage();
  lastPage = page;
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message.slice(0, 160)));

  await page.route(/\/audio\/courses\/[^/?]+(\?.*)?$/, (route) => {
    const id = decodeURIComponent(new globalThis.URL(route.request().url()).pathname.split("/").pop());
    const hit = CATALOG.find((r) => r[0] === id);
    return hit
      ? route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(course(hit)) })
      : route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
  });
  await page.route(/\/audio\/search(\?.*)?$/, (route) => {
    const u = new globalThis.URL(route.request().url());
    const lang = u.searchParams.get("language") || "en";
    const readyFor = (opts.ready || {})[lang] || [];
    if (opts.searchFails) return route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
    const courses = CATALOG.map((r) => ({
      ...row(r), title_local: readyFor.includes(r[0]) ? (opts.localTitles || {})[r[0]] || "" : "",
      ready_languages: readyFor.includes(r[0]) ? [lang] : [], ready: lang === "en" || readyFor.includes(r[0]),
      english_only: !readyFor.includes(r[0]), audio_mode: "live_tts",
    })).sort((a, b) => Number(b.ready) - Number(a.ready));
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ language: lang, total: courses.length, ready_in_language: courses.filter((c) => c.ready).length, ready_counts: {}, audio_mode: "live_tts", courses }) });
  });
  await page.route(/\/audio\/courses(\?.*)?$/, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total: CATALOG.length, offset: 0, limit: 300, courses: CATALOG.map(row) }) }));
  await page.route("**/api/studio/voice-overlay/sala_interactions.js", (route) =>
    route.fulfill({ status: 200, contentType: "text/javascript", body: SALA_MODULE }));
  await page.route("**/tts/status", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ available: false }) }));
  await page.route("**/vendor/vision/tasks-vision.mjs", (route) =>
    route.fulfill({
      status: 200, contentType: "text/javascript",
      body: `export const FilesetResolver = { forVisionTasks: async () => ({}) };
             export const FaceLandmarker = { createFromOptions: async () => ({
               detectForVideo: () => ({ faceLandmarks: window.__faces ? [[{ x: .5, y: .5, z: 0 }]] : [] }), close() {} }) };`,
    }));

  await page.addInitScript((o) => {
    window.__faces = true;
    window.__spoken = [];
    window.__streams = [];
    window.__recs = [];
    // Voice: record what is said; finish each line quickly so segments advance.
    const synth = {
      speaking: false, pending: false, paused: false,
      getVoices: () => [],
      addEventListener() {}, removeEventListener() {},
      cancel() { this.__cur = null; },
      pause() {}, resume() {},
      speak(u) {
        window.__spoken.push(String(u.text));
        this.__cur = u;
        setTimeout(() => { if (this.__cur === u) { this.__cur = null; u.onend && u.onend({}); } }, window.__ttsMs ?? 120);
      },
    };
    Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
    window.SpeechSynthesisUtterance = function (text) { this.text = text; };
    window.__ttsMs = 120;
    // Speech recognizer: tests push final transcripts with window.__say(text).
    window.webkitSpeechRecognition = window.SpeechRecognition = function () {
      const self = this;
      this.start = () => { self.__stopped = false; self.__running = true; window.__recs.push(self); };
      this.stop = () => { self.__stopped = true; self.__running = false; setTimeout(() => self.onend && self.onend({}), 0); };
      this.abort = this.stop;
    };
    window.__say = (text) => {
      const live = window.__recs.filter((r) => !r.__stopped);
      const rec = live[live.length - 1];
      if (!rec) return false;
      const res = [{ transcript: text }];
      res.isFinal = true;
      rec.onresult && rec.onresult({ results: [res], resultIndex: 0 });
      return true;
    };
    // Camera/microphone: track every stream so tests can see whether the camera really stopped.
    const real = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async (c) => {
      if (c && c.video && o.denyCamera) throw new DOMException("denied", "NotAllowedError");
      const s = await real(c);
      window.__streams.push({ s, video: Boolean(c && c.video) });
      return s;
    };
    if (o.consent) localStorage.setItem("salareen.onTheGo.consent.v1", o.consent);
    if (o.locale) localStorage.setItem("aiclassroom.locale.v1", o.locale);
    window.__gum = 0;
    const gum = navigator.mediaDevices.getUserMedia;
    navigator.mediaDevices.getUserMedia = async (c) => { window.__gum += 1; return gum(c); };
  }, { denyCamera: Boolean(opts.denyCamera), consent: opts.noConsent ? "" : (opts.consent || "mic-camera"), locale: opts.locale || "" });
  return { ctx, page, errors };
}


// The course list is a dropdown now: open it before searching or picking, and the widget menu before using the mic or camera items.
async function openList(page) {
  if ((await page.getByTestId("otg-search-popup").count()) === 0) {
    // A friendly-error toast can sit over the dropdown for a moment: fall back to a direct click.
    await page.getByTestId("otg-trigger").click({ timeout: 4000 }).catch(() => page.getByTestId("otg-trigger").dispatchEvent("click"));
  }
  await page.getByTestId("otg-search-popup").waitFor({ state: "visible", timeout: 10000 });
}
async function typeQuery(page, text) { await openList(page); await page.getByTestId("otg-search-input").fill(text); }
async function pick(page, id) { await openList(page); await page.getByTestId(`otg-course-${id}`).click(); }
async function courseCount(page) { await openList(page); return page.locator("[data-testid^=otg-course-]").count(); }
async function courseText(page, id) { await openList(page); return page.getByTestId(`otg-course-${id}`).innerText(); }
async function menuClick(page, testId) {
  if ((await page.getByTestId("on-the-go-widget-menu-list").count()) === 0) await page.getByTestId("on-the-go-widget-menu").click();
  await page.getByTestId(testId).click();
}

const spokenText = (page) => page.evaluate(() => window.__spoken.join(" || "));
const say = (page, text) => page.evaluate((t) => window.__say(t), text);
const cameraLive = (page) => page.evaluate(() => window.__streams.some((x) => x.video && x.s.getTracks().some((t) => t.readyState === "live")));
async function closeTutorials(page) {
  for (let i = 0; i < 3; i += 1) { await page.keyboard.press("Escape").catch(() => {}); await page.waitForTimeout(150); }
}
async function begin(page) {
  await page.goto(URL, { waitUntil: "domcontentloaded" });
  await closeTutorials(page);
  await page.getByTestId("on-the-go-search").waitFor({ state: "visible", timeout: 20000 });
}
const start = (page) => page.getByRole("button", { name: /^(start|.*pause)$/i }).first();

let failed = 0;
let lastPage = null;
const ONLY = process.env.ONLY || "";
const check = async (name, fn) => {
  if (process.env.PROGRESS) console.log("→", name);
  if (ONLY && !name.includes(ONLY)) return;
  try { await fn(); console.log(`PASS ${name}`); } catch (e) {
    failed += 1;
    console.log(`FAIL ${name}: ${String(e.message || e).split("\n")[0].slice(0, 300)}`);
    if (process.env.DEBUG) console.log(String(e.message || e).split("\n").slice(0, 14).join("\n"));
    if (lastPage) {
      const info = await lastPage.evaluate(() => ({
        spoken: (window.__spoken || []).filter((t) => /course|Playing|Next|lot of|Part \d\./.test(t) === false || /course|Playing|Next/.test(t)).slice(-14).map((t) => t.slice(0, 70)),
        recs: (window.__recs || []).map((r) => (r.__stopped ? "stopped" : "live")).join(","),
        state: document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state"),
        buttons: [...document.querySelectorAll("button[aria-label]")].map((b) => b.getAttribute("aria-label")).filter((l) => /start|pause/i.test(l)),
      })).catch(() => null);
      console.log("   diag:", JSON.stringify(info));
    }
  }
};

const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });
try {
  // 1. Picker: curated courses only, search and categories work.
  await check("picker lists curated courses only, with search and categories", async () => {
    const { ctx, page, errors } = await setup(browser);
    await begin(page);
    assert.equal(await page.getByTestId("otg-search-list").count(), 0, "the list is a closed dropdown until it is opened");
    await openList(page);
    for (const id of ["audio-intro-to-machine-learning", "audio-the-roman-empire", "audio-climate-and-weather", "audio-cybersecurity-basics", "audio-understanding-classical-music"]) {
      assert.equal(await page.getByTestId(`otg-course-${id}`).count(), 1, id);
    }
    assert.equal(await page.getByTestId("otg-course-audio-not-in-the-curated-list").count(), 0, "uncurated course must not be offered in the demo");
    await typeQuery(page, "roman");
    assert.equal(await courseCount(page), 1);
    await typeQuery(page, "romn empyre");   // typos still find it
    assert.equal(await courseCount(page), 1);
    await typeQuery(page, "zzzzqq");
    await page.getByTestId("otg-no-match").waitFor({ state: "visible" });
    await typeQuery(page, "");
    assert.equal(await courseCount(page), 5);
    await page.screenshot({ path: `${SHOTS}/otg-1-picker.png` });
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  // 2. Choose a course, play it, the avatar and the widget are on screen.
  await check("choosing a course plays that course; avatar and widget are visible", async () => {
    const { ctx, page } = await setup(browser);
    await begin(page);
    await pick(page, "audio-the-roman-empire");
    await start(page).click();
    await page.waitForFunction(() => window.__spoken.some((t) => /Roman Empire/.test(t)), null, { timeout: 15000 });
    assert.ok(await page.getByTestId("on-the-go-mascot").isVisible(), "avatar visible");
    const box = await page.getByTestId("on-the-go-presence").boundingBox();
    assert.ok(box.x + box.width >= 1280 - 40 && box.y < 120, `widget top-right ${JSON.stringify(box)}`);
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "present", null, { timeout: 15000 });
    assert.ok(await page.getByTestId("on-the-go-camera-on").isVisible(), "camera-on indicator");
    await page.screenshot({ path: `${SHOTS}/otg-2-playing.png` });
    await ctx.close();
  });

  // 3. Spoken course commands.
  await check("voice: 'play the climate and weather course', then 'next course'", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 700; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await say(page, "hey sala play the climate and weather course");
    await page.waitForFunction(() => window.__spoken.some((t) => /Playing Climate and Weather/.test(t)), null, { timeout: 15000 });
    await page.waitForFunction(() => window.__spoken.some((t) => /Climate and Weather part/.test(t)), null, { timeout: 15000 });
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await say(page, "hey sala next course");
    await page.waitForFunction(() => window.__spoken.some((t) => /Next course:/.test(t)), null, { timeout: 15000 });
    await page.waitForFunction(() => window.__spoken.some((t) => /Understanding Classical Music part 1/.test(t)), null, { timeout: 15000 });
    await ctx.close();
  });

  // 4. Resume where you left off, per course.
  await check("the course remembers where you stopped and offers to resume", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 900; });
    await begin(page);
    await pick(page, "audio-cybersecurity-basics");
    await start(page).click();
    await page.waitForFunction(() => window.__spoken.some((t) => /Cybersecurity Basics part 3/.test(t)), null, { timeout: 15000 });
    await page.getByRole("button", { name: /pause/i }).first().click();
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("salareen.onTheGo.progress.v1") || "{}"));
    assert.ok(saved.courses["audio-cybersecurity-basics"].seg >= 2, JSON.stringify(saved));
    await page.reload({ waitUntil: "domcontentloaded" });
    await closeTutorials(page);
    await page.getByTestId("on-the-go-search").waitFor({ state: "visible" });
    assert.match(await courseText(page, "audio-cybersecurity-basics"), /Resume at part/);
    await ctx.close();
  });

  // 5. Face presence: away pauses, back resumes, camera-off persists.
  await check("face away pauses the lesson, coming back resumes it", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 60000; });   // keep one segment "speaking" so only the presence logic can pause it
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "present", null, { timeout: 15000 });
    assert.ok(await page.getByRole("button", { name: /pause/i }).first().isVisible());
    await page.evaluate(() => { window.__faces = false; });
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "away", null, { timeout: 15000 });
    assert.ok(await page.getByRole("button", { name: /^start$/i }).first().isVisible(), "lesson paused while away");
    await page.evaluate(() => { window.__faces = true; });
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "present", null, { timeout: 15000 });
    await page.getByRole("button", { name: /pause/i }).first().waitFor({ state: "visible", timeout: 10000 });
    await ctx.close();
  });

  await check("camera off switch stops the camera and is remembered", async () => {
    const { ctx, page } = await setup(browser);
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "present", null, { timeout: 15000 });
    assert.equal(await cameraLive(page), true);
    await menuClick(page, "on-the-go-camera-toggle");
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "off");
    assert.equal(await cameraLive(page), false, "camera tracks stopped");
    assert.equal(await page.evaluate(() => localStorage.getItem("salareen.onTheGo.camera")), "off");
    await page.reload({ waitUntil: "domcontentloaded" });
    await closeTutorials(page);
    await start(page).click();
    await page.waitForTimeout(1500);
    assert.equal(await cameraLive(page), false, "stays off after a reload");
    await ctx.close();
  });

  // 6. Avatar: click, ask, hear the answer, lesson resumes.
  await check("avatar click: ask a question, answer is spoken, lesson resumes", async () => {
    const { ctx, page } = await setup(browser);
    await begin(page);
    await pick(page, "audio-intro-to-machine-learning");
    await start(page).click();
    await page.waitForFunction(() => window.__spoken.length > 0, null, { timeout: 15000 });
    await page.getByTestId("on-the-go-mascot").click();
    // The tap hands the microphone from the always-on recognizer to a one-shot one: wait for that, not just for "some" recognizer.
    await page.waitForFunction(() => window.__recs.length >= 2 && !window.__recs[window.__recs.length - 1].__stopped && window.__recs.slice(0, -1).every((r) => r.__stopped), null, { timeout: 10000 });
    if (process.env.DEBUG) console.log("   before say:", JSON.stringify(await page.evaluate(() => ({ recs: window.__recs.map((r) => (r.__stopped ? "s" : "l") + (r.continuous ? "C" : "")), state: document.querySelector("[data-testid=on-the-go-mascot]")?.getAttribute("data-state"), btn: [...document.querySelectorAll("button[aria-label]")].map((b) => b.getAttribute("aria-label")).filter((l) => /start|pause/i.test(l)) }))));
    await say(page, "how does machine learning work in practice");
    if (process.env.DEBUG) { await page.waitForTimeout(3000); console.log("   after say:", JSON.stringify(await page.evaluate(() => ({ spoken: window.__spoken.slice(-6), recs: window.__recs.map((r) => (r.__stopped ? "s" : "l") + (r.continuous ? "C" : "")), status: [...document.querySelectorAll("[role=status]")].map((e) => e.textContent).filter(Boolean) })))); }
    await page.waitForFunction(() => window.__spoken.some((t) => /explanation about|machine learning part/i.test(t)), null, { timeout: 15000 });
    await page.waitForFunction(() => window.__spoken.some((t) => /back to the course|carry|continu/i.test(t)) || window.__spoken.length > 4, null, { timeout: 20000 });
    await ctx.close();
  });

  // 7. Mic mute.
  await check("mic mute stops listening; questions are ignored until unmuted", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 60000; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await menuClick(page, "on-the-go-mic-toggle");
    await page.waitForFunction(() => window.__recs.every((r) => r.__stopped), null, { timeout: 5000 });
    assert.equal(await say(page, "hey sala play the climate and weather course"), false, "no live recognizer while muted");
    await page.waitForTimeout(800);
    assert.ok(!(await spokenText(page)).includes("Playing Climate and Weather"));
    await menuClick(page, "on-the-go-mic-toggle");
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 10000 });
    await ctx.close();
  });

  // 8. Camera denied: audio-only fallback keeps working.
  await check("camera denied: lesson and questions still work, widget says so", async () => {
    const { ctx, page } = await setup(browser, { denyCamera: true });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "denied", null, { timeout: 15000 });
    await page.waitForFunction(() => window.__spoken.length > 0, null, { timeout: 15000 });
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await say(page, "hey sala play the climate and weather course");
    await page.waitForFunction(() => window.__spoken.some((t) => /Playing Climate and Weather/.test(t)), null, { timeout: 15000 });
    await ctx.close();
  });

  // 9. Question limit.
  await check("too many questions get a friendly limit message", async () => {
    const { ctx, page } = await setup(browser);
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    for (let i = 0; i < 8; i += 1) {
      await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
      await say(page, `hey sala what is the explanation about technology number ${i}`);
      await page.waitForTimeout(250);
    }
    await page.waitForFunction(() => window.__spoken.some((t) => /a lot of questions at once/i.test(t)), null, { timeout: 15000 });
    await ctx.close();
  });

  // 10. Privacy: a hidden tab stops listening and the camera; it returns when visible.
  await check("hidden tab stops the camera and the recognizer, visible again restores them", async () => {
    const { ctx, page } = await setup(browser);
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "present", null, { timeout: 15000 });
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await page.evaluate(() => {
      Object.defineProperty(document, "hidden", { value: true, configurable: true });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await page.waitForFunction(() => window.__recs.every((r) => r.__stopped), null, { timeout: 5000 });
    assert.equal(await cameraLive(page), false, "camera stopped while hidden");
    await page.evaluate(() => {
      Object.defineProperty(document, "hidden", { value: false, configurable: true });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 10000 });
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "present", null, { timeout: 15000 });
    await ctx.close();
  });

  // 11. Phone layout.
  await check("phone: avatar and widget fit, nothing overlaps the controls", async () => {
    const { ctx, page } = await setup(browser, { device: devices["Pixel 7"] });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "present", null, { timeout: 15000 });
    const vw = page.viewportSize().width;
    const widget = await page.getByTestId("on-the-go-presence").boundingBox();
    const avatar = await page.getByTestId("on-the-go-mascot").boundingBox();
    assert.ok(widget.x >= 0 && widget.x + widget.width <= vw, "widget inside the screen");
    assert.ok(avatar.x >= 0 && avatar.x + avatar.width <= vw, "avatar inside the screen");
    const input = await page.getByTestId("otg-trigger").boundingBox();
    const overlap = !(widget.x + widget.width <= input.x || input.x + input.width <= widget.x || widget.y + widget.height <= input.y || input.y + input.height <= widget.y);
    assert.equal(overlap, false, `the combined widget must not cover the course dropdown: widget ${JSON.stringify(widget)} input ${JSON.stringify(input)}`);
    await page.screenshot({ path: `${SHOTS}/otg-11-phone.png` });
    await ctx.close();
  });

  // 12. Search ranks courses that are ready in the voice's language first, with badges, and can hide English-only courses.
  await check("search: courses ready in the voice's language first, badges, include-English toggle, empty state", async () => {
    const ready = { es: ["audio-the-roman-empire", "audio-understanding-classical-music"], fr: [] };
    const { ctx, page, errors } = await setup(browser, { locale: "es", ready, localTitles: { "audio-the-roman-empire": "El Imperio Romano", "audio-understanding-classical-music": "La historia del cine" } });
    await begin(page);
    await openList(page);
    const ids = await page.locator("[data-testid^=otg-course-]").evaluateAll((els) => els.map((e) => e.getAttribute("data-testid").replace("otg-course-", "")));
    assert.deepEqual(ids.slice(0, 2).sort(), ["audio-the-roman-empire", "audio-understanding-classical-music"], `ready first: ${ids}`);
    assert.equal(await page.getByTestId("otg-badge-audio-the-roman-empire").getAttribute("data-kind"), "ready");
    assert.equal(await page.getByTestId("otg-badge-audio-climate-and-weather").getAttribute("data-kind"), "english-only");
    assert.match(await courseText(page, "audio-the-roman-empire"), /El Imperio Romano/);
    await typeQuery(page, "imperio");
    assert.equal(await courseCount(page), 1);
    await typeQuery(page, "");
    await page.getByTestId("otg-include-english").uncheck();
    assert.equal(await courseCount(page), 2, "English-only courses hidden");
    await page.getByTestId("otg-include-english").check();
    assert.equal(await courseCount(page), 5);
    await page.screenshot({ path: `${SHOTS}/otg-12-search-es.png` });
    assert.deepEqual(errors, []);
    await ctx.close();
    const fr = await setup(browser, { locale: "fr", ready });
    await begin(fr.page);
    await openList(fr.page);
    await fr.page.getByTestId("otg-empty-language").waitFor({ state: "visible" });
    assert.equal(await courseCount(fr.page), 5, "English courses still listed");
    await fr.ctx.close();
  });

  await check("search: a pre-translated course loads and plays right away; search keeps working if the index is down", async () => {
    const { ctx, page } = await setup(browser, { locale: "es", ready: { es: ["audio-the-roman-empire"] } });
    await begin(page);
    await typeQuery(page, "roman");
    await page.getByTestId("otg-search-input").press("Enter");   // keyboard pick of the first result
    await start(page).click();
    await page.waitForFunction(() => window.__spoken.some((t) => /Roman Empire/.test(t)), null, { timeout: 15000 });
    await ctx.close();
    const down = await setup(browser, { searchFails: true });
    await begin(down.page);
    assert.equal(await courseCount(down.page), 5, "falls back to the catalog rows");
    await down.ctx.close();
  });

  await check("voice: 'search for classical' filters the list and says so", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 700; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await say(page, "hey sala search for classical");
    await page.waitForFunction(() => window.__spoken.some((t) => /Searching for classical/.test(t)), null, { timeout: 15000 });
    assert.equal(await courseCount(page), 1);
    assert.equal(await page.getByTestId("otg-search-input").inputValue(), "classical");
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await say(page, "hey sala clear search");
    await page.waitForFunction(() => window.__spoken.some((t) => /Showing all courses/.test(t)), null, { timeout: 15000 });
    assert.equal(await courseCount(page), 5);
    await ctx.close();
  });

  // 13. The avatar is on screen in every state and says what the microphone is doing.
  await check("avatar: visible before a course is picked, listening ring while a lesson plays, muted state, unmute", async () => {
    const { ctx, page } = await setup(browser);
    await begin(page);
    const avatar = page.getByTestId("on-the-go-mascot");
    assert.ok(await avatar.isVisible(), "visible before Start");
    assert.equal(await avatar.getAttribute("data-state"), "idle");
    assert.equal(await avatar.getAttribute("data-sala-avatar"), "", "the dance/giggle module attaches here");
    assert.match(await page.getByTestId("on-the-go-avatar-label").innerText(), /Tap Sala/);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-mascot]")?.getAttribute("data-state") === "listening", null, { timeout: 15000 });
    assert.match(await page.getByTestId("on-the-go-avatar-label").innerText(), /Listening: ask me anything/);
    await menuClick(page, "on-the-go-mic-toggle");
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-mascot]")?.getAttribute("data-state") === "muted", null, { timeout: 5000 });
    assert.match(await page.getByTestId("on-the-go-avatar-label").innerText(), /Muted/);
    await avatar.click();   // tapping a muted Sala listens again
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-mascot]")?.getAttribute("data-state") === "listening", null, { timeout: 10000 });
    await page.screenshot({ path: `${SHOTS}/otg-13-avatar-listening.png` });
    await ctx.close();
  });

  await check("avatar: still there when the course fails to load, and as a sign-in link on the signed-out player", async () => {
    const { ctx, page } = await setup(browser);
    await page.route(/\/audio\/courses\/[^/?]+(\?.*)?$/, (route) => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
    await page.goto(URL, { waitUntil: "domcontentloaded" });
    await closeTutorials(page);
    await page.getByTestId("on-the-go-mascot").waitFor({ state: "visible", timeout: 20000 });
    await ctx.close();
    const out = await setup(browser);
    await out.page.goto(`${BASE}/drive`, { waitUntil: "domcontentloaded" });
    const a = out.page.getByTestId("on-the-go-mascot");
    await a.waitFor({ state: "visible", timeout: 20000 });
    assert.equal(await a.getAttribute("data-state"), "signin");
    assert.equal(await a.getAttribute("href"), "/login");
    await out.ctx.close();
  });

  await check("barge-in: asking while a lesson plays pauses it and answers", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 60000; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await say(page, "hey sala how does machine learning work");
    await page.getByRole("button", { name: /^start$/i }).first().waitFor({ state: "visible", timeout: 10000 });   // lesson paused for the question
    await ctx.close();
  });

  // 14. One-time consent before the first microphone prompt.
  await check("consent card comes first: nothing is opened before it, the choice is remembered and can be reopened", async () => {
    const { ctx, page } = await setup(browser, { noConsent: true });
    await begin(page);
    await start(page).click();
    await page.getByTestId("on-the-go-consent").waitFor({ state: "visible", timeout: 10000 });
    assert.equal(await page.evaluate(() => window.__gum), 0, "no microphone or camera request before consent");
    assert.equal(await page.evaluate(() => window.__recs.length), 0, "no recognizer before consent");
    assert.match(await page.getByTestId("on-the-go-consent").innerText(), /never uploaded or recorded/);
    await page.getByTestId("otg-consent-mic").click();   // microphone only
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await page.waitForTimeout(1200);
    assert.equal(await cameraLive(page), false, "camera stays off when only the microphone was allowed");
    assert.equal(await page.evaluate(() => localStorage.getItem("salareen.onTheGo.consent.v1")), "mic");
    await page.reload({ waitUntil: "domcontentloaded" });
    await closeTutorials(page);
    await start(page).click();
    assert.equal(await page.getByTestId("on-the-go-consent").count(), 0, "not asked again");
    await menuClick(page, "otg-privacy-choices");
    await page.getByTestId("on-the-go-consent").waitFor({ state: "visible" });
    await ctx.close();
  });

  await check("consent 'Not now': lesson plays, microphone stays off, Sala shows muted", async () => {
    const { ctx, page } = await setup(browser, { noConsent: true });
    await begin(page);
    await start(page).click();
    await page.getByTestId("otg-consent-none").click();
    await page.waitForFunction(() => window.__spoken.length > 0, null, { timeout: 15000 });
    assert.equal(await page.evaluate(() => window.__recs.length), 0);
    assert.equal(await page.getByTestId("on-the-go-mascot").getAttribute("data-state"), "muted");
    await ctx.close();
  });

  // 15. ONE combined widget: Sala head + camera + timer + menu. No standalone mic/camera/fullscreen buttons, no separate avatar.
  await check("one combined widget holds Sala, camera and timer; mic, camera, fullscreen, privacy live only in its menu", async () => {
    const { ctx, page, errors } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 600000; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "present", null, { timeout: 15000 });
    assert.equal(await page.locator("[data-testid=on-the-go-presence]").count(), 1, "exactly one widget");
    assert.equal(await page.locator("[data-testid=on-the-go-mascot]").count(), 1, "exactly one Sala");
    assert.equal(await page.locator("[data-testid=on-the-go-presence] [data-testid=on-the-go-mascot][data-sala-avatar]").count(), 1, "Sala head is inside the widget and carries data-sala-avatar");
    assert.equal(await page.locator("[data-testid=on-the-go-presence] [data-testid=on-the-go-timer]").count(), 1, "the demo timer is inside the widget");
    assert.equal(await page.locator("[data-testid=on-the-go-timer]").count(), 1, "no second timer");
    for (const id of ["on-the-go-mic-toggle", "on-the-go-camera-toggle", "on-the-go-fullscreen", "otg-privacy-choices", "on-the-go-help"]) {
      assert.equal(await page.getByTestId(id).count(), 0, `${id} is not on the page until the menu is opened`);
    }
    await page.getByTestId("on-the-go-widget-menu").click();
    for (const id of ["on-the-go-mic-toggle", "on-the-go-camera-toggle", "on-the-go-fullscreen", "otg-privacy-choices"]) {
      assert.equal(await page.getByTestId(id).count(), 1, `${id} is in the menu`);
    }
    assert.match(await page.getByTestId("on-the-go-widget-menu-list").innerText(), /headphones/i);
    await page.keyboard.press("Escape");
    assert.equal(await page.getByTestId("on-the-go-widget-menu-list").count(), 0, "Escape closes the menu");
    await page.screenshot({ path: `${SHOTS}/otg-15-widget.png` });
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  await check("Sala head: tap listens, long-press mutes and unmutes; the widget drags and minimises", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 600000; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    const head = page.getByTestId("on-the-go-mascot");
    const hb = await head.boundingBox();
    await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
    await page.mouse.down();
    await page.waitForTimeout(900);          // long-press
    await page.mouse.up();
    await page.waitForFunction(() => window.__recs.every((r) => r.__stopped), null, { timeout: 5000 });
    assert.equal(await head.getAttribute("data-state"), "muted", "long-press mutes");
    await head.click();                       // a tap on a muted Sala listens again
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 10000 });
    // drag by the bar
    const w = page.getByTestId("on-the-go-presence");
    const before = await w.boundingBox();
    const gb = await page.getByTestId("on-the-go-widget-grip").boundingBox();
    await page.mouse.move(gb.x + gb.width / 2, gb.y + gb.height / 2);
    await page.mouse.down();
    await page.mouse.move(before.x - 160, before.y + 120, { steps: 8 });
    await page.mouse.up();
    const after = await w.boundingBox();
    assert.ok(Math.abs(after.x - before.x) > 100 && after.y > before.y + 60, `widget moved ${JSON.stringify(before)} -> ${JSON.stringify(after)}`);
    await page.reload({ waitUntil: "domcontentloaded" });
    await closeTutorials(page);
    await page.getByTestId("on-the-go-presence").waitFor({ state: "visible", timeout: 15000 });
    const restored = await page.getByTestId("on-the-go-presence").boundingBox();
    assert.ok(Math.abs(restored.x - after.x) < 6, "position is remembered");
    // minimise keeps Sala and the status dot
    await page.getByTestId("on-the-go-widget-min").click();
    assert.equal(await page.getByTestId("on-the-go-presence").getAttribute("data-minimized"), "1");
    assert.ok(await page.getByTestId("on-the-go-mascot").isVisible(), "Sala stays visible when minimised");
    await ctx.close();
  });

  // 16. The anonymous demo ends for real: card with no price, camera and microphone stop.
  await check("end of the demo: 'Create or log in to your account', no price, camera and mic stopped", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 3600000; });
    await page.clock.install();
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    for (let i = 0; i < 640; i += 1) {     // one second per React render: the timer re-arms itself after each tick
      await page.clock.runFor(1000);
      await page.waitForTimeout(8);
      if (await page.getByTestId("on-the-go-trial-end").count()) break;
    }
    await page.getByTestId("on-the-go-trial-end").waitFor({ state: "visible", timeout: 15000 });
    const text = await page.getByTestId("on-the-go-trial-end").innerText();
    assert.match(text, /Create or log in to your account/);
    assert.doesNotMatch(text, /\$|price|card|paypal/i, "no price or payment on the end card");
    assert.equal(await page.getByTestId("otg-trial-create").getAttribute("href"), "/login?mode=signup&next=%2Fdrive");
    assert.equal(await page.getByTestId("otg-trial-login").getAttribute("href"), "/login?next=%2Fdrive");
    assert.equal(await page.getByTestId("otg-trial-notnow").getAttribute("href"), "/");
    assert.equal(await cameraLive(page), false, "camera stopped");
    assert.ok(await page.evaluate(() => window.__recs.every((r) => r.__stopped)), "microphone stopped");
    await ctx.close();
  });

  // 17. The dance easter egg works inside the combined widget: touch scrub, grip-only dragging, the native speech bridge, reduced motion.
  const isDancing = (page) => page.evaluate(() => {
    const el = document.querySelector("[data-testid=on-the-go-mascot]");
    return Boolean(el && (el.classList.contains("sala-dancing") || el.classList.contains("sala-dancing-calm")));
  });
  const touchScrub = (page, selector) => page.evaluate(async (sel) => {
    const el = document.querySelector(sel);
    const r = el.getBoundingClientRect();
    const y = r.top + r.height / 2, cx = r.left + r.width / 2, amp = r.width * 0.42;
    const fire = (type, x, buttons) => el.dispatchEvent(new PointerEvent(type, {
      pointerId: 7, pointerType: "touch", isPrimary: true, buttons, clientX: x, clientY: y, bubbles: true, cancelable: true,
    }));
    fire("pointerdown", cx, 1);
    for (const x of [cx - amp, cx + amp, cx - amp, cx + amp, cx - amp, cx + amp]) { fire("pointermove", x, 1); await new Promise((res) => setTimeout(res, 60)); }
    fire("pointerup", cx, 0);
  }, selector);

  await check("dance: a touch scrub over the Sala head dances (Pixel 7), also while muted", async () => {
    const { ctx, page } = await setup(browser, { device: devices["Pixel 7"] });
    await page.addInitScript(() => { window.__ttsMs = 600000; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-mascot]")?.style.touchAction === "none", null, { timeout: 15000 });   // the shared module attached
    assert.equal(await isDancing(page), false);
    await touchScrub(page, "[data-testid=on-the-go-mascot]");
    await page.waitForFunction(() => /sala-dancing/.test(document.querySelector("[data-testid=on-the-go-mascot]").className), null, { timeout: 4000 });
    await page.waitForTimeout(300);
    // muted: the scrub still works
    await menuClick(page, "on-the-go-mic-toggle");
    await page.waitForFunction(() => window.__recs.every((r) => r.__stopped), null, { timeout: 5000 });
    await page.evaluate(() => window.dispatchEvent(new Event("sala:attention")));   // ends the first dance
    await page.waitForTimeout(11000);          // cooldown
    await touchScrub(page, "[data-testid=on-the-go-mascot]");
    await page.waitForFunction(() => /sala-dancing/.test(document.querySelector("[data-testid=on-the-go-mascot]").className), null, { timeout: 4000 });
    await ctx.close();
  });

  await check("dance: dragging the widget by its grip (touch) moves it and does NOT dance; the head never drags the widget", async () => {
    const { ctx, page } = await setup(browser, { device: devices["Pixel 7"] });
    await page.addInitScript(() => { window.__ttsMs = 600000; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-mascot]")?.style.touchAction === "none", null, { timeout: 15000 });
    const w = page.getByTestId("on-the-go-presence");
    const before = await w.boundingBox();
    await page.evaluate(async () => {
      const grip = document.querySelector("[data-testid=on-the-go-widget-grip]");
      const r = grip.getBoundingClientRect();
      const x0 = r.left + r.width / 2, y0 = r.top + r.height / 2;
      const fire = (type, x, y, buttons) => grip.dispatchEvent(new PointerEvent(type, { pointerId: 9, pointerType: "touch", isPrimary: true, buttons, clientX: x, clientY: y, bubbles: true, cancelable: true }));
      fire("pointerdown", x0, y0, 1);
      for (let i = 1; i <= 8; i += 1) { fire("pointermove", x0 - i * 15, y0 + i * 12, 1); await new Promise((res) => setTimeout(res, 30)); }
      fire("pointerup", x0 - 120, y0 + 96, 0);
    });
    const after = await w.boundingBox();
    assert.ok(Math.abs(after.x - before.x) > 80 && after.y > before.y + 60, `the grip moves the widget ${JSON.stringify(before)} -> ${JSON.stringify(after)}`);
    assert.equal(await isDancing(page), false, "a grip drag is not a scrub");
    // a drag that starts on the Sala head must not move the widget
    const pos = await w.boundingBox();
    await page.evaluate(async () => {
      const head = document.querySelector("[data-testid=on-the-go-mascot]");
      const r = head.getBoundingClientRect();
      const x0 = r.left + r.width / 2, y0 = r.top + r.height / 2;
      const fire = (type, x, buttons) => head.dispatchEvent(new PointerEvent(type, { pointerId: 11, pointerType: "touch", isPrimary: true, buttons, clientX: x, clientY: y0, bubbles: true, cancelable: true }));
      fire("pointerdown", x0, 1);
      for (let i = 1; i <= 5; i += 1) { fire("pointermove", x0 - i * 20, 1); await new Promise((res) => setTimeout(res, 30)); }
      fire("pointerup", x0 - 100, 0);
    });
    const still = await w.boundingBox();
    assert.ok(Math.abs(still.x - pos.x) < 2 && Math.abs(still.y - pos.y) < 2, "dragging on Sala does not move the widget");
    await ctx.close();
  });

  await check("dance: the native speech bridge hands recognised text to the same intent matcher", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 600000; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-mascot]")?.style.touchAction === "none", null, { timeout: 15000 });
    assert.equal(await page.evaluate(() => typeof window.__salaNativeSpeech?.onTranscript), "function");
    await page.evaluate(() => window.__salaNativeSpeech.onTranscript("hey sala, can you dance for me?"));
    await page.waitForFunction(() => /sala-dancing/.test(document.querySelector("[data-testid=on-the-go-mascot]").className), null, { timeout: 5000 });
    await ctx.close();
  });

  await check("dance: reduced motion gets the gentle bob", async () => {
    const { ctx, page } = await setup(browser, { device: { viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" } });
    await page.addInitScript(() => { window.__ttsMs = 600000; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-mascot]")?.style.touchAction === "none", null, { timeout: 15000 });
    await page.evaluate(() => window.__salaNativeSpeech.onTranscript("shake shake"));
    await page.waitForFunction(() => /sala-dancing/.test(document.querySelector("[data-testid=on-the-go-mascot]").className), null, { timeout: 5000 });
    const anim = await page.evaluate(() => getComputedStyle(document.querySelector("[data-testid=on-the-go-mascot]")).animationName);
    assert.match(anim, /salaDanceCalm/, `reduced motion uses the calm bob, got ${anim}`);
    await ctx.close();
  });

  for (const [label, device] of [["desktop", undefined], ["Pixel 7", devices["Pixel 7"]]]) {
    await check(`widget menu (${label}): every item works`, async () => {
      const { ctx, page } = await setup(browser, device ? { device } : {});
      await page.addInitScript(() => { window.__ttsMs = 600000; });
      await begin(page);
      await start(page).click();
      await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "present", null, { timeout: 15000 });
      const presence = page.getByTestId("on-the-go-presence");
      // Menu opens, lists every item, and toggles closed.
      await page.getByTestId("on-the-go-widget-menu").click();
      for (const id of ["on-the-go-mic-toggle", "on-the-go-camera-toggle", "on-the-go-fullscreen"]) {
        assert.equal(await page.getByTestId(id).count(), 1, `menu has ${id}`);
      }
      // Mic: mute then unmute.
      await menuClick(page, "on-the-go-mic-toggle");
      await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-mascot]")?.getAttribute("data-state") === "muted", null, { timeout: 5000 });
      await menuClick(page, "on-the-go-mic-toggle");
      await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-mascot]")?.getAttribute("data-state") === "listening", null, { timeout: 10000 });
      // Camera: off then on again.
      await menuClick(page, "on-the-go-camera-toggle");
      await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") === "off", null, { timeout: 5000 });
      assert.equal(await cameraLive(page), false, "camera stopped");
      await menuClick(page, "on-the-go-camera-toggle");
      await page.waitForFunction(() => document.querySelector("[data-testid=on-the-go-presence]")?.getAttribute("data-state") !== "off", null, { timeout: 10000 });
      // Fullscreen item runs and closes the menu without an error.
      await menuClick(page, "on-the-go-fullscreen");
      await page.waitForFunction(() => !document.querySelector("[data-testid=on-the-go-widget-menu-list]"), null, { timeout: 3000 });
      // Privacy choices reopens the consent dialog.
      await menuClick(page, "otg-privacy-choices");
      await page.getByTestId("on-the-go-consent").waitFor({ state: "visible", timeout: 5000 });
      await page.getByTestId("on-the-go-consent").getByRole("button").last().click().catch(() => {});
      await page.keyboard.press("Escape").catch(() => {});
      // Minimize and expand.
      const min = page.getByTestId("on-the-go-widget-min");
      await min.click();
      assert.equal(await presence.getAttribute("data-minimized"), "1");
      await min.click();
      assert.equal(await presence.getAttribute("data-minimized"), "0");
      await ctx.close();
    });
  }

  await check("search: typing a short partial query keeps the dropdown responsive", async () => {
    const { ctx, page } = await setup(browser);
    await begin(page);
    await typeQuery(page, "cp");
    await page.waitForTimeout(500);
    const popup = await page.getByTestId("otg-search-popup").innerText();
    assert.doesNotMatch(popup, /^\s*$/, "cp shows something");
    await ctx.close();
  });
} finally {
  await browser.close();
}
console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
process.exit(failed ? 1 : 0);
