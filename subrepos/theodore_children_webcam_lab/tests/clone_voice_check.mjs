import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
const MOD = "../src/theodore_children_webcam_lab/static/clone_voice.js";
globalThis.window = { CLONE_VOICE_ASSETS: "/voice-assets" };
const { clipHash, cloneClipUrl, resetForTests, resolveVoice, resolveSelectedVoice } = await import(MOD);
delete globalThis.window;
const dflt = await import(MOD + "?default");   // no override: the Vultr Object Storage URL is the default
let probed = ""; globalThis.fetch = async (u) => { probed = u; return { ok: false, json: async () => ({}) }; };
await dflt.cloneClipUrl("en", "x", "channarith");
assert.ok(probed.startsWith("https://salareen-prod.sjc1.vultrobjects.com/voice-assets/"), probed);

const vectors = JSON.parse(readFileSync(new URL("./hash_vectors.json", import.meta.url), "utf8"));
for (const c of vectors.cases) assert.equal(clipHash(c.lang, c.text), c.hash, `${c.lang} ${c.text}`);

const serve = (files) => { globalThis.fetch = async (u) => (u in files ? { ok: true, json: async () => files[u] } : { ok: false, json: async () => ({}) }); };
const h = clipHash("en", "Freeze!. Hold still like a statue!");
serve({ "/voice-assets/voices.json": { voices: [{ id: "channarith", label: "C", active: true }] }, "/voice-assets/channarith/index.json": { ext: "mp3", clips: { en: [h] } } });
assert.equal(await cloneClipUrl("en", "Freeze!. Hold  still like a statue!", "channarith"), `/voice-assets/channarith/en/${h}.mp3`);
assert.equal(await cloneClipUrl("en", "Freeze!. Hold still like a statue!", "default"), null);
assert.equal(await cloneClipUrl("en", "never rendered", "channarith"), null);
resetForTests();
serve({ "/voice-assets/voices.json": { voices: [{ id: "channarith", label: "C", active: false }] }, "/voice-assets/channarith/index.json": { ext: "mp3", clips: { en: [h] } } });
assert.equal(await cloneClipUrl("en", "Freeze!. Hold still like a statue!", "channarith"), null, "revoked voice must never resolve");
resetForTests();
serve({});
assert.equal(await cloneClipUrl("en", "x", "channarith"), null);

// ---- the published default (Sage) narrates when nothing was chosen on purpose -----------------------------------------------------
const SAGE = { id: "stock-f-young-warm", label: "Sage (designed)", name: "Sage", active: true, default: true, gender: "female" };
const CHAN = { id: "channarith", label: "C", active: true };
assert.equal(resolveVoice({ saved: null, edgeVoice: "", tone: "", voices: [CHAN, SAGE] }), SAGE.id);
assert.equal(resolveVoice({ saved: "default", edgeVoice: "", tone: "", voices: [CHAN, SAGE] }), SAGE.id, "the old automatic voice migrates to Sage");
assert.equal(resolveVoice({ saved: "default", edgeVoice: "en-GB-RyanNeural", tone: "", voices: [CHAN, SAGE] }), "default");
assert.equal(resolveVoice({ saved: null, edgeVoice: "", tone: "anime", voices: [CHAN, SAGE] }), "default", "a tone means the live edge voice");
assert.equal(resolveVoice({ saved: "channarith", edgeVoice: "", tone: "", voices: [CHAN, SAGE] }), "channarith");
assert.equal(resolveVoice({ saved: "gone", edgeVoice: "", tone: "", voices: [CHAN, SAGE] }), SAGE.id, "a withdrawn voice falls back to the default");
assert.equal(resolveVoice({ saved: null, edgeVoice: "", tone: "", voices: [CHAN] }), "default", "no default published: the live edge voice");
resetForTests();
const hs = clipHash("en", "Hold still like a statue!");
serve({ "/voice-assets/voices.json": { voices: [CHAN, SAGE] }, "/voice-assets/stock-f-young-warm/index.json": { ext: "mp3", clips: { en: [hs] } } });
const store = {};
globalThis.localStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
assert.equal(await resolveSelectedVoice(), SAGE.id);
assert.equal(await cloneClipUrl("en", "Hold still like a statue!"), `/voice-assets/stock-f-young-warm/en/${hs}.mp3`);
assert.equal(await cloneClipUrl("en", "A line that was never rendered."), null, "no clip: the caller falls back to the default server voice");
assert.equal(await cloneClipUrl("es", "Quédate quieto como una estatua."), null, "Sage is cleared for English only");
store.aoep_drive_voice = "en-GB-RyanNeural";
assert.equal(await cloneClipUrl("en", "Hold still like a statue!"), null, "an edge voice picked on purpose wins");
store.aoep_voice_explicit = "0";   // the Salane Voice picked on purpose afterwards
assert.equal(await cloneClipUrl("en", "Hold still like a statue!"), `/voice-assets/stock-f-young-warm/en/${hs}.mp3`);
delete globalThis.localStorage;
console.log("clone_voice ok");
