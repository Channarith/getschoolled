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
import { FALLBACK, STRINGS, type StringKey } from "./strings";

type Vars = Record<string, string | number>;

export function detectDeviceLocale(): LocaleCode {
  try {
    const locales = Localization.getLocales?.() || [];
    for (const l of locales) {
      const code = (l.languageCode || "").toLowerCase();
      if (isSupportedLocale(code)) return code;
    }
    const raw = (Localization.locale || "en").toLowerCase().split(/[-_]/)[0];
    if (isSupportedLocale(raw)) return raw;
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
  const tpl = dict[key] ?? FALLBACK[key] ?? key;
  return interpolate(tpl, vars);
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

// Top-level provider. We resolve the initial locale in this order:
//   1. AsyncStorage (user's explicit pick, sticky across sessions)
//   2. Device locale (Localization.getLocales)
//   3. English fallback.
export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<LocaleCode>(DEFAULT_LOCALE);

  useEffect(() => {
    (async () => {
      const stored = await readStoredLocale();
      if (stored) { setLocaleState(stored); return; }
      const device = detectDeviceLocale();
      setLocaleState(device);
    })();
  }, []);

  const setLocale = useCallback((next: LocaleCode) => {
    if (!isSupportedLocale(next)) return;
    setLocaleState(next);
    void writeStoredLocale(next);
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
