import test from "node:test";
import assert from "node:assert/strict";

import {
  catalogVoiceForLanguage, initialLocale, languageFamily, languageForGroup, languageForVoice, localeFromVoiceId, sameFamily, uiLocaleForVoiceLocale,
} from "../../app/lib/voiceLanguage.ts";
import { groupKeyForVoice } from "../../app/lib/voicePicker.ts";

const SUPPORTED = ["en", "en-GB", "en-AU", "en-SG", "es", "fr", "zh", "yue", "km", "ar", "he", "th", "ja", "vi", "pt"];
const CLONES = [
  { id: "channarith", primary_lang: "en", active: true },
  { id: "wei-miao", primary_lang: "en", active: true },
  { id: "wei", primary_lang: "yue", active: true },
  { id: "stock-f-young-warm", primary_lang: "en", active: true, default: true },
];

test("voice ids from the catalog and from Microsoft give their locale", () => {
  assert.equal(localeFromVoiceId("en-GB-SoniaNeural"), "en-GB");
  assert.equal(localeFromVoiceId("zh-HK-HiuMaanNeural"), "zh-HK");
  assert.equal(localeFromVoiceId("en_gb_f"), "en-GB");
  assert.equal(localeFromVoiceId("en_us_ny_f"), "en-US");
  assert.equal(localeFromVoiceId("km-KH-SreymomNeural"), "km-KH");
  assert.equal(localeFromVoiceId("es-MX"), "es-MX");
  assert.equal(localeFromVoiceId("km"), "km");
  assert.equal(localeFromVoiceId("not a voice"), "");
});

test("edge voice locale -> UI locale, accents kept, Cantonese is its own language", () => {
  const f = (l) => uiLocaleForVoiceLocale(l, SUPPORTED);
  assert.equal(f("en-US"), "en");
  assert.equal(f("en-GB"), "en-GB");
  assert.equal(f("en-AU"), "en-AU");
  assert.equal(f("en-SG"), "en-SG");
  assert.equal(f("en-IN"), "en");
  assert.equal(f("zh-CN"), "zh");
  assert.equal(f("zh-TW"), "zh");
  assert.equal(f("zh-HK"), "yue");
  assert.equal(f("yue"), "yue");
  assert.equal(f("es-MX"), "es");
  assert.equal(f("es-ES"), "es");
  assert.equal(f("pt-BR"), "pt");
  assert.equal(f("ar-EG"), "ar");
  assert.equal(f("eu-ES"), "", "a language the app has no locale for leaves the language alone");
});

test("picking a voice sets the language; a company voice keeps the current accent of the same language", () => {
  const ctx = (current) => ({ current, supported: SUPPORTED, clones: CLONES });
  assert.equal(languageForVoice({ type: "edge", id: "km-KH-SreymomNeural" }, ctx("en")), "km");
  assert.equal(languageForVoice({ type: "edge", id: "en-GB-SoniaNeural" }, ctx("es")), "en-GB");
  assert.equal(languageForVoice({ type: "edge", id: "zh-HK-HiuMaanNeural" }, ctx("zh")), "yue");
  assert.equal(languageForVoice({ type: "clone", id: "wei" }, ctx("en")), "yue", "Wei is the Cantonese voice");
  assert.equal(languageForVoice({ type: "clone", id: "channarith" }, ctx("es")), "en");
  assert.equal(languageForVoice({ type: "clone", id: "channarith" }, ctx("en-GB")), "en-GB", "same language: keep the UK menus");
  assert.equal(languageForVoice({ type: "auto" }, ctx("en-AU")), "en-AU", "Sage is English: the Australian visitor keeps en-AU");
  assert.equal(languageForVoice({ type: "auto" }, ctx("fr")), "en");
  assert.equal(languageForVoice({ type: "clone", id: "gone" }, ctx("fr")), "", "an unknown voice changes nothing");
  assert.equal(languageForVoice({ type: "auto" }, { current: "fr", supported: SUPPORTED, clones: [] }), "", "no default published: nothing to follow");
});

test("a language group in the picker maps to a locale; the current accent is kept", () => {
  assert.equal(languageForGroup("es", "en", SUPPORTED), "es");
  assert.equal(languageForGroup("en", "en-GB", SUPPORTED), "en-GB");
  assert.equal(languageForGroup("en", "fr", SUPPORTED), "en");
  assert.equal(languageForGroup("yue", "zh", SUPPORTED), "yue");
  assert.equal(languageForGroup("eu", "en", SUPPORTED), "");
});

test("start-up: a deliberate voice beats the stored language, which beats the browser's", () => {
  const f = (o) => initialLocale({ supported: SUPPORTED, fallback: "en", storedLocale: "", edgeVoiceId: "", browserLocale: "", ...o });
  assert.equal(f({}), "en");
  assert.equal(f({ browserLocale: "fr" }), "fr");
  assert.equal(f({ storedLocale: "es", browserLocale: "fr" }), "es", "only a language was stored: the visitor keeps it");
  assert.equal(f({ storedLocale: "es", edgeVoiceId: "km-KH-SreymomNeural", browserLocale: "fr" }), "km", "a stored voice: the language follows it");
  assert.equal(f({ storedLocale: "en-AU", edgeVoiceId: "en-US-AriaNeural" }), "en-AU", "same language, the stored accent stays");
  assert.equal(f({ storedLocale: "en", edgeVoiceId: "en-GB-SoniaNeural" }), "en-GB");
  assert.equal(f({ storedLocale: "xx", browserLocale: "zz" }), "en", "unsupported values fall back");
  assert.equal(f({ edgeVoiceId: "eu-ES-AinhoaNeural", storedLocale: "fr" }), "fr", "a voice in a language the app has no locale for keeps the stored language");
});

test("a saved voice is used only when it speaks the lesson language", () => {
  assert.equal(catalogVoiceForLanguage("es", "en_us_f"), "es_es_f");
  assert.equal(catalogVoiceForLanguage("es", "en_us_m", true), "es_es_m");
  assert.equal(catalogVoiceForLanguage("es", "es_mx_m"), "es_mx_m");
  assert.equal(catalogVoiceForLanguage("km", "en_us_f"), "km_kh_f");
  assert.equal(catalogVoiceForLanguage("yue", "zh_cn_f"), "zh_hk_f");
  assert.equal(catalogVoiceForLanguage("yue", "zh_hk_f"), "zh_hk_f");
  assert.equal(catalogVoiceForLanguage("en-GB", "en_gb_f"), "en_gb_f");
  assert.equal(catalogVoiceForLanguage("en-GB", "es_es_f"), "en_gb_f");
  assert.equal(catalogVoiceForLanguage("fr", ""), "");
});

test("language families", () => {
  assert.equal(languageFamily("en-GB"), "en");
  assert.equal(languageFamily("zh-HK"), "yue");
  assert.equal(languageFamily("Singlish"), "en");
  assert.ok(sameFamily("en", "en-AU") && !sameFamily("zh", "yue") && !sameFamily("", "en"));
  for (const l of ["en", "en-GB", "zh-CN", "zh-HK", "yue", "zh-MO", "pt_BR", "km-KH", "singlish", ""]) {
    assert.equal(groupKeyForVoice(l), languageFamily(l), `the picker's group key must equal the language family for ${l}`);
  }
});
