import assert from "node:assert/strict";

import { cameraContinueEnabled, trackingContinueEnabled } from "../src/cameraCheck.ts";
import { isLoopbackUrl, resolveWebAppUrl, worldsPageUrl } from "../src/webAppUrl.ts";
import {
  createSpeakPlan,
  noteAgentFailure,
  noteAudio,
  noteResponseEnd,
  requestSpeak,
  takeQueuedForSend,
  takeUnheardForFallback,
} from "../src/xaiSpeakPlan.ts";

assert.equal(cameraContinueEnabled(false, false), false);
assert.equal(cameraContinueEnabled(true, true), false);
assert.equal(cameraContinueEnabled(true, false), true);
assert.equal(trackingContinueEnabled(false, false, false), true);
assert.equal(trackingContinueEnabled(true, false, false), false);
assert.equal(trackingContinueEnabled(true, true, false), true);
assert.equal(trackingContinueEnabled(true, true, true), false);

assert.equal(isLoopbackUrl("http://localhost:3000"), true);
assert.equal(isLoopbackUrl("http://127.0.0.1:3000"), true);
assert.equal(isLoopbackUrl("https://www.salareen.com"), false);
assert.equal(
  resolveWebAppUrl({ deployMode: "cloud", platform: "ios", configured: "http://localhost:3000" }),
  "https://www.salareen.com",
);
assert.equal(
  resolveWebAppUrl({ deployMode: "cloud", platform: "android", configured: "http://127.0.0.1:3000" }),
  "https://www.salareen.com",
);
assert.equal(
  resolveWebAppUrl({ deployMode: "local", platform: "ios" }),
  "http://localhost:3000",
);
assert.equal(
  resolveWebAppUrl({ deployMode: "local", platform: "android" }),
  "http://10.0.2.2:3000",
);
assert.equal(worldsPageUrl("https://www.salareen.com/"), "https://www.salareen.com/worlds");

import { demoPathWithLocale, childrenLabLocaleScript } from "../src/publicDemos.ts";
assert.equal(
  demoPathWithLocale("/children-lab?embed=mobile", "es"),
  "/children-lab?embed=mobile&lang=es",
);
assert.equal(
  demoPathWithLocale("/studio?access=sample&course=drivers-ed&embed=mobile", "zh-CN"),
  "/studio?access=sample&course=drivers-ed&embed=mobile&lang=zh",
);
assert.equal(demoPathWithLocale("/worlds", "fr"), "/worlds");
const script = childrenLabLocaleScript("ja");
assert.match(script, /language=/);
assert.match(script, /ja-JP/);
assert.doesNotMatch(script, /language=en/);

const plan = createSpeakPlan();
plan.phase = "checking";
assert.equal(requestSpeak(plan, "slide-1", "Hello class", true, false).kind, "queue");
assert.equal(takeUnheardForFallback(plan).length, 1);
assert.equal(plan.phase, "unavailable");
assert.equal(requestSpeak(plan, "slide-1", "Hello class", true, false).kind, "ignore");

const live = createSpeakPlan();
live.phase = "live";
const sent = requestSpeak(live, "slide-2", "Read this", true, true);
assert.equal(sent.kind, "send");
assert.equal(noteAudio(live, live.inflight?.gen ?? null), "play");
assert.equal(noteResponseEnd(live), "finish");
assert.equal(noteResponseEnd(live), "ignore");
assert.equal(noteAgentFailure(live), null);

const silent = createSpeakPlan();
silent.phase = "live";
requestSpeak(silent, "slide-3", "No audio", true, true);
const failed = noteAgentFailure(silent);
assert.equal(failed?.id, "slide-3");
assert.equal(noteAudio(silent, failed?.gen ?? null), "drop");
assert.equal(requestSpeak(silent, "slide-3", "No audio", true, true).kind, "ignore");

const queued = createSpeakPlan();
queued.phase = "checking";
requestSpeak(queued, "a", "one", true, false);
requestSpeak(queued, "b", "two", true, false);
const first = takeQueuedForSend(queued);
assert.equal(first?.id, "a");
assert.equal(queued.phase, "live");
noteAudio(queued, first?.gen ?? null);
const lost = takeUnheardForFallback(queued);
assert.deepEqual(lost.map((turn) => turn.id), ["b"]);

console.log("mobile helper checks ok");
