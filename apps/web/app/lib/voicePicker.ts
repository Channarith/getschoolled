// Helpers for the single voice dropdown (profile menu): which catalog voices to list and how custom voices are named.
// The voice is the ONE language control: voices are grouped by language, and picking one sets the app language (voiceLanguage.ts).
import type { VoiceGroup } from "./api";

/** Voice name without the accent prefix, e.g. "New York — Guy (M)" -> "Guy (M)". */
function voiceName(label: string): string {
  const parts = label.split("—");
  return (parts[parts.length - 1] || label).trim();
}

/**
 * One option per real audio voice. The catalog lists some voices several times under regional labels
 * ("New York — Guy" and "American — Guy" are the same neural voice), which looks like extra choices but sounds identical.
 * The first row for each locale + voice name is kept, plus whichever voice the visitor already saved so their choice never vanishes.
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
  } catch { /* unknown code: show the code */ }
  return `${name} (${language}) · AI-generated voice`;
}

export const CUSTOM_PREFIX = "clone:";


// ---- one list, grouped by language ---------------------------------------------------------------------------------------------

/** Same rule as languageFamily() in voiceLanguage.ts (a unit test keeps the two equal): "zh-HK" and "yue" are Cantonese, else the primary subtag. */
export function groupKeyForVoice(locale: string): string {
  const l = (locale || "").toLowerCase().replace(/_/g, "-");
  if (l === "yue" || l.startsWith("yue-") || l === "zh-hk" || l.startsWith("zh-hk") || l === "zh-mo" || l.startsWith("zh-mo")) return "yue";
  if (l === "singlish") return "en";
  return l.split("-")[0];
}

/** Option values: "clone:<id>" (a company or designed voice), "auto:<language>" (the Salane Voice for that language), else an edge voice id. */
export const AUTO_PREFIX = "auto:";

export type VoiceOption = { value: string; label: string; locale: string };
export type VoiceOptionGroup = { key: string; label: string; english: string; options: VoiceOption[] };
export type PickerClone = { id: string; label: string; name?: string; primary_lang?: string; default?: boolean; active?: boolean; kind?: string };

function displayName(code: string, inLocale: string): string {
  try {
    const n = new Intl.DisplayNames([inLocale], { type: "language" }).of(code);
    if (n && n !== code) return n;
  } catch { /* unknown code */ }
  return "";
}

/** The language's own name, capitalised ("Español", "ខ្មែរ", "粵語"); the code when the runtime has no data for it. */
export function nativeLanguageName(code: string): string {
  const n = displayName(code, code) || displayName(code, "en") || code;
  return n.charAt(0).toLocaleUpperCase(code) + n.slice(1);
}

export function englishLanguageName(code: string): string {
  return displayName(code, "en") || code;
}

function stripMarks(text: string): string {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/**
 * Every voice in one list, one group per language (English first, then by English name). Each group opens with its Salane Voice
 * ("Salane Voice (Sage)" for English while a default is published, else "Salane Voice (default)"), then company/designed voices whose
 * language it is, then the edge voices. The visitor's saved edge voice stays listed even when it was a regional duplicate.
 */
export function buildVoiceOptions(input: {
  groups: VoiceGroup[]; clones: PickerClone[]; savedVoiceId?: string; salaneLabel?: string; hasDefault?: boolean;
  /** The app's own name for each language ({ km: "ខ្មែរ", yue: "粵語" }): browsers differ in how many languages they can name natively. */
  nativeNames?: Record<string, string>;
}): VoiceOptionGroup[] {
  const { groups, clones, savedVoiceId = "", salaneLabel = "Salane Voice", hasDefault = false, nativeNames = {} } = input;
  const by = new Map<string, VoiceOptionGroup>();
  const group = (key: string): VoiceOptionGroup => {
    let g = by.get(key);
    if (!g) {
      g = { key, label: nativeNames[key] || nativeLanguageName(key), english: englishLanguageName(key), options: [] };
      by.set(key, g);
    }
    return g;
  };
  for (const v of distinctVoiceGroups(groups, savedVoiceId).flatMap((g) => g.voices)) {
    group(groupKeyForVoice(v.locale || v.language)).options.push({ value: v.id, label: `${v.accent} · ${v.label}`, locale: v.locale });
  }
  for (const c of clones) {
    if (c.active === false || (c.default && hasDefault)) continue;   // the default is the group's first entry, not a second copy
    const key = groupKeyForVoice(c.primary_lang || "en");
    const name = c.kind === "stock" ? `${c.name || c.label} (designed)` : c.label;
    group(key).options.unshift({ value: `${CUSTOM_PREFIX}${c.id}`, label: `${name} · AI-generated voice`, locale: c.primary_lang || "en" });
  }
  group("en");   // English always exists: it carries the default Salane Voice even when the catalog is offline
  for (const g of by.values()) {
    g.options.unshift({ value: `${AUTO_PREFIX}${g.key}`, label: g.key === "en" && hasDefault ? salaneLabel : "Salane Voice (default)", locale: g.key });
  }
  return [...by.values()].sort((a, b) => (a.key === "en" ? -1 : b.key === "en" ? 1 : a.english.localeCompare(b.english)));
}

/** Narrow the list by a search box: matches the option text, the language's own and English names, and the locale code; the selected option always stays. */
export function filterVoiceOptions(groups: VoiceOptionGroup[], query: string, keepValue = ""): VoiceOptionGroup[] {
  const q = stripMarks(query.trim());
  if (!q) return groups;
  const out: VoiceOptionGroup[] = [];
  for (const g of groups) {
    const headMatch = [g.label, g.english, g.key].some((x) => stripMarks(x).includes(q));
    const options = g.options.filter((o) => o.value === keepValue || headMatch || stripMarks(`${o.label} ${o.locale}`).includes(q));
    if (options.length) out.push({ ...g, options });
  }
  return out;
}

/** The option the select shows: the picked company voice, else the saved edge voice, else the Salane Voice of the app's language. */
export function selectedVoiceValue(input: { cloneId: string; cloneListed: boolean; savedVoiceId: string; locale: string; groups: VoiceOptionGroup[] }): string {
  const { cloneId, cloneListed, savedVoiceId, locale, groups } = input;
  if (cloneId && cloneListed) return `${CUSTOM_PREFIX}${cloneId}`;
  if (savedVoiceId) return savedVoiceId;
  const key = groupKeyForVoice(locale);
  return groups.some((g) => g.key === key) ? `${AUTO_PREFIX}${key}` : `${AUTO_PREFIX}en`;
}
