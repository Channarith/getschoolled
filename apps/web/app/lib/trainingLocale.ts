/** Spoken lesson language for Drive Mode (en / es / zh). */

export type TrainingLocale = "en" | "es" | "zh";

export const TRAINING_LOCALES: TrainingLocale[] = ["en", "es", "zh"];

export const TRAINING_LOCALE_LABELS: Record<TrainingLocale, string> = {
  en: "English",
  es: "Español",
  zh: "中文",
};

const STORAGE_KEY = "aoep-training-locale";

export function normalizeTrainingLocale(locale: string | null | undefined): TrainingLocale {
  const base = (locale || "en").toLowerCase().split("-")[0];
  if (base === "es" || base === "zh") return base;
  return "en";
}

export function getTrainingLocale(): TrainingLocale | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) return normalizeTrainingLocale(raw);
  } catch { /* ignore */ }
  return null;
}

/** Persisted choice, or English when unset. */
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
