#!/usr/bin/env node
// Estimate whether each locale's UI strings fit the narrowest phone slots.
//
// Run from anywhere:
//   node --experimental-strip-types apps/mobile/scripts/scan-i18n-cramp.mjs
//
// Exit 1 when a tight slot (tabs, home shortcuts, hero) cannot show the full
// string on a 320pt-wide phone. Body copy is reported only when one
// unbreakable chunk is wider than the screen, which is what actually paints
// on top of the next control.

import { softenLineBreaks } from "../src/i18n/lineBreaks.ts";
import { FALLBACK, STRINGS } from "../src/i18n/strings.ts";
import { LANGUAGES } from "../src/i18n/languages.ts";

const PHONE = 320;
const CONTENT = PHONE - 32;

// Worst-case boxes after the shared layout: 6 tabs, or 4 home shortcuts.
const TIGHT = {
  tab: { width: 50, font: 10, lines: 2, bold: true, tracking: 0 },
  nav: { width: 64, font: 11, lines: 2, bold: true, tracking: 0 },
  hero: { width: CONTENT, font: 28, lines: 3, bold: true, tracking: 0 },
  kicker: { width: CONTENT, font: 11, lines: 2, bold: true, tracking: 1.2 },
  sub: { width: CONTENT, font: 14, lines: 4, bold: false, tracking: 0 },
  chip: { width: 120, font: 14, lines: 2, bold: true, tracking: 0 },
};

const SLOT_BY_KEY = {};
for (const key of Object.keys(FALLBACK)) {
  if (key.startsWith("tab.")) SLOT_BY_KEY[key] = "tab";
  else if (key.startsWith("home.nav")) SLOT_BY_KEY[key] = "nav";
  else if (key === "home.hero") SLOT_BY_KEY[key] = "hero";
  else if (key === "home.kicker") SLOT_BY_KEY[key] = "kicker";
  else if (key === "home.subDefault" || key === "home.subStreak") SLOT_BY_KEY[key] = "sub";
  else if (
    key === "settings.refresh" || key === "settings.send" || key === "settings.request"
    || key === "settings.driveNotDriving" || key === "settings.playFullIntro"
  ) {
    SLOT_BY_KEY[key] = "chip";
  }
}

// Labels that are still hardcoded in HomeScreen, measured as nav slots.
const HARDCODED_NAV = ["Worlds", "Corporate", "Kids"];

function isMark(cp) {
  return (
    (cp >= 0x0300 && cp <= 0x036f)
    || (cp >= 0x0900 && cp <= 0x0903)
    || (cp >= 0x093a && cp <= 0x094f)
    || (cp >= 0x0951 && cp <= 0x0957)
    || (cp >= 0x0981 && cp <= 0x0983)
    || (cp >= 0x09bc && cp <= 0x09c4)
    || (cp >= 0x09c7 && cp <= 0x09cd)
    || (cp >= 0x0e31)
    && (
      (cp >= 0x0e31 && cp <= 0x0e3a)
      || (cp >= 0x0e47 && cp <= 0x0e4e)
    )
    || (cp >= 0x17b6 && cp <= 0x17d3)
    || (cp >= 0x17dd && cp <= 0x17dd)
    || (cp >= 0xfe00 && cp <= 0xfe0f)
    || (cp >= 0x200b && cp <= 0x200d)
    || cp === 0x00ad
  );
}

