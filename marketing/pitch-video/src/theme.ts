// Salareen brand tokens — sourced from docs/brand/branding.txt,
// apps/web/app/globals.css and apps/mobile/src/theme.ts.
export const COLORS = {
  bg: "#0b1020",
  bgDeep: "#070a16",
  panel: "#151c34",
  panel2: "#1d2746",
  text: "#e8ecf6",
  muted: "#9aa6c2",
  border: "#2a3461",
  accent: "#6ea8fe", // web interactive blue
  brand: "#0ea5e9", // sky-cyan
  mint: "#8be9c0",
  gold: "#fbbf24",
  red: "#e50914", // Netflix-style CTA red
};

export const FONT =
  '"Helvetica Neue", Helvetica, "Segoe UI", Roboto, Arial, system-ui, sans-serif';

export const VIDEO = {
  fps: 30,
  width: 1920,
  height: 1080,
};

// Scene durations in frames (30fps). Total ~885f ≈ 29.5s.
export const SCENES = {
  hook: 110,
  problem: 110,
  reveal: 150,
  features: 195,
  safety: 85,
  scale: 150,
  close: 85,
};

export const TOTAL_FRAMES = Object.values(SCENES).reduce((a, b) => a + b, 0);
