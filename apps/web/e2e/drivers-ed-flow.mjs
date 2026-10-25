// Driver's Ed demo flow: tutorial -> camera consent card -> opening video behind the widget and Sala -> the lesson starts by itself.
//   node apps/web/e2e/drivers-ed-flow.mjs http://127.0.0.1:3100 /tmp/shots
// Needs the web app with the course studio behind /studio and a course with id "drivers-ed".
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");

const BASE = process.argv[2] || "http://127.0.0.1:3100";
const SHOTS = process.argv[3] || "/tmp";
const MATRIX = [
  ["desktop", { viewport: { width: 1280, height: 800 } }],
  ["pixel7", devices["Pixel 7"]],
];
const frameOf = (page) => page.frameLocator('iframe[title^="Driver"]');

// Count every getUserMedia call, so "no camera before consent" is a measurement, not a hope.
const COUNT_CAMERA = `(() => {
  window.__gum = 0;
  const md = navigator.mediaDevices;
  if (md && md.getUserMedia) {
    const real = md.getUserMedia.bind(md);
    md.getUserMedia = (c) => { window.__gum += 1; return real(c); };
  }
})();`;
async function gum(page) {
  // The count lives in the lesson frame (it owns the camera).
  const frame = page.frames().find((f) => f.url().includes("/studio"));
  return frame ? frame.evaluate(() => window.__gum || 0) : -1;
}

async function walkTutorial(page) {
  const go = frameOf(page).locator(".sala-tutorial .go");
  await go.waitFor({ state: "visible", timeout: 30000 });
  for (let i = 0; i < 8; i += 1) {
    const label = (await go.innerText()).trim();
    await go.click();
    if (/start the lesson|done/i.test(label)) break;
    await page.waitForTimeout(120);
  }
}

