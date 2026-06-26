/** Spoken lesson language for Drive Mode (en / es / zh). */

export type TrainingLocale = "en" | "es" | "zh";

export const TRAINING_LOCALES: TrainingLocale[] = ["en", "es", "zh"];

export const TRAINING_LOCALE_LABELS: Record<TrainingLocale, string> = {
  en: "English",
  es: "Español",
  zh: "中文",
};

export function normalizeTrainingLocale(locale: string | null | undefined): TrainingLocale {
  const base = (locale || "en").toLowerCase().split("-")[0];
  if (base === "es" || base === "zh") return base;
  return "en";
}

export function trainingLocaleFromUi(uiLocale: string): TrainingLocale {
  return normalizeTrainingLocale(uiLocale);
}
