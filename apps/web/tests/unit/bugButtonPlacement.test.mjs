import test from "node:test";
import assert from "node:assert/strict";
import { bugButtonHidden, defaultBugPosition } from "../../app/lib/bugButtonPlacement.ts";

test("the bug button stays out of immersive screens", () => {
  assert.equal(bugButtonHidden("/demo/on-the-go"), true);
  assert.equal(bugButtonHidden("/drive"), true);
  assert.equal(bugButtonHidden("/report-bug"), true);
  assert.equal(bugButtonHidden("/learn/drivers-ed"), false);
  assert.equal(bugButtonHidden("/demo/on-the-goat"), false);
});

test("on a phone it sits above the page's own bottom-right controls", () => {
  const plain = defaultBugPosition("/our-story", 390, 664, 42);
  const crowded = defaultBugPosition("/learn/drivers-ed", 390, 664, 42);
  assert.equal(plain.y, 664 - 42 - 18);
  assert.ok(crowded.y < plain.y);
  assert.equal(crowded.x, plain.x);
});

test("landscape phones count as phones; desktops keep the corner", () => {
  assert.ok(defaultBugPosition("/learn/x", 863, 393, 42).y < 393 - 42 - 18);
  assert.equal(defaultBugPosition("/learn/x", 1440, 900, 42).y, 900 - 42 - 18);
});
