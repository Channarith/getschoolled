// Account-menu Tone picker: ten tones plus the Mix group, saved choice, and disabled (with a tooltip) for a company voice, which has no
// stylized-versions consent. Needs `next dev` (or a build) running; the speech catalog and the company voice are stubbed.
//   node apps/web/e2e/voice-tone-picker.mjs http://localhost:3127
import { createRequire } from "node:module";
import fs from "node:fs";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const pw = require("playwright");
const BASE = process.argv[2] || "http://localhost:3127";
const catalog = fs.readFileSync(new URL("./fixtures/tts-voices-small.json", import.meta.url), "utf8");
const b = await pw.chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1300, height: 900 } }); const page = await ctx.newPage();
const errors = []; page.on("pageerror", (e) => errors.push(String(e).slice(0, 160)));
await page.route("**/tts/voices", (r) => r.fulfill({ status: 200, contentType: "application/json", body: catalog }));
await page.route("**/voice-assets/voices.json", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ voices: [{ id: "channarith", label: "Channarith", ai_label: "AI-generated voice of Channarith", active: true, gender: "male" }] }) }));
await page.route("**/voice-assets/channarith/index.json", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ext: "mp3", clips: { en: ["00000000000001"] } }) }));
const bodies = [];
await page.route("**/tts", async (r) => { try { bodies.push(JSON.parse(r.request().postData() || "{}")); } catch {} await r.fulfill({ status: 501, body: "" }); });
await page.goto(`${BASE}/report-bug`, { waitUntil: "domcontentloaded", timeout: 120000 });
await page.waitForTimeout(3000);
await page.getByRole("button", { name: /profile|account|menu/i }).first().click({ timeout: 8000 }).catch(async () => { await page.locator("header button").last().click(); });
await page.waitForTimeout(1500);
const tone = page.getByLabel("Voice tone");
assert.ok(await tone.isVisible()); assert.equal(await tone.isDisabled(), false);
assert.equal(await tone.locator("option").count(), 23); assert.equal(await tone.locator("optgroup[label=Mix] option").count(), 13);
await tone.selectOption("anime");
assert.equal(await page.evaluate(() => localStorage.getItem("aoep_demo_tone")), "anime");
// now choose the company voice
const sel = page.locator("select").filter({ has: page.locator("option", { hasText: "Channarith" }) }).first();
await sel.selectOption({ label: /Channarith/ }).catch(async () => { const v = await sel.locator("option", { hasText: "Channarith" }).first().getAttribute("value"); await sel.selectOption(v); });
await page.waitForTimeout(800);
assert.equal(await tone.isDisabled(), true); assert.equal(await tone.inputValue(), "neutral"); assert.match(await tone.getAttribute("title") || "", /separate signed consent/);
// back to an edge voice
await sel.selectOption("en_us_f");
await page.waitForTimeout(500);
assert.equal(await tone.isDisabled(), false); assert.equal(await tone.inputValue(), "anime");
assert.deepEqual(errors, []);
console.log("voice tone picker: ok");
await b.close();
