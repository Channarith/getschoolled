// Playwright smoke test for the "Say anything" panel with a stubbed synthesizer (Chromium). From the repo root:
//   node tts_bakeoff/tests/say_anything_smoke.mjs [screenshot-dir]
// Starts the enrollment UI with one consented speaker and a fake CUDA host whose "model" writes a 1 s tone.
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import assert from "node:assert/strict";
import path from "node:path";

const require = createRequire(path.join(process.cwd(), "apps/web/"));
const { chromium } = require("playwright");
const shots = process.argv[2] || "/tmp/say-shots";
mkdirSync(shots, { recursive: true });
const PY = process.env.LAB_PYTHON || "python3";
const root = mkdtempSync(path.join(tmpdir(), "say-ui-"));

const WRAPPER = `
import math, subprocess, sys, wave
from pathlib import Path
from tts_bakeoff.voice_clone import enroll_ui as ui, registry
root = Path(sys.argv[1]); form = root.parent / (root.name + "-form.txt")
form.write_text("signed consent form " * 20)
registry.record_consent("alice", "Alice Tran", "employee", form, base=root)
def tone(path, secs):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(b"".join(int(9000 * math.sin(2 * math.pi * 220 * i / 24000)).to_bytes(2, "little", signed=True) for i in range(int(24000 * secs))))
ref = registry.speaker_dir("alice", root) / "samples" / "ref.wav"; ref.parent.mkdir(parents=True, exist_ok=True); tone(ref, 2)
registry.add_sample("alice", ref, "reference words", "en", root)
STUB = "import math, pathlib, sys, time, wave\\nwav = pathlib.Path(sys.argv[1]); time.sleep(3.5); wav.with_suffix('.running').touch(); time.sleep(4)\\nw = wave.open(str(wav), 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)\\nw.writeframes(b''.join(int(9000*math.sin(2*math.pi*220*i/24000)).to_bytes(2,'little',signed=True) for i in range(24000))); w.close(); wav.with_suffix('.running').unlink()"
ui.cuda_host = lambda: True
ui._launch = lambda argv, env, log: subprocess.Popen([sys.executable, "-c", STUB, argv[5]])
from tts_bakeoff.voice_clone.enroll_ui.__main__ import main
main(["--root", str(root), "--port", "0"])
`;

const server = await new Promise((resolve, reject) => {
  const proc = spawn(PY, ["-u", "-c", WRAPPER, path.join(root, "voices")], { cwd: process.cwd() });
  let buf = "";
  const timer = setTimeout(() => reject(new Error("server did not start: " + buf)), 30000);
  proc.stdout.on("data", (d) => { buf += d; const m = buf.match(/http:\/\/localhost:(\d+)\//); if (m) { clearTimeout(timer); resolve({ proc, url: m[0] }); } });
  proc.stderr.on("data", (d) => { buf += d; });
  proc.on("exit", (c) => reject(new Error("server exited " + c + ": " + buf)));
});

const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
try {
  const page = await (await browser.newContext({ viewport: { width: 900, height: 900 } })).newPage();
  await page.goto(server.url);
  await page.click("#tab-say");
  await page.waitForSelector("#say-speaker option[value=alice]", { state: "attached" });
  assert.equal(await page.locator("#say-model option").count(), 2);
  await page.selectOption("#say-model", "cosyvoice2");
  assert.deepEqual(await page.locator("#say-lang option").evaluateAll((o) => o.map((x) => x.value)), ["en", "es", "zh"]);
  await page.selectOption("#say-model", "voxcpm2");
  assert.ok((await page.locator("#say-lang option").count()) >= 8);

  await page.fill("#say-text", "Hello, this is my voice saying something new.");
  assert.equal(await page.textContent("#say-count"), "45 / 500");
  await page.click("#say-go");
  await page.waitForSelector('.say-item[data-state="waiting for GPU lock"]');
  await page.click("#say-go");                                              // a second click while queued is refused
  await page.waitForFunction(() => /already/.test(document.querySelector("#say-err").textContent));
  await page.waitForSelector('.say-item[data-state="running"]', { timeout: 20000 });
  await page.waitForSelector('.say-item[data-state="done"] audio', { timeout: 30000 });
  assert.match(await page.textContent(".say-item .ai"), /^AI-generated voice of Alice Tran$/);
  const href = await page.getAttribute(".say-item a[download]", "href");
  assert.match(href, /^\/api\/say\/audio\/[a-f0-9]{12}\.wav$/);
  const dur = await page.evaluate(async () => {
    const a = document.querySelector(".say-item audio");
    await new Promise((r) => (a.readyState >= 1 ? r() : a.addEventListener("loadedmetadata", r, { once: true })));
    return a.duration;
  });
  assert.ok(dur > 0.9 && dur < 1.1, "audio plays back about 1 s, got " + dur);
  await page.screenshot({ path: path.join(shots, "say-anything.png") });
  console.log("say anything smoke: ok (duration " + dur.toFixed(2) + " s)");
} finally {
  await browser.close();
  server.proc.kill();
}
