// Helpers for the single voice list (home footer and Settings). Mirrors apps/web/app/lib/voicePicker.ts so the app and the site list the same voices.
import type { VoiceGroup } from "./api";

/** Voice name without the accent prefix, e.g. "New York — Guy (M)" -> "Guy (M)". */
function voiceName(label: string): string {
  const parts = label.split("—");
  return (parts[parts.length - 1] || label).trim();
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
 * Every voice in one list, one group per language (English first, then by English name), the same as the site's account menu. Each group
 * opens with its Salane Voice ("Salane Voice (Sage)" for English while a default is published), then company/designed voices of that
 * language, then the catalog voices. The (F)/(M) marker is part of each catalog label, so there is no separate gender filter.
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
    group(groupKeyForVoice(v.locale || v.language)).options.push({ key: v.id, label: `${v.accent} · ${v.label}`, locale: v.locale });
  }
  for (const c of clones) {
    if (c.active === false || (c.default && hasDefault)) continue;   // the default is the group's first entry, not a second copy
    const name = c.kind === "stock" ? `${c.name || c.label} (designed)` : c.label;
    group(groupKeyForVoice(c.primary_lang || "en")).options.unshift({ key: `${CUSTOM_PREFIX}${c.id}`, label: `${name} · AI-generated voice`, locale: c.primary_lang || "en" });
  }
  group("en");   // English always exists: it carries the default Salane Voice even when the catalog is offline
  for (const g of by.values()) {
    g.options.unshift({ key: `${AUTO_PREFIX}${g.key}`, label: g.key === "en" && hasDefault ? salaneLabel : "Salane Voice (default)", locale: g.key });
  }
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

/** The option that is selected: the picked company voice, else the deliberately chosen catalog voice, else the Salane Voice of the app's language. */
export function selectedVoiceKey(args: { cloneId: string; cloneListed: boolean; savedVoiceId: string; locale: string; groups: VoiceOptionGroup[] }): string {
  const { cloneId, cloneListed, savedVoiceId, locale, groups } = args;
  if (cloneId && cloneListed) return `${CUSTOM_PREFIX}${cloneId}`;
  if (savedVoiceId) return savedVoiceId;
  const key = groupKeyForVoice(locale);
  return groups.some((g) => g.key === key) ? `${AUTO_PREFIX}${key}` : `${AUTO_PREFIX}en`;
}
