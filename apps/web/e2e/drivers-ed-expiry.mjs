// End of the anonymous Driver's Ed demo: when the 10 minutes are up the demo really ends.
//   node apps/web/e2e/drivers-ed-expiry.mjs http://127.0.0.1:3100 /tmp/shots
// - a card says "Create or log in to your account" (Create account / Log in / Not now): no price, no card or PayPal, no billing request
// - narration, mic and the webcam stream are released; the lesson is not usable behind the card
// - "Not now" goes to the two-button front page and Back does not return to the demo
// - a refused (already expired) demo shows the same card at once, with no lesson
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");
const BASE = process.argv[2] || "http://127.0.0.1:3100";
const SHOTS = process.argv[3] || "/tmp";
const MATRIX = [["desktop", { viewport: { width: 1280, height: 800 } }], ["pixel7", devices["Pixel 7"]]];
const frameOf = (page) => page.frameLocator('iframe[title^="Driver"]');

const RECORD_STREAMS = `(() => {
  window.__streams = [];
  const md = navigator.mediaDevices;
  if (md && md.getUserMedia) { const real = md.getUserMedia.bind(md); md.getUserMedia = async (c) => { const s = await real(c); window.__streams.push(s); return s; }; }
})();`;
const SKIP_OPENING = `try { sessionStorage.setItem('salareen.driversEdIntro.seen.v1','1'); sessionStorage.setItem('sala_demo_tutorial_seen_v4','1'); localStorage.setItem('salareen_camera_pref_v1','yes'); } catch (e) {}`;

