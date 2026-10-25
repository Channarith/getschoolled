import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import HomeFooter from "../components/HomeFooter";

const mockSetSelectedVoice = jest.fn(async () => {});
const mockSetSettings = jest.fn(async (patch: object) => ({ voiceId: "", instructorId: "", voiceGender: "female", ...patch }));

jest.mock("../i18n", () => ({
  LANGUAGES: [{ code: "en", flag: "US", native: "English" }, { code: "km", flag: "KH", native: "Khmer" }],
  languageInfo: () => ({ code: "en", flag: "US", native: "English" }),
  useT: () => ({
    locale: "en", setLocale: jest.fn(),
    t: (key: string) => ({
      "voice.defaultAuto": "Default (auto)", "voice.customGroup": "Custom voices (AI-generated)", "voice.footerTitle": "Language and voice",
      "settings.language": "Language", "settings.sectionVoice": "Voice", "settings.voiceAgent": "Live voice", "settings.voiceAgentSala": "Salane Voice (default)",
      "settings.voiceAgentXai": "xAI Voice Agent (opt-in)",
    } as Record<string, string>)[key] ?? key,
  }),
}));
jest.mock("../cloneVoice", () => ({
  DEFAULT_VOICE_ID: "default",
  loadCloneVoices: async () => [{ id: "channarith", label: "Channarith", ai_label: "AI-generated voice of Channarith", active: true }],
  cloneVoiceLanguages: async () => ["en"],
  getSelectedVoice: async () => "default",
  setSelectedVoice: (...a: unknown[]) => (mockSetSelectedVoice as (...x: unknown[]) => Promise<void>)(...a),
}));
jest.mock("../narrationTts", () => ({
  applyVoicePrefsToTts: jest.fn(),
  voicePrefsFromSettings: (s: object) => s,
  loadVoiceCatalog: async () => [{ language: "en", voices: [
    { id: "en-US-AvaNeural", locale: "en-US", accent: "American", label: "American — Ava (F)", gender: "female", language: "en", dialect: "" },
    { id: "en-US-GuyNeural", locale: "en-US", accent: "American", label: "American — Guy (M)", gender: "male", language: "en", dialect: "" },
  ] }],
}));
jest.mock("../storage", () => ({
  getSettings: async () => ({ voiceId: "", instructorId: "", voiceGender: "female" }),
  setSettings: (p: object) => mockSetSettings(p),
}));
jest.mock("../voiceAgentPref", () => ({
  loadVoiceAgentChoice: async () => "sala", saveVoiceAgentChoice: async () => "sala", subscribeVoiceAgent: () => () => {},
}));

test("the footer lists language, then one voice dropdown with custom voices and (F)/(M) voices, and no Any/Female/Male filter", async () => {
  const screen = render(<HomeFooter />);
  expect(screen.getByTestId("home-footer")).toBeTruthy();
  expect(screen.queryByText("Any")).toBeNull();
  expect(screen.queryByText("Female")).toBeNull();
  expect(screen.queryByText("Male")).toBeNull();
  expect(screen.getByText("Salane Voice (default)")).toBeTruthy();

  fireEvent.press(screen.getByText("Voice"));   // open the voice dropdown
  await waitFor(() => expect(screen.getByText("Channarith (English) · AI-generated voice")).toBeTruthy());
  expect(screen.getByText("CUSTOM VOICES (AI-GENERATED)")).toBeTruthy();
  expect(screen.getByText("American · American — Ava (F)")).toBeTruthy();
  expect(screen.getByText("American · American — Guy (M)")).toBeTruthy();

  fireEvent.press(screen.getByText("Channarith (English) · AI-generated voice"));
  await waitFor(() => expect(mockSetSelectedVoice).toHaveBeenCalledWith("channarith"));

  fireEvent.press(screen.getByText("Voice"));
  fireEvent.press(await screen.findByText("American · American — Guy (M)"));
  await waitFor(() => expect(mockSetSettings).toHaveBeenCalledWith({ voiceId: "en-US-GuyNeural", voiceGender: "male" }));
  expect(mockSetSelectedVoice).toHaveBeenLastCalledWith("default");
});
