// Engine-agnostic voice control: the router (positive and negative cases), pace, localised commands, the ask budget, and parity
// with the studio player's vanilla-JS parser (so Salane, Sage, company and edge voices all control the course the same way).
import assert from "node:assert/strict";
import test from "node:test";
import { registerHooks } from "node:module";

// Node strips types but does not resolve extensionless relative imports; let ./voiceCommands find voiceCommands.ts.
registerHooks({
  resolve(specifier, context, nextResolve) {
    try { return nextResolve(specifier, context); } catch (error) {
      if (specifier.startsWith(".") && !/\.\w+$/.test(specifier)) return nextResolve(`${specifier}.ts`, context);
      throw error;
    }
  },
});

const { routeUtterance, paceAfter, flexPrompt, findTopicIndex, matchLocalizedCommand, MIN_PLAYBACK_RATE, MAX_PLAYBACK_RATE } = await import("../../app/lib/voiceControl.ts");
const { QuestionBudget } = await import("../../app/lib/voiceAsk.ts");
const studio = await import("../../../../subrepos/theodore_course_studio/src/theodore_course_studio/voice_static/course_voice.js");

const type = (s, o) => routeUtterance(s, o).type;

test("pace range is 0.75x to 2x", () => {
  assert.equal(MIN_PLAYBACK_RATE, 0.75);
  assert.equal(MAX_PLAYBACK_RATE, 2);
  assert.equal(paceAfter(1, { kind: "slower" }), 0.85);
  assert.equal(paceAfter(1.95, { kind: "faster" }), 2);
  assert.equal(paceAfter(0.8, { kind: "slower" }), 0.75);
  assert.equal(paceAfter(1, { kind: "speed", rate: 3 }), 2);
});

test("commands: pause, resume, next, back, repeat, speed", () => {
  assert.deepEqual(routeUtterance("pause"), { type: "playback", command: { kind: "pause" } });
  assert.deepEqual(routeUtterance("please continue"), { type: "playback", command: { kind: "resume" } });
  assert.deepEqual(routeUtterance("next"), { type: "playback", command: { kind: "next" } });
  assert.deepEqual(routeUtterance("go back"), { type: "playback", command: { kind: "previous" } });
  assert.deepEqual(routeUtterance("say that again"), { type: "playback", command: { kind: "repeat" } });
  assert.deepEqual(routeUtterance("speed 1.5"), { type: "playback", command: { kind: "speed", rate: 1.5 } });
});

test("adaptive pacing phrases", () => {
  assert.deepEqual(routeUtterance("you're going too fast"), { type: "playback", command: { kind: "slower" } });
  assert.deepEqual(routeUtterance("too slow"), { type: "playback", command: { kind: "faster" } });
  assert.deepEqual(routeUtterance("I'm lost"), { type: "flex", kind: "lost" });
  assert.deepEqual(routeUtterance("I know this"), { type: "know_this", count: 2 });
  assert.equal(type("this is too easy"), "know_this");
  assert.equal(type("skip this section"), "skip_section");
});

test("flexibility intents", () => {
  assert.deepEqual(routeUtterance("explain that more simply"), { type: "flex", kind: "simpler" });
  assert.deepEqual(routeUtterance("go deeper"), { type: "flex", kind: "deeper" });
  assert.deepEqual(routeUtterance("give me an example"), { type: "flex", kind: "example" });
  assert.deepEqual(routeUtterance("quiz me"), { type: "flex", kind: "quiz_me" });
  assert.deepEqual(routeUtterance("summarize"), { type: "flex", kind: "summarize" });
  assert.deepEqual(routeUtterance("go back to the brakes"), { type: "go_back_to", topic: "brakes" });
});

test("volume, captions, fullscreen, mic", () => {
  assert.deepEqual(routeUtterance("louder"), { type: "volume", kind: "louder" });
  assert.deepEqual(routeUtterance("mute"), { type: "volume", kind: "mute" });
  assert.deepEqual(routeUtterance("captions on"), { type: "captions", on: true });
  assert.deepEqual(routeUtterance("turn off the subtitles"), { type: "captions", on: false });
  assert.deepEqual(routeUtterance("fullscreen"), { type: "fullscreen", on: true });
  assert.deepEqual(routeUtterance("exit fullscreen"), { type: "fullscreen", on: false });
  assert.deepEqual(routeUtterance("stop listening"), { type: "stop_listening" });
});

test("questions go to the lesson, never run as commands", () => {
  for (const q of ["why does the brake pause the car?", "what is a yield sign", "how do I slow down on ice", "can you explain the next lesson in detail please"]) {
    assert.equal(type(q), "question", q);
  }
});

test("noise and chatter are ignored", () => {
  for (const s of ["", "   ", "uh", "hmm okay", "the weather is nice today and i like soup"]) assert.equal(type(s), "none", s);
});

test("localised commands", () => {
  assert.deepEqual(routeUtterance("pausa", { locale: "es-ES" }), { type: "playback", command: { kind: "pause" } });
  assert.deepEqual(routeUtterance("plus vite", { locale: "fr-FR" }), { type: "playback", command: { kind: "faster" } });
  assert.deepEqual(routeUtterance("langsamer", { locale: "de" }), { type: "playback", command: { kind: "slower" } });
  assert.deepEqual(routeUtterance("暂停", { locale: "zh-CN" }), { type: "playback", command: { kind: "pause" } });
  assert.deepEqual(routeUtterance("一時停止", { locale: "ja" }), { type: "playback", command: { kind: "pause" } });
  assert.equal(matchLocalizedCommand("pausa", "en"), null);
});

test("flex prompt carries the lesson part; topic search prefers the latest earlier match", () => {
  assert.match(flexPrompt("simpler", "Brakes slow the car."), /Brakes slow the car\./);
  assert.ok(flexPrompt("quiz_me", "").length > 20);
  assert.equal(findTopicIndex("brakes", ["Intro", "Brakes", "Signs", "Brakes again"], 3), 1);
  assert.equal(findTopicIndex("volcano", ["Intro", "Brakes"]), -1);
});

test("question budget: 6 a minute, 40 a session", () => {
  let t = 0;
  const b = new QuestionBudget(() => t);
  for (let i = 0; i < 6; i++) assert.equal(b.check(), "ok");
  assert.equal(b.check(), "rate");
  t += 61_000;
  assert.equal(b.check(), "ok");
  const c = new QuestionBudget(() => t);
  let ok = 0;
  for (let i = 0; i < 60; i++) { t += 11_000; if (c.check() === "ok") ok++; }
  assert.equal(ok, 40);
  assert.equal(c.check(), "session");
});

test("studio player parser agrees with the TypeScript router on pace and flexibility", () => {
  const cases = [["too fast", "pace"], ["too slow", "pace"], ["speed 2", "pace"], ["i'm lost", "flex"], ["go deeper", "flex"], ["quiz me", "flex"], ["i know this", "know_this"], ["skip this section", "skip_section"]];
  for (const [phrase, kind] of cases) assert.equal(studio.parseExtraCommand(phrase)?.kind, kind, phrase);
  for (const q of ["why does the brake pause the car?", "what is a yield sign"]) assert.equal(studio.parseExtraCommand(q), null, q);
  assert.equal(studio.clampPace(5), 2);
  assert.equal(studio.clampPace(0.1), 0.75);
  assert.equal(studio.MIN_PACE, MIN_PLAYBACK_RATE);
  assert.equal(studio.MAX_PACE, MAX_PLAYBACK_RATE);
});
