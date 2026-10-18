// node --test apps/web/tests/unit/courseVoiceIntent.test.mjs
// (The web package has no CI unit-test job today; this file keeps parity with
// the sibling tests under apps/web/tests/unit and is also run locally. The
// mobile Jest mirror in apps/mobile/src/__tests__/courseVoiceIntent.test.ts
// is wired into CI.)
import test from "node:test";
import assert from "node:assert/strict";
import {
  courseVoiceIntentCatalog,
  languageCodeFromSpoken,
  parseCourseVoiceIntent,
} from "../../app/lib/courseVoiceIntent.ts";

test("recognizes the catalog of intents from everyday phrasing", () => {
  const cases = [
    ["pause", "pause"],
    ["pause please", "pause"],
    ["stop", "pause"],
    ["Sala, pause the course", "pause"],
    ["hey sala, stop the lesson", "pause"],
    ["resume", "resume"],
    ["play", "resume"],
    ["unpause", "resume"],
    ["keep going", "resume"],
    ["restart", "restart"],
    ["start over", "restart"],
    ["from the beginning", "restart"],
    ["start", "start"],
    ["begin", "start"],
    ["start the course", "start"],
    ["next", "next"],
    ["next slide", "next"],
    ["skip ahead", "next"],
    ["back", "previous"],
    ["previous", "previous"],
    ["go back", "previous"],
    ["last slide", "previous"],
    ["repeat", "repeat"],
    ["say that again", "repeat"],
    ["captions on", "captions_on"],
    ["turn on captions", "captions_on"],
    ["enable subtitles", "captions_on"],
    ["show closed captions", "captions_on"],
    ["captions off", "captions_off"],
    ["turn off cc", "captions_off"],
    ["hide subtitles", "captions_off"],
    ["captions", "captions_toggle"],
    ["subtitles", "captions_toggle"],
    ["fullscreen", "fullscreen_on"],
    ["go fullscreen", "fullscreen_on"],
    ["make it bigger", "fullscreen_on"],
    ["exit fullscreen", "fullscreen_off"],
    ["leave fullscreen", "fullscreen_off"],
    ["exit", "fullscreen_off"],
    ["slow down", "set_speed"],
    ["speed up", "set_speed"],
    ["normal speed", "set_speed"],
    ["stop listening", "mute_mic"],
    ["mute the microphone", "mute_mic"],
    ["be quiet mic", "mute_mic"],
    ["show the controls", "show_controls"],
    ["display options", "show_controls"],
    ["hide the controls", "hide_controls"],
    ["help", "help"],
    ["what can i say", "help"],
    ["commands", "help"],
  ];
  for (const [utterance, kind] of cases) {
    const parsed = parseCourseVoiceIntent(utterance);
    assert.ok(parsed, `expected an intent for ${JSON.stringify(utterance)}`);
    assert.equal(parsed.kind, kind, `wrong intent for ${JSON.stringify(utterance)}: got ${parsed.kind}`);
  }
});

test("set_language maps spoken language names to BCP-47 base codes", () => {
  const samples = [
    ["speak Spanish", "es"],
    ["say it in french", "fr"],
    ["change language to german", "de"],
    ["switch to mandarin", "zh"],
    ["in cantonese please", "yue"],
    ["speak khmer", "km"],
  ];
  for (const [utterance, code] of samples) {
    const parsed = parseCourseVoiceIntent(utterance);
    assert.ok(parsed, utterance);
    assert.equal(parsed.kind, "set_language", utterance);
    assert.equal(parsed.language, code, utterance);
  }
});

test("unknown language names fall through so Sala can answer in prose", () => {
  // Not a language we know -> no set_language; may become an ask or null.
  const parsed = parseCourseVoiceIntent("say it in Esperanto");
  assert.notEqual(parsed?.kind, "set_language");
});

test("speed set returns the direction the learner asked for", () => {
  assert.equal(parseCourseVoiceIntent("slower")?.["speed"], "slower");
  assert.equal(parseCourseVoiceIntent("faster")?.["speed"], "faster");
  assert.equal(parseCourseVoiceIntent("regular speed")?.["speed"], "normal");
});

test("ask-style utterances pass through as ask intents", () => {
  const q = parseCourseVoiceIntent("What is machine learning?");
  assert.equal(q?.kind, "ask");
  assert.ok(q?.question?.includes("machine learning"));
  const explicit = parseCourseVoiceIntent("ask sala, define covariance");
  assert.equal(explicit?.kind, "ask");
  assert.equal(explicit?.question, "define covariance");
});

test("empty, pure-filler, and ambiguous input returns null", () => {
  assert.equal(parseCourseVoiceIntent(""), null);
  assert.equal(parseCourseVoiceIntent("    "), null);
  assert.equal(parseCourseVoiceIntent("uhhh"), null, "fillers are not intents");
  assert.equal(parseCourseVoiceIntent("the lesson was good"), null, "narration echoes are not intents");
});

test("the wake word is optional and does not change the matched intent", () => {
  const bare = parseCourseVoiceIntent("pause");
  const prefixed = parseCourseVoiceIntent("sala pause");
  const hey = parseCourseVoiceIntent("hey sala, pause");
  assert.equal(bare?.kind, "pause");
  assert.equal(prefixed?.kind, "pause");
  assert.equal(hey?.kind, "pause");
});

test("languageCodeFromSpoken is deterministic and rejects unknown names", () => {
  assert.equal(languageCodeFromSpoken("Spanish"), "es");
  assert.equal(languageCodeFromSpoken("MANDARIN"), "zh");
  assert.equal(languageCodeFromSpoken("en"), "en");
  assert.equal(languageCodeFromSpoken("klingon"), null);
  assert.equal(languageCodeFromSpoken(""), null);
});

test("the exported catalog covers every CourseVoiceIntent kind the parser can emit", () => {
  const kinds = new Set(courseVoiceIntentCatalog());
  // Sample a representative utterance for every kind in the catalog to prove
  // the catalog is not drifting ahead of the parser.
  const probes = {
    pause: "pause", resume: "resume", restart: "restart", start: "start",
    next: "next", previous: "back", repeat: "repeat",
    captions_on: "captions on", captions_off: "captions off", captions_toggle: "captions",
    fullscreen_on: "fullscreen", fullscreen_off: "exit fullscreen",
    set_language: "speak spanish", set_speed: "slower",
    mute_mic: "stop listening",
    show_controls: "show the controls", hide_controls: "hide the controls",
    help: "help",
    ask: "what is calculus",
  };
  for (const kind of kinds) {
    assert.ok(probes[kind], `catalog kind ${kind} has no probe utterance in this test`);
    const parsed = parseCourseVoiceIntent(probes[kind]);
    assert.equal(parsed?.kind, kind, `probe for ${kind} resolved to ${parsed?.kind}`);
  }
});
