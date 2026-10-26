// Minimal i18n runtime for AI Classroom mobile.
//
// Why no i18next/react-intl? They're ~50 kB minified each and we don't need
// pluralization rules, ICU, or compile-time extraction. A 30-line `t()` with
// {placeholder} substitution + an English fallback covers every screen we
// have today and stays trivially shake-able by Metro.

import * as Localization from "expo-localization";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  DEFAULT_LOCALE, isSupportedLocale, languageInfo,
  LANGUAGES, RTL_LOCALES, type LocaleCode,
} from "./languages";
import { softenLineBreaks } from "./lineBreaks";
import { FALLBACK, STRINGS, type StringKey } from "./strings";
import { englishVariety, englishVoiceForLocale, varyEnglish } from "./englishVariety";
import { catalogVoiceForLanguage } from "../voiceLanguage";
import { explicitEdgeVoice } from "../cloneVoice";
import { initialLocale } from "../voiceLanguage";
import { getMe, setAccountLanguage } from "../api";
import { getSettings, setSettings } from "../storage";

type Vars = Record<string, string | number>;

function localeFromDeviceTag(tag: string, region?: string | null): LocaleCode | null {
  const raw = (tag || "").toLowerCase().replace(/_/g, "-");
  const regionCode = (region || "").toUpperCase();
  if (
    raw === "yue" || raw.startsWith("yue-") ||
    raw === "zh-hk" || raw.startsWith("zh-hk") ||
    raw === "zh-mo" || raw.startsWith("zh-mo") ||
    ((raw === "zh" || raw.startsWith("zh-")) && (regionCode === "HK" || regionCode === "MO"))
  ) return "yue";
  const variety = englishVariety(raw, regionCode);
  if (variety) return variety;
  const base = raw.split("-")[0];
  return isSupportedLocale(base) ? base : null;
}

export function detectDeviceLocale(): LocaleCode {
  try {
    const locales = Localization.getLocales?.() || [];
    for (const l of locales) {
      const picked = localeFromDeviceTag(
        l.languageTag || l.languageCode || "",
        l.regionCode,
      );
      if (picked) return picked;
    }
    const raw = (Localization.locale || "en").toLowerCase();
    return localeFromDeviceTag(raw) || DEFAULT_LOCALE;
  } catch {}
  return DEFAULT_LOCALE;
}

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, k) =>
    Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : `{${k}}`,
  );
}

export function translateWith(locale: LocaleCode, key: StringKey, vars?: Vars): string {
  const dict = STRINGS[locale] || {};
  const own = dict[key];
  const base = own || FALLBACK[key] || key;
  const tpl = own ? base : varyEnglish(base, locale);
  return softenLineBreaks(interpolate(tpl, vars));
}

type LocaleContextValue = {
  locale: LocaleCode;
  isRTL: boolean;
  setLocale: (next: LocaleCode) => void;
  t: (key: StringKey, vars?: Vars) => string;
};

const LocaleContext = createContext<LocaleContextValue>({
  locale: DEFAULT_LOCALE,
  isRTL: false,
  setLocale: () => {},
  t: (key, vars) => translateWith(DEFAULT_LOCALE, key, vars),
});

import AsyncStorage from "@react-native-async-storage/async-storage";

const STORAGE_KEY = "@aic/locale.v1";

async function readStoredLocale(): Promise<LocaleCode | null> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (raw && isSupportedLocale(raw)) return raw;
  } catch {}
  return null;
}
async function writeStoredLocale(code: LocaleCode): Promise<void> {
  try { await AsyncStorage.setItem(STORAGE_KEY, code); } catch {}
}
async function rememberLocale(next: LocaleCode): Promise<void> {
  const cur = await getSettings();
  const male = cur.voiceGender === "male" || (cur.voiceId || "").endsWith("_m");
  const voiceId = englishVoiceForLocale(next, cur.voiceId) || catalogVoiceForLanguage(next, cur.voiceId, male);
  await setSettings(voiceId && voiceId !== cur.voiceId ? { trainingLocale: next, voiceId } : { trainingLocale: next });
}

// Top-level provider. We resolve the initial locale in this order:
//   1. AsyncStorage (user's explicit pick, sticky across sessions)
//   2. Device locale (Localization.getLocales)
//   3. English fallback.
export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<LocaleCode>(DEFAULT_LOCALE);

  useEffect(() => {
    (async () => {
      // The language follows the VOICE (there is no separate language setting): a voice picked on purpose decides it, then a stored
      // language from an older release, then the device's. The older key keeps being read, so nobody's language is lost.
      const stored = await readStoredLocale();
      const voice = await explicitEdgeVoice();
      const followed = voice
        ? (initialLocale({ storedLocale: stored || "", edgeVoiceId: voice, browserLocale: "", supported: LANGUAGES.map((l) => l.code), fallback: "" }) as LocaleCode | "")
        : "";
      if (followed && isSupportedLocale(followed)) {
        setLocaleState(followed);
        void writeStoredLocale(followed);
        void rememberLocale(followed);
        return;
      }
      if (stored) {
        setLocaleState(stored);
        void rememberLocale(stored);
        return;
      } // an older explicit pick wins over the device
      // Adopt the signed-in learner's saved language so the app + course appear
      // in their language on this device; fall back to the device locale.
      try {
        const acct = await getMe();
        const pref = localeFromDeviceTag(acct.preferred_language || "");
        if (pref) {
          setLocaleState(pref);
          void writeStoredLocale(pref);
          void rememberLocale(pref);
          return;
        }
      } catch { /* signed out / offline: use the device locale */ }
      const detected = detectDeviceLocale();
      setLocaleState(detected);
      void rememberLocale(detected);
    })();
  }, []);

  const setLocale = useCallback((next: LocaleCode) => {
    if (!isSupportedLocale(next)) return;
    setLocaleState(next);
    void writeStoredLocale(next);
    void rememberLocale(next);
    // Persist to the profile so the choice follows the learner to their other
    // devices and the AI teacher answers in this language (best-effort).
    void setAccountLanguage(next).catch(() => { /* guest / offline */ });
  }, []);

  const t = useCallback(
    (key: StringKey, vars?: Vars) => translateWith(locale, key, vars),
    [locale],
  );

  const value = useMemo<LocaleContextValue>(() => ({
    locale, isRTL: RTL_LOCALES.has(locale), setLocale, t,
  }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useT() {
  return useContext(LocaleContext);
}

export { LANGUAGES, languageInfo };
export type { LocaleCode, StringKey };
