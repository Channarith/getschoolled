// Executed by tests/test_minimal_shell.py with LAB_URL set. Real browser, phone emulation, fake camera.
// Proves: every registered game uses ONE minimal shell (demo and signed-in); the removed chrome is gone; double-tap goes full
// screen; touching a quiz answer selects it (no throw); a dead detector never shows the "left the camera" banner.
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.resolve(here, "../../../apps/web/") + "/");
const pw = require("playwright");
const LAB = process.env.LAB_URL;
assert.ok(LAB, "LAB_URL is required");

const REMOVED = [".topbar > :not(#touch-mode)", ".controls", "#play-game", ".vision-tools", ".dashboard", "#vision-readout", ".pq-top", ".pq-chips", "#chrome-toggle", "#fullscreen"];
const visible = (page, selector) => page.evaluate((s) => [...document.querySelectorAll(s)].filter((e) => {
  const r = e.getBoundingClientRect(); const c = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && c.visibility !== "hidden" && c.display !== "none" && Number(c.opacity) > 0;
}).length, selector);

const setGame = (page, id) => page.evaluate((game) => {
  const select = document.getElementById("game");
  select.value = game;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}, id);

const browser = await pw.chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });

async function newPage({ signedIn = false, desktop = false, block = false } = {}) {
  const ctx = await browser.newContext(desktop ? { viewport: { width: 1280, height: 800 }, permissions: ["camera", "microphone"] }
    : { ...pw.devices["Pixel 7"], permissions: ["camera", "microphone"] });
  if (signedIn) await ctx.addInitScript(() => { try { localStorage.setItem("aoep_token", "test-token"); localStorage.setItem("aoep_student_id", "student-1"); } catch (_) {} });
  const page = await ctx.newPage();
  await page.route("**/voice-assets/**", (r) => r.abort());
  if (block) await page.route(/\/vendor\/vision\/|jsdelivr|storage\.googleapis/, (r) => r.abort());
  await page.goto(`${LAB}/?lang=en`, { waitUntil: "domcontentloaded" });
  return { page, ctx };
}

// 1. Every registered game, demo and signed-in, phone and desktop: same minimal shell.
for (const mode of [{ signedIn: false, name: "demo" }, { signedIn: true, name: "signed-in" }]) {
  const { page, ctx } = await newPage({ signedIn: mode.signedIn });
  await page.click("#demo");
  await page.waitForSelector("#lab-widget", { state: "visible" });
  const games = await page.evaluate(() => [...document.querySelectorAll("#game option")].map((o) => o.value));
  assert.ok(games.length >= 40, `expected the full registry, got ${games.length}`);
  for (const id of games) {
    await setGame(page, id);
    await page.waitForTimeout(60);
    for (const sel of REMOVED) assert.equal(await visible(page, sel), 0, `${mode.name}/${id}: ${sel} must not be visible`);
    assert.equal(await visible(page, "#lab-widget"), 1, `${mode.name}/${id}: one widget`);
    assert.equal(await visible(page, "#lab-progress"), 1, `${mode.name}/${id}: thin progress line`);
    assert.equal(await page.evaluate(() => document.querySelectorAll("#lab-widget").length), 1);
    const exists = await page.evaluate(() => Boolean(document.getElementById("touch-mode")));
    assert.ok(exists, `${mode.name}/${id}: touch pill exists in the DOM`);
    const bar = await page.evaluate(() => { const r = document.getElementById("lab-progress").getBoundingClientRect(); return {top: r.top, h: r.height}; });
    assert.ok(bar.top <= 1 && bar.h <= 4, `${mode.name}/${id}: progress line is thin and at the very top`);
  }
  // the menu holds the choices
  await page.click("#lab-more");
  assert.ok(await visible(page, "#lab-menu #game") === 1 && await visible(page, "#lab-menu #pace") === 1, `${mode.name}: game and pace live in the menu`);
  await ctx.close();
}

// 2. Desktop keeps the same shell.
{
  const { page, ctx } = await newPage({ desktop: true });
  await page.click("#demo");
  await page.waitForSelector("#lab-widget", { state: "visible" });
  for (const sel of REMOVED) assert.equal(await visible(page, sel), 0, `desktop: ${sel}`);
  await ctx.close();
}

