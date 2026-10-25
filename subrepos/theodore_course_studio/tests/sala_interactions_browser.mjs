// Real-browser check of Sala's gestures. Run: node subrepos/theodore_course_studio/tests/sala_interactions_browser.mjs
// Needs Playwright (apps/web/node_modules). Exits 1 on any failure.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.resolve(here, "../../../apps/web/package.json"));
const { chromium } = require("playwright");
const MODULE = readFileSync(path.resolve(here, "../src/theodore_course_studio/voice_static/sala_interactions.js"), "utf8");

const HTML = `<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<body style="margin:0;font:16px system-ui">
<div id="stage" style="width:600px;height:300px;background:#eef">lesson</div>
<div id="theodore-avatar-wrap" style="position:relative;width:200px;height:220px;margin:20px;background:#fed"><div class="avatar-handle" style="height:24px;background:#ccc">grip</div><div id="theodore-avatar" style="height:150px"></div></div>
<script type="module">
  import * as S from "http://sala.test/sala_interactions.js";
  window.S = S; window.log = { clicks: 0, dbl: 0, dance: 0, giggle: 0 };
  document.addEventListener("click", () => { window.log.clicks += 1; }, true);   // stands in for the studio's click handler
  document.getElementById("stage").addEventListener("dblclick", () => { window.log.dbl += 1; });
  const wrap = document.getElementById("theodore-avatar-wrap");
  window.h = S.attachSalaInteractions(wrap, { onDance: () => { window.log.dance += 1; }, onGiggle: () => { window.log.giggle += 1; }, isMicListening: () => true });
  S.attachTouchDoubleTap(document.getElementById("stage"));
  window.ready = true;
</script></body>`;

