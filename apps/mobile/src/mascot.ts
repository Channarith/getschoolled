import { MASCOT_IMAGES } from "./mascots/imageAssets";

export const DEFAULT_MASCOT_LOCALE = "en";
export const DEFAULT_MASCOT_ASSET = require("../assets/salareen_mark_256.png");

export type MascotResolve = {
  enabled: boolean;
  locale: string;
  path: string;
  localized: boolean;
  preview_locale?: string | null;
  variant?: {
    locale: string;
    region: string;
    cultural_theme: string;
  };
};

const LOCALES = Object.keys(MASCOT_IMAGES);

/** Normalize a BCP-47 tag to a supported mascot locale code. */
export function normalizeMascotLocale(locale: string | null | undefined): string {
  const raw = (locale || "en").toLowerCase().replace(/_/g, "-");
  if (
    raw === "yue" || raw.startsWith("yue-") ||
    raw === "zh-hk" || raw.startsWith("zh-hk") ||
    raw === "zh-mo" || raw.startsWith("zh-mo")
  ) return LOCALES.includes("zh") ? "zh" : DEFAULT_MASCOT_LOCALE;
  const base = raw.split("-")[0];
  return LOCALES.includes(base) ? base : DEFAULT_MASCOT_LOCALE;
}

/** Client-side fallback when the memory service is unreachable. */
export function resolveMascotLocal(
  locale: string,
  opts?: { enabled?: boolean; previewLocale?: string | null },
): MascotResolve {
  if (opts?.enabled === false) {
    return { enabled: false, locale: DEFAULT_MASCOT_LOCALE, path: "", localized: false };
  }
  const code = normalizeMascotLocale(opts?.previewLocale || locale);
  return {
    enabled: true,
    locale: code,
    path: `/mascots/${code}.webp`,
    localized: true,
    variant: { locale: code, region: code.toUpperCase(), cultural_theme: "" },
  };
}

export function mascotImageForLocale(locale: string, opts?: { enabled?: boolean }): number {
  if (opts?.enabled === false) return DEFAULT_MASCOT_ASSET;
  const code = normalizeMascotLocale(locale);
  return MASCOT_IMAGES[code] || MASCOT_IMAGES[DEFAULT_MASCOT_LOCALE];
}
