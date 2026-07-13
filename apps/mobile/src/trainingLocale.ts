/**
 * Spoken lesson language for Drive Mode / audio courses.
 *
 * The list mirrors the platform's supported languages (see the UI language
 * list in ``i18n/languages``). English, Spanish, and Chinese ship with fully
 * curated spoken content; other languages are served via the backend body
 * translator when configured, and otherwise fall back to English narration.
 * The player always narrates using the course's returned ``body_locale`` so
 * the voice matches the actual text language.
 */

import { LANGUAGES, type LocaleCode } from "./i18n/languages";

export type TrainingLocale = LocaleCode;

export const TRAINING_LOCALES: TrainingLocale[] = LANGUAGES.map((l) => l.code);

export const TRAINING_LOCALE_LABELS: Record<TrainingLocale, string> =
  LANGUAGES.reduce((acc, l) => {
    acc[l.code] = l.native;
    return acc;
  }, {} as Record<TrainingLocale, string>);

const SUPPORTED = new Set<string>(TRAINING_LOCALES);

export function normalizeTrainingLocale(locale: string | null | undefined): TrainingLocale {
  const base = (locale || "en").toLowerCase().split("-")[0];
  return (SUPPORTED.has(base) ? base : "en") as TrainingLocale;
}

export function trainingLocaleFromUi(uiLocale: string): TrainingLocale {
  return normalizeTrainingLocale(uiLocale);
}
