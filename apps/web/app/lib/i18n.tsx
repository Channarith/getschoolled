// Lightweight i18n for the Salarean / Salarean web app.
//
// Mirrors the mobile i18n in apps/mobile/src/i18n: a `LocaleProvider`
// at the root + a `useT()` hook in screens. No i18next / react-intl;
// the dictionary lives in `i18n-strings.ts` and `t(key, vars)` does
// {placeholder} substitution with English fallback for partial
// translations.
//
// First-class locales:
//   en, es, fr, de, it, pt, ru, ar, hi, zh, ja, ko, vi, km.
//
// Why `vi` and `km` specifically: vi is a product requirement; km is a
// brand requirement (Salarean = ស្ហាលារៀន, the Khmer word for school).
//
// Persistence: the user's pick is stored in localStorage so a return
// visit lands in the same language without flicker.

"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  LANGUAGE_LIST,
  LOCALES,
  RTL_LOCALES,
  STRINGS,
  type Locale,
} from "./i18n-strings";

const DEFAULT_LOCALE: Locale = "en";
// localStorage key carries the legacy "salareen" prefix for one
// release cycle so existing visitors keep their language pick.
// New keys we add elsewhere should use the corrected "salarean"
// spelling.
const STORAGE_KEY = "salareen.locale.v1";

function isSupported(code: string): code is Locale {
  return (LOCALES as readonly string[]).includes(code);
}

export function detectInitialLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  // 1. User's explicit pick wins.
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && isSupported(stored)) return stored;
  } catch {
    /* localStorage may be blocked in private mode */
  }
  // 2. Browser language.
  const candidates = (navigator.languages || [navigator.language || ""])
    .map((c) => (c || "").toLowerCase().split("-")[0]);
  for (const c of candidates) {
    if (isSupported(c)) return c;
  }
  return DEFAULT_LOCALE;
}

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_m, k) =>
    Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : `{${k}}`,
  );
}

export function translateWith(locale: Locale, key: string,
                              vars?: Record<string, string | number>): string {
  const here = STRINGS[locale] || {};
  const fallback = STRINGS[DEFAULT_LOCALE] || {};
  const tpl = here[key] ?? fallback[key] ?? key;
  return interpolate(tpl, vars);
}

type LocaleContextValue = {
  locale: Locale;
  isRTL: boolean;
  setLocale: (next: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  languages: typeof LANGUAGE_LIST;
};

const LocaleContext = createContext<LocaleContextValue>({
  locale: DEFAULT_LOCALE,
  isRTL: false,
  setLocale: () => {},
  t: (key, vars) => translateWith(DEFAULT_LOCALE, key, vars),
  languages: LANGUAGE_LIST,
});

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  // SSR renders with the default; the effect below swaps to the user's
  // pick once we have access to localStorage / navigator.
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const initial = detectInitialLocale();
    if (initial !== locale) setLocaleState(initial);
    // intentionally only on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale;
      document.documentElement.dir = RTL_LOCALES.has(locale) ? "rtl" : "ltr";
    }
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    if (!isSupported(next)) return;
    setLocaleState(next);
    try { window.localStorage.setItem(STORAGE_KEY, next); } catch { /* ignore */ }
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => translateWith(locale, key, vars),
    [locale],
  );

  const value = useMemo<LocaleContextValue>(() => ({
    locale, isRTL: RTL_LOCALES.has(locale), setLocale, t, languages: LANGUAGE_LIST,
  }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useT() {
  return useContext(LocaleContext);
}

export { LANGUAGE_LIST, LOCALES };
export type { Locale };
