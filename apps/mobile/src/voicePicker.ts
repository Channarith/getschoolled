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

export type VoiceOption = { key: string; label: string; header?: boolean };

/**
 * The options of the one voice dropdown, in the same order as the web: Default (auto), the consented custom voices that have clips in the
 * current language, then every real catalog voice grouped by language. The (F)/(M) marker is part of each catalog label, so there is no
 * separate gender filter.
 */
export function buildVoiceOptions(args: {
  defaultLabel: string;
  customHeader: string;
  custom: { id: string; label: string }[];
  groups: VoiceGroup[];
  savedVoiceId: string;
}): VoiceOption[] {
  const out: VoiceOption[] = [{ key: "", label: args.defaultLabel }];
  if (args.custom.length) {
    out.push({ key: "hdr:custom", label: args.customHeader.toUpperCase(), header: true });
    for (const v of args.custom) out.push({ key: `${CUSTOM_PREFIX}${v.id}`, label: v.label });
  }
  for (const g of distinctVoiceGroups(args.groups, args.savedVoiceId)) {
    out.push({ key: `hdr:${g.language}`, label: g.language.toUpperCase(), header: true });
    for (const v of g.voices) out.push({ key: v.id, label: `${v.accent} · ${v.label}` });
  }
  return out;
}
