import test from "node:test";
import assert from "node:assert/strict";

import {
  MIX_TONES, NEUTRAL_TONE, TONES, TONE_KEY, getTone, isKnownTone, setTone, toneBlockedForVoice,
} from "../../app/lib/voiceTone.ts";

function fakeWindow() {
  const store = new Map();
  globalThis.localStorage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) };
  const events = [];
  globalThis.window = { dispatchEvent: (e) => events.push(e), localStorage: globalThis.localStorage };
  globalThis.CustomEvent = class { constructor(type, init) { this.type = type; this.detail = init?.detail; } };
  return { store, events };
}

test("ten tones plus thirteen mixes, neutral first", () => {
  assert.equal(TONES.length, 10);
  assert.equal(TONES[0].id, NEUTRAL_TONE);
  assert.equal(MIX_TONES.length, 13);
  assert.ok(MIX_TONES.every((m) => m.id.startsWith("blend-")));
  assert.ok(isKnownTone("anime") && isKnownTone("blend-professional50-cute50") && !isKnownTone("blend-nope") && !isKnownTone(""));
});

test("the mix ids are exactly the ones the speech gateway and the clips use", () => {
  assert.deepEqual(
    MIX_TONES.map((m) => m.id).slice(0, 3),
    ["blend-professional75-cute25", "blend-professional50-cute50", "blend-professional25-cute75"],
  );
  assert.ok(MIX_TONES.some((m) => m.id === "blend-pro34-cute33-anime33"));
});

test("saved tone round-trips; neutral and unknown ids mean the plain voice", () => {
  const { store, events } = fakeWindow();
  assert.equal(getTone(), "");
  setTone("cute");
  assert.equal(store.get(TONE_KEY), "cute");
  assert.equal(getTone(), "cute");
  assert.equal(events.at(-1).detail, "cute");
  setTone("neutral");
  assert.equal(getTone(), "");
  setTone("definitely-not-a-tone");
  assert.equal(store.get(TONE_KEY), "neutral");
  store.set(TONE_KEY, "blend-nope");
  assert.equal(getTone(), "");
});

test("a company voice cannot take a tone without its own stylized consent", () => {
  assert.equal(toneBlockedForVoice(null), false);          // an edge voice: tones allowed
  assert.equal(toneBlockedForVoice({}), true);              // a company voice with no stylized consent
  assert.equal(toneBlockedForVoice({ stylized: false }), true);
  assert.equal(toneBlockedForVoice({ stylized: true }), false);
});