// 3. Double-tap anywhere on the scene = full screen.
{
  const { page, ctx } = await newPage();
  await page.click("#demo");
  await page.waitForSelector("#lab-widget", { state: "visible" });
  await setGame(page, "air-drums");
  await page.waitForTimeout(300);
  // The game's own tutorial comes first; dismiss it like a player would.
  const go = page.locator(".gt-go");
  if (await go.count()) await go.first().click();
  await page.waitForTimeout(300);
  await page.touchscreen.tap(200, 520);
  await page.touchscreen.tap(203, 523);
  await page.waitForTimeout(400);
  const full = await page.evaluate(() => Boolean(document.fullscreenElement) || document.body.classList.contains("stage-fill"));
  assert.ok(full, "double-tap must toggle full screen");
  await ctx.close();
}

// 4. Pop Quiz Toss by touch: touching the answer selects it, no throw; the thin line grows on a correct answer.
{
  const { page, ctx } = await newPage();
  let answer = "";
  page.on("response", async (res) => { if (res.url().includes("/api/child/quiz-round")) { try { answer = (await res.json()).answer || answer; } catch (_) {} } });
  await page.click("#demo");
  await page.waitForSelector("#lab-widget", { state: "visible" });
  await setGame(page, "pop-quiz-toss");
  const skip = page.locator(".pq-skip");
  if (await skip.count().then((n) => n > 0).catch(() => false)) await skip.first().click({ timeout: 4000 }).catch(() => {});
  await page.waitForSelector(".pq-target", { state: "visible", timeout: 15000 });
  await page.waitForFunction(() => document.querySelectorAll(".pq-target").length === 2);
  await page.waitForTimeout(400);
  const target = page.locator(`.pq-target[data-answer="${answer.replace(/"/g, '\\"')}"]`).first();
  const box = await (await target.elementHandle()).boundingBox();
  assert.ok(box, "correct target on screen");
  await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForFunction(() => document.querySelector(".pq-target.hit,.pq-target.miss"), null, { timeout: 4000 });
  assert.ok(await page.evaluate(() => Boolean(document.querySelector(".pq-target.hit"))), "tapping the right answer scores");
  assert.ok(await page.evaluate(() => !document.querySelector(".pq-ball.flying")), "no ball is thrown");
  // The thin line at the very top follows the percentage the game reports (read in the same tick: the quiz HUD also reports).
  const line = await page.evaluate(() => {
    const out = [];
    for (const percent of [40, 75]) {
      window.dispatchEvent(new CustomEvent("lab:progress", { detail: { percent } }));
      out.push([document.getElementById("lab-progress").getAttribute("aria-valuenow"), document.querySelector("#lab-progress i").style.width]);
    }
    return out;
  });
  assert.deepEqual(line, [["40", "40%"], ["75", "75%"]]);
  await ctx.close();
}

// 5. Detector unavailable (models blocked): no "left the camera" banner, the game is playable by touch.
{
  const { page, ctx } = await newPage({ block: true });
  await page.click("#start");
  await page.waitForSelector("#lab-widget", { state: "visible" });
  await page.waitForTimeout(6000);
  const info = await page.evaluate(() => ({
    note: document.getElementById("presence-note")?.textContent || "",
    noteHidden: document.getElementById("presence-note")?.hidden,
    away: Boolean(window.labShellApi) && JSON.stringify(window.labShellApi.health()),
    touch: document.body.classList.contains("screen-touch"),
    text: document.body.innerText,
  }));
  assert.ok(!/left the camera/i.test(info.text), "no 'left the camera' banner while the detector is unavailable");
  assert.ok(info.touch, "the game falls back to touch quietly");
  assert.match(info.away, /"state":"failed"/, "the failure is recorded for the triage log");
  await ctx.close();
}

// 6. /diag/vision has the hand test and fails gracefully when the models cannot load (no crash, the button comes back).
{
  const ctx = await browser.newContext({ ...pw.devices["Pixel 7"], permissions: ["camera", "microphone"] });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.route(/\/vendor\/vision\//, (r) => r.abort());
  await page.goto(`${LAB}/diag/vision`, { waitUntil: "domcontentloaded" });
  assert.equal(await page.locator("#handtest").count(), 1, "the hand test button exists");
  await page.click("#handtest");
  await page.waitForFunction(() => !document.getElementById("handtest").disabled && /Hand test|failed|Done/.test(document.getElementById("rows").textContent + document.getElementById("status").textContent), null, { timeout: 30000 });
  assert.deepEqual(errors, [], "no uncaught errors on the diagnostics page");
  const report = await page.inputValue("#report");
  assert.match(report, /variant-test|Hand test|variant test failed/, "the failure is in the pasteable report");
  await ctx.close();
}

await browser.close();
console.log("minimal shell ok");