function emOf(cp) {
  if (isMark(cp) || cp === 0x200b || cp === 0x00ad || cp === 0xfeff) return 0;
  const ch = String.fromCodePoint(cp);
  if (ch === " ") return 0.28;
  if (/[iljI1|!'.:,;`]/.test(ch)) return 0.32;
  if (/[mwMW@%&]/.test(ch)) return 0.92;
  if (cp >= 0x4e00 && cp <= 0x9fff) return 1;
  if (cp >= 0x3400 && cp <= 0x4dbf) return 1;
  if (cp >= 0x3040 && cp <= 0x30ff) return 1;
  if (cp >= 0xac00 && cp <= 0xd7a3) return 0.96;
  if (cp >= 0x0600 && cp <= 0x06ff) return 0.48;
  if (cp >= 0x0750 && cp <= 0x077f) return 0.48;
  if (cp >= 0xfb50 && cp <= 0xfdff) return 0.48;
  if (cp >= 0xfe70 && cp <= 0xfefc) return 0.48;
  if (cp >= 0x0590 && cp <= 0x05ff) return 0.52;
  if (cp >= 0x0900 && cp <= 0x097f) return 0.72;
  if (cp >= 0x0980 && cp <= 0x09ff) return 0.72;
  if (cp >= 0x0e00 && cp <= 0x0e7f) return 0.58;
  if (cp >= 0x1780 && cp <= 0x17ff) return 0.95;
  if (cp >= 0x0400 && cp <= 0x052f) return 0.6;
  if (cp >= 0x0370 && cp <= 0x03ff) return 0.62;
  if (cp > 0xffff) return 1.15;
  return 0.58;
}

function graphemes(text) {
  if (typeof Intl.Segmenter === "function") {
    return [...new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text)].map((s) => s.segment);
  }
  return [...text];
}

function graphemeWidth(g, font, bold) {
  let em = 0;
  for (const ch of g) em += emOf(ch.codePointAt(0));
  if (em === 0) em = emOf(g.codePointAt(0));
  return em * font * (bold ? 1.06 : 1);
}

// CJK, Hangul, and Kana break on every cluster. Khmer, Thai, and Indic
// scripts do not, unless the string has a space or a soft break.
function canBreakAnywhere(text) {
  const cps = [...text].map((ch) => ch.codePointAt(0));
  const letters = cps.filter((cp) => emOf(cp) > 0);
  if (!letters.length) return false;
  const breaking = letters.filter((cp) =>
    (cp >= 0x4e00 && cp <= 0x9fff)
    || (cp >= 0x3040 && cp <= 0x30ff)
    || (cp >= 0xac00 && cp <= 0xd7a3)
  ).length;
  return breaking / letters.length > 0.6;
}

function measure(text, slot) {
  const raw = softenLineBreaks(String(text)).replace(/\{(\w+)\}/g, (_, k) => (k === "n" || k === "days" || k === "i" ? "12" : "xxxx"));
  const chunks = graphemes(raw);
  const free = canBreakAnywhere(raw);
  const lines = [];
  let line = 0;
  let worstToken = 0;
  let token = 0;
  const tracking = slot.tracking || 0;

  const push = (w, breakable) => {
    const extra = line > 0 ? tracking : 0;
    if (line > 0 && line + extra + w > slot.width && lines.length + 1 < slot.lines) {
      lines.push(line);
      line = w;
    } else if (line === 0) {
      line = w;
    } else {
      line += extra + w;
    }
    if (!breakable) token += w;
    else {
      worstToken = Math.max(worstToken, token);
      token = 0;
    }
  };

  for (let i = 0; i < chunks.length; i += 1) {
    const g = chunks[i];
    const w = graphemeWidth(g, slot.font, slot.bold);
    const soft = g === " " || g === "\n" || g === "\u200b" || g === "\u00ad" || /[/\-·|]/.test(g);
    push(w, free || soft);
  }
  worstToken = Math.max(worstToken, token);
  if (line > 0) lines.push(line);
  const widest = lines.reduce((m, w) => Math.max(m, w), 0);
  return {
    fits: widest <= slot.width + 1 && lines.length <= slot.lines && worstToken <= slot.width + 1,
    widest: Math.ceil(widest),
    lines: lines.length,
    worstToken: Math.ceil(worstToken),
  };
}

function resolved(locale) {
  return { ...FALLBACK, ...(STRINGS[locale] || {}) };
}

const failures = [];
const seen = new Map();

function note(locale, key, text, slotName, slot) {
  const result = measure(text, slot);
  if (result.fits) return;
  const id = `${locale}:${key}:${text}`;
  if (seen.has(id)) return;
  seen.set(id);
  failures.push({ locale, key, text, slotName, ...result, budget: slot.width, linesAllowed: slot.lines });
}

for (const lang of LANGUAGES) {
  const dict = resolved(lang.code);
  for (const [key, slotName] of Object.entries(SLOT_BY_KEY)) {
    note(lang.code, key, dict[key], slotName, TIGHT[slotName]);
  }
  for (const label of HARDCODED_NAV) {
    note(lang.code, "(hardcoded nav)", label, "nav", TIGHT.nav);
  }
  for (const [key, text] of Object.entries(dict)) {
    if (SLOT_BY_KEY[key]) continue;
    const slot = { width: CONTENT, font: 15, lines: 8, bold: false, tracking: 0 };
    const result = measure(text, slot);
    if (result.worstToken > CONTENT) {
      failures.push({
        locale: lang.code,
        key,
        text,
        slotName: "unbreakable",
        widest: result.widest,
        lines: result.lines,
        worstToken: result.worstToken,
        budget: CONTENT,
        linesAllowed: 8,
      });
    }
  }
}

const byLocale = new Map();
for (const row of failures) {
  if (!byLocale.has(row.locale)) byLocale.set(row.locale, []);
  byLocale.get(row.locale).push(row);
}

const full = LANGUAGES.filter((l) => l.tier === "full").map((l) => l.code);
const fallback = LANGUAGES.filter((l) => l.tier === "fallback").map((l) => l.code);
console.log(`locales=${LANGUAGES.length} full=${full.join(",")} fallback=${fallback.join(",")} (fallback uses English)`);
console.log(`tight failures=${failures.filter((f) => f.slotName !== "unbreakable").length} unbreakable=${failures.filter((f) => f.slotName === "unbreakable").length}`);

for (const lang of LANGUAGES) {
  const rows = byLocale.get(lang.code) || [];
  if (!rows.length) continue;
  console.log(`\n${lang.code} ${lang.native} (${lang.tier})`);
  for (const row of rows) {
    const sample = row.text.replace(/\s+/g, " ").slice(0, 72);
    console.log(
      `  ${row.slotName} ${row.key} ${row.widest}px/${row.budget}px lines=${row.lines}/${row.linesAllowed} token=${row.worstToken}px  ${sample}`,
    );
  }
}

if (!failures.length) console.log("\nNo cramped strings.");
process.exit(failures.length ? 1 : 0);
