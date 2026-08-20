/** Vision + voice test helpers for the camera check walkthrough. */

const CHAR_POOL = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

export function randomVisionChars(len = 7): string {
  let out = "";
  for (let i = 0; i < len; i++) {
    out += CHAR_POOL[Math.floor(Math.random() * CHAR_POOL.length)];
  }
  return out;
}

export const VISION_COLORS: { id: string; hex: string; names: Record<string, string[]> }[] = [
  { id: "red", hex: "#dc2626", names: { en: ["red"], es: ["rojo"], fr: ["rouge"], vi: ["đỏ", "do"], km: ["ក្រហម", "krahom"] } },
  { id: "green", hex: "#16a34a", names: { en: ["green"], es: ["verde"], fr: ["vert"], vi: ["xanh lá", "xanh la"], km: ["បៃតង", "baitong"] } },
  { id: "blue", hex: "#2563eb", names: { en: ["blue"], es: ["azul"], fr: ["bleu"], vi: ["xanh dương", "xanh duong"], km: ["ខៀវ", "khiev"] } },
  { id: "yellow", hex: "#eab308", names: { en: ["yellow"], es: ["amarillo"], fr: ["jaune"], vi: ["vàng", "vang"], km: ["លឿង", "leung"] } },
];

export function pickVisionColor() {
  return VISION_COLORS[Math.floor(Math.random() * VISION_COLORS.length)];
}

/** Normalize spoken/typed answer for fuzzy match. */
export function normalizeSpeech(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function spokenMatchesChars(spoken: string, expected: string): boolean {
  const norm = normalizeSpeech(spoken).replace(/\s/g, "");
  const target = expected.toLowerCase();
  if (!norm || !target) return false;
  // Allow in-order letters with gaps (e.g. "p r s t l n e").
  let ti = 0;
  for (const ch of norm) {
    if (ch === target[ti]) ti++;
    if (ti >= target.length) return true;
  }
  return norm.includes(target);
}

export function spokenMatchesColor(spoken: string, color: (typeof VISION_COLORS)[0], locale: string): boolean {
  const norm = normalizeSpeech(spoken);
  if (!norm) return false;
  const loc = locale.split("-")[0];
  const names = [...(color.names.en || []), ...(color.names[loc] || [])];
  return names.some((n) => norm.includes(normalizeSpeech(n)));
}

/** Eye-region blink: sudden drop in upper-face luminance between frames. */
export function detectBlink(prevEye: number | null, eyeLuma: number): boolean {
  if (prevEye == null) return false;
  return prevEye - eyeLuma > 0.12;
}

export function eyeRegionLuma(grid: number[][], box: { x: number; y: number; width: number; height: number } | null): number | null {
  if (!box || !grid.length || !grid[0]?.length) return null;
  const gh = grid.length;
  const gw = grid[0].length;
  const x0 = Math.max(0, Math.floor((box.x + box.width * 0.15) * gw));
  const x1 = Math.min(gw, Math.ceil((box.x + box.width * 0.85) * gw));
  const y0 = Math.max(0, Math.floor((box.y + box.height * 0.1) * gh));
  const y1 = Math.min(gh, Math.ceil((box.y + box.height * 0.45) * gh));
  let sum = 0;
  let n = 0;
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      sum += grid[y][x];
      n++;
    }
  }
  return n ? sum / n : null;
}
