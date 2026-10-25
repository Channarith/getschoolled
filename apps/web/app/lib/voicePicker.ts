// Helpers for the single voice dropdown (profile menu): which catalog voices to list and how custom voices are named.
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
