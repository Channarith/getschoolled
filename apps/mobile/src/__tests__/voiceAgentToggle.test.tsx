import { fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";

import VoiceAgentToggle, { lessonVoiceButtonKey } from "../components/VoiceAgentToggle";
import { translateWith } from "../i18n";
import { setSettings } from "../storage";
import { useXaiClassVoice } from "../useXaiClassVoice";
import {
  getStoredVoiceAgent,
  loadVoiceAgentChoice,
  publicVoiceError,
  resolveVoiceAgent,
  saveVoiceAgentChoice,
} from "../voiceAgentPref";

const mockSpeakNatural = jest.fn();
jest.mock("../tts", () => ({
  speakNatural: (...args: unknown[]) => mockSpeakNatural(...args),
  stopSpeech: jest.fn(),
}));

jest.mock("../xaiPcmPlayer", () => ({
  createPcmQueue: () => ({
    push: jest.fn(),
    stop: jest.fn(),
    flush: (after?: () => void) => after?.(),
  }),
}));

const session = { mode: "solo" as const, context: "Fractions", language: "en" };

beforeEach(async () => {
  await AsyncStorage.clear();
  mockSpeakNatural.mockClear();
});

test("voice agent choice persists and defaults to Sala", async () => {
  expect(await getStoredVoiceAgent()).toBeNull();
  expect(resolveVoiceAgent(null, { engine: "salane", available: true })).toBe("sala");
  expect(resolveVoiceAgent(null, { engine: "none", available: false })).toBe("sala");
  expect(resolveVoiceAgent(null, { engine: "xai", available: true })).toBe("xai");
  expect(resolveVoiceAgent("sala", { engine: "xai", available: true })).toBe("sala");

  await setSettings({ dailyReminder: false });
  expect(await getStoredVoiceAgent()).toBeNull();

  await saveVoiceAgentChoice("xai");
  expect(await getStoredVoiceAgent()).toBe("xai");
  expect(await loadVoiceAgentChoice()).toBe("xai");

  await saveVoiceAgentChoice("sala");
  expect(await getStoredVoiceAgent()).toBe("sala");
  expect(await loadVoiceAgentChoice()).toBe("sala");
});

test("xAI errors stay public and do not fall through to Sala", async () => {
  const secret = "xai-supersecretvalue123456";
  expect(publicVoiceError(
    `xAI voice token failed (503): {"detail":"xAI Voice Agent is unavailable. Switch back to Sala."}`,
    "fallback",
  )).toBe("xAI Voice Agent is unavailable. Switch back to Sala.");
  expect(publicVoiceError(`bearer ${secret}`, "fallback")).toBe("fallback");

  const fetchMock = jest.fn(async (_url: string, init?: { body?: string }) => {
    const body = JSON.parse(init?.body || "{}");
    expect(body.engine).toBe("xai");
    expect(JSON.stringify(body)).not.toContain(secret);
    return {
      ok: false,
      status: 503,
      text: async () => JSON.stringify({
        detail: "xAI Voice Agent is unavailable. Switch back to Sala.",
      }),
    };
  });
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  const { result } = renderHook(() => useXaiClassVoice(true, session, "xai"));
  await waitFor(() => expect(result.current.phase).toBe("unavailable"));
  expect(result.current.agent).toBe("xai");
  expect(result.current.hint).toMatch(/Switch back to Sala/);
  expect(mockSpeakNatural).not.toHaveBeenCalled();
  expect(fetchMock).toHaveBeenCalled();

  const fallback = jest.fn();
  result.current.speakLatest("slide-1", "Read this slide", { fallback });
  expect(fallback).not.toHaveBeenCalled();
  expect(mockSpeakNatural).not.toHaveBeenCalled();
});

test("Sala routes to narration and does not mint an xAI session", async () => {
  const fetchMock = jest.fn();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  const { result } = renderHook(() => useXaiClassVoice(true, session, "sala"));
  await waitFor(() => expect(result.current.phase).toBe("live"));
  expect(result.current.agent).toBe("sala");
  expect(result.current.hint).toBe("Sala is using Salane Voice.");
  expect(fetchMock).not.toHaveBeenCalled();
  result.current.speakLatest("slide-1", "Hello class");
  expect(mockSpeakNatural).toHaveBeenCalled();
});

test("the selector shows Sala and xAI Voice Agent", () => {
  const onChange = jest.fn();
  render(<VoiceAgentToggle value="sala" onChange={onChange} />);
  expect(screen.getByText("Sala")).toBeTruthy();
  expect(screen.getByText("xAI Voice Agent")).toBeTruthy();
  fireEvent.press(screen.getByTestId("voice-agent-xai"));
  expect(onChange).toHaveBeenCalledWith("xai");
  expect(lessonVoiceButtonKey("xai", true, "unavailable")).toBe("lesson.xaiUnavailable");
  expect(lessonVoiceButtonKey("sala", true, "live")).toBe("lesson.salaOn");
  expect(translateWith("nl", "settings.voiceAgentXai")).toBe("xAI Voice Agent");
  // Dutch now has a machine translation (machineFill.json) instead of falling back to English; the brand names must survive it.
  expect(translateWith("nl", "voice.xaiUnavailable")).toMatch(/Sala/);
  expect(translateWith("nl", "voice.xaiUnavailable")).not.toMatch(/Switch back to Sala/);
});
