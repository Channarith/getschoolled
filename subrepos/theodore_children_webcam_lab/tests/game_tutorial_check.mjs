import assert from "node:assert/strict";
import {
  TUTORIALS, TUTORIAL_KEY_PREFIX, hasSeenTutorial, markTutorialSeen, tutorialFor,
} from "../src/theodore_children_webcam_lab/static/game_tutorial.js";
import {
  HOWTO, HOWTO_LANGS, LABELS, POP_QUIZ_STEPS, UI, howtoFor, howtoLang, popQuizSteps,
} from "../src/theodore_children_webcam_lab/static/game_howto.js";

const memory = () => {
  const data = new Map();
  return {getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v))};
};

assert.deepEqual(HOWTO_LANGS, ["en", "es", "km"]);
for (const [id, row] of Object.entries(HOWTO)) {
  assert.equal(row.length, 4, `${id} has an icon plus en, es and km text`);
  assert.ok(row[0], `${id} has an icon`);
  for (const lang of HOWTO_LANGS) {
    const t = howtoFor(id, lang);
    assert.ok(t.title.length > 2, `${id}/${lang} title`);
    assert.equal(t.lines.length, 4, `${id}/${lang} has see, do, score and tip`);
    assert.equal(t.labels.length, 4);
    for (const line of t.lines) {
      assert.ok(line.length > 10 && line.length < 260, `${id}/${lang} line length`);
      assert.ok(!line.startsWith("@"), `${id}/${lang} score reference resolved`);
    }
  }
  // A translation must not be a copy of the English text.
  assert.notEqual(howtoFor(id, "es").lines[1], howtoFor(id, "en").lines[1], `${id} es differs from en`);
  assert.notEqual(howtoFor(id, "km").lines[1], howtoFor(id, "en").lines[1], `${id} km differs from en`);
  assert.ok(/[ក-៿]/.test(howtoFor(id, "km").lines[1]), `${id} km uses Khmer script`);
  // Every game has its own "what to do" line, not a shared generic one.
  assert.ok(howtoFor(id, "en").lines[1].length > 20, `${id} specific instruction`);
}
const instructions = Object.keys(HOWTO).map((id) => howtoFor(id, "en").lines[1]);
const sharedLine = instructions.filter((line, i) => instructions.indexOf(line) !== i);
assert.deepEqual(sharedLine, [], "no two games share the same instruction line");

for (const lang of HOWTO_LANGS) {
  assert.equal(LABELS[lang].length, 4);
  assert.ok(UI[lang].letsPlay && UI[lang].skip && UI[lang].help);
  assert.equal(POP_QUIZ_STEPS[lang].length, 5, `Pop Quiz Toss has 5 steps in ${lang}`);
  assert.equal(popQuizSteps(lang).length, 5);
}
const popEn = popQuizSteps("en").map((s) => `${s.title} ${s.lines.join(" ")}`).join(" ");
assert.ok(/LEFT hand/.test(popEn) && /RIGHT hand/.test(popEn) && /10 seconds/.test(popEn), "Pop Quiz steps explain hands and time");

assert.equal(Object.keys(TUTORIALS).length, Object.keys(HOWTO).length);
assert.equal(tutorialFor("not-a-game").title, "How to play", "unknown games get the default tutorial");
assert.equal(tutorialFor("ninja-weave").title, "Ninja Weave");
assert.equal(tutorialFor("heart", "es").title, "Haz corazones");
assert.equal(tutorialFor("heart", "xx").title, "Make hearts", "unsupported language falls back to English");

assert.equal(howtoLang("?lang=es", ""), "es");
assert.equal(howtoLang("?lang=km_KH", ""), "km");
assert.equal(howtoLang("", "es-MX"), "es");
assert.equal(howtoLang("", "fr"), "en");

const store = memory();
assert.equal(hasSeenTutorial("heart", store), false);
markTutorialSeen("heart", store);
assert.equal(hasSeenTutorial("heart", store), true);
assert.equal(hasSeenTutorial("idea", store), false, "seen is remembered per game");
assert.ok(TUTORIAL_KEY_PREFIX.endsWith("."));
const broken = {getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }};
assert.equal(hasSeenTutorial("heart", broken), false, "blocked storage does not throw");
markTutorialSeen("heart", broken);
console.log("game tutorial OK");
