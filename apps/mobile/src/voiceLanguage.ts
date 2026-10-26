// One control: the VOICE. The voice a visitor picks decides the app language (menus, lesson text, speech, direction), so there is no
// separate language setting. Pure functions with no imports, so the unit tests load this file as is; the callers pass the list of
// UI locales in (LOCALES from i18n-strings).
//
// Language of a voice:
//   edge-tts voice  -> its locale: en-US -> "en", en-GB/en-AU/en-SG keep the accent, zh-HK -> "yue", zh-CN/zh-TW -> "zh", es-MX -> "es", ...
//   company/stock voice -> its primary_lang ("en", "yue"); when that is the same language family as the current one the current locale
//     stays (a UK-English visitor who picks Sage keeps en-GB menus).
// Using a company voice for lines in another language (cross-lingual clips) never changes the language: the language is set once, when
// the voice is picked, and clip lookups use the language of each line.

export type VoiceChoice =
  | { type: "auto" }
  | { type: "clone"; id: string }
  | { type: "edge"; id: string };

export type CloneVoiceLang = { id: string; primary_lang?: string; default?: boolean; active?: boolean };

/** "en-GB" -> "en", "yue" -> "yue", "zh-HK" -> "yue", "pt_BR" -> "pt". The language family the clips and the groups are stored under. */
export function languageFamily(locale: string): string {
  const l = (locale || "").toLowerCase().replace(/_/g, "-");
  if (l === "yue" || l.startsWith("yue-") || l === "zh-hk" || l.startsWith("zh-hk") || l === "zh-mo" || l.startsWith("zh-mo")) return "yue";
  if (l === "singlish") return "en";
  return l.split("-")[0];
}

export function sameFamily(a: string, b: string): boolean {
  return Boolean(a) && Boolean(b) && languageFamily(a) === languageFamily(b);
}

/** First catalog voice for a language. Male falls back to female when that language has one voice. */
const CATALOG_VOICE: Record<string, { f: string; m?: string }> = {
  en: { f: "en_us_f", m: "en_us_m" },
  es: { f: "es_es_f", m: "es_es_m" },
  fr: { f: "fr_fr_f" },
  de: { f: "de_de_f", m: "de_de_m" },
  it: { f: "it_it_f" },
  pt: { f: "pt_br_f" },
  nl: { f: "nl_nl_f" },
  pl: { f: "pl_pl_f" },
  ru: { f: "ru_ru_f" },
  uk: { f: "uk_ua_f" },
  tr: { f: "tr_tr_f" },
  ar: { f: "ar_sa_f" },
  he: { f: "he_il_f" },
  hi: { f: "hi_in_f" },
  bn: { f: "bn_bd_f" },
  ur: { f: "ur_pk_f" },
  fa: { f: "fa_ir_f" },
  zh: { f: "zh_cn_f", m: "zh_cn_m" },
  yue: { f: "zh_hk_f", m: "zh_yue_gz_m" },
  ja: { f: "ja_jp_f" },
  ko: { f: "ko_kr_f" },
  vi: { f: "vi_vn_f" },
  th: { f: "th_th_f" },
  id: { f: "id_id_f" },
  sw: { f: "sw_ke_f" },
  el: { f: "el_gr_f" },
  cs: { f: "cs_cz_f" },
  km: { f: "km_kh_f", m: "km_kh_m" },
  tl: { f: "tl_ph_f" },
};

function accentDefault(locale: string, male: boolean): string {
  const raw = (locale || "").toLowerCase().replace(/_/g, "-");
  if (raw === "en-gb" || raw.startsWith("en-gb")) return male ? "en_gb_m" : "en_gb_f";
  if (raw === "en-au" || raw.startsWith("en-au")) return male ? "en_au_m" : "en_au_f";
  if (raw === "en-sg" || raw.startsWith("en-sg")) return male ? "en_sg_m" : "en_sg_f";
  const row = CATALOG_VOICE[languageFamily(raw)];
  if (!row) return "";
  return male && row.m ? row.m : row.f;
}

/**
 * Voice id to send for this lesson language.
 * A saved voice is kept only when it speaks that language. An empty saved voice
 * stays empty so the server can pick the language default. A mismatch is replaced.
 */
