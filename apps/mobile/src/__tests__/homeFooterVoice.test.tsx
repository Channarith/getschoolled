import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import HomeFooter from "../components/HomeFooter";

const mockSetSelectedVoice = jest.fn(async () => {});
const mockSetExplicit = jest.fn(async () => {});
const mockSetLocale = jest.fn();
const mockSetSettings = jest.fn(async (patch: object) => ({ voiceId: "", instructorId: "", voiceGender: "female", ...patch }));

jest.mock("../i18n", () => ({
  LANGUAGES: [
    { code: "en", flag: "US", native: "English (US)" }, { code: "en-GB", flag: "GB", native: "English (UK)" },
    { code: "km", flag: "KH", native: "ខ្មែរ" }, { code: "yue", flag: "HK", native: "粵語" },
  ],
  useT: () => ({
    locale: "en", setLocale: (...a: unknown[]) => mockSetLocale(...a),
    t: (key: string) => ({
      "voice.footerTitle": "Voice and language", "voice.search": "Search voices or languages", "settings.sectionVoice": "Voice",
      "settings.voiceAgent": "Live voice", "settings.voiceAgentSala": "Salane Voice (default)", "settings.voiceAgentXai": "xAI Voice Agent (opt-in)",
    } as Record<string, string>)[key] ?? key,
  }),
}));
jest.mock("../cloneVoice", () => {
  const voices = [
    { id: "channarith", label: "Channarith (English)", ai_label: "x", active: true, primary_lang: "en" },
    { id: "wei", label: "Wei (Cantonese)", ai_label: "x", active: true, primary_lang: "yue" },
    { id: "stock-f-young-warm", label: "Sage (designed)", name: "Sage", ai_label: "x", active: true, default: true, kind: "stock", primary_lang: "en" },
  ];
  return {
    DEFAULT_VOICE_ID: "default",
    loadCloneVoices: async () => voices,
    getSelectedVoice: async () => "default",
    explicitEdgeVoice: async () => "",
    defaultCloneVoice: (vs: typeof voices) => vs.find((v) => v.active && v.default) ?? null,
    salaneVoiceLabel: () => "Salane Voice (Sage)",
    setSelectedVoice: (...a: unknown[]) => (mockSetSelectedVoice as (...x: unknown[]) => Promise<void>)(...a),
    setExplicitEdgeVoice: (...a: unknown[]) => (mockSetExplicit as (...x: unknown[]) => Promise<void>)(...a),
  };
});
jest.mock("../narrationTts", () => ({
  applyVoicePrefsToTts: jest.fn(),
  voicePrefsFromSettings: (s: object) => s,
  loadVoiceCatalog: async () => [
    { language: "en", voices: [
      { id: "en-US-AvaNeural", locale: "en-US", accent: "American", label: "American — Ava (F)", gender: "female", language: "en", dialect: "" },
      { id: "en-GB-RyanNeural", locale: "en-GB", accent: "British", label: "British — Ryan (M)", gender: "male", language: "en", dialect: "" },
    ] },
    { language: "km", voices: [{ id: "km-KH-SreymomNeural", locale: "km-KH", accent: "Khmer", label: "Khmer — Sreymom (F)", gender: "female", language: "km", dialect: "" }] },
  ],
}));
jest.mock("../storage", () => ({
  getSettings: async () => ({ voiceId: "", instructorId: "", voiceGender: "female" }),
  setSettings: (p: object) => mockSetSettings(p),
}));
jest.mock("../voiceAgentPref", () => ({
  loadVoiceAgentChoice: async () => "sala", saveVoiceAgentChoice: async () => "sala", subscribeVoiceAgent: () => () => {},
}));

beforeEach(() => jest.clearAllMocks());

test("the footer is ONE voice control: no language dropdown, no Any/Female/Male, Salane Voice (Sage) selected", async () => {
  const screen = render(<HomeFooter />);
  expect(screen.getByTestId("home-footer")).toBeTruthy();
  expect(screen.queryByText("Language")).toBeNull();
  expect(screen.queryByText("Any")).toBeNull();
  expect(screen.queryByText("Female")).toBeNull();
  await waitFor(() => expect(screen.getByText("Salane Voice (Sage)")).toBeTruthy());
});

test("voices are grouped by language with search; picking a voice sets the app language", async () => {
  const screen = render(<HomeFooter />);
  await waitFor(() => expect(screen.getByText("Salane Voice (Sage)")).toBeTruthy());
  fireEvent.press(screen.getByText("Voice"));   // open the voice dropdown
  await waitFor(() => expect(screen.getByText("Channarith (English) · AI-generated voice")).toBeTruthy());
  expect(screen.getByText("English")).toBeTruthy();   // group headers use the language's own name
  expect(screen.getByText("ខ្មែរ")).toBeTruthy();
  expect(screen.getByText("粵語")).toBeTruthy();
  expect(screen.getByText("American · American — Ava (F)")).toBeTruthy();
  expect(screen.getByTestId("voice-search")).toBeTruthy();

  fireEvent.changeText(screen.getByTestId("voice-search"), "khmer");
  await waitFor(() => expect(screen.queryByText("American · American — Ava (F)")).toBeNull());
  fireEvent.press(await screen.findByText("Khmer · Khmer — Sreymom (F)"));
  await waitFor(() => expect(mockSetSettings).toHaveBeenCalledWith({ voiceId: "km-KH-SreymomNeural", voiceGender: "female" }));
  expect(mockSetExplicit).toHaveBeenCalledWith(true);
  expect(mockSetSelectedVoice).toHaveBeenLastCalledWith("default");
  expect(mockSetLocale).toHaveBeenCalledWith("km");

  fireEvent.press(screen.getByText("Voice"));
  fireEvent.press(await screen.findByText("Wei (Cantonese) · AI-generated voice"));
  await waitFor(() => expect(mockSetSelectedVoice).toHaveBeenCalledWith("wei"));
  expect(mockSetLocale).toHaveBeenLastCalledWith("yue");
});

test("choosing the Salane Voice on purpose clears the edge voice and marks it explicit", async () => {
  const screen = render(<HomeFooter />);
  await waitFor(() => expect(screen.getByText("Salane Voice (Sage)")).toBeTruthy());
  fireEvent.press(screen.getByText("Voice"));
  const own = await screen.findAllByText("Salane Voice (default)");   // the live-voice toggle, then one per non-English language group: Cantonese, then Khmer
  expect(own.length).toBe(3);
  fireEvent.press(own[own.length - 1]);   // the Khmer group's own Salane Voice
  await waitFor(() => expect(mockSetExplicit).toHaveBeenCalledWith(false));
  expect(mockSetSettings).toHaveBeenCalledWith({ voiceId: "" });
  expect(mockSetLocale).toHaveBeenCalledWith("km");
});
