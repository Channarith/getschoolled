// Playwright smoke test for the CANTONESE enrollment wizard with a fake microphone (Chromium). From the repo root:
//   node tts_bakeoff/tests/enroll_ui_yue_smoke.mjs [screenshot-dir]
// Switches the page to 廣東話, checks the draft banner, the Cantonese consent text and spoken statement, records the 8 Cantonese
// lines, enrolls, sees the pronunciation check (fake recognizer), then withdraws.
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, mkdtempSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import assert from "node:assert/strict";
import path from "node:path";

const require = createRequire(path.join(process.cwd(), "apps/web/"));
const { chromium } = require("playwright");
const shots = process.argv[2] || "/tmp/enroll-shots";
mkdirSync(shots, { recursive: true });
const PY = process.env.LAB_PYTHON || "python3";
const root = mkdtempSync(path.join(tmpdir(), "enroll-ui-"));

// 20 s of speech-like audio at 48 kHz: 180 Hz voiced bursts with a quiet noise floor, looped by Chromium's fake mic.
const rate = 48000, n = rate * 20, pcm = Buffer.alloc(n * 2);
for (let i = 0; i < n; i++) {
  const t = i / rate, gate = (t * 3) % 1 < 0.6 ? 1 : 0;
  const v = gate * 0.25 * Math.sin(2 * Math.PI * 180 * t) * (1 + Math.sin(2 * Math.PI * 4 * t)) / 2 + 0.001 * (Math.random() * 2 - 1);
  pcm.writeInt16LE(Math.round(Math.max(-1, Math.min(1, v)) * 32767), i * 2);
}
const hdr = Buffer.alloc(44);
hdr.write("RIFF", 0); hdr.writeUInt32LE(36 + pcm.length, 4); hdr.write("WAVEfmt ", 8); hdr.writeUInt32LE(16, 16); hdr.writeUInt16LE(1, 20);
hdr.writeUInt16LE(1, 22); hdr.writeUInt32LE(rate, 24); hdr.writeUInt32LE(rate * 2, 28); hdr.writeUInt16LE(2, 32); hdr.writeUInt16LE(16, 34);
hdr.write("data", 36); hdr.writeUInt32LE(pcm.length, 40);
const fake = path.join(root, "fake-mic.wav");
writeFileSync(fake, Buffer.concat([hdr, pcm]));

