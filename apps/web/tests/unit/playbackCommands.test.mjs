import test from "node:test";
import assert from "node:assert/strict";
import { parsePlaybackCommand, clampPlaybackRate } from "../../app/lib/voiceCommands.ts";

const kind = (s) => parsePlaybackCommand(s)?.kind ?? null;

test("short playback commands are recognized", () => {
  assert.equal(kind("Pause"), "pause");
  assert.equal(kind("please stop the lesson"), "pause");
  assert.equal(kind("Resume."), "resume");
  assert.equal(kind("keep going"), "resume");
  assert.equal(kind("next"), "next");
  assert.equal(kind("skip ahead"), "next");
  assert.equal(kind("go back"), "previous");
  assert.equal(kind("say that again"), "repeat");
  assert.equal(kind("start over"), "restart");
  assert.equal(kind("speed up"), "faster");
  assert.equal(kind("can you slow down"), "slower");
  assert.equal(kind("normal speed"), "speed");
});

test("speed values are read and clamped", () => {
  assert.deepEqual(parsePlaybackCommand("speed 1.5"), { kind: "speed", rate: 1.5 });
  assert.deepEqual(parsePlaybackCommand("set speed to 2"), { kind: "speed", rate: 1.6 });
  assert.deepEqual(parsePlaybackCommand("0.5x"), { kind: "speed", rate: 0.7 });
  assert.equal(clampPlaybackRate(1.234), 1.23);
});

test("questions and long sentences are not commands", () => {
  assert.equal(kind("why does the brake pause the car"), null);
  assert.equal(kind("what is a feedback loop"), null);
  assert.equal(kind("how do I go back to the highway after merging"), null);
  assert.equal(kind("the next car should wait for the light to change"), null);
  assert.equal(kind("explain how stopping distance works"), null);
  assert.equal(kind(""), null);
});
