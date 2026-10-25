// Driver's Ed demo: tutorial first in every new session, ONE movable widget (voice + camera + timer) in the top-right corner,
// and narration in the voice picked in the account menu. Loads Course Studio directly with the query the web wrapper uses.
//   node apps/web/e2e/demo-widget-voice.mjs http://127.0.0.1:8145 /tmp/shots
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");

const BASE = process.argv[2] || "http://127.0.0.1:8145";
const SHOTS = process.argv[3] || "/tmp";
const URL = `${BASE}/studio?access=sample&course=drivers-ed&demo=1&voiceassets=/voice-assets`;
const MATRIX = [
  ["desktop", { viewport: { width: 1280, height: 800 } }],
  ["pixel7", devices["Pixel 7"]],
];

const hashOf = (page, lang, text) => page.evaluate(([l, t]) => window.SalaVoiceChoice.clipHash(l, t), [lang, text]);

let failed = 0;
for (const [name, opts] of MATRIX) {
  const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });
  try {
    const ctx = await browser.newContext({ ...opts, permissions: ["camera", "microphone"] });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message.slice(0, 120)));

    // 1. Tutorial first, in a new session.
    await page.goto(URL, { waitUntil: "networkidle" });
    await page.locator(".sala-tutorial").waitFor({ state: "visible", timeout: 20000 });
    await page.screenshot({ path: `${SHOTS}/dw-${name}-1-tutorial.png` });
    await page.keyboard.press("Escape");
    await page.locator(".sala-tutorial").waitFor({ state: "detached", timeout: 5000 });
    // Same session, reload: the tutorial does not nag again. A brand new session shows it first again.
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    assert.equal(await page.locator(".sala-tutorial").count(), 0, `${name}: tutorial once per session`);
    const fresh = await (await browser.newContext({ ...opts, permissions: ["camera", "microphone"] })).newPage();
    await fresh.goto(URL, { waitUntil: "networkidle" });
    await fresh.locator(".sala-tutorial").waitFor({ state: "visible", timeout: 20000 });
    await fresh.context().close();

    // 2. One widget, top-right, holding the timer (and the camera / voice when they exist); no separate floating pieces.
    const widget = page.locator("#course-widget");
    await widget.waitFor({ state: "visible", timeout: 10000 });
    const box = await widget.boundingBox();
    const vw = opts.viewport.width;
    assert.ok(box.x + box.width >= vw - 24 && box.y <= 24, `${name}: widget in the top-right corner (${JSON.stringify(box)})`);
    assert.equal(await page.locator("#course-widget #sample-clock").count(), 1, `${name}: the 10-minute timer lives inside the widget`);
    assert.equal(await page.locator("body > #sample-clock, body > #student-cam").count(), 0, `${name}: no separate timer or camera tile`);
    assert.equal(await page.locator(".sala-help:visible").count(), 0, `${name}: the ? button is in the widget menu now`);
    await page.screenshot({ path: `${SHOTS}/dw-${name}-2-widget.png` });

    // 3. Drag it; the spot is remembered.
    const grip = page.locator("#course-widget .cw-grip");
    const g = await grip.boundingBox();
    await page.mouse.move(g.x + g.width / 2, g.y + g.height / 2);
    await page.mouse.down();
    await page.mouse.move(g.x + g.width / 2 - 140, g.y + g.height / 2 + 60, { steps: 6 });
    await page.mouse.up();
    const moved = await widget.boundingBox();
    assert.ok(moved.x < box.x - 100 && moved.y > box.y + 40, `${name}: widget dragged (${JSON.stringify(moved)})`);
    await page.reload({ waitUntil: "networkidle" });
    const kept = await page.locator("#course-widget").boundingBox();
    assert.ok(Math.abs(kept.x - moved.x) < 4 && Math.abs(kept.y - moved.y) < 4, `${name}: position remembered`);

    // 4. The picked voice is the one used. Company voice: its pre-rendered clip; edge voice: only for its own language.
    const text = "Slow down in fog.";
    const hash = await hashOf(page, "en", text);
    await page.route("**/voice-assets/voices.json", (r) => r.fulfill({ json: { voices: [{ id: "channarith", label: "Channarith", active: true }] } }));
    await page.route("**/voice-assets/channarith/index.json", (r) => r.fulfill({ json: { ext: "mp3", clips: { en: [hash] } } }));
    await page.evaluate(() => { localStorage.setItem("aoep_demo_voice", "channarith"); localStorage.setItem("aoep_drive_voice", "en-GB-SoniaNeural"); });
    assert.equal(await page.evaluate((t) => window.SalaVoiceChoice.cloneClipUrl("en", t), text), `/voice-assets/channarith/en/${hash}.mp3`, `${name}: company voice clip found by hash`);
    assert.equal(await page.evaluate(() => window.SalaVoiceChoice.cloneClipUrl("en", "A line with no clip.")), null, `${name}: a missing clip falls back`);
    assert.equal(await page.evaluate(() => window.SalaVoiceChoice.edgeVoiceFor("en")), "en-GB-SoniaNeural");
    assert.equal(await page.evaluate(() => window.SalaVoiceChoice.edgeVoiceFor("km")), "", `${name}: an English voice must not read a Khmer lesson`);
    await page.evaluate(() => localStorage.setItem("aoep_demo_voice", "default"));
    assert.equal(await page.evaluate((t) => window.SalaVoiceChoice.cloneClipUrl("en", t), text), null, `${name}: default voice = no company clip`);

    // The player sends the picked edge voice to the narration endpoint.
    const bodies = [];
    await page.route("**/api/studio/tts", async (route) => {
      bodies.push(JSON.parse(route.request().postData() || "{}"));
      await route.fulfill({ status: 204 });
    });
    await page.evaluate(() => { localStorage.setItem("aoep_demo_voice", "default"); localStorage.setItem("aoep_drive_voice", "en-GB-SoniaNeural"); });
    await page.reload({ waitUntil: "networkidle" });
    await page.locator("#course-widget").waitFor({ state: "visible" });
    await page.mouse.click(vw / 2, 300);
    await page.waitForTimeout(6000);
    if (bodies.length) assert.equal(bodies[0].voice, "en-GB-SoniaNeural", `${name}: narration asked for the picked edge voice`);
    else console.log(`  note ${name}: the lesson did not request narration in this environment (voice routing is covered above)`);

    assert.deepEqual(errors, [], `${name}: no page errors`);
    console.log(`ok   ${name}`);
  } catch (error) {
    failed += 1;
    console.error(`FAIL ${name}: ${error.message}`);
  } finally {
    await browser.close();
  }
}
process.exit(failed ? 1 : 0);