const server = await new Promise((resolve, reject) => {
  const proc = spawn(PY, ["-u", "-m", "tts_bakeoff.voice_clone.enroll_ui", "--root", path.join(root, "voices"), "--port", "0"], { cwd: process.cwd(), env: { ...process.env, ENROLL_ASR: "fake:0" } });
  let buf = "";
  const timer = setTimeout(() => reject(new Error("server did not start: " + buf)), 30000);
  proc.stdout.on("data", (d) => { buf += d; const m = buf.match(/http:\/\/localhost:(\d+)\//); if (m) { clearTimeout(timer); resolve({ proc, url: m[0] }); } });
  proc.stderr.on("data", (d) => { buf += d; });
  proc.on("exit", (c) => reject(new Error("server exited " + c + ": " + buf)));
});

let failed = null;
const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", `--use-file-for-fake-audio-capture=${fake}`, "--autoplay-policy=no-user-gesture-required"] });

try {
  const page = await (await browser.newContext({ viewport: { width: 900, height: 1100 } })).newPage();
  page.on("pageerror", (e) => { throw e; });
  await page.goto(server.url);
  await page.selectOption("#ui-lang", "yue");
  assert.equal(await page.getAttribute("html", "lang"), "zh-HK");
  assert.match(await page.textContent("h1"), /聲音登記/);
  assert.match(await page.textContent("#steps"), /2 同意/);
  await page.fill("#name", "陳大文");
  await page.screenshot({ path: path.join(shots, "yue-1-who.png") });
  await page.click("#to-consent");
  await page.waitForSelector("#s2:not([hidden])");
  assert.match(await page.textContent("#consent-text"), /錄音及聲音模型同意書/);
  assert.match(await page.textContent("#consent-text"), /商業用途/);
  assert.equal(await page.isVisible("#draft-banner"), true);
  assert.match(await page.textContent("#draft-banner"), /草稿譯本/);
  assert.match(await page.textContent("#statement"), /我叫陳大文/);
  await page.click("#submit-consent");
  assert.match(await page.textContent("#e2"), /請先錄低/);
  for (const c of await page.locator("#agreements input").all()) await c.check();
  await page.fill("#typed", "陳大文");
  await page.click("#proof-rec");
  await page.waitForTimeout(4500);
  await page.click("#proof-stop");
  await page.waitForSelector("#proof-audio:not([hidden])");
  await page.screenshot({ path: path.join(shots, "yue-2-consent.png"), fullPage: true });
  // switching the page language clears anything signed against the other text
  await page.selectOption("#ui-lang", "en");
  await page.waitForFunction(() => /My name is/.test(document.getElementById("statement").textContent));
  assert.match(await page.textContent("#consent-text"), /VOICE RECORDING AND VOICE MODEL CONSENT/);
  assert.equal(await page.isVisible("#draft-banner"), false);
  assert.equal(await page.inputValue("#typed"), "");
  assert.equal(await page.locator("#agreements input:checked").count(), 0);
  await page.selectOption("#ui-lang", "yue");
  await page.waitForFunction(() => /我叫陳大文/.test(document.getElementById("statement").textContent));
  for (const c of await page.locator("#agreements input").all()) await c.check();
  await page.fill("#typed", "陳大文");
  await page.click("#proof-rec");
  await page.waitForTimeout(4500);
  await page.click("#proof-stop");
  await page.waitForSelector("#proof-audio:not([hidden])");
  await page.click("#submit-consent");
  await page.waitForSelector("#s3:not([hidden])");
  assert.equal(await page.inputValue("#lang"), "yue");
  const lines = await page.locator("#lines li").count();
  assert.equal(lines, 8);
  assert.match(await page.textContent("#lines li .t"), /大家早晨/);
  assert.match(await page.textContent("#lines li .n"), /第 1 句，共 8 句/);
  await page.click("#mic-on");
  for (let i = 0; i < lines; i++) {
    const li = page.locator("#lines li").nth(i);
    await li.locator(".r").click();
    await page.waitForTimeout(3600);
    await li.locator(".s").click();
    await page.waitForFunction((k) => /已儲存/.test(document.querySelectorAll("#lines li")[k].querySelector(".i").textContent), i, { timeout: 10000 });
    if (i === 3) await page.screenshot({ path: path.join(shots, "yue-3-recording.png"), fullPage: true });
  }
  assert.match(await page.textContent("#total"), /已錄 8 \/ 8 句/);
  await page.click("#finish");
  await page.waitForSelector("#s4:not([hidden])", { timeout: 30000 });
  assert.match(await page.textContent("#done-msg"), /已登記/);
  await page.waitForFunction(() => /所有句子都同稿夾/.test(document.getElementById("check-msg").textContent), null, { timeout: 15000 });
  assert.equal(await page.locator("#check-items li").count(), 8);
  await page.screenshot({ path: path.join(shots, "yue-4-done.png"), fullPage: true });
  await page.click("#see-list");
  await page.waitForSelector(".sp");
  assert.match(await page.textContent(".sp"), /陳大文/);
  await page.click(".b-withdraw");
  await page.fill(".wn", "陳大文");
  await page.click(".wgo");
  await page.waitForFunction(() => /withdrawn/.test(document.querySelector(".sp .tag").textContent));
  const dirs = (await import("node:fs")).readdirSync(path.join(root, "voices"));
  assert.equal(dirs.length, 1);
  const rec = JSON.parse(readFileSync(path.join(root, "voices", dirs[0], "consent.json"), "utf8"));
  assert.equal(rec.revoked, true);
  assert.equal(rec.evidence.consent_language, "yue");
  assert.equal(rec.evidence.consent_text_draft, true);
  assert.ok(rec.evidence.proof_audio.sha256);
  assert.ok(existsSync(path.join(root, "voices", dirs[0], "samples", "web-yue.wav")));
  console.log("ok: Cantonese consent, 8 recordings, enrolled, voice check, withdrawn; screenshots in " + shots);
} catch (e) {
  failed = e;
} finally {
  await browser.close();
  server.proc.kill();
}
if (failed) { console.error(failed); process.exit(1); }
