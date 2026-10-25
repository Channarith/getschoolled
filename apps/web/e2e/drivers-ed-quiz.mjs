// The Driver's Ed learning check: every option can be clicked (nothing covers it), picked/correct/wrong are shown, a clear way to
// continue exists, and spoken answers are accepted (option text, letter, number, ordinal) with a retry when nothing matches.
//   node apps/web/e2e/drivers-ed-quiz.mjs http://127.0.0.1:8791
// Runs against the course studio itself (?e2e=1 opens a learning check without waiting for a lesson).
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");
const STUDIO = process.argv[2] || "http://127.0.0.1:8791";
const SHOTS = process.argv[3] || "/tmp";
const MATRIX = [["desktop", { viewport: { width: 1280, height: 800 } }], ["pixel7", devices["Pixel 7"]]];

const CHOICES = ["Only the cost of the permit", "California rules of the road, including signs, signals, and right-of-way", "Nothing at all", "Just the school bus rules"];
const QUIZ = { questions: Array.from({ length: 8 }, (_, i) => ({ question_id: `q${i}`, prompt: i === 0 ? "Summary — what should you remember about California driver education?" : `Question ${i + 1}?`, choices: CHOICES, correct_index: 1, explanation: "Because." })) };

// A scriptable Web Speech recogniser: window.__say(text) delivers a final result to every active recogniser.
const FAKE_SPEECH = `(() => {
  window.__recs = [];
  class FakeRec {
    constructor() { this.continuous = false; this.interimResults = false; this.lang = 'en-US'; window.__recs.push(this); }
    start() { this.active = true; } stop() { this.active = false; if (this.onend) this.onend(); } abort() { this.active = false; }
  }
  window.SpeechRecognition = FakeRec; window.webkitSpeechRecognition = FakeRec;
  window.__say = (text) => { for (const r of window.__recs) { if (!r.active) continue; const result = [{ transcript: text }]; result.isFinal = true; if (r.onresult) r.onresult({ resultIndex: 0, results: [result] }); } };
})();`;

const options = (page) => page.locator("#quiz-box button[data-sync-choice]");
const progress = (page) => page.locator("#quiz-box .quiz-progress").innerText().catch(() => "");

async function noOverlay(page, name, label) {
  const hits = await page.evaluate(() => [...document.querySelectorAll("#quiz-box button[data-sync-choice], #summary-sync-mic")].map((b) => {
    const r = b.getBoundingClientRect();
    const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return { ok: top === b || b.contains(top), inView: r.top >= 0 && r.bottom <= innerHeight, by: top && `${top.tagName}#${top.id}` };
  }));
  hits.forEach((h, i) => { assert.ok(h.ok, `${name}: ${label} option ${i} is covered by ${h.by}`); assert.ok(h.inView, `${name}: ${label} option ${i} is on screen`); });
}
async function waitQuestion(page, n) {
  await page.waitForFunction((k) => (document.querySelector("#quiz-box .quiz-progress")?.textContent || "").startsWith(`Question ${k} of`), n, { timeout: 8000 });
}

