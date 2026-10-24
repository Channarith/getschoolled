import test from "node:test";
import assert from "node:assert/strict";

import { introPhase, tutorialStateFrom } from "../../app/lib/driversEdIntro.ts";

test("the tutorial comes first and the video waits behind it", () => {
  assert.equal(introPhase("pending", false), "hold");
  assert.equal(introPhase("open", false), "hold");
});

test("the video plays only once the tutorial is closed", () => {
  assert.equal(introPhase("closed", false), "play");
});

test("reopening the tutorial pauses the video again", () => {
  assert.equal(introPhase("open", false), "hold");
  assert.equal(introPhase("closed", false), "play");
});

test("after the video ends or is skipped the course page shows", () => {
  assert.equal(introPhase("closed", true), "done");
  assert.equal(introPhase("open", true), "done");
});

test("only well-formed tutorial messages are accepted", () => {
  assert.equal(tutorialStateFrom({ type: "sala-tutorial", state: "open" }), "open");
  assert.equal(tutorialStateFrom({ type: "sala-tutorial", state: "closed" }), "closed");
  assert.equal(tutorialStateFrom({ type: "sala-tutorial", state: "bogus" }), null);
  assert.equal(tutorialStateFrom({ type: "other", state: "open" }), null);
  assert.equal(tutorialStateFrom(null), null);
  assert.equal(tutorialStateFrom("open"), null);
});
