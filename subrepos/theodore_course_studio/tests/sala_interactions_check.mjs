// Run: node --test subrepos/theodore_course_studio/tests/sala_interactions_check.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { ScrubDetector, DoubleTapDetector, matchDanceIntent } from "../src/theodore_course_studio/voice_static/sala_interactions.js";
import { parseCourseVoiceIntent, parseDemoCommand } from "../src/theodore_course_studio/voice_static/course_voice.js";

// Pointer path through waypoints [x, ms], sampled every 20 ms.
function run(detector, waypoints, width = 200) {
  let fired = 0;
  for (let w = 1; w < waypoints.length; w += 1) {
    const [x0, t0] = waypoints[w - 1];
    const [x1, t1] = waypoints[w];
    for (let t = t0; t <= t1; t += 20) {
      const x = x0 + ((x1 - x0) * (t - t0)) / (t1 - t0);
      if (detector.feed(x, 1000 + t, width)) fired += 1;
    }
  }
  return fired;
}

test("a quick side-to-side scrub is recognised once", () => {
  const d = new ScrubDetector();
  assert.equal(run(d, [[0, 0], [130, 250], [10, 500], [130, 750], [10, 1000]]), 1);
});

test("the same motion done slowly does not trigger", () => {
  const d = new ScrubDetector();
  assert.equal(run(d, [[0, 0], [130, 1000], [10, 2000], [130, 3000], [10, 4000]]), 0);
});

test("small fast jitter does not trigger", () => {
  const d = new ScrubDetector();
  assert.equal(run(d, [[90, 0], [110, 100], [90, 200], [110, 300], [90, 400], [110, 500], [90, 600]]), 0);
});

test("one sweep, a tap and a drag in one direction do not trigger", () => {
  assert.equal(run(new ScrubDetector(), [[0, 0], [190, 300]]), 0);
  assert.equal(run(new ScrubDetector(), [[100, 0], [100, 500]]), 0);
  assert.equal(run(new ScrubDetector(), [[0, 0], [190, 2500]]), 0);
});

test("a scrub that is too narrow does not trigger (needs 40% of the width)", () => {
  assert.equal(run(new ScrubDetector(), [[60, 0], [120, 200], [60, 400], [120, 600], [60, 800]]), 0);
});

test("cooldown: a second scrub right away is ignored, a later one works", () => {
  const d = new ScrubDetector();
  const path = (t0) => [[0, t0], [130, t0 + 250], [10, t0 + 500], [130, t0 + 750], [10, t0 + 1000]];
  let n = 0;
  for (const [x, t] of [[0, 0], [130, 250], [10, 500], [130, 750], [10, 1000]]) if (d.feed(x, t, 200)) n += 1;
  for (const [x, t] of [[0, 1500], [130, 1750], [10, 2000], [130, 2250], [10, 2500]]) if (d.feed(x, t, 200)) n += 1;
  assert.equal(n, 1);
  let later = 0;
  for (const [x, t] of path(20000).map(([x, t]) => [x, t])) if (d.feed(x, t, 200)) later += 1;
  assert.ok(later <= 1);
});

test("double tap: close in time and place only", () => {
  const d = new DoubleTapDetector();
  assert.equal(d.tap(100, 100, 1000), false);
  assert.equal(d.tap(104, 98, 1200), true);
  assert.equal(d.tap(100, 100, 5000), false);
  assert.equal(d.tap(100, 100, 5600), false);          // too slow
  assert.equal(d.tap(100, 100, 7000), false);
  assert.equal(d.tap(300, 400, 7100), false);          // too far
});

test("English dance requests are recognised", () => {
  for (const s of ["dance", "please dance", "can you dance for me", "dance for me", "do a dance", "shake shake", "shake it",
    "show me your moves", "boogie", "let's dance", "Get down", "bust a move", "Dans", "dancing", "Sala, dance!", "go dance",
    "could you do a little dance", "daance"]) {
    assert.equal(matchDanceIntent(s, "en"), true, s);
  }
});

test("questions about dancing and other speech still go to Q&A", () => {
  for (const s of ["dancing is a hobby I want to ask about", "what is the history of dance", "do you like dancing", "next", "pause",
    "explain the second slide about shaking hands", "I want to dance later but first explain the quiz", "who invented the waltz",
    "what does the sign mean", "", "   "]) {
    assert.equal(matchDanceIntent(s, "en"), false, s);
  }
});

test("dance requests in other UI languages (machine-drafted lists)", () => {
  const yes = { es: ["baila", "por favor baila", "baila para mí"], fr: ["danse", "danse pour moi"], de: ["tanz für mich", "tanzen"],
    it: ["balla", "fai un ballo"], pt: ["dança", "dança pra mim"], zh: ["跳舞", "请跳舞", "来跳舞"], yue: ["跳隻舞俾我睇", "跳吓舞"],
    ja: ["ダンスして", "踊って"], ko: ["춤춰줘", "춤춰"], vi: ["nhảy đi", "nhảy múa"], th: ["เต้นหน่อย"], km: ["រាំមួយ"] };
  for (const [lang, list] of Object.entries(yes)) for (const s of list) assert.equal(matchDanceIntent(s, lang), true, `${lang}: ${s}`);
  const no = { es: ["cuéntame la historia del baile"], zh: ["跳舞的历史是什么"], de: ["wann wurde der walzer erfunden"] };
  for (const [lang, list] of Object.entries(no)) for (const s of list) assert.equal(matchDanceIntent(s, lang), false, `${lang}: ${s}`);
  assert.equal(matchDanceIntent("dance", "ja"), true, "English always works");
  assert.equal(matchDanceIntent("跳舞", "zh-HK"), true, "zh-HK is treated as Cantonese");
});

test("every voice command the tutorial lists is understood (demo + full course)", () => {
  // The tutorial chips: pause, next, back, repeat, captions on, full screen, speak Spanish, louder, mute.
  const chips = ["pause", "next", "back", "repeat", "captions on", "full screen", "speak Spanish", "louder", "mute"];
  for (const chip of chips) {
    const understood = Boolean(parseCourseVoiceIntent(chip) || parseDemoCommand(chip));
    assert.equal(understood, true, `tutorial promises "${chip}" but no parser understands it`);
  }
});