let failed = 0;
for (const [name, opts] of MATRIX) {
  const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });
  try {
    const ctx = await browser.newContext({ ...opts, permissions: ["camera", "microphone"] });
    await ctx.addInitScript(FAKE_SPEECH);
    await ctx.addInitScript(`try { sessionStorage.setItem('sala_demo_tutorial_seen_v4','1'); localStorage.setItem('salareen_camera_pref_v1','no'); } catch (e) {}`);
    const page = await ctx.newPage();
    await page.route("**/api/studio/teach/summary-quiz", (r) => r.fulfill({ contentType: "application/json", body: JSON.stringify(QUIZ) }));
    await page.route("**/api/studio/teach/summary-grade", (r) => r.fulfill({ contentType: "application/json", body: JSON.stringify({ correct: 8, total: 8, passed: true, attempts: QUIZ.questions.map((q) => ({ question_id: q.question_id, selected_index: 1, correct: true })) }) }));
    const errors = []; page.on("pageerror", (e) => errors.push(e.message.slice(0, 100)));
    await page.goto(`${STUDIO}/studio?access=sample&course=drivers-ed&demo=1&lang=en&e2e=1`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.__salaStudio, null, { timeout: 15000 });
    await page.waitForTimeout(2500);

    // The learner taps Sala to let her listen (the real path); then the check opens.
    await page.getByTestId("sala-mascot").click();
    await page.waitForTimeout(600);
    const t0 = Date.now();
    await page.evaluate(() => window.__salaStudio.present({ kind: "summary_quiz", activity: "quiz", prompt: "Summary quiz" }));
    await options(page).first().waitFor({ state: "visible", timeout: 5000 });
    assert.ok(Date.now() - t0 < 4000, `${name}: the check appears quickly`);
    await page.screenshot({ path: `${SHOTS}/quiz-${name}-1-open.png` });
    const box = await page.locator("#quiz-box").boundingBox();
    assert.ok(box.height < opts.viewport.height - 8, `${name}: the card does not fill the screen`);

    // Q1: click the right answer. Nothing covers any option; the pick is marked correct and there is a way to continue.
    await noOverlay(page, name, "Q1");
    await options(page).nth(1).click();
    await page.locator("#quiz-box button.is-correct").waitFor({ timeout: 3000 });
    assert.match(await page.locator("#summary-sync-feedback").innerText(), /correct/i, `${name}: correct feedback`);
    assert.ok(await page.locator("#summary-sync-next").isVisible(), `${name}: a clear way to continue`);
    await page.locator("#summary-sync-next").click();

    // Q2: a wrong click shows wrong + the right answer.
    await waitQuestion(page, 2);
    await noOverlay(page, name, "Q2");
    await options(page).nth(0).click();
    await page.locator("#quiz-box button.is-wrong").waitFor({ timeout: 3000 });
    assert.equal(await page.locator("#quiz-box button.is-correct").count(), 1, `${name}: the right answer is shown`);
    await page.locator("#summary-sync-next").click();

    // Voice answers: option text, a letter, "option three", "the third one", "second".
    const spoken = [["California rules of the road including signs signals and right of way", 1], ["C", 2], ["option three", 2], ["the third one", 2], ["second", 1]];
    for (let i = 0; i < spoken.length; i += 1) {
      await waitQuestion(page, 3 + i);
      const [say, want] = spoken[i];
      assert.equal(await page.evaluate(() => window.salaActivity.open()), true, `${name}: the check is listening for an answer`);
      await page.evaluate((t) => window.__say(t), say);
      await page.locator("#quiz-box button.is-picked").waitFor({ timeout: 3000 });
      const picked = await page.evaluate(() => [...document.querySelectorAll("#quiz-box button[data-sync-choice]")].findIndex((b) => b.classList.contains("is-picked")));
      assert.equal(picked, want, `${name}: "${say}" -> option ${want} (got ${picked})`);
      await page.locator("#summary-sync-next").click();
    }

    // Q8: something that is not an answer: shown as heard, asked again, nothing is picked; then the Speak button works.
    await waitQuestion(page, 8);
    await page.evaluate(() => window.__say("banana pancakes"));
    await page.waitForFunction(() => /I heard/.test(document.getElementById("summary-sync-heard")?.textContent || ""), null, { timeout: 3000 });
    assert.equal(await page.locator("#quiz-box button.is-picked").count(), 0, `${name}: no guess on a non-answer`);
    await page.locator("#summary-sync-mic").click();
    await page.waitForTimeout(500);
    await page.evaluate(() => window.__say("a"));
    await page.locator("#quiz-box button.is-picked").waitFor({ timeout: 3000 });
    await page.locator("#summary-sync-next").click();

    // Results.
    await page.locator("#summary-continue-sync").waitFor({ timeout: 8000 });
    await page.screenshot({ path: `${SHOTS}/quiz-${name}-2-results.png` });
    assert.equal(errors.length, 0, `${name}: page errors ${errors.join("|")}`);
    await ctx.close();
    console.log(`PASS ${name}`);
  } catch (error) {
    failed += 1;
    const where = String(error.stack).split("\n").filter((l) => l.includes("drivers-ed-quiz")).slice(0, 1).join("").trim().replace(/^.*\//, "");
    console.log(`FAIL ${name}: ${String(error.message).split("\n")[0]} @ ${where}`);
  } finally {
    await browser.close();
  }
}
process.exit(failed ? 1 : 0);
