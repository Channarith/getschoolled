// Languages the Salarean mobile UI is translated into.
// Source-of-truth list mirrors aoep_shared.languages.SUPPORTED_LANGUAGES so
// content language coverage and UI language coverage stay aligned.
//
// `tier` is "full" when every UI string has a hand-written translation, and
// "fallback" when the app falls back to English for missing keys (so adding
// a language to the picker is non-breaking even before it's fully translated).

export type LocaleCode =
  | "en" | "es" | "fr" | "de" | "it" | "pt" | "nl" | "pl" | "ru" | "uk"
  | "tr" | "ar" | "he" | "hi" | "bn" | "ur" | "fa" | "zh" | "ja" | "ko"
  | "vi" | "th" | "id" | "sw" | "el" | "cs" | "km";

export type LanguageInfo = {
  code: LocaleCode;
  name: string;       // English name
  native: string;     // endonym
  flag: string;
  rtl?: boolean;
  tier: "full" | "fallback";
};

export const LANGUAGES: LanguageInfo[] = [
  { code: "en", name: "English",            native: "English",          flag: "🇬🇧", tier: "full" },
  { code: "es", name: "Spanish",            native: "Español",          flag: "🇪🇸", tier: "full" },
  { code: "fr", name: "French",             native: "Français",         flag: "🇫🇷", tier: "full" },
  { code: "de", name: "German",             native: "Deutsch",          flag: "🇩🇪", tier: "full" },
  { code: "it", name: "Italian",            native: "Italiano",         flag: "🇮🇹", tier: "full" },
  { code: "pt", name: "Portuguese",         native: "Português",        flag: "🇵🇹", tier: "full" },
  { code: "ru", name: "Russian",            native: "Русский",          flag: "🇷🇺", tier: "full" },
  { code: "ar", name: "Arabic",             native: "العربية",            flag: "🇸🇦", rtl: true, tier: "full" },
  { code: "hi", name: "Hindi",              native: "हिन्दी",              flag: "🇮🇳", tier: "full" },
  { code: "zh", name: "Chinese (Mandarin)", native: "中文",              flag: "🇨🇳", tier: "full" },
  { code: "ja", name: "Japanese",           native: "日本語",            flag: "🇯🇵", tier: "full" },
  { code: "ko", name: "Korean",             native: "한국어",             flag: "🇰🇷", tier: "full" },
  { code: "vi", name: "Vietnamese",         native: "Tiếng Việt",       flag: "🇻🇳", tier: "full" },
  { code: "km", name: "Khmer",              native: "ខ្មែរ",            flag: "🇰🇭", tier: "full" },
  // Remaining 13 are wired in the picker but inherit English until a full
  // translation lands. (The strings dictionary cleanly falls through.)
  { code: "nl", name: "Dutch",              native: "Nederlands",       flag: "🇳🇱", tier: "fallback" },
  { code: "pl", name: "Polish",             native: "Polski",           flag: "🇵🇱", tier: "fallback" },
  { code: "uk", name: "Ukrainian",          native: "Українська",       flag: "🇺🇦", tier: "fallback" },
  { code: "tr", name: "Turkish",            native: "Türkçe",           flag: "🇹🇷", tier: "fallback" },
  { code: "he", name: "Hebrew",             native: "עברית",             flag: "🇮🇱", rtl: true, tier: "fallback" },
  { code: "bn", name: "Bengali",            native: "বাংলা",              flag: "🇧🇩", tier: "fallback" },
  { code: "ur", name: "Urdu",               native: "اردو",              flag: "🇵🇰", rtl: true, tier: "fallback" },
  { code: "fa", name: "Persian",            native: "فارسی",            flag: "🇮🇷", rtl: true, tier: "fallback" },
  { code: "th", name: "Thai",               native: "ไทย",               flag: "🇹🇭", tier: "fallback" },
  { code: "id", name: "Indonesian",         native: "Bahasa Indonesia", flag: "🇮🇩", tier: "fallback" },
  { code: "sw", name: "Swahili",            native: "Kiswahili",        flag: "🇰🇪", tier: "fallback" },
  { code: "el", name: "Greek",              native: "Ελληνικά",         flag: "🇬🇷", tier: "fallback" },
  { code: "cs", name: "Czech",              native: "Čeština",          flag: "🇨🇿", tier: "fallback" },
];

export const DEFAULT_LOCALE: LocaleCode = "en";

export function isSupportedLocale(code: string): code is LocaleCode {
  return LANGUAGES.some((l) => l.code === code);
}

export function languageInfo(code: LocaleCode): LanguageInfo {
  return LANGUAGES.find((l) => l.code === code) || LANGUAGES[0];
}

export const RTL_LOCALES: ReadonlySet<LocaleCode> = new Set(
  LANGUAGES.filter((l) => l.rtl).map((l) => l.code)
);
