import {
  appleConfigForLiveRoom,
  applyLiveKitAudioRoute,
  beginLiveKitAudio,
  endLiveKitAudio,
  ensureLiveRoomNarrationRoute,
  liveKitAudioActive,
  type LiveKitAudioSession,
} from "../components/liveKitAudio";

function mockSession(): LiveKitAudioSession & {
  configureAudio: jest.Mock;
  startAudioSession: jest.Mock;
  stopAudioSession: jest.Mock;
  setAppleAudioConfiguration: jest.Mock;
  selectAudioOutput: jest.Mock;
} {
  return {
    configureAudio: jest.fn(async () => undefined),
    startAudioSession: jest.fn(async () => undefined),
    stopAudioSession: jest.fn(async () => undefined),
    setAppleAudioConfiguration: jest.fn(async () => undefined),
    selectAudioOutput: jest.fn(async () => undefined),
  };
}

describe("appleConfigForLiveRoom", () => {
  it("uses playback + spokenAudio when the mic is off (teacher TTS path)", () => {
    expect(appleConfigForLiveRoom(false)).toEqual({
      audioCategory: "playback",
      audioCategoryOptions: ["mixWithOthers"],
      audioMode: "spokenAudio",
    });
  });

  it("uses playAndRecord + defaultToSpeaker when the mic is on", () => {
    const cfg = appleConfigForLiveRoom(true);
    expect(cfg.audioCategory).toBe("playAndRecord");
    expect(cfg.audioMode).toBe("videoChat");
    expect(cfg.audioCategoryOptions).toContain("defaultToSpeaker");
    expect(cfg.audioCategoryOptions).toContain("mixWithOthers");
  });
});

describe("liveKitAudio bridge", () => {
  afterEach(async () => {
    await endLiveKitAudio();
  });

  it("tracks active session and forces speaker after begin", async () => {
    const s = mockSession();
    expect(liveKitAudioActive()).toBe(false);
    await beginLiveKitAudio(s, { micEnabled: false });
    expect(liveKitAudioActive()).toBe(true);
    expect(s.configureAudio).toHaveBeenCalled();
    expect(s.setAppleAudioConfiguration).toHaveBeenCalledWith(
      appleConfigForLiveRoom(false),
    );
  });

  it("switches to mic config when applyLiveKitAudioRoute(true)", async () => {
    const s = mockSession();
    await beginLiveKitAudio(s, { micEnabled: false });
    s.setAppleAudioConfiguration.mockClear();
    await applyLiveKitAudioRoute(true);
    expect(s.setAppleAudioConfiguration).toHaveBeenCalledWith(
      appleConfigForLiveRoom(true),
    );
  });

  it("ensureLiveRoomNarrationRoute is a no-op without an active session", async () => {
    const s = mockSession();
    await ensureLiveRoomNarrationRoute();
    expect(s.setAppleAudioConfiguration).not.toHaveBeenCalled();
  });

  it("endLiveKitAudio clears the active session", async () => {
    const s = mockSession();
    await beginLiveKitAudio(s);
    await endLiveKitAudio();
    expect(liveKitAudioActive()).toBe(false);
  });
});
