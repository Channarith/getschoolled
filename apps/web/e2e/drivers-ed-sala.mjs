// The Driver's Ed demo's Sala is THE avatar of the shared module (data-sala-avatar): tap -> giggle, a quick scrub across her -> the dance
// easter egg, a spoken "dance" request, and a real double-tap on touch screens still toggles the lesson's full screen.
//   node apps/web/e2e/drivers-ed-sala.mjs http://127.0.0.1:8791
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");
const STUDIO = process.argv[2] || "http://127.0.0.1:8791";
const URL = `${STUDIO}/studio?access=sample&course=drivers-ed&demo=1&lang=en&e2e=1`;
const SKIP = `try { sessionStorage.setItem('sala_demo_tutorial_seen_v4','1'); localStorage.setItem('salareen_camera_pref_v1','no'); } catch (e) {}`;
let failed = 0;
const check = (name, ok, detail = "") => { console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`); if (!ok) failed += 1; };

const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });

// ---- mouse: giggle on tap, dance on scrub --------------------------------------------------------------------------------------
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, permissions: ["camera", "microphone"] });
  await ctx.addInitScript(SKIP);
  const page = await ctx.newPage();
  await page.goto(URL, { waitUntil: "domcontentloaded" });
  const sala = page.locator("[data-sala-avatar]");
  await sala.first().waitFor({ state: "visible", timeout: 15000 });
  check("exactly one avatar element carries data-sala-avatar", (await sala.count()) === 1, `count ${await sala.count()}`);
  check("it is the clickable mascot", (await sala.first().getAttribute("data-testid")) === "sala-mascot");
  await page.waitForTimeout(2500);
  await sala.first().click();
  await page.waitForFunction(() => document.querySelector("[data-sala-avatar]")?.classList.contains("sala-giggling"), null, { timeout: 2000 }).then(() => check("tap -> giggle", true)).catch(() => check("tap -> giggle", false));
  await page.waitForTimeout(900);
  const box = await sala.first().boundingBox();
  const y = box.y + box.height / 2;
  await page.mouse.move(box.x + 2, y);
  for (let i = 0; i < 7; i += 1) await page.mouse.move(box.x + (i % 2 ? 2 : box.width - 2), y, { steps: 3 });
  await page.waitForFunction(() => /sala-dancing/.test(document.querySelector("[data-sala-avatar]")?.className || ""), null, { timeout: 2500 }).then(() => check("scrub -> dance", true)).catch(() => check("scrub -> dance", false));
  await ctx.close();
}

// ---- touch: finger scrub and double-tap on the lesson ---------------------------------------------------------------------------------
{
  const ctx = await browser.newContext({ ...devices["Pixel 7"], permissions: ["camera", "microphone"] });
  await ctx.addInitScript(SKIP);
  const page = await ctx.newPage();
  await page.addInitScript(() => { window.__dbl = 0; document.addEventListener("dblclick", () => { window.__dbl += 1; }, true); });
  await page.goto(URL, { waitUntil: "domcontentloaded" });
  const sala = page.locator("[data-sala-avatar]");
  await sala.first().waitFor({ state: "visible", timeout: 15000 });
  await page.waitForTimeout(2500);
  await sala.first().tap();
  await page.waitForFunction(() => document.querySelector("[data-sala-avatar]")?.classList.contains("sala-giggling"), null, { timeout: 2000 }).then(() => check("touch: tap -> giggle", true)).catch(() => check("touch: tap -> giggle", false));
  // A real double-tap on the lesson (away from Sala and the widget) fires dblclick, which the lesson uses for full screen.
  await page.waitForTimeout(800);
  const vp = page.viewportSize();
  const x = Math.round(vp.width * 0.6), yy = Math.round(vp.height * 0.45);
  await page.touchscreen.tap(x, yy); await page.waitForTimeout(90); await page.touchscreen.tap(x, yy);
  await page.waitForTimeout(500);
  const dbl = await page.evaluate(() => window.__dbl);
  check("touch: double-tap on the lesson fires dblclick", dbl >= 1, `dblclick count ${dbl}`);
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
