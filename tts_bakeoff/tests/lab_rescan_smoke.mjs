// Playwright smoke test: the lab picks up clips added while it runs (no restart), shows per-language counts, hides languages without
// clips behind a toggle, and shows the run's live progress. Run from the repo root:  node tts_bakeoff/tests/lab_rescan_smoke.mjs [screenshot-dir]
import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import assert from "node:assert/strict";
import path from "node:path";

function loadPlaywright() {
  for (const base of [path.join(process.cwd(), "apps/web/"), path.join(process.cwd(), "../../../apps/web/")]) {
    try { return createRequire(base)("playwright"); } catch { /* next */ }
  }
  throw new Error("playwright not found under apps/web/node_modules");
}
const { chromium } = loadPlaywright();
const PY = process.env.LAB_PYTHON || "python3";
const shots = process.argv[2] || "/tmp/lab-rescan-shots";
mkdirSync(shots, { recursive: true });
const run = mkdtempSync(path.join(tmpdir(), "lab-rescan-"));

const add = (lang, running) => {
  const code = `
import json, sys
from pathlib import Path
from tts_bakeoff.adapters.base import write_wav
import numpy as np
root = Path(${JSON.stringify(run)}) / "voxcpm2~wei-miao"
root.mkdir(parents=True, exist_ok=True)
(root / "meta.json").write_text(json.dumps({"model": "voxcpm2~wei-miao", "clone": True, "consented": True, "label": "Wei Miao (English) · voxcpm2"}))
for sid in ("S01", "M01"):
    wav = root / ${JSON.stringify(lang)} / (sid + ".wav")
    wav.parent.mkdir(exist_ok=True)
    write_wav(wav, 0.2 * np.sin(np.arange(16000) / 7.0), 16000)
    with (root / "manifest.jsonl").open("a") as f:
        f.write(json.dumps({"model": "voxcpm2~wei-miao", "lang": ${JSON.stringify(lang)}, "id": sid, "text": "sample " + sid, "wav": "voxcpm2~wei-miao/" + ${JSON.stringify(lang)} + "/" + sid + ".wav", "status": "ok", "duration_s": 1.0}) + "\\n")
Path(${JSON.stringify(run)}, "progress.json").write_text(json.dumps({"clips_total": 6, "clips_done": ${running ? 2 : 6}, "clips_skipped_existing": 0, "running": ${running ? "True" : "False"}, "workers": [{"worker": 0, "finished": False}]}))
`;
  const r = spawnSync(PY, ["-c", code], { cwd: process.cwd(), encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
};

add("en", true);
const server = await new Promise((resolve, reject) => {
  const proc = spawn(PY, ["-u", "-m", "tts_bakeoff.lab", "--out", run, "--no-open", "--port", "0"], { cwd: process.cwd() });
  let buf = "";
  const timer = setTimeout(() => reject(new Error("server did not start: " + buf)), 60000);
  proc.stdout.on("data", (d) => { buf += d; const m = buf.match(/http:\/\/127\.0\.0\.1:(\d+)\//); if (m) { clearTimeout(timer); resolve({ proc, url: m[0] }); } });
  proc.stderr.on("data", (d) => { buf += d; });
});
const browser = await chromium.launch();
try {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  await page.goto(server.url);
  await page.waitForFunction(() => window.__lab && window.__lab.counts().clips >= 2, null, { timeout: 20000 });
  await page.screenshot({ path: path.join(shots, "1-loaded.png") });
  // live progress line from progress.json
  await page.waitForFunction(() => !document.querySelector("#run-live").hidden, null, { timeout: 10000 });
  assert.match(await page.locator("#run-live").innerText(), /2\/6 clips/);
  // the picker lists only languages with clips, with counts; the toggle shows the rest
  await page.click("#lang-btn");
  const hidden = await page.locator(".lang-opt").count();
  assert.ok(hidden <= 2, `only languages with clips are listed by default, got ${hidden}`);
  assert.match(await page.locator(".lang-summary").innerText(), /1 of \d+ languages have clips/);
  assert.match(await page.locator(".lang-opt").first().innerText(), /1 voice · 2 clips/);
  await page.check("#lang-empty");
  assert.ok((await page.locator(".lang-opt").count()) > 20, "toggle shows languages without clips");
  assert.ok((await page.locator(".lang-opt.noclips").count()) > 20, "they are greyed out");
  assert.match(await page.locator("#lang-list").innerText(), /no clips yet/);
  await page.screenshot({ path: path.join(shots, "2-picker-all.png") });
  await page.uncheck("#lang-empty");
  await page.keyboard.press("Escape");
  // new clips appear without a restart
  add("es", false);
  await page.click("#rescan");
  await page.waitForFunction(() => window.__lab.counts().clips >= 4, null, { timeout: 15000 });
  await page.waitForFunction(() => /6\/6 clips/.test(document.querySelector("#run-live").textContent), null, { timeout: 10000 });
  await page.click("#lang-btn");
  assert.match(await page.locator(".lang-summary").innerText(), /2 of \d+ languages have clips/);
  assert.ok((await page.locator("#lang-opt-es").count()) === 1, "Spanish now listed");
  await page.screenshot({ path: path.join(shots, "3-after-rescan.png") });
  await page.click("#rescan");
  await page.waitForFunction(() => /No new clips/.test(document.querySelector("#status").textContent), null, { timeout: 8000 });
  console.log("lab rescan smoke: ok");
} finally {
  await browser.close();
  server.proc.kill();
}