async function open(browser, opts, { nearEnd }) {
  const ctx = await browser.newContext({ ...opts, permissions: ["camera", "microphone"] });
  await ctx.addInitScript(RECORD_STREAMS);
  await ctx.addInitScript(SKIP_OPENING);
  const page = await ctx.newPage();
  const billing = [];
  page.on("request", (r) => { if (/\/api\/(studio\/)?pay|\/billing\//.test(r.url())) billing.push(r.url()); });
  if (nearEnd) {
    // The lesson starts with ~3 s left on the 10 minutes (the clock is the server's start time).
    await page.route("**/api/studio/teach/start", async (route) => {
      const res = await route.fetch();
      const body = await res.json();
      if (body.session) body.session.started_at_ms = Date.now() - (10 * 60_000 - 3000);
      await route.fulfill({ response: res, body: JSON.stringify(body) });
    });
  }
  return { ctx, page, billing };
}

let failed = 0;
for (const [name, opts] of MATRIX) {
  const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });
  try {
    // ---- 1. the clock runs out ------------------------------------------------------------------------------------------
    const { ctx, page, billing } = await open(browser, opts, { nearEnd: true });
    await page.goto(`${BASE}/demo/drivers-ed`, { waitUntil: "domcontentloaded" });
    const card = frameOf(page).getByTestId("trial-end");
    await card.waitFor({ state: "visible", timeout: 40000 });
    const text = await card.innerText();
    assert.match(text, /create or log in to your account/i, `${name}: heading`);
    assert.ok(await card.getByRole("button", { name: "Create account" }).isVisible(), `${name}: Create account`);
    assert.ok(await card.getByRole("button", { name: "Log in" }).isVisible(), `${name}: Log in`);
    assert.ok(await card.getByRole("button", { name: "Not now" }).isVisible(), `${name}: Not now`);
    assert.doesNotMatch(text, /\$|price|credit card|paypal|pay for/i, `${name}: no price or payment on the card`);
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${SHOTS}/expiry-${name}-1-card.png` });
    assert.equal(await frameOf(page).locator("#pay-screen.is-open").count(), 0, `${name}: no payment overlay`);
    assert.equal(await frameOf(page).locator("#course-price:visible").count(), 0, `${name}: no price button`);
    assert.equal(billing.length, 0, `${name}: no billing request (${billing.join(",")})`);
    const frame = page.frames().find((f) => f.url().includes("/studio"));
    const released = await frame.evaluate(() => ({ streams: window.__streams.length, live: window.__streams.flatMap((s) => s.getTracks()).filter((t) => t.readyState === "live").length }));
    assert.ok(released.streams >= 1, `${name}: the camera had been on`);
    assert.equal(released.live, 0, `${name}: every camera/mic track is stopped`);
    const behind = await frame.evaluate(() => {
      const x = Math.round(innerWidth / 2), y = Math.round(innerHeight / 2);
      const top = document.elementFromPoint(x, y);
      return { inCard: Boolean(top && top.closest("#trial-end")), ended: document.body.classList.contains("trial-ended"), mascotVisible: getComputedStyle(document.querySelector(".sala-mascot") || document.body).visibility !== "hidden" && Boolean(document.querySelector(".sala-mascot")) };
    });
    assert.ok(behind.inCard && behind.ended, `${name}: only the card is usable`);
    assert.equal(behind.mascotVisible, false, `${name}: nothing of the lesson is left usable`);

    // ---- 2. exits --------------------------------------------------------------------------------------------------------
    await card.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL(/\/login\?mode=signup&next=%2Flearn%2Fdrivers-ed/, { timeout: 15000 });
    await page.goBack().catch(() => {});
    await page.waitForTimeout(500);
    assert.doesNotMatch(page.url(), /\/demo\/drivers-ed$/, `${name}: Back does not reopen the demo (${page.url()})`);
    await ctx.close();

    const second = await open(browser, opts, { nearEnd: true });
    await second.page.goto(`${BASE}/demo/drivers-ed`, { waitUntil: "domcontentloaded" });
    const card2 = frameOf(second.page).getByTestId("trial-end");
    await card2.waitFor({ state: "visible", timeout: 40000 });
    await card2.getByRole("button", { name: "Log in" }).click();
    await second.page.waitForURL(/\/login\?next=%2Flearn%2Fdrivers-ed/, { timeout: 15000 });
    await second.ctx.close();

    const third = await open(browser, opts, { nearEnd: true });
    await third.page.goto(`${BASE}/demo/drivers-ed`, { waitUntil: "domcontentloaded" });
    const card3 = frameOf(third.page).getByTestId("trial-end");
    await card3.waitFor({ state: "visible", timeout: 40000 });
    await card3.getByRole("button", { name: "Not now" }).click();
    await third.page.waitForURL(`${BASE}/`, { timeout: 15000 });
    await third.page.getByRole("button", { name: /skip/i }).click({ timeout: 4000 }).catch(() => {});
    await third.page.getByRole("link", { name: /try the demo/i }).waitFor({ state: "visible", timeout: 15000 });
    assert.ok(await third.page.getByRole("link", { name: /^log in$/i }).isVisible(), `${name}: the two-button front page`);
    await third.page.screenshot({ path: `${SHOTS}/expiry-${name}-2-landing.png` });
    await third.page.goBack().catch(() => {});
    await third.page.waitForTimeout(800);
    assert.doesNotMatch(third.page.url(), /\/demo\/drivers-ed$/, `${name}: Back from the front page does not reopen the demo`);
    await third.ctx.close();

    // ---- 3. the server refuses an expired demo: a reload shows the card at once, with no lesson -------------------------------
    const fourth = await open(browser, opts, { nearEnd: false });
    await fourth.page.route("**/api/studio/teach/start", (route) => route.fulfill({ status: 403, contentType: "application/json", headers: { "x-aoep-gate": "trial_expired" }, body: JSON.stringify({ detail: "trial_expired: Your free 10-minute demo has ended. Create an account or log in to your account to keep learning." }) }));
    await fourth.page.goto(`${BASE}/demo/drivers-ed`, { waitUntil: "domcontentloaded" });
    const card4 = frameOf(fourth.page).getByTestId("trial-end");
    await card4.waitFor({ state: "visible", timeout: 40000 });
    assert.equal(await frameOf(fourth.page).locator("#teach-stage:visible").count(), 0, `${name}: no lesson behind a refused demo`);
    await fourth.ctx.close();
    console.log(`PASS ${name}`);
  } catch (error) {
    failed += 1;
    const where = String(error.stack).split("\n").filter((l) => l.includes("drivers-ed-expiry")).slice(0, 1).join("").trim().replace(/^.*\//, "");
    console.log(`FAIL ${name}: ${String(error.message).split("\n")[0]} @ ${where}`);
  } finally {
    await browser.close();
  }
}
process.exit(failed ? 1 : 0);
