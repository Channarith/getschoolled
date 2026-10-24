import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
const MOD = "../src/theodore_children_webcam_lab/static/clone_voice.js";
globalThis.window = { CLONE_VOICE_ASSETS: "/voice-assets" };
const { clipHash, cloneClipUrl, resetForTests } = await import(MOD);
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
console.log("clone_voice ok");