export function catalogVoiceForLanguage(locale: string, savedVoiceId: string, male = false): string {
  const saved = (savedVoiceId || "").trim();
  if (!saved) return "";
  const savedLocale = localeFromVoiceId(saved) || saved;
  if (sameFamily(savedLocale, locale)) return saved;
  return accentDefault(locale, male);
}

/**
 * Locale of an edge voice id or catalog voice: "en-GB-SoniaNeural", "zh-HK-HiuMaanNeural" (Microsoft names) and "en_gb_f" (the catalog's
 * short ids) both give their region. "" when the id carries no locale.
 */
export function localeFromVoiceId(id: string): string {
  const m = /^([a-z]{2,3})[-_]([A-Za-z]{2,4})(?:[-_]|$)/.exec(id || "");
  if (!m) return /^[a-z]{2,3}$/.test(id || "") ? id : "";
  return `${m[1].toLowerCase()}-${m[2].toUpperCase()}`;
}

/** The UI locale a voice locale maps to, restricted to the locales the app has ("" when it has none for that language). */
export function uiLocaleForVoiceLocale(voiceLocale: string, supported: readonly string[]): string {
  const l = (voiceLocale || "").trim().replace(/_/g, "-");
  if (!l) return "";
  const fam = languageFamily(l);
  if (fam === "yue") return supported.includes("yue") ? "yue" : "";
  if (fam === "en") {
    const region = (l.split("-")[1] || "").toUpperCase();
    const accent = region === "GB" || region === "UK" ? "en-GB" : region === "AU" ? "en-AU" : region === "SG" ? "en-SG" : "en";
    return supported.includes(accent) ? accent : "en";
  }
  return supported.includes(fam) ? fam : "";
}

export function uiLocaleForCloneVoice(primaryLang: string | undefined, supported: readonly string[]): string {
  return primaryLang ? uiLocaleForVoiceLocale(primaryLang, supported) : "";
}

/**
 * The locale to switch to when `choice` is picked, or "" to leave the language alone (no default voice published, unknown voice, a
 * language the app has no locale for).
 */
export function languageForVoice(
  choice: VoiceChoice,
  ctx: { current: string; supported: readonly string[]; clones: readonly CloneVoiceLang[] },
): string {
  if (choice.type === "edge") return uiLocaleForVoiceLocale(localeFromVoiceId(choice.id), ctx.supported);
  const voice = choice.type === "clone"
    ? ctx.clones.find((v) => v.id === choice.id)
    : ctx.clones.find((v) => v.active !== false && v.default);
  if (!voice) return "";
  const own = uiLocaleForCloneVoice(voice.primary_lang, ctx.supported);
  if (!own) return "";
  return sameFamily(ctx.current, own) ? ctx.current : own;
}

/** The locale for a language group of the picker ("es", "en", "yue"): the current locale when it already is that language, else the group's. */
export function languageForGroup(key: string, current: string, supported: readonly string[]): string {
  if (sameFamily(current, key)) return current;
  return uiLocaleForVoiceLocale(key, supported);
}

/**
 * The locale at start-up. An explicit voice wins over a stored language ("the language follows the voice"), a stored language wins over the
 * browser's, and the browser's language is the last resort. `edgeVoiceId` is the saved edge voice ("" = automatic).
 */
export function initialLocale(input: {
  storedLocale: string; edgeVoiceId: string; browserLocale: string; supported: readonly string[]; fallback?: string;
}): string {
  const { storedLocale, edgeVoiceId, browserLocale, supported, fallback = "en" } = input;
  const fromVoice = edgeVoiceId ? uiLocaleForVoiceLocale(localeFromVoiceId(edgeVoiceId), supported) : "";
  if (fromVoice) {
    // The same language family keeps the stored accent (stored en-AU + saved en_us voice from an older release stays en-AU).
    return storedLocale && supported.includes(storedLocale) && sameFamily(storedLocale, fromVoice) && !/-/.test(fromVoice) ? storedLocale : fromVoice;
  }
  if (storedLocale && supported.includes(storedLocale)) return storedLocale;
  return browserLocale && supported.includes(browserLocale) ? browserLocale : fallback;
}

