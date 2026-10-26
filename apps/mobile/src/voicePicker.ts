// Helpers for the single voice list (home footer and Settings). Mirrors apps/web/app/lib/voicePicker.ts so the app and the site list the same voices.
import type { VoiceGroup } from "./api";

/** Voice name without the accent prefix, e.g. "New York — Guy (M)" -> "Guy (M)". */
function voiceName(label: string): string {
  const parts = label.split("—");
  return (parts[parts.length - 1] || label).trim();
}

/** "Ava (F)" stays; "Channarith (English)" drops the language parenthesis. Then the language is added once. */
function withLanguage(name: string, language: string): string {
  const bare = name.replace(/\s*\((?!F\)|M\))[^)]*\)\s*$/i, "").trim();
  return `${bare || name} · ${language}`;
}

/**
 * One option per real audio voice. The catalog lists some voices several times under regional labels
 * ("New York — Guy" and "American — Guy" are the same neural voice). The first row for each locale + voice name is kept,
 * plus whichever voice is already saved so a saved choice never vanishes.
 */
export function distinctVoiceGroups(groups: VoiceGroup[], savedId = ""): VoiceGroup[] {
  const seen = new Set<string>();
  const out: VoiceGroup[] = [];
  for (const g of groups) {
    const voices = g.voices.filter((v) => {
      const key = `${v.locale}|${voiceName(v.label)}`;
      if (v.id === savedId) {
        seen.add(key);
        return true;
      }
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    if (voices.length) out.push({ ...g, voices });
  }
  return out;
}

/** Language code the clips are stored under for a UI locale (Cantonese is "yue", everything else its primary subtag). */
export function clipLangForLocale(locale: string): string {
  const l = (locale || "en").toLowerCase().replace("_", "-");
  if (l === "yue" || l.startsWith("yue-") || l.startsWith("zh-hk") || l.startsWith("zh-mo")) return "yue";
  return l.split("-")[0];
}

export function customVoiceLabel(name: string, lang: string, uiLocale: string): string {
  let language = lang;
  try {
    language = new Intl.DisplayNames([uiLocale || "en"], { type: "language" }).of(lang) || lang;
  } catch { /* unknown code or no Intl.DisplayNames on this engine: show the code */ }
  return `${name} (${language}) · AI-generated voice`;
}

export const CUSTOM_PREFIX = "clone:";

/** Option keys: "clone:<id>" (a company or designed voice), "auto:<language>" (the Salane Voice for that language), else a catalog voice id. */
export const AUTO_PREFIX = "auto:";

export type VoiceOption = { key: string; label: string; header?: boolean; locale?: string };
/** One language of the picker: its header, the English name (for search) and its options (never includes the header row). */
export type VoiceOptionGroup = { key: string; label: string; english: string; options: VoiceOption[] };
export type PickerClone = { id: string; label: string; name?: string; primary_lang?: string; default?: boolean; active?: boolean; kind?: string };

/** Same rule as languageFamily() in voiceLanguage.ts (a test keeps the two equal): "zh-HK" and "yue" are Cantonese, else the primary subtag. */
export function groupKeyForVoice(locale: string): string {
  const l = (locale || "").toLowerCase().replace(/_/g, "-");
  if (l === "yue" || l.startsWith("yue-") || l === "zh-hk" || l.startsWith("zh-hk") || l === "zh-mo" || l.startsWith("zh-mo")) return "yue";
  if (l === "singlish") return "en";
  return l.split("-")[0];
}

function displayName(code: string, inLocale: string): string {
  try {
    const n = new Intl.DisplayNames([inLocale], { type: "language" }).of(code);
    if (n && n !== code) return n;
  } catch { /* unknown code or no Intl.DisplayNames on this engine */ }
  return "";
}

export function englishLanguageName(code: string): string {
  return displayName(code, "en") || code;
}

function stripMarks(text: string): string {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/**
 * Every voice in one list, grouped by the language that voice speaks. English opens with Sage (or the Salane Voice).
 * Every other row is a named voice labeled with its language. There is no language-only choice.
 */
export function buildVoiceGroups(args: {
  groups: VoiceGroup[]; clones: PickerClone[]; savedVoiceId?: string; salaneLabel?: string; hasDefault?: boolean; nativeNames?: Record<string, string>;
}): VoiceOptionGroup[] {
  const { groups, clones, savedVoiceId = "", salaneLabel = "Salane Voice", hasDefault = false, nativeNames = {} } = args;
  const by = new Map<string, VoiceOptionGroup>();
  const group = (key: string): VoiceOptionGroup => {
    let g = by.get(key);
    if (!g) {
      const english = englishLanguageName(key);
      g = { key, label: nativeNames[key] || displayName(key, key) || english, english, options: [] };
      by.set(key, g);
    }
    return g;
  };
  for (const v of distinctVoiceGroups(groups, savedVoiceId).flatMap((g) => g.voices)) {
    const g = group(groupKeyForVoice(v.locale || v.language));
    g.options.push({ key: v.id, label: withLanguage(voiceName(v.label), g.label), locale: v.locale });
  }
  for (const c of clones) {
    if (c.active === false || (c.default && hasDefault)) continue;   // Sage is the English group's first entry, not a second copy
    const g = group(groupKeyForVoice(c.primary_lang || "en"));
    const name = c.kind === "stock" ? (c.name || c.label) : c.label;
    g.options.unshift({ key: `${CUSTOM_PREFIX}${c.id}`, label: withLanguage(name, g.label), locale: c.primary_lang || "en" });
  }
  const english = group("en");   // English always exists: it carries Sage even when the catalog is offline
  english.options.unshift({
    key: `${AUTO_PREFIX}en`,
    label: withLanguage(hasDefault && /sage/i.test(salaneLabel) ? "Sage" : salaneLabel, english.label),
    locale: "en",
  });
  return [...by.values()].sort((a, b) => (a.key === "en" ? -1 : b.key === "en" ? 1 : a.english.localeCompare(b.english)));
}

/** Narrow the list by a search box (option text, the language's own and English names, the locale code); the selected option always stays. */
export function filterVoiceGroups(groups: VoiceOptionGroup[], query: string, keepKey = ""): VoiceOptionGroup[] {
  const q = stripMarks(query.trim());
  if (!q) return groups;
  const out: VoiceOptionGroup[] = [];
  for (const g of groups) {
    const headMatch = [g.label, g.english, g.key].some((x) => stripMarks(x).includes(q));
    const options = g.options.filter((o) => o.key === keepKey || headMatch || stripMarks(`${o.label} ${o.locale || ""}`).includes(q));
    if (options.length) out.push({ ...g, options });
  }
  return out;
}

/** The rows the dropdown shows: each language's header, then its options. */
export function flattenVoiceGroups(groups: VoiceOptionGroup[]): VoiceOption[] {
  return groups.flatMap((g) => [{ key: `hdr:${g.key}`, label: g.label, header: true }, ...g.options]);
}

/** The option that is selected: the picked voice, else the first voice that speaks the current language, else Sage. */
export function selectedVoiceKey(args: { cloneId: string; cloneListed: boolean; savedVoiceId: string; locale: string; groups: VoiceOptionGroup[] }): string {
  const { cloneId, cloneListed, savedVoiceId, locale, groups } = args;
  if (cloneId && cloneListed) return `${CUSTOM_PREFIX}${cloneId}`;
  if (savedVoiceId) return savedVoiceId;
  const match = groups.find((g) => g.key === groupKeyForVoice(locale));
  if (match?.options[0]) return match.options[0].key;
  return groups.find((g) => g.key === "en")?.options[0]?.key || `${AUTO_PREFIX}en`;
}
