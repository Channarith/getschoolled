// Checks the Driver's Ed demo opening order: tutorial first, video waiting paused behind it,
// course title page held back, then video, then the lesson page.
//   node apps/web/e2e/drivers-ed-intro-order.mjs http://127.0.0.1:3100 /tmp/shots
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium, webkit, firefox, devices } = require("playwright");

const BASE = process.argv[2] || "http://127.0.0.1:3100";
const SHOTS = process.argv[3] || "/tmp";
const MATRIX = [
  ["chromium-desktop", chromium, { viewport: { width: 1280, height: 800 } }],
  ["webkit-iphone14", webkit, devices["iPhone 14"]],
  ["chromium-pixel7", chromium, devices["Pixel 7"]],
  ["chromium-ipad", chromium, devices["iPad Pro 11"]],
  ["firefox-desktop", firefox, { viewport: { width: 1280, height: 800 } }],
];

const frameOf = (page) => page.frameLocator('iframe[title^="Driver"]');
const video = (page) => page.getByTestId("drivers-ed-intro-video");
const videoState = (page) =>
  video(page).evaluate((v) => ({ paused: v.paused, t: v.currentTime, ended: v.ended }));

// The title text is visible to a person only if the element is rendered and not hidden by the hold.
async function lessonVisible(page) {
  return frameOf(page).locator("body").evaluate((body) => {
    const hold = document.documentElement.classList.contains("sala-intro-hold");
    const stage = document.querySelector("#teach-stage, .teach-stage");
    if (!stage) return { hold, visible: false, exists: false };
    const style = getComputedStyle(stage);
    return { hold, exists: true, visible: style.visibility !== "hidden" && style.display !== "none" };
  });
}

let failed = 0;
for (const [name, engine, opts] of MATRIX) {
  const browser = await engine.launch();
  try {
    const ctx = await browser.newContext({ ...opts });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message.slice(0, 120)));
    await page.goto(`${BASE}/demo/drivers-ed`, { waitUntil: "domcontentloaded" });

    // 1. Tutorial first, on top.
    const tut = frameOf(page).locator(".sala-tutorial");
    await tut.waitFor({ state: "visible", timeout: 30000 });
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${SHOTS}/dv-${name}-1-tutorial.png` });
    assert.equal(await page.getByTestId("drivers-ed-intro").getAttribute("data-phase"), "hold", `${name}: video waits`);

    // 2. Video is present but paused on its first frame while the tutorial is up.
    const waiting = await videoState(page);
    assert.equal(waiting.paused, true, `${name}: video paused behind tutorial`);
    assert.ok(waiting.t < 0.05, `${name}: video still at start (${waiting.t})`);

    // 3. The lesson page (first slide) is held back.
    const held = await lessonVisible(page);
    assert.equal(held.hold, true, `${name}: lesson held`);
    assert.equal(held.visible, false, `${name}: lesson text hidden`);
    assert.equal(await page.getByTestId("drivers-ed-intro-skip").count(), 0, `${name}: no skip while waiting`);

    // 4. Walk the tutorial to the end. The video must not start before the last step.
    const next = tut.locator(".go");
    for (let i = 0; i < 6; i += 1) {
      const label = (await next.innerText()).trim();
      if (/start the lesson|done/i.test(label)) break;
      await next.click();
      await page.waitForTimeout(150);
      assert.equal((await videoState(page)).paused, true, `${name}: still paused mid-tutorial`);
    }
    await next.click();

    // 5. Video plays now (or shows a play button where autoplay is blocked).
    await page.waitForFunction(
      () => document.querySelector('[data-testid="drivers-ed-intro"]')?.getAttribute("data-phase") === "play",
      null,
      { timeout: 10000 },
    );
    await page.waitForTimeout(1200);
    const after = await videoState(page);
    const tapNeeded = (await page.getByTestId("drivers-ed-intro-play").count()) > 0;
    assert.ok(after.paused === false || tapNeeded, `${name}: video plays or offers play`);
    await page.screenshot({ path: `${SHOTS}/dv-${name}-2-video.png` });
    assert.equal((await lessonVisible(page)).visible, false, `${name}: lesson still hidden while video plays`);

    // 6. Skip: the lesson page appears.
    await page.getByTestId("drivers-ed-intro-skip").click();
    await page.getByTestId("drivers-ed-intro").waitFor({ state: "detached", timeout: 5000 });
    await page.waitForTimeout(500);
    const done = await lessonVisible(page);
    assert.equal(done.hold, false, `${name}: hold released`);
    assert.equal(done.visible, true, `${name}: lesson visible after video`);
    await page.screenshot({ path: `${SHOTS}/dv-${name}-3-lesson.png` });

    // 7. Reload: the video is once per session, tutorial remembered, so straight to the lesson.
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    assert.equal(await page.getByTestId("drivers-ed-intro").count(), 0, `${name}: no second video this session`);
    assert.equal(await frameOf(page).locator(".sala-tutorial").count(), 0, `${name}: tutorial remembered`);
    assert.equal(errors.length, 0, `${name}: page errors ${errors.join("|")}`);
    console.log(`PASS ${name}`);
  } catch (error) {
    failed += 1;
    console.log(`FAIL ${name}: ${String(error.message).split("\n")[0]}`);
  } finally {
    await browser.close();
  }
}
process.exit(failed ? 1 : 0);