let failed = 0;
for (const [name, opts] of MATRIX) {
  const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });
  try {
    // ---- Path 1: allow the camera -------------------------------------------------------------------------------------
    const ctx = await browser.newContext({ ...opts, permissions: ["camera", "microphone"] });
    await ctx.addInitScript(COUNT_CAMERA);
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message.slice(0, 120)));
    await page.goto(`${BASE}/demo/drivers-ed`, { waitUntil: "domcontentloaded" });

    const tutorial = frameOf(page).locator(".sala-tutorial");
    await tutorial.waitFor({ state: "visible", timeout: 30000 });
    assert.equal(await gum(page), 0, `${name}: no camera request while the tutorial is open`);
    assert.equal(await frameOf(page).locator(".sala-cam-consent").count(), 0, `${name}: consent card not yet`);

    await walkTutorial(page);
    const card = frameOf(page).getByTestId("camera-consent");
    await card.waitFor({ state: "visible", timeout: 10000 });
    assert.match(await card.innerText(), /never uploaded or recorded/i, `${name}: consent wording`);
    assert.equal(await gum(page), 0, `${name}: the browser was NOT asked for the camera before consent`);
    assert.equal(await page.getByTestId("drivers-ed-intro-skip").count(), 0, `${name}: no Skip/Next button`);
    await page.screenshot({ path: `${SHOTS}/flow-${name}-1-consent.png` });

    await card.getByRole("button", { name: /turn on camera/i }).click();
    await card.waitFor({ state: "detached", timeout: 5000 });
    await page.waitForFunction(() => document.querySelector('[data-testid="drivers-ed-intro"]')?.getAttribute("data-phase") !== "hold", null, { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1500);
    assert.ok((await gum(page)) >= 1, `${name}: camera requested after consent`);

    // While the opening scene runs (or has just ended on a browser without the video codec): widget + Sala on top, no Skip.
    const intro = page.getByTestId("drivers-ed-intro");
    const inIntro = (await intro.count()) > 0;
    if (inIntro) {
      assert.equal(await page.getByTestId("drivers-ed-intro-skip").count(), 0, `${name}: still no Skip/Next`);
      const mascot = frameOf(page).getByTestId("sala-mascot");
      await mascot.waitFor({ state: "visible", timeout: 5000 });
      const widget = frameOf(page).locator("#course-widget");
      assert.ok(await widget.isVisible(), `${name}: widget visible during the opening scene`);
      await page.screenshot({ path: `${SHOTS}/flow-${name}-2-video.png` });
    }

    // The lesson starts by itself (video end, error, or the 15 s cap): wait for hold to release.
    await frameOf(page).locator("html:not(.sala-intro-hold)").waitFor({ state: "attached", timeout: 30000 });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${SHOTS}/flow-${name}-3-lesson.png` });

    // Sala is there, clickable, and nothing covers it (elementFromPoint at its center).
    const sala = frameOf(page).getByTestId("sala-mascot");
    await sala.waitFor({ state: "visible", timeout: 5000 });
    const hit = await frameOf(page).locator("body").evaluate(() => {
      const m = document.querySelector('[data-testid="sala-mascot"]');
      const r = m.getBoundingClientRect();
      const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return { ok: m.contains(top) || top === m, left: r.left, bottom: window.innerHeight - r.bottom };
    });
    assert.ok(hit.ok, `${name}: nothing covers Sala`);
    assert.ok(hit.left < 40, `${name}: Sala is bottom-left (${hit.left})`);
    await sala.click();
    await page.waitForTimeout(400);
    assert.notEqual(await sala.getAttribute("data-listen"), null, `${name}: Sala reacts to a tap`);

    // The camera preview is shown by default in the widget, with a visible switch.
    const widgetState = await frameOf(page).locator("body").evaluate(() => {
      const cam = document.querySelector("#course-widget .cw-cam");
      const clock = document.querySelector("#course-widget .cw-bar .cw-clock");
      const video = document.querySelector("#student-cam");
      const c = clock && clock.getBoundingClientRect();
      const v = video && video.getBoundingClientRect();
      return { cam: cam && cam.dataset.cam, toggle: Boolean(document.querySelector('[data-testid="camera-toggle"]')), overlap: c && v ? !(c.bottom <= v.top || v.bottom <= c.top || c.right <= v.left || v.right <= c.left) : false };
    });
    assert.equal(widgetState.cam, "on", `${name}: camera preview on by default after consent`);
    assert.ok(widgetState.toggle, `${name}: one-tap camera switch`);
    assert.equal(widgetState.overlap, false, `${name}: timer does not overlap the camera picture`);

    // The two cream bars are not drawn; their text is still there for screen readers.
    const bars = await frameOf(page).locator("body").evaluate(() => {
      const box = (id) => { const e = document.getElementById(id); if (!e) return null; const r = e.getBoundingClientRect(); return { w: r.width, h: r.height, t: (e.textContent || "").trim().length, live: e.getAttribute("aria-live") }; };
      return { activity: box("teach-activity"), warn: box("lang-warning"), all: document.body.innerText.includes("not translated yet") };
    });
    assert.ok(!bars.activity || bars.activity.w <= 2, `${name}: question bar not drawn`);
    assert.ok(!bars.warn || bars.warn.w <= 2, `${name}: notes bar not drawn`);
    assert.equal(bars.all, false, `${name}: no "not translated yet" text`);
    if (bars.activity) assert.equal(bars.activity.live, "polite", `${name}: question text kept for screen readers`);

    // Menu: Show captions (off by default) brings the bar back; camera items are there.
    await frameOf(page).locator("#course-widget .cw-menu-btn").click();
    const menu = frameOf(page).locator("#course-widget .cw-menu");
    await menu.getByRole("menuitem", { name: /show captions/i }).click();
    assert.equal(await frameOf(page).locator("body.sala-captions").count(), 1, `${name}: captions switch works`);
    await frameOf(page).locator("#course-widget .cw-menu-btn").click();
    assert.ok(await menu.getByRole("menuitem", { name: /turn camera off/i }).count(), `${name}: camera menu item`);
    await menu.getByRole("menuitem", { name: /show captions|hide captions/i }).first().click();   // back to off
    assert.equal(await frameOf(page).locator("body.sala-captions").count(), 0, `${name}: captions off again`);
    // Camera off in one tap.
    await frameOf(page).getByTestId("camera-toggle").click();
    await page.waitForTimeout(400);
    assert.equal(await frameOf(page).locator("#course-widget .cw-cam").getAttribute("data-cam"), "off", `${name}: camera off in one tap`);

    // Reload: the consent is remembered and asked nowhere again.
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    assert.equal(await frameOf(page).locator(".sala-cam-consent").count(), 0, `${name}: consent not asked twice`);
    assert.equal(errors.length, 0, `${name}: page errors ${errors.join("|")}`);
    await ctx.close();

    // ---- Path 2: "Not now" -> audio-only, lesson still runs --------------------------------------------------------------
    const ctx2 = await browser.newContext({ ...opts, permissions: ["camera", "microphone"] });
    await ctx2.addInitScript(COUNT_CAMERA);
    const page2 = await ctx2.newPage();
    await page2.goto(`${BASE}/demo/drivers-ed`, { waitUntil: "domcontentloaded" });
    await walkTutorial(page2);
    const card2 = frameOf(page2).getByTestId("camera-consent");
    await card2.waitFor({ state: "visible", timeout: 10000 });
    await card2.getByRole("button", { name: /not now/i }).click();
    await frameOf(page2).locator("html:not(.sala-intro-hold)").waitFor({ state: "attached", timeout: 30000 });
    await page2.waitForTimeout(2500);
    assert.equal(await gum(page2), 0, `${name}: declined -> camera never requested`);
    const off = await frameOf(page2).locator("#course-widget .cw-cam").getAttribute("data-cam");
    assert.equal(off, "off", `${name}: widget shows audio-only state`);
    assert.ok(await frameOf(page2).locator("#teach-stage").isVisible(), `${name}: the lesson still runs without a camera`);
    await page2.screenshot({ path: `${SHOTS}/flow-${name}-4-declined.png` });
    await ctx2.close();
    console.log(`PASS ${name}`);
  } catch (error) {
    failed += 1;
    const where = String(error.stack).split("\n").filter((l) => l.includes("drivers-ed-flow")).slice(0, 1).join("");
    console.log(`FAIL ${name}: ${String(error.message).split("\n")[0]} ${where.trim()}`);
  } finally {
    await browser.close();
  }
}
process.exit(failed ? 1 : 0);
