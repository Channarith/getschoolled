// American, British, Australian, and Singapore English (Singlish).
// Keep this file in step with apps/mobile/src/i18n/englishVariety.ts.
//
// `en` stays American so saved locales and the English UI dictionary do not
// move. The other three fall back to that dictionary, then these phrase and
// spelling passes. Lesson translation still uses base `en`.

export type EnglishVariety = "en" | "en-GB" | "en-AU" | "en-SG";

const SPELLING: ReadonlyArray<readonly [string, string]> = [
  ["organizations", "organisations"],
  ["organization", "organisation"],
  ["organizing", "organising"],
  ["organized", "organised"],
  ["organize", "organise"],
  ["recognizing", "recognising"],
  ["recognized", "recognised"],
  ["recognize", "recognise"],
  ["canceling", "cancelling"],
  ["canceled", "cancelled"],
  ["favorites", "favourites"],
  ["favorite", "favourite"],
  ["behaviors", "behaviours"],
  ["behavior", "behaviour"],
  ["coloring", "colouring"],
  ["colored", "coloured"],
  ["catalogs", "catalogues"],
  ["catalog", "catalogue"],
  ["dialogs", "dialogues"],
  ["dialog", "dialogue"],
  ["traveling", "travelling"],
  ["modeling", "modelling"],
  ["labeled", "labelled"],
  ["centers", "centres"],
  ["center", "centre"],
  ["colors", "colours"],
  ["color", "colour"],
  ["honors", "honours"],
  ["honor", "honour"],
  ["toward", "towards"],
  ["gray", "grey"],
];

const PHRASES_GB: ReadonlyArray<readonly [string, string]> = [
  ["Try the demo", "Have a go"],
];

const PHRASES_AU: ReadonlyArray<readonly [string, string]> = [
  ["Thousands of classes. One AI campus.", "G'day — thousands of classes. One AI campus."],
  ["Tap any class to start hands-free in On the Go.", "Tap any class to start hands-free in On the Go. No worries."],
  ["Try the demo", "Give it a go"],
  ["Nice work", "Good on ya"],
  ["Good job", "Good on ya"],
];

const PHRASES_SG: ReadonlyArray<readonly [string, string]> = [
  ["Thousands of classes. One AI campus.", "So many classes. One AI campus lah."],
  ["Tap any class to start hands-free in On the Go.", "Tap any class, can start hands-free in On the Go."],
  ["Type to search courses, games, and settings", "Type to search courses, games, and settings, can"],
  ["Capture canceled — try again or skip.", "Capture cancel already — try again or skip, can."],
  ["Sign in to take this course", "Sign in first, then can take this course"],
  ["Loading your catalog…", "Loading the catalog already…"],
  ["Pull to retry.", "Pull to try again, can."],
  ["Try the demo", "Try the demo lah"],
  ["Nice work", "Good job lah"],
  ["Good job", "Good job lah"],
  ["No problem", "Can, no problem"],
  ["Sign in", "Sign in lah"],
  ["Log in", "Log in lah"],
];

const ENGLISH_VOICES: Record<EnglishVariety, { f: string; m: string }> = {
  en: { f: "en_us_f", m: "en_us_m" },
  "en-GB": { f: "en_gb_f", m: "en_gb_m" },
  "en-AU": { f: "en_au_f", m: "en_au_m" },
  "en-SG": { f: "en_sg_f", m: "en_sg_m" },
};

const FOLLOW_VOICE = new Set([
  "",
  "en_us_f", "en_us_m",
  "en_gb_f", "en_gb_m",
  "en_au_f", "en_au_m",
  "en_sg_f", "en_sg_m",
]);

export function englishVariety(tag: string, region?: string | null): EnglishVariety | "" {
  const raw = (tag || "").trim().toLowerCase().replace(/_/g, "-");
  if (raw === "singlish") return "en-SG";
  const parts = raw.split("-").filter(Boolean);
  const base = parts[0] || "";
  if (base !== "en") return "";
  const place = (parts[1] || region || "").trim().toLowerCase();
  if (place === "gb" || place === "uk") return "en-GB";
  if (place === "au") return "en-AU";
  if (place === "sg") return "en-SG";
  return "en";
}

export function englishBcp47(locale: string): string {
  const variety = englishVariety(locale);
  if (variety === "en") return "en-US";
  if (variety === "en-GB") return "en-GB";
  if (variety === "en-AU") return "en-AU";
  if (variety === "en-SG") return "en-SG";
  return "";
}

/** Speech-gateway language. American stays `en`; the other three keep the region. */
export function englishSpokenCode(locale: string): string {
  const variety = englishVariety(locale);
  if (!variety) return "";
  return variety === "en" ? "en" : variety;
}

export function englishVoiceForLocale(locale: string, currentVoiceId: string): string {
  const variety = englishVariety(locale);
  if (!variety) return "";
  const current = currentVoiceId || "";
  if (!FOLLOW_VOICE.has(current)) return "";
  if (!current && variety === "en") return "";
  const pair = ENGLISH_VOICES[variety];
  return current.endsWith("_m") ? pair.m : pair.f;
}

function matchCase(source: string, replacement: string): string {
  if (source === source.toUpperCase()) return replacement.toUpperCase();
  if (source[0] === source[0].toUpperCase()) {
    return replacement[0].toUpperCase() + replacement.slice(1);
  }
  return replacement;
}

function applyPhrases(text: string, phrases: ReadonlyArray<readonly [string, string]>): string {
  const ordered = [...phrases].sort((a, b) => b[0].length - a[0].length);
  let out = text;
  for (const [from, to] of ordered) {
    if (out.includes(from)) out = out.split(from).join(to);
  }
  return out;
}

function applySpelling(text: string): string {
  const ordered = [...SPELLING].sort((a, b) => b[0].length - a[0].length);
  let out = text;
  for (const [from, to] of ordered) {
    out = out.replace(new RegExp(`\\b${from}\\b`, "gi"), (found) => matchCase(found, to));
  }
  return out;
}

export function varyEnglish(text: string, locale: string): string {
  const variety = englishVariety(locale);
  if (!text || variety === "" || variety === "en") return text;
  if (variety === "en-GB") return applySpelling(applyPhrases(text, PHRASES_GB));
  if (variety === "en-AU") return applySpelling(applyPhrases(text, PHRASES_AU));
  return applyPhrases(text, PHRASES_SG);
}
