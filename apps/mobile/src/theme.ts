/** Salareen mobile design tokens — aligned with apps/web globals.css + Netflix UX. */
export const theme = {
  colors: {
    bg: "#0b1020",
    panel: "rgba(21, 28, 52, 0.82)",
    panelSolid: "#151c34",
    panel2: "#1d2746",
    border: "rgba(42, 52, 97, 0.65)",
    text: "#e8ecf6",
    muted: "#9aa6c2",
    accent: "#6ea8fe",
    accent2: "#8be9c0",
    brand: "#0ea5e9",
    netflix: "#e50914",
    netflixDark: "#b20710",
    success: "#22c55e",
    danger: "#ef4444",
    gold: "#fbbf24",
    scrim: "rgba(11, 16, 32, 0.72)",
    scrimHeavy: "rgba(11, 16, 32, 0.92)",
    glass: "rgba(21, 28, 52, 0.55)",
  },
  radius: {
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    pill: 999,
  },
  shadow: {
    card: {
      shadowColor: "#000",
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.35,
      shadowRadius: 16,
      elevation: 8,
    },
    hero: {
      shadowColor: "#000",
      shadowOffset: { width: 0, height: 12 },
      shadowOpacity: 0.45,
      shadowRadius: 24,
      elevation: 12,
    },
  },
  spacing: {
    screenX: 16,
    railGap: 12,
    section: 22,
  },
  typography: {
    hero: { fontSize: 28, fontWeight: "800" as const, letterSpacing: -0.5 },
    title: { fontSize: 22, fontWeight: "800" as const },
    railTitle: { fontSize: 18, fontWeight: "800" as const },
    body: { fontSize: 14, lineHeight: 20 },
    caption: { fontSize: 12, lineHeight: 16 },
    kicker: {
      fontSize: 11,
      fontWeight: "700" as const,
      letterSpacing: 1.2,
      textTransform: "uppercase" as const,
    },
  },
  motion: {
    pressScale: 0.96,
    pressDuration: 120,
    fadeDuration: 220,
    kenBurnsMs: 52000,
  },
} as const;

export const wallpapers = {
  hero: require("../assets/wallpapers/wisdom_bodhi.webp"),
  library: require("../assets/wallpapers/wisdom_library.webp"),
  realistic: require("../assets/wallpapers/realistic_library.webp"),
} as const;

/** Category → poster gradient (Netflix-style tile art). */
export function categoryGradient(category: string): [string, string] {
  const key = category.toLowerCase();
  if (key.includes("language")) return ["#4338ca", "#7c3aed"];
  if (key.includes("science")) return ["#0ea5e9", "#0369a1"];
  if (key.includes("history")) return ["#b45309", "#78350f"];
  if (key.includes("tech")) return ["#1e293b", "#0f766e"];
  if (key.includes("finance") || key.includes("business")) return ["#15803d", "#14532d"];
  if (key.includes("wellness") || key.includes("mind")) return ["#be185d", "#831843"];
  return ["#1f2937", "#4338ca"];
}
