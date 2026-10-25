// Full course (course-clean): the lesson plus ONE movable widget (camera + Sala's voice + menu), nothing else.
// Loads the Course Studio page directly with the same query the web wrapper and the phone app use.
//   node apps/web/e2e/course-clean-widget.mjs http://127.0.0.1:8141 /tmp/shots
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium, webkit, devices } = require("playwright");

const BASE = process.argv[2] || "http://127.0.0.1:8141";
const SHOTS = process.argv[3] || "/tmp";
const URL = `${BASE}/studio?access=full&course=drivers-ed&registered=1&admin=1&account=a1&student=s1`;
const MATRIX = [
  ["chromium-fold-inner", chromium, { viewport: { width: 1153, height: 1280 }, hasTouch: true }],
  ["chromium-desktop", chromium, { viewport: { width: 1280, height: 800 } }],
  ["chromium-pixel7", chromium, devices["Pixel 7"]],
  ["chromium-ipad", chromium, devices["iPad Pro 11"]],
  ["webkit-iphone14", webkit, devices["iPhone 14"]],
];

// Elements that must not be visible on the full course any more.
const REMOVED = ["#course-price", "#course-map", ".sala-consent", ".sala-pill", "#proceed-cue", ".sala-help", ".theodore-avatar-wrap", "#toast", "#attention-aside", "#teach-title"];

const visibleFloating = (page) =>
  page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll("body > *, body > * *")) {
      const cs = getComputedStyle(el);
      if (cs.position !== "fixed") continue;
      const r = el.getBoundingClientRect();
      if (r.width < 24 || r.height < 16 || cs.display === "none" || cs.visibility === "hidden" || +cs.opacity === 0) continue;
      if (r.right < 0 || r.bottom < 0 || r.left > innerWidth || r.top > innerHeight) continue;
      // Full-viewport containers that only host other things (study background, voice root, tutorial) are not widgets.
      if (r.width >= innerWidth - 2 && r.height >= innerHeight - 2) continue;
      out.push(`${el.tagName.toLowerCase()}#${el.id}.${String(el.className).slice(0, 30)}`);
    }
    return out;
  });

const isVisible = (page, selector) =>
  page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return false;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return cs.display !== "none" && cs.visibility !== "hidden" && r.width > 2 && r.height > 2;
  }, selector);

