import { LOCALES, type Locale } from "./i18n-strings";

export const DEFAULT_MASCOT_SRC = "/bayon-mark.webp";

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

/** Normalize a BCP-47 tag to a supported mascot locale code. */
export function normalizeMascotLocale(locale: string | null | undefined): Locale {
  const base = (locale || "en").toLowerCase().split("-")[0].split("_")[0];
  return (LOCALES as readonly string[]).includes(base) ? (base as Locale) : "en";
}

/** Build the static asset path for a locale mascot WebP. */
export function mascotAssetPath(locale: string): string {
  return `/mascots/${normalizeMascotLocale(locale)}.webp`;
}

/** Client-side fallback when the memory service is unreachable. */
export function resolveMascotLocal(
  locale: string,
  opts?: { enabled?: boolean; previewLocale?: string | null },
): MascotResolve {
  const enabled = opts?.enabled !== false;
  if (!enabled) {
    return { enabled: false, locale: "en", path: DEFAULT_MASCOT_SRC, localized: false };
  }
  const code = normalizeMascotLocale(opts?.previewLocale || locale);
  return {
    enabled: true,
    locale: code,
    path: mascotAssetPath(code),
    localized: true,
    variant: { locale: code, region: code.toUpperCase(), cultural_theme: "" },
  };
}
