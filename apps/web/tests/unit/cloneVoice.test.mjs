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

// ---- Sage as the default Salane Voice ------------------------------------------------------------------------------------------
import { defaultCloneVoice, explicitEdgeVoice, resolveSelectedVoice, resolveVoice, salaneVoiceLabel, selectedCloneGender } from "../../app/lib/cloneVoice.ts";

const SAGE = { id: "stock-f-young-warm", label: "Sage (designed)", name: "Sage", ai_label: "AI-generated voice (designed with VoxCPM2)", active: true, default: true, gender: "female", primary_lang: "en", kind: "stock" };
const CHAN = { id: "channarith", label: "Channarith (English)", name: "Channarith", ai_label: "x", active: true, gender: "male", primary_lang: "en" };
const voices = [CHAN, SAGE];

function browser(store = {}) {
  const data = { ...store };
  globalThis.window = { dispatchEvent() {} };
  globalThis.localStorage = { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, removeItem: (k) => { delete data[k]; } };
  return data;
}

test("a visitor who never chose gets the published default (Sage)", () => {
  assert.equal(resolveVoice({ saved: null, edgeVoice: "", tone: "", voices }), SAGE.id);
  assert.equal(defaultCloneVoice(voices).id, SAGE.id);
  assert.equal(salaneVoiceLabel(voices), "Salane Voice (Sage)");
});

test("the old automatic voice ('default') migrates to Sage; only a deliberate choice stays", () => {
  assert.equal(resolveVoice({ saved: "default", edgeVoice: "", tone: "", voices }), SAGE.id);
  assert.equal(resolveVoice({ saved: "default", edgeVoice: "en-GB-SoniaNeural", tone: "", voices }), DEFAULT_VOICE_ID, "an edge voice picked on purpose wins");
  assert.equal(resolveVoice({ saved: "channarith", edgeVoice: "en-GB-SoniaNeural", tone: "", voices }), "channarith", "a company voice picked on purpose wins");
  assert.equal(resolveVoice({ saved: null, edgeVoice: "", tone: "anime", voices }), DEFAULT_VOICE_ID, "pre-rendered Sage is the plain voice: a tone means the live edge voice");
  assert.equal(resolveVoice({ saved: null, edgeVoice: "", tone: "neutral", voices }), SAGE.id);
});

test("a stale or withdrawn saved voice falls back to the default, not to silence", () => {
  assert.equal(resolveVoice({ saved: "gone-voice", edgeVoice: "", tone: "", voices }), SAGE.id);
  assert.equal(resolveVoice({ saved: "channarith", edgeVoice: "", tone: "", voices: [{ ...CHAN, active: false }, SAGE] }), SAGE.id);
});

test("with nothing published (offline, nothing cleared) the live edge voice speaks", () => {
  assert.equal(resolveVoice({ saved: null, edgeVoice: "", tone: "", voices: [] }), DEFAULT_VOICE_ID);
  assert.equal(salaneVoiceLabel([]), "Salane Voice");
  assert.equal(resolveVoice({ saved: null, edgeVoice: "", tone: "", voices: [CHAN] }), DEFAULT_VOICE_ID, "no default flag, no default voice");
  assert.equal(resolveVoice({ saved: null, edgeVoice: "", tone: "", voices: [{ ...SAGE, active: false }] }), DEFAULT_VOICE_ID);
});

test("an edge voice id the app wrote to follow the language is not a deliberate choice", () => {
  browser({ aoep_drive_voice: "en_gb_f" });
  assert.equal(explicitEdgeVoice(), "");
  browser({ aoep_drive_voice: "en_gb_f", aoep_voice_explicit: "1" });
  assert.equal(explicitEdgeVoice(), "en_gb_f");
  browser({ aoep_drive_voice: "en-US-AriaNeural" });
  assert.equal(explicitEdgeVoice(), "en-US-AriaNeural", "a Microsoft voice name only gets there by picking it");
  browser({ aoep_drive_voice: "en-US-AriaNeural", aoep_voice_explicit: "0" });
  assert.equal(explicitEdgeVoice(), "", "the Salane Voice was picked on purpose afterwards");
});

test("no saved choice: the clip URL is Sage's; an explicit edge voice or a saved voice wins", async () => {
  resetCloneVoiceCacheForTests();
  const h = clipHash("en", "Welcome to the lesson.");
  serve({
    "/voice-assets/voices.json": { voices },
    "/voice-assets/stock-f-young-warm/index.json": { ext: "mp3", clips: { en: [h] } },
    "/voice-assets/channarith/index.json": { ext: "mp3", clips: { en: [h] } },
  });
  browser({});
  assert.equal(await resolveSelectedVoice(), SAGE.id);
  assert.equal(await cloneClipUrl("en", "Welcome to the lesson."), `/voice-assets/stock-f-young-warm/en/${h}.mp3`);
  assert.equal(await selectedCloneGender(), "female");
  browser({ aoep_demo_voice: "default" });
  assert.equal(await cloneClipUrl("en", "Welcome to the lesson."), `/voice-assets/stock-f-young-warm/en/${h}.mp3`, "chose auto before: migrated");
  browser({ aoep_demo_voice: "default", aoep_drive_voice: "en-GB-RyanNeural" });
  assert.equal(await cloneClipUrl("en", "Welcome to the lesson."), null, "edge voice on purpose: no clip, the live edge voice speaks");
  browser({ aoep_demo_voice: "channarith" });
  assert.equal(await cloneClipUrl("en", "Welcome to the lesson."), `/voice-assets/channarith/en/${h}.mp3`);
  assert.equal(await selectedCloneGender(), "male");
});

test("a line Sage has no clip for resolves to null so the caller falls back to a same-gender edge voice in the same language", async () => {
  resetCloneVoiceCacheForTests();
  serve({
    "/voice-assets/voices.json": { voices },
    "/voice-assets/stock-f-young-warm/index.json": { ext: "mp3", clips: { en: [clipHash("en", "Other line.")] } },
  });
  browser({});
  assert.equal(await cloneClipUrl("en", "A line that was never rendered."), null);
  assert.equal(await cloneClipUrl("es", "Una línea en español."), null, "Sage is cleared for English only");
  assert.equal(await selectedCloneGender(), "female", "the fallback edge voice is female, like Sage");
});

test("a slow voices.json does not hold the first narrated line for more than a moment", async () => {
  resetCloneVoiceCacheForTests();
  globalThis.fetch = () => new Promise(() => {});   // never answers
  browser({});
  const t0 = Date.now();
  assert.equal(await resolveSelectedVoice(), DEFAULT_VOICE_ID);
  assert.ok(Date.now() - t0 < 2500);
});