let failed = 0;
const check = (name, ok, detail = "") => { console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`); if (!ok) failed += 1; };

const browser = await chromium.launch();
async function fresh(reducedMotion = false) {
  const ctx = await browser.newContext({ viewport: { width: 900, height: 700 }, hasTouch: true, reducedMotion: reducedMotion ? "reduce" : "no-preference" });
  const page = await ctx.newPage();
  await page.route("http://sala.test/**", (route) => {
    const url = route.request().url();
    if (url.endsWith("sala_interactions.js")) return route.fulfill({ contentType: "text/javascript", body: MODULE });
    return route.fulfill({ contentType: "text/html", body: HTML });
  });
  await page.goto("http://sala.test/");
  await page.waitForFunction(() => window.ready === true);
  return { ctx, page };
}
const dancing = (page) => page.evaluate(() => window.h.isDancing());
const box = async (page, sel) => (await page.locator(sel).boundingBox());

// 1. mouse scrub over the avatar body
{
  const { ctx, page } = await fresh();
  const b = await box(page, "#theodore-avatar");
  const y = b.y + b.height / 2;
  await page.mouse.move(b.x + 5, y);
  for (let k = 0; k < 4; k += 1) { await page.mouse.move(b.x + (k % 2 ? 8 : b.width - 8), y, { steps: 6 }); }
  check("mouse scrub makes Sala dance", await dancing(page));
  check("dance class applied", await page.locator("#theodore-avatar-wrap.sala-dancing").count() === 1);
  // a tap while dancing stops it and is not passed on to the studio's click handler
  const clicksBefore = await page.evaluate(() => window.log.clicks);
  await page.mouse.click(b.x + 50, y);
  check("tap stops the dance", !(await dancing(page)));
  check("that tap is not also a giggle/mute click", (await page.evaluate(() => window.log.clicks)) === clicksBefore);
  await ctx.close();
}
// 2. slow movement, small jitter, plain tap
{
  const { ctx, page } = await fresh();
  const b = await box(page, "#theodore-avatar");
  const y = b.y + b.height / 2;
  await page.mouse.move(b.x + 5, y);
  for (let k = 0; k < 4; k += 1) { await page.mouse.move(b.x + (k % 2 ? 8 : b.width - 8), y, { steps: 6 }); await page.waitForTimeout(900); }
  check("the same scrub done slowly does not dance", !(await dancing(page)));
  await page.mouse.move(b.x + 90, y);
  for (let k = 0; k < 8; k += 1) await page.mouse.move(b.x + (k % 2 ? 80 : 100), y, { steps: 2 });
  check("small jitter does not dance", !(await dancing(page)));
  await page.mouse.click(b.x + 60, y);
  check("a plain tap does not dance", !(await dancing(page)));
  await ctx.close();
}
// 3. dragging the widget handle must not dance
{
  const { ctx, page } = await fresh();
  const hb = await box(page, ".avatar-handle");
  const y = hb.y + hb.height / 2;
  await page.mouse.move(hb.x + 5, y);
  for (let k = 0; k < 6; k += 1) await page.mouse.move(hb.x + (k % 2 ? 8 : hb.width - 8), y, { steps: 6 });
  check("scrubbing the drag handle does not dance", !(await dancing(page)));
  await ctx.close();
}
// 4. touch scrub (pointer events, finger down) and the click after it is swallowed
{
  const { ctx, page } = await fresh();
  const b = await box(page, "#theodore-avatar");
  const y = b.y + b.height / 2;
  const fire = (type, x, buttons) => page.evaluate(([t, px, py, bt]) => {
    const el = document.getElementById("theodore-avatar");
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, pointerType: "touch", pointerId: 7, isPrimary: true, clientX: px, clientY: py, buttons: bt }));
  }, [type, x, y, buttons]);
  await fire("pointerdown", b.x + 5, 1);
  for (let k = 0; k < 5; k += 1) { for (let s = 0; s <= 5; s += 1) { const x = k % 2 ? b.x + b.width - 8 - ((b.width - 16) * s) / 5 : b.x + 8 + ((b.width - 16) * s) / 5; await fire("pointermove", x, 1); } }
  check("finger scrub makes Sala dance", await dancing(page));
  await fire("pointerup", b.x + 10, 0);
  const before = await page.evaluate(() => window.log.clicks);
  await page.evaluate(() => document.getElementById("theodore-avatar").dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true })));
  check("the click that ends a finger scrub is swallowed", (await page.evaluate(() => window.log.clicks)) === before);
  await ctx.close();
}
// 5. reduced motion: a gentle bob, no sparkles
{
  const { ctx, page } = await fresh(true);
  await page.evaluate(() => window.h.dance("api"));
  check("reduced motion uses the calm bob", await page.locator("#theodore-avatar-wrap.sala-dancing-calm").count() === 1);
  check("reduced motion draws no sparkles", await page.locator(".sala-spark").count() === 0);
  await ctx.close();
}
// 6. voice request, consumed during cooldown too
{
  const { ctx, page } = await fresh();
  const r1 = await page.evaluate(() => window.h.handleUtterance("can you dance for me", "en"));
  check("voice: 'can you dance for me' dances", r1 === true && (await dancing(page)));
  await page.evaluate(() => window.h.stopDance());
  const r2 = await page.evaluate(() => window.h.handleUtterance("dance", "en"));
  check("voice during cooldown is consumed but does not restart", r2 === true && !(await dancing(page)));
  const r3 = await page.evaluate(() => window.h.handleUtterance("what is the history of dance", "en"));
  check("a question about dance is left for Q&A", r3 === false);
  await ctx.close();
}
// 7. giggle on any page mode
{
  const { ctx, page } = await fresh();
  await page.evaluate(() => window.h.giggle());
  check("giggle animates without the demo-only CSS", await page.locator("#theodore-avatar-wrap.sala-giggling").count() === 1);
  await ctx.close();
}
// 8. touch double-tap fires dblclick where the browser would not (synthetic pointer events do not generate a native dblclick)
{
  const { ctx, page } = await fresh();
  const tap = () => page.evaluate(() => {
    const el = document.getElementById("stage");
    const r = el.getBoundingClientRect(); const cx = r.x + 100; const cy = r.y + 100;
    const o = { bubbles: true, pointerType: "touch", pointerId: 3, isPrimary: true, clientX: cx, clientY: cy };
    el.dispatchEvent(new PointerEvent("pointerdown", { ...o, buttons: 1 }));
    el.dispatchEvent(new PointerEvent("pointerup", { ...o, buttons: 0 }));
    el.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: cx, clientY: cy }));
  });
  await tap(); await page.waitForTimeout(120); await tap(); await page.waitForTimeout(250);
  check("touch double-tap fires one dblclick", (await page.evaluate(() => window.log.dbl)) === 1);
  await page.waitForTimeout(600);
  await tap(); await page.waitForTimeout(700); await tap(); await page.waitForTimeout(250);
  check("two slow taps are not a double-tap", (await page.evaluate(() => window.log.dbl)) === 1);
  await ctx.close();
}
await browser.close();
console.log(failed ? `\n${failed} FAILED` : "\nall passed");
process.exit(failed ? 1 : 0);
