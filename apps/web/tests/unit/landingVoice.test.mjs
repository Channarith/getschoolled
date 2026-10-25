import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { clipHash, landingClipUrl, resetCloneVoiceCacheForTests } from "../../app/lib/cloneVoice.ts";

const lines = JSON.parse(readFileSync(new URL("../../app/lib/landingVoiceLines.json", import.meta.url), "utf8")).lines;
const shipped = JSON.parse(readFileSync(new URL("../../public/landing-voice/salane/index.json", import.meta.url), "utf8"));

function reset(files) {
  resetCloneVoiceCacheForTests();
  globalThis.fetch = async (url) => {
    const body = files[String(url)];
    return body === undefined ? { ok: false, json: async () => ({}) } : { ok: true, json: async () => body };
  };
}

test("every landing line has a shipped Salane clip under its own hash", () => {
  for (const l of lines) assert.ok(shipped.clips[l.lang].includes(clipHash(l.lang, l.text)), l.id);
});

test("default voice plays the shipped Salane clip", async () => {
  reset({ "/landing-voice/salane/index.json": shipped });
  const { id, lang, text } = lines[0];
  const url = await landingClipUrl(lang, text, "default");
  assert.equal(url, `/landing-voice/salane/${lang}/${clipHash(lang, text)}.mp3`, id);
});

test("a line without a clip returns null so the caller can fall back", async () => {
  reset({ "/landing-voice/salane/index.json": shipped });
  assert.equal(await landingClipUrl("en", "A sentence nobody rendered.", "default"), null);
});

test("missing index returns null (never throws)", async () => {
  reset({});
  assert.equal(await landingClipUrl("en", lines[0].text, "default"), null);
});

test("a chosen consented voice wins when it has the clip, otherwise Salane plays", async () => {
  const { lang, text } = lines[0];
  const h = clipHash(lang, text);
  const files = {
    "/voice-assets/voices.json": { voices: [{ id: "channarith", label: "Channarith", ai_label: "AI", active: true }] },
    "/voice-assets/channarith/index.json": { ext: "mp3", clips: { en: [h] } },
    "/landing-voice/salane/index.json": shipped,
  };
  reset(files);
  assert.equal(await landingClipUrl(lang, text, "channarith"), `/voice-assets/channarith/en/${h}.mp3`);
  reset({ ...files, "/voice-assets/channarith/index.json": { ext: "mp3", clips: { en: [] } } });
  assert.equal(await landingClipUrl(lang, text, "channarith"), `/landing-voice/salane/en/${h}.mp3`);
});

test("a revoked voice (not in voices.json) falls back to Salane", async () => {
  const { lang, text } = lines[0];
  const h = clipHash(lang, text);
  reset({
    "/voice-assets/voices.json": { voices: [] },
    "/voice-assets/channarith/index.json": { ext: "mp3", clips: { en: [h] } },
    "/landing-voice/salane/index.json": shipped,
  });
  assert.equal(await landingClipUrl(lang, text, "channarith"), `/landing-voice/salane/en/${h}.mp3`);
});
