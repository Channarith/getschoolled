/**
 * Spoken lesson language for Drive Mode / audio courses (web).
 *
 * The list mirrors the platform's supported languages (see ``i18n-strings``).
 * English, Spanish, and Chinese ship with fully curated spoken content; other
 * languages are served via the backend body translator when configured, and
 * otherwise fall back to English narration. The player narrates using the
 * course's returned ``body_locale`` so the voice matches the text language.
 */

import { LANGUAGE_LIST, LOCALES, type Locale } from "./i18n-strings";

export type TrainingLocale = Locale;

export const TRAINING_LOCALES: TrainingLocale[] = [...LOCALES];

export const TRAINING_LOCALE_LABELS: Record<TrainingLocale, string> =
  LANGUAGE_LIST.reduce((acc, l) => {
    acc[l.code] = l.native;
    return acc;
  }, {} as Record<TrainingLocale, string>);

const STORAGE_KEY = "aoep-training-locale";
const SUPPORTED = new Set<string>(TRAINING_LOCALES);

export function normalizeTrainingLocale(locale: string | null | undefined): TrainingLocale {
  const base = (locale || "en").toLowerCase().split("-")[0];
  return (SUPPORTED.has(base) ? base : "en") as TrainingLocale;
}

export function getTrainingLocale(): TrainingLocale | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) return normalizeTrainingLocale(raw);
  } catch { /* ignore */ }
  return null;
}

/** Persisted choice, or the UI-derived default when unset. */
export function getTrainingLocaleOrDefault(uiLocale?: string): TrainingLocale {
  return getTrainingLocale() ?? trainingLocaleFromUi(uiLocale || "en");
}

export function setTrainingLocale(locale: TrainingLocale): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, locale);
  } catch { /* ignore */ }
}

/** Default training language from UI locale when supported, else English. */
export function trainingLocaleFromUi(uiLocale: string): TrainingLocale {
  return normalizeTrainingLocale(uiLocale);
}
