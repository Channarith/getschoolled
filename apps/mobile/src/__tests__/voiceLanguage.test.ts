import { readFileSync } from "fs";
import { join } from "path";

import { initialLocale, languageFamily, languageForGroup, languageForVoice, localeFromVoiceId, sameFamily, uiLocaleForVoiceLocale } from "../voiceLanguage";
import { groupKeyForVoice } from "../voicePicker";

const SUPPORTED = ["en", "en-GB", "en-AU", "en-SG", "es", "fr", "zh", "yue", "km", "ar", "he", "th", "ja", "vi", "pt"];
const CLONES = [
  { id: "channarith", primary_lang: "en", active: true }, { id: "wei", primary_lang: "yue", active: true },
  { id: "stock-f-young-warm", primary_lang: "en", active: true, default: true },
];

test("the mobile copy is identical to the site's voiceLanguage.ts (one rule, two apps)", () => {
  const web = readFileSync(join(__dirname, "../../../web/app/lib/voiceLanguage.ts"), "utf8");
  const mobile = readFileSync(join(__dirname, "../voiceLanguage.ts"), "utf8");
  expect(mobile).toBe(web);
});

test("voice ids give their locale; edge voice locale maps to a UI locale with accents and Cantonese kept", () => {
  expect(localeFromVoiceId("en-GB-SoniaNeural")).toBe("en-GB");
  expect(localeFromVoiceId("zh-HK-HiuMaanNeural")).toBe("zh-HK");
  expect(localeFromVoiceId("en_gb_f")).toBe("en-GB");
  const f = (l: string) => uiLocaleForVoiceLocale(l, SUPPORTED);
  expect([f("en-US"), f("en-GB"), f("en-AU"), f("en-SG"), f("zh-CN"), f("zh-TW"), f("zh-HK"), f("es-MX"), f("pt-BR"), f("eu-ES")])
    .toEqual(["en", "en-GB", "en-AU", "en-SG", "zh", "zh", "yue", "es", "pt", ""]);
});

test("picking a voice sets the language; a company voice keeps the accent of the same language", () => {
  const ctx = (current: string) => ({ current, supported: SUPPORTED, clones: CLONES });
  expect(languageForVoice({ type: "edge", id: "km-KH-SreymomNeural" }, ctx("en"))).toBe("km");
  expect(languageForVoice({ type: "clone", id: "wei" }, ctx("en"))).toBe("yue");
  expect(languageForVoice({ type: "clone", id: "channarith" }, ctx("en-GB"))).toBe("en-GB");
  expect(languageForVoice({ type: "auto" }, ctx("fr"))).toBe("en");
  expect(languageForVoice({ type: "clone", id: "gone" }, ctx("fr"))).toBe("");
  expect(languageForGroup("es", "en", SUPPORTED)).toBe("es");
  expect(languageForGroup("en", "en-AU", SUPPORTED)).toBe("en-AU");
});

test("start-up: a deliberate voice beats the stored language, which beats the device's", () => {
  const f = (o: object) => initialLocale({ supported: SUPPORTED, fallback: "en", storedLocale: "", edgeVoiceId: "", browserLocale: "", ...o });
  expect(f({ browserLocale: "fr" })).toBe("fr");
  expect(f({ storedLocale: "es", browserLocale: "fr" })).toBe("es");
  expect(f({ storedLocale: "es", edgeVoiceId: "km-KH-SreymomNeural" })).toBe("km");
  expect(f({ storedLocale: "en-AU", edgeVoiceId: "en-US-AriaNeural" })).toBe("en-AU");
});

test("language families, and the picker's group key equals them", () => {
  expect(languageFamily("zh-HK")).toBe("yue");
  expect(sameFamily("en", "en-AU")).toBe(true);
  for (const l of ["en", "en-GB", "zh-CN", "zh-HK", "yue", "zh-MO", "pt_BR", "km-KH", "singlish", ""]) expect(groupKeyForVoice(l)).toBe(languageFamily(l));
});
