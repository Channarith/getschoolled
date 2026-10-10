// Khmer words are written without spaces. iOS and Android will not break
// those runs, so a sentence draws as one line and slides over the next
// control. A zero-width space before each consonant (never after a coeng,
// which ties the next consonant to the previous one) is an invisible break.

const COENG = 0x17d2;

export function softenLineBreaks(text: string): string {
  if (!/[\u1780-\u17FF]/.test(text)) return text;
  let out = "";
  let prev = 0;
  let inKhmer = false;
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0;
    const consonant = cp >= 0x1780 && cp <= 0x17b3;
    if (consonant && inKhmer && prev !== COENG) out += "\u200b";
    out += ch;
    inKhmer = cp >= 0x1780 && cp <= 0x17ff;
    prev = cp;
  }
  return out;
}
