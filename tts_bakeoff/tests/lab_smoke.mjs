// Playwright smoke test for the listening lab (Chromium and WebKit). Run from the repo root:
//   node tts_bakeoff/tests/lab_smoke.mjs [screenshot-dir]
// Starts `python3 -m tts_bakeoff.lab --demo`, loads the page, plays a clip, toggles blind mode, rates and exports.
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync } from "node:fs";
import assert from "node:assert/strict";
import path from "node:path";

const require = createRequire(path.join(process.cwd(), "apps/web/"));
const { chromium, webkit } = require("playwright");
const shots = process.argv[2] || "/tmp/lab-shots";
mkdirSync(shots, { recursive: true });
const PY = process.env.LAB_PYTHON || "python3";

function startServer() {
  return new Promise((resolve, reject) => {
    const proc = spawn(PY, ["-u", "-m", "tts_bakeoff.lab", "--demo", "--no-open", "--port", "0"], { cwd: process.cwd() });
    let buf = "";
    const timer = setTimeout(() => reject(new Error("server did not start: " + buf)), 30000);
    proc.stdout.on("data", (d) => {
      buf += d;
      const m = buf.match(/http:\/\/127\.0\.0\.1:(\d+)\//);
      const dm = buf.match(/demo run written to (\S+)/);
      if (m && dm) { clearTimeout(timer); resolve({ proc, url: m[0], demoDir: dm[1] }); }
    });
    proc.stderr.on("data", (d) => { buf += d; });
    proc.on("exit", (c) => reject(new Error("server exited " + c + ": " + buf)));
  });
}

async function run(engine, name, url, demoDir) {
  const browser = await engine.launch(name === "chromium" ? { args: ["--autoplay-policy=no-user-gesture-required"] } : {});
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
  const page = await ctx.newPage();
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push("console: " + m.text()); });
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("requestfailed", (r) => { if (!/favicon/.test(r.url())) problems.push("requestfailed: " + r.url()); });
  page.on("response", (r) => { if (r.status() >= 400 && !/favicon/.test(r.url())) problems.push(`http ${r.status()}: ${r.url()}`); });

  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector(".cell:not(.empty)");
  const counts = await page.evaluate(() => window.__lab.counts());
  assert.equal(counts.voices, 3, "three demo voices");
  assert.ok(counts.cells >= 3 && counts.rows >= 1, "grid rendered: " + JSON.stringify(counts));
  assert.ok(await page.locator("#banner-demo").isVisible(), "demo banner visible");
  const langs = await page.$$eval("#f-lang option", (o) => o.map((x) => x.value));
  assert.ok(langs.includes("en") && langs.includes("km"), "languages: " + langs);
  const badges = await page.$$eval(".cell .badge", (b) => b.map((x) => x.textContent));
  assert.ok(badges.includes("NOT SHIPPABLE"), "reference voice is marked NOT SHIPPABLE: " + badges);
  assert.ok((await page.locator(".cell .chip").count()) > 0, "score chips shown");
  await page.screenshot({ path: `${shots}/grid-${name}.png`, fullPage: false });

  // play the first clip: the shared player must start and time must advance
  await page.evaluate(() => { window.__played = false; window.__lab.player.addEventListener("playing", () => { window.__played = true; }); });
  await page.locator(".cell:not(.empty) .play").first().click();
  await page.waitForFunction(() => window.__played || window.__lab.player.currentTime > 0.05, null, { timeout: 8000 });
  const t0 = await page.evaluate(() => window.__lab.player.currentTime);
  await page.waitForTimeout(400);
  const t1 = await page.evaluate(() => window.__lab.player.currentTime);
  assert.ok(t1 > t0 || t1 > 0, `currentTime advances (${t0} -> ${t1})`);
  await page.evaluate(() => window.__lab.stopAll());

  // rate with the keyboard on the selected cell: 5 = naturalness, Alt+4 = clarity
  await page.locator(".cell:not(.empty)").first().focus();
  await page.keyboard.press("5");
  await page.keyboard.press("Alt+Digit4");
  await page.waitForFunction(() => document.querySelector(".cell .rate button[aria-label='naturalness 5'][aria-pressed='true']"));
  await page.waitForFunction(() => document.querySelector(".cell .rate button[aria-label='clarity 4'][aria-pressed='true']"));

  // blind mode: names disappear, labels stay
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("b");
  await page.waitForFunction(() => document.querySelector("#t-blind").checked);
  assert.equal(await page.locator(".cell .vname").count(), 0, "no voice names in blind mode");
  assert.equal(await page.locator(".cell .badge").count(), 0, "no license badges in blind mode");
  assert.ok((await page.locator(".cell .lbl").count()) >= 3, "A/B/C labels shown");
  await page.screenshot({ path: `${shots}/blind-${name}.png`, fullPage: false });

  // the rating survives the re-render and exports in the panel format with an embedded key
  await page.fill("#t-rater", "smoke");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#x-json")]);
  const data = JSON.parse(readFileSync(await dl.path(), "utf8"));
  assert.match(data.panel, /^lab-[a-z]+-7$/);
  assert.equal(data.rater, "smoke");
  assert.ok(data.ratings.length >= 1 && data.ratings[0].naturalness === 5 && data.ratings[0].clarity === 4, JSON.stringify(data.ratings));
  assert.ok(Object.keys(data.key).length >= 1, "embedded key");
  assert.ok(Object.values(data.key).every((v) => ["voxcpm2", "cosyvoice2", "fish_speech15"].includes(v)));

  // the summary must not leak voice names while blind; the reveal button turns blind mode off
  await page.click("#tab-summary");
  await page.waitForSelector("#reveal");
  assert.equal(await page.locator("#summary table.sum").count(), 0, "no per-voice table while blind");
  await page.click("#reveal");
  await page.waitForSelector("#summary table.sum");
  assert.equal(await page.locator("#t-blind").isChecked(), false, "revealed");
  assert.ok(await page.locator("#summary .verdict").count() >= 1, "verdict template");
  await page.screenshot({ path: `${shots}/summary-${name}.png` });
  await page.click("#tab-samples");
  assert.ok((await page.locator("#samples button").count()) >= 3, "sample buttons");
  await page.click("#tab-grid");

  // add other voices by file: one is inferable from its name, one needs the label form
  await page.setInputFiles("#add-files", [
    { name: "edge-tts_en_S01.wav", mimeType: "audio/wav", buffer: readFileSync(path.join(demoDir, "voxcpm2/en/S01.wav")) },
    { name: "clip1.wav", mimeType: "audio/wav", buffer: readFileSync(path.join(demoDir, "voxcpm2/en/M01.wav")) },
  ]);
  await page.waitForSelector("#label-dlg:not([hidden])");
  await page.screenshot({ path: `${shots}/label-${name}.png` });
  await page.fill("#label-rows input[data-f=model]", "production-voice");
  await page.selectOption("#label-rows select", "en");
  await page.fill("#label-rows input[data-f=sid]", "m01");
  await page.click("#label-apply");
  await page.selectOption("#f-lang", "en");
  await page.waitForFunction(() => window.__lab.counts().voices === 5);
  await page.waitForFunction(() => document.querySelectorAll(".cell .badge.b-unk").length >= 2, null, { timeout: 8000 });
  const badgesNow = await page.$$eval(".cell .badge", (b) => b.map((x) => x.textContent));
  const unknown = badgesNow.filter((t) => t === "UNKNOWN LICENSE").length;
  assert.ok(unknown >= 2, "dropped voices are marked UNKNOWN LICENSE, never assumed shippable: " + JSON.stringify(badgesNow));
  await page.screenshot({ path: `${shots}/added-${name}.png` });

  assert.deepEqual(problems, [], "no console errors or failed requests");
  await browser.close();
  console.log(`${name}: ok (${JSON.stringify(counts)})`);
}

const { proc, url, demoDir } = await startServer();
let failed = 0;
for (const [name, engine] of [["chromium", chromium], ["webkit", webkit]]) {
  try { await run(engine, name, url, demoDir); } catch (e) { failed++; console.error(`${name}: FAILED: ${e.message}`); }
}
proc.kill();
process.exit(failed ? 1 : 0);
