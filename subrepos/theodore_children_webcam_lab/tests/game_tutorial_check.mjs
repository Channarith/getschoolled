import assert from "node:assert/strict";
import {
  TUTORIALS, TUTORIAL_KEY_PREFIX, hasSeenTutorial, markTutorialSeen, tutorialFor,
} from "../src/theodore_children_webcam_lab/static/game_tutorial.js";

const memory = () => {
  const data = new Map();
  return {getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v))};
};

for (const [id, [icon, title, lines]] of Object.entries(TUTORIALS)) {
  assert.ok(icon && title, `${id} has an icon and title`);
  assert.ok(lines.length >= 2 && lines.length <= 4, `${id} has a short list of steps`);
  assert.ok(lines.every((line) => line.length > 3 && line.length < 90), `${id} steps are short`);
}
assert.equal(tutorialFor("not-a-game").title, "How to play", "unknown games get the default tutorial");
assert.equal(tutorialFor("ninja-weave").title, "Ninja Weave");

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
