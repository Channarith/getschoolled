import { liveAudioPhoneScript } from "../liveAudioPhone";

describe("phone live audio chip", () => {
  test("shrinks the voice panel, lets it be dragged, and lifts quiet playback", () => {
    const script = liveAudioPhoneScript();
    expect(script).toContain("theodore-live-audio");
    expect(script).toContain("aoep.liveAudio.pos");
    expect(script).toContain("pointerdown");
    expect(script).toContain("__SALAREEN_LIVE_GAIN__");
    expect(script).toContain("2.6");
    expect(script).toContain("xAI");
  });
});
