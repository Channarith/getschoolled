import { DEFAULT_VOICE_ID, cloneClipUrl, clipHash, defaultCloneVoice, resetCloneVoiceCacheForTests, resolveSelectedVoice, resolveVoice, salaneVoiceLabel, selectedCloneGender, explicitEdgeVoice } from "../cloneVoice";

const mockStore: Record<string, string> = {};
let mockSettings: { voiceId: string } = { voiceId: "" };
jest.mock("@react-native-async-storage/async-storage", () => ({
  __esModule: true,
  default: {
    getItem: jest.fn(async (k: string) => (k in mockStore ? mockStore[k] : null)),
    setItem: jest.fn(async (k: string, v: string) => { mockStore[k] = v; }),
  },
}));
jest.mock("../storage", () => ({ getSettings: async () => mockSettings }));

const BASE = "https://salareen-prod.sjc1.vultrobjects.com/voice-assets";
const SAGE = { id: "stock-f-young-warm", label: "Sage (designed)", name: "Sage", ai_label: "AI-generated voice (designed with VoxCPM2)", active: true, default: true, gender: "female" as const, primary_lang: "en", kind: "stock" as const };
const CHAN = { id: "channarith", label: "Channarith (English)", name: "Channarith", ai_label: "x", active: true, gender: "male" as const, primary_lang: "en" };

function serve(files: Record<string, unknown>) {
  (globalThis as { fetch: unknown }).fetch = async (url: string) => (url in files ? { ok: true, json: async () => files[url] } : { ok: false, json: async () => ({}) });
}
function reset(store: Record<string, string> = {}, voiceId = "") {
  for (const k of Object.keys(mockStore)) delete mockStore[k];
  Object.assign(mockStore, store);
  mockSettings = { voiceId };
  resetCloneVoiceCacheForTests();
}

describe("Sage as the default Salane Voice (same rules as the site)", () => {
  it("a learner who never chose gets the published default", () => {
    expect(resolveVoice({ saved: null, edgeVoice: "", tone: "", voices: [CHAN, SAGE] })).toBe(SAGE.id);
    expect(defaultCloneVoice([CHAN, SAGE])?.id).toBe(SAGE.id);
    expect(salaneVoiceLabel([CHAN, SAGE])).toBe("Salane Voice (Sage)");
    expect(salaneVoiceLabel([])).toBe("Salane Voice");
  });

  it("the old automatic voice migrates to Sage; a deliberate choice wins", () => {
    expect(resolveVoice({ saved: "default", edgeVoice: "", tone: "", voices: [CHAN, SAGE] })).toBe(SAGE.id);
    expect(resolveVoice({ saved: "default", edgeVoice: "en-GB-RyanNeural", tone: "", voices: [CHAN, SAGE] })).toBe(DEFAULT_VOICE_ID);
    expect(resolveVoice({ saved: "channarith", edgeVoice: "", tone: "", voices: [CHAN, SAGE] })).toBe("channarith");
    expect(resolveVoice({ saved: "gone", edgeVoice: "", tone: "", voices: [CHAN, SAGE] })).toBe(SAGE.id);
    expect(resolveVoice({ saved: null, edgeVoice: "", tone: "", voices: [] })).toBe(DEFAULT_VOICE_ID);
    expect(resolveVoice({ saved: null, edgeVoice: "", tone: "", voices: [CHAN] })).toBe(DEFAULT_VOICE_ID);
  });

  it("an accent voice the app wrote itself is not a choice; a Microsoft voice name or the marker is", async () => {
    reset({}, "en_gb_f");
    expect(await explicitEdgeVoice()).toBe("");
    reset({ aoep_voice_explicit: "1" }, "en_gb_f");
    expect(await explicitEdgeVoice()).toBe("en_gb_f");
    reset({}, "en-US-AriaNeural");
    expect(await explicitEdgeVoice()).toBe("en-US-AriaNeural");
    reset({ aoep_voice_explicit: "0" }, "en-US-AriaNeural");
    expect(await explicitEdgeVoice()).toBe("");
  });

  it("no saved choice: the clip URL is Sage's, and the fallback gender is female", async () => {
    reset();
    const h = clipHash("en", "Welcome to the lesson.");
    serve({
      [`${BASE}/voices.json`]: { voices: [CHAN, SAGE] },
      [`${BASE}/stock-f-young-warm/index.json`]: { ext: "mp3", clips: { en: [h] } },
      [`${BASE}/channarith/index.json`]: { ext: "mp3", clips: { en: [h] } },
    });
    expect(await resolveSelectedVoice()).toBe(SAGE.id);
    expect(await cloneClipUrl("en", "Welcome to the lesson.")).toBe(`${BASE}/stock-f-young-warm/en/${h}.mp3`);
    expect(await selectedCloneGender()).toBe("female");
    expect(await cloneClipUrl("en", "A line that was never rendered.")).toBeNull();
    expect(await cloneClipUrl("es", "Una línea en español.")).toBeNull();
    reset({ aoep_demo_voice: "default" });
    expect(await cloneClipUrl("en", "Welcome to the lesson.")).toBe(`${BASE}/stock-f-young-warm/en/${h}.mp3`);
    reset({ aoep_demo_voice: "default", aoep_voice_explicit: "1" }, "en-GB-RyanNeural");
    expect(await cloneClipUrl("en", "Welcome to the lesson.")).toBeNull();
    reset({ aoep_demo_voice: "channarith" });
    expect(await cloneClipUrl("en", "Welcome to the lesson.")).toBe(`${BASE}/channarith/en/${h}.mp3`);
    expect(await selectedCloneGender()).toBe("male");
  });

  it("nothing published: the live voice speaks and nothing throws", async () => {
    reset();
    serve({});
    expect(await resolveSelectedVoice()).toBe(DEFAULT_VOICE_ID);
    expect(await cloneClipUrl("en", "Hello")).toBeNull();
    expect(await selectedCloneGender()).toBe("");
  });
});
