// On the Go (hidden demo): course picker, resume points, spoken course commands, face presence, avatar Q&A, mic mute, camera denied,
// question limits and privacy on a hidden tab. Everything outside the page is stubbed: API, camera detector, speech recognizer, voice.
//   node apps/web/e2e/on-the-go-demo.mjs http://127.0.0.1:3071 /tmp/shots
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");

const BASE = process.argv[2] || "http://127.0.0.1:3071";
const SHOTS = process.argv[3] || "/tmp";
const URL = `${BASE}/demo/on-the-go`;

const CATALOG = [
  ["audio-intro-to-machine-learning", "Intro to Machine Learning (audio)", "Technology"],
  ["audio-the-roman-empire", "The Roman Empire (audio)", "History"],
  ["audio-ancient-egypt", "Ancient Egypt (audio)", "History"],
  ["audio-cybersecurity-basics", "Cybersecurity Basics (audio)", "Technology"],
  ["audio-the-history-of-cinema", "The History of Cinema (audio)", "Arts & Culture"],
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
  await page.route(/\/audio\/courses(\?.*)?$/, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total: CATALOG.length, offset: 0, limit: 300, courses: CATALOG.map(row) }) }));
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
  }, { denyCamera: Boolean(opts.denyCamera) });
  return { ctx, page, errors };
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
  await page.getByTestId("on-the-go-picker").waitFor({ state: "visible", timeout: 20000 });
}
const start = (page) => page.getByRole("button", { name: /^(start|.*pause)$/i }).first();

let failed = 0;
let lastPage = null;
const ONLY = process.env.ONLY || "";
const check = async (name, fn) => {
  if (ONLY && !name.includes(ONLY)) return;
  try { await fn(); console.log(`PASS ${name}`); } catch (e) {
    failed += 1;
    console.log(`FAIL ${name}: ${String(e.message || e).split("\n")[0].slice(0, 300)}`);
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
    for (const id of ["audio-intro-to-machine-learning", "audio-the-roman-empire", "audio-ancient-egypt", "audio-cybersecurity-basics", "audio-the-history-of-cinema"]) {
      assert.equal(await page.getByTestId(`otg-course-${id}`).count(), 1, id);
    }
    assert.equal(await page.getByTestId("otg-course-audio-not-in-the-curated-list").count(), 0, "uncurated course must not be offered in the demo");
    await page.getByRole("searchbox").fill("roman");
    assert.equal(await page.locator("[data-testid^=otg-course-]").count(), 1);
    await page.getByRole("searchbox").fill("");
    await page.getByRole("button", { name: "History", exact: true }).click();
    assert.equal(await page.locator("[data-testid^=otg-course-]").count(), 2);
    await page.screenshot({ path: `${SHOTS}/otg-1-picker.png` });
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  // 2. Choose a course, play it, the avatar and the widget are on screen.
  await check("choosing a course plays that course; avatar and widget are visible", async () => {
    const { ctx, page } = await setup(browser);
    await begin(page);
    await page.getByTestId("otg-course-audio-the-roman-empire").click();
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
  await check("voice: 'play the ancient egypt course', then 'next course'", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 700; });
    await begin(page);
    await start(page).click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await say(page, "hey sala play the ancient egypt course");
    await page.waitForFunction(() => window.__spoken.some((t) => /Playing Ancient Egypt/.test(t)), null, { timeout: 15000 });
    await page.waitForFunction(() => window.__spoken.some((t) => /Ancient Egypt part/.test(t)), null, { timeout: 15000 });
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 15000 });
    await say(page, "hey sala next course");
    await page.waitForFunction(() => window.__spoken.some((t) => /Next course:/.test(t)), null, { timeout: 15000 });
    await page.waitForFunction(() => window.__spoken.some((t) => /The History of Cinema part 1/.test(t)), null, { timeout: 15000 });
    await ctx.close();
  });

  // 4. Resume where you left off, per course.
  await check("the course remembers where you stopped and offers to resume", async () => {
    const { ctx, page } = await setup(browser);
    await page.addInitScript(() => { window.__ttsMs = 900; });
    await begin(page);
    await page.getByTestId("otg-course-audio-cybersecurity-basics").click();
    await start(page).click();
    await page.waitForFunction(() => window.__spoken.some((t) => /Cybersecurity Basics part 3/.test(t)), null, { timeout: 15000 });
    await page.getByRole("button", { name: /pause/i }).first().click();
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("salareen.onTheGo.progress.v1") || "{}"));
    assert.ok(saved.courses["audio-cybersecurity-basics"].seg >= 2, JSON.stringify(saved));
    await page.reload({ waitUntil: "domcontentloaded" });
    await closeTutorials(page);
    await page.getByTestId("on-the-go-picker").waitFor({ state: "visible" });
    assert.match(await page.getByTestId("otg-course-audio-cybersecurity-basics").innerText(), /Resume at part/);
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
    await page.getByTestId("on-the-go-camera-toggle").click();
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
    await page.getByTestId("otg-course-audio-intro-to-machine-learning").click();
    await start(page).click();
    await page.waitForFunction(() => window.__spoken.length > 0, null, { timeout: 15000 });
    await page.getByTestId("on-the-go-mascot").click();
    await page.waitForFunction(() => window.__recs.some((r) => !r.__stopped), null, { timeout: 10000 });
    await say(page, "how does machine learning work in practice");
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
    await page.getByTestId("on-the-go-mic-toggle").click();
    await page.waitForFunction(() => window.__recs.every((r) => r.__stopped), null, { timeout: 5000 });
    assert.equal(await say(page, "hey sala play the ancient egypt course"), false, "no live recognizer while muted");
    await page.waitForTimeout(800);
    assert.ok(!(await spokenText(page)).includes("Playing Ancient Egypt"));
    await page.getByTestId("on-the-go-mic-toggle").click();
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
    await say(page, "hey sala play the ancient egypt course");
    await page.waitForFunction(() => window.__spoken.some((t) => /Playing Ancient Egypt/.test(t)), null, { timeout: 15000 });
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
    await page.screenshot({ path: `${SHOTS}/otg-11-phone.png` });
    await ctx.close();
  });
} finally {
  await browser.close();
}
console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
process.exit(failed ? 1 : 0);