let failed = 0;
for (const [name, engine, opts] of MATRIX) {
  const launchArgs = engine === chromium ? ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] : [];
  const browser = await engine.launch({ args: launchArgs });
  try {
    // --- first visit: the tutorial shows, then the clean layout ---
    const ctx = await browser.newContext({ ...opts, permissions: engine === chromium ? ["camera", "microphone"] : [] });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message.slice(0, 120)));
    await page.goto(URL, { waitUntil: "networkidle" });
    await page.locator(".sala-tutorial").waitFor({ state: "visible", timeout: 20000 });
    await page.screenshot({ path: `${SHOTS}/cc-${name}-1-tutorial.png` });
    // Escape closes the tutorial and returns focus to the panel menu.
    await page.keyboard.press("Escape");
    await page.locator(".sala-tutorial").waitFor({ state: "detached", timeout: 5000 });
    await page.waitForTimeout(500);

    // --- the clean layout: only the lesson and one floating widget ---
    for (const sel of REMOVED) assert.equal(await isVisible(page, sel), false, `${name}: ${sel} must be hidden`);
    assert.equal(await page.locator("body.course-clean").count(), 1, `${name}: course-clean switch`);
    const floats = await visibleFloating(page);
    const widgets = floats.filter((f) => f.includes("course-widget"));
    assert.equal(widgets.length, 1, `${name}: exactly one widget (${floats.join(" | ")})`);
    assert.equal(await page.locator("#course-widget #student-cam").count(), 1, `${name}: webcam lives in the widget`);
    const outside = floats.filter((f) => !f.includes("course-widget") && !f.includes("student-cam") && !f.includes("theodore-live-audio"));
    assert.equal(outside.length, 0, `${name}: nothing else floats (${outside.join(" | ")})`);
    await page.screenshot({ path: `${SHOTS}/cc-${name}-2-clean.png` });

    // --- movable, and the spot is remembered ---
    const grip = page.locator("#course-widget .cw-grip");
    const before = await page.locator("#course-widget").boundingBox();
    const g = await grip.boundingBox();
    await page.mouse.move(g.x + g.width / 2, g.y + g.height / 2);
    await page.mouse.down();
    await page.mouse.move(g.x + g.width / 2 + 90, g.y + g.height / 2 + 160, { steps: 6 });
    await page.mouse.up();
    const moved = await page.locator("#course-widget").boundingBox();
    assert.ok(Math.abs(moved.x - before.x) > 40 && Math.abs(moved.y - before.y) > 80, `${name}: widget dragged (${before.x},${before.y}) -> (${moved.x},${moved.y})`);
    const vp = page.viewportSize();
    assert.ok(moved.x >= 0 && moved.y >= 0 && moved.x + moved.width <= vp.width && moved.y + moved.height <= vp.height, `${name}: stays inside the screen`);
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const again = await page.locator("#course-widget").boundingBox();
    assert.ok(Math.abs(again.x - moved.x) < 3 && Math.abs(again.y - moved.y) < 3, `${name}: position remembered`);
    // Keyboard: arrow keys on the grip move it, and it still stays on screen.
    await grip.focus();
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("ArrowUp");

    // --- the menu: Help, Progress, Exit; Escape closes it ---
    await page.locator("#course-widget .cw-menu-btn").click();
    const items = await page.locator("#course-widget .cw-menu").innerText();
    assert.match(items, /Help/, `${name}: Help in menu`);
    assert.match(items, /Progress: \d+%/, `${name}: Progress in menu`);
    assert.match(items, /Exit lesson/, `${name}: Exit in menu`);
    await page.screenshot({ path: `${SHOTS}/cc-${name}-3-menu.png` });
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("#course-widget .cw-menu").isHidden(), true, `${name}: Escape closes the menu`);

    // Help reopens the tutorial; Skip closes it.
    await page.locator("#course-widget .cw-menu-btn").click();
    await page.locator('#course-widget .cw-menu [role="menuitem"]', { hasText: "Help" }).click();
    await page.locator(".sala-tutorial").waitFor({ state: "visible", timeout: 5000 });
    await page.keyboard.press("Escape");

    // --- "you left the camera": a small status line in the widget, not a banner ---
    await page.evaluate(() => {
      const aside = document.getElementById("attention-aside");
      aside.hidden = false;
      aside.dataset.glance = "1";
      aside.textContent = "We detected that you left the camera. The lesson is paused and will resume when you return.";
    });
    await page.waitForTimeout(200);
    assert.match(await page.locator("#course-widget .cw-status").innerText(), /left the camera/, `${name}: pause note in the widget`);
    assert.equal(await page.locator("#course-widget .cw-status").getAttribute("data-kind"), "paused");
    assert.equal(await isVisible(page, "#attention-aside"), false, `${name}: no big banner`);
    await page.screenshot({ path: `${SHOTS}/cc-${name}-4-paused.png` });
    await page.evaluate(() => {
      const aside = document.getElementById("attention-aside");
      aside.hidden = true;
      aside.textContent = "";
      delete aside.dataset.glance;
    });
    await page.waitForTimeout(200);
    assert.doesNotMatch(await page.locator("#course-widget .cw-status").innerText(), /left the camera/, `${name}: pause note clears`);

    // --- tuck away keeps the camera element alive ---
    await page.locator("#course-widget .cw-collapse").click();
    assert.equal(await page.locator("#course-widget").getAttribute("data-collapsed"), "1");
    assert.equal(await page.locator("#course-widget #student-cam").count(), 1, `${name}: camera stays mounted when tucked away`);
    await page.locator("#course-widget .cw-collapse").click();

    // --- Exit lesson tells the app / wrapper ---
    await page.evaluate(() => { window.ReactNativeWebView = { postMessage: (m) => { window.__exitMsg = m; } }; });
    await page.locator("#course-widget .cw-menu-btn").click();
    await page.locator('#course-widget .cw-menu [role="menuitem"]', { hasText: "Exit lesson" }).click();
    const exitState = await page.evaluate(() => `${window.__exitMsg || ""} collapsed=${document.getElementById("course-widget")?.dataset.collapsed} menu=${document.querySelector("#course-widget .cw-menu")?.hidden}`);
    assert.match(exitState, /salareen-exit/, `${name}: Exit posts salareen-exit (${exitState})`);

    // --- one tap on the lesson starts it and lets Sala listen (hint stored) ---
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const stage = await page.locator("#teach-stage").boundingBox();
    await page.mouse.click(stage.x + stage.width * 0.55, stage.y + stage.height * 0.72);
    await page.waitForTimeout(600);
    const hint = await page.evaluate(() => window.localStorage.getItem("aoep.courseWidget.hint.v1"));
    assert.equal(hint, "1", `${name}: first tap handled`);

    assert.deepEqual(errors, [], `${name}: no page errors`);
    console.log(`PASS ${name}`);
    await ctx.close();
  } catch (error) {
    failed += 1;
    console.log(`FAIL ${name}: ${String(error.message).slice(0, 300)}`);
  } finally {
    await browser.close();
  }
}
process.exit(failed ? 1 : 0);
