import AsyncStorage from "@react-native-async-storage/async-storage";

import { clipHash, cloneClipUrl, resetCloneVoiceCacheForTests, setSelectedVoice } from "../cloneVoice";

jest.mock("@react-native-async-storage/async-storage", () => {
  const store: Record<string, string> = {};
  return {
    __esModule: true,
    default: {
      getItem: jest.fn(async (k: string) => (k in store ? store[k] : null)),
      setItem: jest.fn(async (k: string, v: string) => { store[k] = v; }),
    },
  };
});

// Copy of tts_manifest/hash_vectors.json (a Python test keeps this list in sync).
const vectors = { cases: [
  {"lang": "en", "text": "Hello world", "hash": "02fef90579b6a3"},
  {"lang": "en", "text": "  Hello \n world  ", "hash": "02fef90579b6a3"},
  {"lang": "zh-CN", "text": "你好！欢迎来到今天的课程。", "hash": "0d9c652e907e1a"},
  {"lang": "km", "text": "សូមស្វាគមន៍មកកាន់មេរៀនរបស់អ្នក។", "hash": "14be88f30d34be"},
  {"lang": "es", "text": "Visión general. Bienvenidos.", "hash": "092c52511e4094"},
  {"lang": "en", "text": "emoji 😀 pair", "hash": "11c87f95b37626"},
  {"lang": "th", "text": "ยินดีต้อนรับ", "hash": "0dfdfeab7313bf"},
  {"lang": "en", "text": "a b　c", "hash": "10c737c68a5030"}
] };

function serve(files: Record<string, unknown>) {
  (globalThis as { fetch: unknown }).fetch = async (url: string) =>
    (url in files ? { ok: true, json: async () => files[url] } : { ok: false, json: async () => ({}) });
}
const BASE = "https://salareen-prod.sjc1.vultrobjects.com/voice-assets";

describe("cloneVoice", () => {
  beforeEach(() => resetCloneVoiceCacheForTests());

  it("hashes exactly like the Python and web code", () => {
    for (const c of vectors.cases) expect(clipHash(c.lang, c.text)).toBe(c.hash);
  });

  it("uses the default voice until one is chosen", async () => {
    serve({});
    expect(await cloneClipUrl("en", "Hello world")).toBeNull();
    expect(AsyncStorage.getItem).toHaveBeenCalled();
  });

  it("resolves the clip for a chosen, active voice and falls back on a miss", async () => {
    const h = clipHash("en", "Hello world");
    serve({
      [`${BASE}/voices.json`]: { voices: [{ id: "channarith", label: "C", ai_label: "AI", active: true }] },
      [`${BASE}/channarith/index.json`]: { ext: "mp3", clips: { en: [h] } },
    });
    await setSelectedVoice("channarith");
    expect(await cloneClipUrl("en", "Hello   world")).toBe(`${BASE}/channarith/en/${h}.mp3`);
    expect(await cloneClipUrl("en", "not rendered")).toBeNull();
  });

  it("never resolves a revoked voice", async () => {
    const h = clipHash("en", "Hello world");
    serve({
      [`${BASE}/voices.json`]: { voices: [{ id: "channarith", label: "C", ai_label: "AI", active: false }] },
      [`${BASE}/channarith/index.json`]: { ext: "mp3", clips: { en: [h] } },
    });
    await setSelectedVoice("channarith");
    expect(await cloneClipUrl("en", "Hello world")).toBeNull();
  });
});
