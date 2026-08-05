/**
 * Mic feedback: the device must visibly react while you speak.
 *
 * Reported symptom: "when I click to speak, it doesn't appear to show the
 * device listening". Two causes are pinned here:
 *   1. interim speech was never surfaced, so nothing changed on screen until
 *      the whole utterance was submitted;
 *   2. a "no-speech" result was swallowed silently, so a capture that heard
 *      nothing looked identical to one that was still listening.
 */

const listeners: Record<string, (event: Record<string, unknown>) => void> = {};

const mockSpeech = {
  start: jest.fn(),
  stop: jest.fn(),
  abort: jest.fn(),
  addSpeechRecognitionListener: jest.fn((name: string, cb: (e: Record<string, unknown>) => void) => {
    listeners[name] = cb;
    return { remove: jest.fn() };
  }),
  isRecognitionAvailable: jest.fn().mockReturnValue(true),
  getStateAsync: jest.fn().mockResolvedValue("inactive"),
  requestPermissionsAsync: jest.fn().mockResolvedValue({ granted: true }),
  getPermissionsAsync: jest.fn().mockResolvedValue({ granted: true }),
};

jest.mock("../nativeModules", () => ({
  isExpoSpeechRecognitionAvailable: () => true,
  // voiceAssistant pulls the native module through tryRequireModule and reads
  // both the listener API and ExpoSpeechRecognitionModule off the same object.
  tryRequireModule: () => ({
    ExpoSpeechRecognitionModule: mockSpeech,
    addSpeechRecognitionListener: mockSpeech.addSpeechRecognitionListener,
  }),
}));

jest.mock("react-native", () => ({ Platform: { OS: "ios" } }));

import { startVoiceListening, stopVoiceListening } from "../voiceAssistant";

describe("deliberate tap-to-speak capture", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    for (const key of Object.keys(listeners)) delete listeners[key];
  });

  afterEach(() => stopVoiceListening());

  it("reports interim speech so the UI can show what it is hearing", async () => {
    const onPartial = jest.fn();
    const onResult = jest.fn();

    const started = await startVoiceListening({
      locale: "en",
      autoSubmitOnPause: true,
      pauseSubmitMs: 4500,
      onPartial,
      onResult,
      onError: jest.fn(),
      onEnd: jest.fn(),
    });
    expect(started).toBe(true);

    listeners.result?.({ results: [{ transcript: "what is" }], isFinal: false });
    listeners.result?.({ results: [{ transcript: "what is photosynthesis" }], isFinal: false });

    expect(onPartial).toHaveBeenCalledWith("what is");
    expect(onPartial).toHaveBeenLastCalledWith("what is photosynthesis");
    // Still mid-sentence: nothing submitted yet.
    expect(onResult).not.toHaveBeenCalled();
  });

  it("tells the learner when it heard nothing instead of failing silently", async () => {
    const onError = jest.fn();
    await startVoiceListening({
      locale: "en",
      autoSubmitOnPause: true,
      onPartial: jest.fn(),
      onResult: jest.fn(),
      onError,
      onEnd: jest.fn(),
    });

    listeners.error?.({ error: "no-speech" });
    expect(onError).toHaveBeenCalledWith("no_speech");
  });

  it("stays quiet about no-speech while ambient hands-free idles", async () => {
    const onError = jest.fn();
    await startVoiceListening({
      locale: "en",
      // Ambient listening: silence is the normal state, not a failure.
      autoSubmitOnPause: false,
      continuous: true,
      onPartial: jest.fn(),
      onResult: jest.fn(),
      onError,
      onEnd: jest.fn(),
    });

    listeners.error?.({ error: "no-speech" });
    expect(onError).not.toHaveBeenCalled();
  });

  it("never reports our own stop as an error", async () => {
    const onError = jest.fn();
    await startVoiceListening({
      locale: "en",
      autoSubmitOnPause: true,
      onPartial: jest.fn(),
      onResult: jest.fn(),
      onError,
      onEnd: jest.fn(),
    });

    listeners.error?.({ error: "aborted" });
    expect(onError).not.toHaveBeenCalled();
  });
});
