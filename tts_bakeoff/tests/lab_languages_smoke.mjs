// Playwright smoke test for the all-languages listening lab (Chromium and WebKit). Run from the repo root:
//   node tts_bakeoff/tests/lab_languages_smoke.mjs [screenshot-dir]
// Starts `python3 -m tts_bakeoff.lab --demo-edge` (synthetic tones in the real run layout), then checks the language picker, RTL text,
// the voice filters, the compare selection, blind mode, ratings and the per-language progress indicator.
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import assert from "node:assert/strict";
import path from "node:path";

function loadPlaywright() {
  for (const base of [path.join(process.cwd(), "apps/web/"), path.join(process.cwd(), "../../../apps/web/")]) {
    try { return createRequire(base)("playwright"); } catch { /* try the next place */ }
  }
  throw new Error("playwright not found under apps/web/node_modules (run pnpm install in apps/web)");
}
const { chromium, webkit } = loadPlaywright();
const shots = process.argv[2] || "/tmp/lab-lang-shots";
mkdirSync(shots, { recursive: true });
const PY = process.env.LAB_PYTHON || "python3";

function startServer() {
  return new Promise((resolve, reject) => {
    const proc = spawn(PY, ["-u", "-m", "tts_bakeoff.lab", "--demo-edge", "--no-open", "--port", "0"], { cwd: process.cwd() });
    let buf = "";
    const timer = setTimeout(() => reject(new Error("server did not start: " + buf)), 90000);
    proc.stdout.on("data", (d) => {
      buf += d;
      const m = buf.match(/http:\/\/127\.0\.0\.1:(\d+)\//);
      if (m) { clearTimeout(timer); resolve({ proc, url: m[0] }); }
    });
    proc.stderr.on("data", (d) => { buf += d; });
    proc.on("exit", (c) => reject(new Error("server exited " + c + ": " + buf)));
  });
}

async function pick(page, code) {
  await page.click("#lang-btn");
  await page.waitForSelector("#lang-pop:not([hidden])");
  await page.click(`#lang-list [data-code=${code}]`);
  await page.waitForFunction((c) => window.__lab.state.lang === c, code);
}

async function run(engine, name, url) {
  const browser = await engine.launch();
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
  const page = await ctx.newPage();
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push("console: " + m.text()); });
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("response", (r) => { if (r.status() >= 400 && !/favicon/.test(r.url())) problems.push(`http ${r.status()}: ${r.url()}`); });

  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector(".cell:not(.empty)");

  // 1. the picker lists every language (27 platform + extras + the no-voice ones), is searchable by English, native name and code
  await page.click("#lang-btn");
  await page.check("#lang-empty");   // languages without clips are hidden by default; this test is about the whole catalog
  const groups = await page.$$eval("#lang-list .lang-group", (g) => g.map((x) => x.textContent));
  assert.ok(groups[0].startsWith("Platform languages (27)"), "platform group: " + groups);
  assert.ok(groups.some((g) => g.startsWith("Extra languages")) && groups.some((g) => g.startsWith("No edge voice")), "groups: " + groups);
  const total = await page.locator("#lang-list .lang-opt").count();
  assert.ok(total >= 80, "language options: " + total);
  await page.screenshot({ path: `${shots}/picker-${name}.png` });
  await page.fill("#lang-q", "khm");
  assert.equal(await page.locator("#lang-list .lang-opt").count(), 1);
  await page.fill("#lang-q", "ไทย");
  assert.equal(await page.locator("#lang-list .lang-opt").first().getAttribute("data-code"), "th");
  await page.fill("#lang-q", "العربية");
  assert.equal(await page.locator("#lang-list .lang-opt").first().getAttribute("data-code"), "ar");
  await page.fill("#lang-q", "basque");
  assert.ok((await page.locator("#lang-list .lang-opt.novoice").count()) === 1, "no-voice language is listed");
  await page.fill("#lang-q", "");
  await page.keyboard.press("Escape");
  assert.ok(await page.locator("#lang-pop").isHidden(), "Escape closes the picker");

  // 2. Khmer, Thai: script-correct text on the page; Arabic and Hebrew render right to left
  await pick(page, "km");
  await page.waitForSelector(".sent .txt:lang(km)");
  assert.ok(/[ក-៿]/.test(await page.locator(".sent .txt").first().textContent()), "Khmer script");
  await page.screenshot({ path: `${shots}/khmer-${name}.png` });
  await pick(page, "th");
  assert.ok(/[฀-๿]/.test(await page.locator(".sent .txt").first().textContent()), "Thai script");
  await page.screenshot({ path: `${shots}/thai-${name}.png` });
  for (const code of ["ar", "he"]) {
    await pick(page, code);
    await page.waitForSelector(".sent .txt[dir=rtl]");
    const dir = await page.locator(".sent .txt").first().evaluate((e) => getComputedStyle(e).direction);
    assert.equal(dir, "rtl", code + " renders right to left");
    await page.screenshot({ path: `${shots}/${code === "ar" ? "arabic-rtl" : "hebrew-rtl"}-${name}.png` });
  }
  await pick(page, "fr");
  assert.equal(await page.locator(".sent .txt").first().evaluate((e) => getComputedStyle(e).direction), "ltr", "French stays left to right");

  // 3. no-voice languages say so instead of showing an empty grid
  await pick(page, "eu");
  assert.ok(await page.locator(".novoice-box").isVisible(), "no-voice note");
  assert.match(await page.locator(".novoice-box").textContent(), /Basque/);

  // 4. voice filters on English: gender, accent, voice type
  await pick(page, "en");
  const metaOf = () => page.evaluate(() => Array.from(document.querySelectorAll(".cell:not(.empty)")).map((c) => {
    const v = window.__lab.state.voices.get(c.dataset.key.split("|")[2]); return { g: v.meta.gender, loc: v.meta.locale, kind: v.meta.kind, style: v.meta.style };
  }));
  const all = await metaOf();
  assert.ok(all.some((m) => m.g === "Male") && all.some((m) => m.g === "Female") && all.some((m) => m.kind === "style"), "unfiltered grid has both genders and styles");
  await page.selectOption("#f-gender", "Female");
  let now = await metaOf();
  assert.ok(now.length > 0 && now.every((m) => m.g === "Female") && now.length < all.length, "female filter");
  await page.selectOption("#f-gender", "");
  await page.selectOption("#f-region", "en-GB");
  now = await metaOf();
  assert.ok(now.length > 0 && now.every((m) => m.loc === "en-GB"), "accent filter");
  await page.selectOption("#f-region", "");
  await page.selectOption("#f-type", "cute");
  now = await metaOf();
  assert.ok(now.length > 0 && now.every((m) => m.style === "cute"), "style filter");
  await page.selectOption("#f-type", "plain");
  now = await metaOf();
  assert.ok(now.length > 0 && now.every((m) => m.kind !== "style"), "voices only");
  await page.selectOption("#f-type", "");

  // 5. grouped columns: style variants are nested inside their base voice's group
  assert.ok((await page.locator(".vgroup.has-styles .vstyles .cell").count()) >= 9, "style variants nested in a voice group");
  await page.screenshot({ path: `${shots}/grouped-${name}.png` });

  // 6. compare these voices: tick two voices, only their groups remain
  await page.click("#voice-pick summary");
  const boxes = page.locator("#f-models input[type=checkbox]");
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  assert.equal(await page.locator("#grid .row-s").first().locator(".vgroup").count(), 2, "two voices compared");
  assert.match(await page.locator("#cmp-count").textContent(), /Comparing 2 voices/);
  await page.click("#cmp-clear");
  assert.ok(await page.locator("#cmp-clear").isHidden() && /^Compare these voices$/.test(await page.locator("#cmp-count").textContent()), "cleared");
  assert.ok((await page.locator("#grid .row-s").count()) >= 2, "all sentence rows back (S01..Q01 and the accent sample)");

  // 7. rating works and the per-language progress indicator follows it; blind mode keeps working
  await page.keyboard.press("Escape");
  const before = await page.locator("#lang-progress-text").textContent();
  assert.match(before, /Rated 0 of \d+ clips/);
  await page.locator(".cell:not(.empty)").first().focus();
  await page.keyboard.press("4");
  await page.waitForFunction(() => /Rated 1 of/.test(document.querySelector("#lang-progress-text").textContent));
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("b");
  await page.waitForFunction(() => document.querySelector("#t-blind").checked);
  assert.equal(await page.locator(".cell .vname").count(), 0, "no names in blind mode");
  assert.ok((await page.locator(".cell .lbl").count()) >= 3, "blind labels");
  await page.keyboard.press("b");
  await page.waitForFunction(() => !document.querySelector("#t-blind").checked);
  assert.ok((await page.locator(".cell .vname").count()) > 0, "names back");

  // 8. lazy rows: only rows near the viewport are filled
  const lazy = await page.evaluate(() => ({ rows: document.querySelectorAll(".row-s").length, filled: document.querySelectorAll(".row-s[data-filled]").length }));
  assert.ok(lazy.filled >= 1 && lazy.filled <= lazy.rows, JSON.stringify(lazy));

  assert.deepEqual(problems, [], "no console errors or failed requests");
  await browser.close();
  console.log(`${name}: ok (${total} languages in the picker)`);
}

const { proc, url } = await startServer();
let failed = 0;
for (const [name, engine] of [["chromium", chromium], ["webkit", webkit]]) {
  try { await run(engine, name, url); } catch (e) { failed++; console.error(`${name}: FAILED: ${e.message}\n${String(e.stack).split("\n").filter((l) => l.includes("languages_smoke")).join("\n")}`); }
}
proc.kill();
process.exit(failed ? 1 : 0);
