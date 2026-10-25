import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { parsePlaybackCommand, hasWakeWord } from "../../app/lib/voiceCommands.ts";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const pages = read("../../app/lib/i18n-pages.ts");
const onTheGo = read("../../app/components/OnTheGo.tsx");

// English text of an On the Go tutorial step (the first block in the file is English).
const step = (n) => {
  const m = pages.match(new RegExp(`"drive\\.tutorialStep${n}": "((?:[^"\\\\]|\\\\.)*)"`));
  assert.ok(m, `drive.tutorialStep${n} is missing`);
  return m[1].replace(/\\"/g, '"');
};
const quoted = (text) => [...text.matchAll(/"([^"]+)"/g)].map((m) => m[1]);

test("every command the On the Go tutorial tells you to say is understood", () => {
  for (const n of [2, 3]) {
    const phrases = quoted(step(n));
    assert.ok(phrases.length >= 2, `step ${n} lists no quoted commands`);
    for (const phrase of phrases) {
      assert.notEqual(parsePlaybackCommand(phrase), null, `tutorial step ${n} says "${phrase}" but it is not a playback command`);
    }
  }
});

test("'Hey Sala' is a wake phrase", () => {
  const phrases = quoted(step(1));
  assert.ok(phrases.includes("Hey Sala"));
  assert.equal(hasWakeWord("Hey Sala, what does that mean"), true);
});

test("the tapped-Sala, tap-anywhere and help-button promises exist in the component", () => {
  assert.match(step(1), /Tap the Sala logo/);
  assert.ok(onTheGo.includes("data-testid=\"on-the-go-mascot\""), "a tappable Sala");
  assert.ok(onTheGo.includes("tapping anywhere else on the page resumes the lesson"), "tap anywhere resumes after an answer");
  assert.match(step(4), /tap anywhere/);
  assert.match(step(5), /\? button/);
  assert.ok(onTheGo.includes("data-testid=\"on-the-go-help\""), "the ? help button");
});

test("the dance easter egg is wired into On the Go and is not in the tutorial", () => {
  assert.ok(onTheGo.includes("matchDanceIntent"));
  assert.ok(onTheGo.includes("sala_interactions.js"));
  for (let n = 1; n <= 5; n += 1) assert.doesNotMatch(step(n).toLowerCase(), /dance/);
});
