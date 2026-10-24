import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  DEFAULT_VOICE_ID, clipHash, cloneClipUrl, loadCloneVoices, resetCloneVoiceCacheForTests,
} from "../../app/lib/cloneVoice.ts";

const vectors = JSON.parse(readFileSync(new URL("../../../../tts_manifest/hash_vectors.json", import.meta.url), "utf8"));

function serve(files) {
  globalThis.fetch = async (url) => {
    const body = files[String(url)];
    return body === undefined ? { ok: false, json: async () => ({}) } : { ok: true, json: async () => body };
  };
}

test("hash matches the Python vectors (same clip id on both sides)", () => {
  for (const c of vectors.cases) assert.equal(clipHash(c.lang, c.text), c.hash, `${c.lang} ${c.text}`);
});

test("default voice never looks up a clip", async () => {
  resetCloneVoiceCacheForTests();
  serve({});
  assert.equal(await cloneClipUrl("en", "Hello world", DEFAULT_VOICE_ID), null);
});

test("an active voice resolves the pre-rendered clip by language and text hash", async () => {
  resetCloneVoiceCacheForTests();
  const h = clipHash("en", "Hello world");
  serve({
    "/voice-assets/voices.json": { voices: [{ id: "channarith", label: "C", ai_label: "AI-generated voice of C", active: true }] },
    "/voice-assets/channarith/index.json": { ext: "mp3", clips: { en: [h] } },
  });
  assert.equal(await cloneClipUrl("en-GB", "  Hello   world ", "channarith"), `/voice-assets/channarith/en/${h}.mp3`);
  assert.equal(await cloneClipUrl("en", "Something not rendered", "channarith"), null);
  assert.equal(await cloneClipUrl("es", "Hello world", "channarith"), null);
});

test("a revoked voice (inactive or unlisted) never resolves, even if clips exist", async () => {
  resetCloneVoiceCacheForTests();
  const h = clipHash("en", "Hello world");
  serve({
    "/voice-assets/voices.json": { voices: [{ id: "channarith", label: "C", ai_label: "x", active: false }] },
    "/voice-assets/channarith/index.json": { ext: "mp3", clips: { en: [h] } },
  });
  assert.deepEqual(await loadCloneVoices(), []);
  assert.equal(await cloneClipUrl("en", "Hello world", "channarith"), null);
});

test("no published assets means no voices and no clip, without throwing", async () => {
  resetCloneVoiceCacheForTests();
  serve({});
  assert.deepEqual(await loadCloneVoices(), []);
  assert.equal(await cloneClipUrl("en", "Hello world", "channarith"), null);
});
