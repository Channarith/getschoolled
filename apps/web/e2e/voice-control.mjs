// Voice control for every voice: a stub SpeechRecognition (and the native-app hook) drives the studio course page.
// Checks pace (0.75-2x, persisted), commands, grounded questions, flexibility prompts and the ask cap. No real mic or LLM is used.
//   node apps/web/e2e/voice-control.mjs http://127.0.0.1:8146 /tmp/shots
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://127.0.0.1:8146";
const SHOTS = process.argv[3] || "/tmp";
const PAGES = [
  ["drivers-ed demo", `${BASE}/studio?access=sample&course=drivers-ed&demo=1&voiceassets=/voice-assets`],
  ["studio course", `${BASE}/studio?access=sample&course=drivers-ed&voiceassets=/voice-assets`],
];

for (const [name, url] of PAGES) {
  const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });
  try {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, permissions: ["camera", "microphone"] });
    await ctx.addInitScript(() => {
      window.__recs = [];
      class FakeRec {
        constructor() { this.continuous = false; window.__recs.push(this); }
        start() {} stop() { if (this.onend) this.onend(); } abort() {}
      }
      window.SpeechRecognition = FakeRec;
      window.webkitSpeechRecognition = FakeRec;
      window.__hear = (text) => {
        const rec = window.__recs[window.__recs.length - 1];
        if (!rec || !rec.onresult) return false;
        rec.onresult({ resultIndex: 0, results: [[{ transcript: text }]] });
        return true;
      };
    });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message.slice(0, 120)));
    const asked = [];
    page.on("console", (m) => { if (m.type() === "error") console.log("  console", m.text().slice(0, 150)); });
    await page.route("**/api/studio/teach/voice/respond", async (route) => {
      asked.push(JSON.parse(route.request().postData() || "{}"));
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ voice: { message: "A stubbed grounded answer." }, tts: null }) });
    });
    await page.goto(url, { waitUntil: "networkidle" });
    await page.keyboard.press("Escape").catch(() => {});
    await page.waitForTimeout(500);

    const consent = page.locator(".sala-consent-accept");
    if (await consent.count()) {
      const card = await page.locator(".sala-consent").innerText();
      assert.match(card, /never recorded or stored/i, `${name}: consent card says audio is not stored`);
      await consent.evaluate((el) => el.click());
    }
    await page.waitForFunction(() => window.__recs && window.__recs.length > 0, null, { timeout: 5000 });
    const pill = page.locator(".sala-pill");
    if (await pill.count()) assert.match(await pill.innerText(), /listening|Starting/i, `${name}: privacy indicator visible while the mic is on`);

    const hear = (text) => page.evaluate((t) => window.__hear(t), text);
    const pace = () => page.evaluate(() => Number(localStorage.getItem("aoep_voice_pace") || 0));

    // Pace: step, absolute, clamped at both ends, persisted.
    await hear("too fast");
    assert.equal(await pace(), 0.85, `${name}: "too fast" slows by one step`);
    await hear("speed 2");
    assert.equal(await pace(), 2, `${name}: "speed 2" = 2x`);
    await hear("speed 3");
    assert.equal(await pace(), 2, `${name}: capped at 2x`);
    await hear("speed 0.5");
    assert.equal(await pace(), 0.75, `${name}: floored at 0.75x`);
    await hear("normal speed");
    assert.equal(await pace(), 1);

    // Questions reach the grounded endpoint through the page's normal ask path, in every mode.
    await page.evaluate(() => (document.getElementById("btn-start-voice") || document.getElementById("btn-teach"))?.click());
    await page.waitForTimeout(6000);
    await hear("why does a yield sign matter?");
    await page.waitForTimeout(800);
    assert.ok(asked.length >= 1, `${name}: a spoken question reached the Q&A (${asked.length})`);

    // Flexibility intents become a ready-made prompt.
    await hear("explain that more simply");
    await page.waitForTimeout(800);
    assert.ok(asked.some((a) => /simpler words/i.test(JSON.stringify(a))), `${name}: "simpler" sent the simplify prompt`);

    // Native-app hook feeds the same router.
    const before = await pace();
    const handled = await page.evaluate(() => window.__salaNativeSpeech && window.__salaNativeSpeech.onTranscript("too slow"));
    assert.equal(handled, true, `${name}: native hook accepted the transcript`);
    assert.ok((await pace()) > before, `${name}: native transcript changed the pace`);

    // Cap: 6 questions a minute.
    for (let i = 0; i < 8; i++) await hear(`what is rule number ${i + 1}?`);
    await page.waitForTimeout(800);
    assert.ok(asked.length <= 6, `${name}: ask cap holds (${asked.length} calls)`);

    await page.reload({ waitUntil: "networkidle" });
    assert.equal(await pace(), 1.15, `${name}: pace survives reload (1 + one "too slow" step)`);
    await page.screenshot({ path: `${SHOTS}/vc-${name.replace(/\W+/g, "-")}.png` });
    assert.deepEqual(errors, [], `${name}: no page errors`);
    console.log(`PASS ${name}`);
  } catch (e) {
    console.error(`FAIL ${name}:`, e.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}
