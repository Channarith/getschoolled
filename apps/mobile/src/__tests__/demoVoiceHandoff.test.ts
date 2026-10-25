import { demoVoiceHandoffScript } from "../publicDemos";

function run(script: string) {
  const store: Record<string, string> = {};
  const localStorage = { setItem: (k: string, v: string) => { store[k] = v; }, removeItem: (k: string) => { delete store[k]; } };
  // eslint-disable-next-line no-new-func
  new Function("localStorage", script)(localStorage);
  return store;
}

describe("demoVoiceHandoffScript", () => {
  test("copies the app's voice choices into the page's storage under the site's keys", () => {
    expect(run(demoVoiceHandoffScript({ cloneVoice: "channarith", voiceId: "en-US-AvaNeural", agent: "xai" }))).toEqual({
      aoep_demo_voice: "channarith",
      aoep_drive_voice: "en-US-AvaNeural",
      aoep_live_voice_engine: "xai",
    });
  });

  test("defaults: default custom voice, no catalog voice, Salane engine", () => {
    expect(run(demoVoiceHandoffScript({}))).toEqual({ aoep_demo_voice: "default", aoep_live_voice_engine: "salane" });
  });

  test("a stale catalog voice in the page is removed when the app has none selected", () => {
    const store: Record<string, string> = { aoep_drive_voice: "old" };
    const ls = { setItem: (k: string, v: string) => { store[k] = v; }, removeItem: (k: string) => { delete store[k]; } };
    // eslint-disable-next-line no-new-func
    new Function("localStorage", demoVoiceHandoffScript({ voiceId: "" }))(ls);
    expect(store.aoep_drive_voice).toBeUndefined();
  });

  test("values are quoted safely", () => {
    const store = run(demoVoiceHandoffScript({ cloneVoice: 'x"); alert(1); ("', voiceId: "a'b" }));
    expect(store.aoep_demo_voice).toBe('x"); alert(1); ("');
    expect(store.aoep_drive_voice).toBe("a'b");
  });
});
