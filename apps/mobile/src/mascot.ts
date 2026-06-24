import { MASCOT_SVG } from "./mascots/svgContent";

export const DEFAULT_MASCOT_LOCALE = "en";

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

const LOCALES = Object.keys(MASCOT_SVG);

/** Normalize a BCP-47 tag to a supported mascot locale code. */
export function normalizeMascotLocale(locale: string | null | undefined): string {
  const base = (locale || "en").toLowerCase().split("-")[0].split("_")[0];
  return LOCALES.includes(base) ? base : DEFAULT_MASCOT_LOCALE;
}

/** Client-side fallback when the memory service is unreachable. */
export function resolveMascotLocal(
  locale: string,
  opts?: { enabled?: boolean; previewLocale?: string | null },
): MascotResolve {
  const enabled = opts?.enabled !== false;
  if (!enabled) {
    return { enabled: false, locale: DEFAULT_MASCOT_LOCALE, path: "", localized: false };
  }
  const code = normalizeMascotLocale(opts?.previewLocale || locale);
  return {
    enabled: true,
    locale: code,
    path: `/mascots/${code}.svg`,
    localized: true,
    variant: { locale: code, region: code.toUpperCase(), cultural_theme: "" },
  };
}

/** Return embedded SVG markup for a locale (bundled offline). */
export function mascotSvgForLocale(locale: string, opts?: { enabled?: boolean }): string {
  if (opts?.enabled === false) return MASCOT_SVG[DEFAULT_MASCOT_LOCALE];
  const code = normalizeMascotLocale(locale);
  return MASCOT_SVG[code] || MASCOT_SVG[DEFAULT_MASCOT_LOCALE];
}
