// Site-wide background / wallpaper catalog.
//
// 50+ themed designs usable throughout the year: holiday, seasonal, social,
// economic, realistic, surreal, artistic, kids, anime, and minimal. Most are
// lightweight CSS (gradients + inline SVG patterns) so they load instantly and
// add no binary weight; a few rich "image" wallpapers live in /public/wallpapers.
//
// `seasonalBackgroundId(date)` rotates an appropriate design by date (holidays
// first, then season) so the site stays fresh all year on "Auto".

import type { CSSProperties } from "react";

export type BgKind = "css" | "image";

export type Background = {
  id: string;
  name: string;
  category:
    | "holiday" | "seasonal" | "social" | "economic" | "realistic"
    | "surreal" | "artistic" | "kids" | "anime" | "minimal";
  kind: BgKind;
  css: string;        // CSS `background` value (also used as fallback for images)
  src?: string;       // /wallpapers/*.webp when kind === "image"
};

// --- inline SVG pattern helpers (URL-encoded data URIs) -------------------- //
function svg(body: string, w = 60, h = 60): string {
  const s = `<svg xmlns='http://www.w3.org/2000/svg' width='${w}' height='${h}' viewBox='0 0 ${w} ${h}'>${body}</svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(s)}")`;
}
const dots = (c: string) => svg(`<circle cx='6' cy='6' r='2' fill='${c}'/>`, 24, 24);
const grid = (c: string) => svg(`<path d='M40 0H0V40' fill='none' stroke='${c}' stroke-width='1'/>`, 40, 40);
const diag = (c: string) => svg(`<path d='M0 20L20 0M-5 5L5 -5M15 25L25 15' stroke='${c}' stroke-width='2'/>`, 20, 20);
const hearts = (c: string) => svg(`<path d='M12 21s-7-4.5-7-9a4 4 0 017-2.6A4 4 0 0119 12c0 4.5-7 9-7 9z' fill='${c}'/>`, 48, 48);
const snow = (c: string) => svg(`<g fill='${c}'><circle cx='10' cy='10' r='2'/><circle cx='30' cy='24' r='1.5'/><circle cx='46' cy='12' r='2'/><circle cx='20' cy='40' r='1.5'/></g>`, 56, 56);
const leaves = (c: string) => svg(`<path d='M8 24C8 14 18 8 28 8 28 18 18 24 8 24z' fill='${c}'/>`, 48, 48);
const network = (c: string) => svg(`<g stroke='${c}' stroke-width='1' fill='${c}'><line x1='10' y1='10' x2='50' y2='30'/><line x1='50' y1='30' x2='20' y2='55'/><line x1='10' y1='10' x2='20' y2='55'/><circle cx='10' cy='10' r='3'/><circle cx='50' cy='30' r='3'/><circle cx='20' cy='55' r='3'/></g>`, 70, 70);
const sparkle = (c: string) => svg(`<g fill='${c}'><path d='M20 6l2 8 8 2-8 2-2 8-2-8-8-2 8-2z'/><circle cx='44' cy='44' r='2'/><circle cx='48' cy='12' r='1.5'/></g>`, 60, 60);

// Quick CSS builders.
const lin = (deg: number, ...c: string[]) => `linear-gradient(${deg}deg, ${c.join(", ")})`;
const rad = (...c: string[]) => `radial-gradient(circle at 30% 20%, ${c.join(", ")})`;
const con = (...c: string[]) => `conic-gradient(from 210deg at 60% 40%, ${c.join(", ")})`;
const pat = (svgUrl: string, base: string) => `${svgUrl}, ${base}`;

export const BACKGROUNDS: Background[] = [
  // -------------------- holiday (year-round) -------------------- //
  { id: "newyear", name: "New Year Fireworks", category: "holiday", kind: "css",
    css: pat(sparkle("rgba(255,215,0,.5)"), rad("#1e293b", "#0b1020 60%")) },
  { id: "lunar", name: "Lunar New Year", category: "holiday", kind: "css",
    css: pat(sparkle("rgba(255,221,148,.5)"), lin(135, "#7f1d1d", "#b91c1c", "#dc2626")) },
  { id: "february-hearts", name: "February Hearts", category: "holiday", kind: "css",
    css: pat(hearts("rgba(244,114,182,.35)"), lin(135, "#831843", "#be185d", "#f472b6")) },
  { id: "march-green", name: "March Green", category: "holiday", kind: "css",
    css: pat(diag("rgba(255,255,255,.06)"), lin(135, "#064e3b", "#047857", "#10b981")) },
  { id: "spring-pastels", name: "Spring Pastels", category: "holiday", kind: "css",
    css: lin(135, "#fbcfe8", "#bae6fd", "#bbf7d0", "#fef9c3") },
  { id: "earthday", name: "Earth Day", category: "holiday", kind: "css",
    css: rad("#34d399", "#0ea5e9 55%", "#1e3a8a") },
  { id: "evening-lights", name: "Evening Lights", category: "holiday", kind: "css",
    css: pat(sparkle("rgba(250,204,21,.4)"), lin(160, "#1e1b4b", "#4c1d95", "#6d28d9")) },
  { id: "pride", name: "Pride Spectrum", category: "holiday", kind: "css",
    css: lin(120, "#e40303", "#ff8c00", "#ffed00", "#008026", "#004dff", "#750787") },
  { id: "july4", name: "Independence Day", category: "holiday", kind: "css",
    css: pat(sparkle("rgba(255,255,255,.4)"), lin(135, "#7f1d1d", "#1e3a8a", "#b91c1c")) },
  { id: "halloween", name: "Halloween Spooky", category: "holiday", kind: "css",
    css: rad("#f59e0b", "#7c2d12 45%", "#1c1917") },
  { id: "autumn-lights", name: "Autumn Lights", category: "holiday", kind: "css",
    css: pat(sparkle("rgba(255,191,0,.55)"), con("#7c2d12", "#b45309", "#f59e0b", "#7c2d12")) },
  { id: "thanksgiving", name: "Thanksgiving Harvest", category: "holiday", kind: "css",
    css: pat(leaves("rgba(180,83,9,.25)"), lin(135, "#78350f", "#b45309", "#d97706")) },
  { id: "winter-eve", name: "Winter Eve", category: "holiday", kind: "css",
    css: pat(snow("rgba(255,255,255,.5)"), lin(135, "#064e3b", "#7f1d1d")) },
  { id: "winter-blue", name: "Winter Blue", category: "holiday", kind: "css",
    css: pat(sparkle("rgba(255,255,255,.4)"), lin(135, "#0c4a6e", "#0369a1", "#38bdf8")) },
  { id: "kwanzaa", name: "Kwanzaa", category: "holiday", kind: "css",
    css: lin(135, "#7f1d1d", "#166534", "#111827") },

  // -------------------- seasonal -------------------- //
  { id: "spring", name: "Spring Bloom", category: "seasonal", kind: "css",
    css: pat(hearts("rgba(244,114,182,.18)"), lin(135, "#bbf7d0", "#fbcfe8", "#fde68a")) },
  { id: "summer", name: "Summer Sun", category: "seasonal", kind: "css",
    css: rad("#fde047", "#fb923c 50%", "#ef4444") },
  { id: "autumn", name: "Autumn Leaves", category: "seasonal", kind: "css",
    css: pat(leaves("rgba(120,53,15,.25)"), lin(135, "#b45309", "#9a3412", "#7c2d12")) },
  { id: "winter", name: "Winter Frost", category: "seasonal", kind: "css",
    css: pat(snow("rgba(255,255,255,.55)"), lin(135, "#1e3a8a", "#0ea5e9", "#bae6fd")) },

  // -------------------- social -------------------- //
  { id: "network", name: "Social Network", category: "social", kind: "css",
    css: pat(network("rgba(110,168,254,.18)"), lin(135, "#0b1020", "#1e293b")) },
  { id: "community", name: "Community Dots", category: "social", kind: "css",
    css: pat(dots("rgba(139,233,192,.25)"), lin(135, "#134e4a", "#0f766e")) },
  { id: "unity", name: "Unity Wave", category: "social", kind: "css",
    css: con("#1d4ed8", "#9333ea", "#db2777", "#1d4ed8") },
  { id: "awareness", name: "Awareness Ribbon", category: "social", kind: "css",
    css: lin(135, "#9333ea", "#ec4899", "#f59e0b") },
  { id: "global", name: "Global Connect", category: "social", kind: "css",
    css: pat(dots("rgba(255,255,255,.12)"), rad("#0ea5e9", "#1e3a8a 60%")) },

  // -------------------- economic -------------------- //
  { id: "market", name: "Market Grid", category: "economic", kind: "css",
    css: pat(grid("rgba(52,211,153,.16)"), lin(135, "#052e16", "#064e3b")) },
  { id: "growth", name: "Growth Chart", category: "economic", kind: "css",
    css: pat(svg(`<path d='M2 56L18 36L30 44L54 10' fill='none' stroke='rgba(52,211,153,.5)' stroke-width='3'/><path d='M48 10h8v8' fill='none' stroke='rgba(52,211,153,.5)' stroke-width='3'/>`, 60, 60), lin(135, "#0b1020", "#14532d")) },
  { id: "gold", name: "Gold Bull", category: "economic", kind: "css",
    css: con("#78350f", "#b45309", "#fbbf24", "#78350f") },
  { id: "fintech", name: "Fintech Circuit", category: "economic", kind: "css",
    css: pat(grid("rgba(56,189,248,.18)"), lin(135, "#0b1020", "#0c4a6e")) },
  { id: "blueprint", name: "Blueprint", category: "economic", kind: "css",
    css: pat(grid("rgba(147,197,253,.25)"), "#1e3a8a") },

  // -------------------- realistic -------------------- //
  { id: "dawn", name: "Dawn Sky", category: "realistic", kind: "css",
    css: lin(0, "#fde68a", "#fb923c", "#7c3aed", "#1e1b4b") },
  { id: "ocean", name: "Ocean Horizon", category: "realistic", kind: "css",
    css: lin(0, "#bae6fd", "#0ea5e9", "#0c4a6e", "#082f49") },
  { id: "mountain", name: "Mountain Mist", category: "realistic", kind: "css",
    css: lin(0, "#e2e8f0", "#94a3b8", "#475569", "#1e293b") },
  { id: "forest", name: "Forest Canopy", category: "realistic", kind: "css",
    css: rad("#4ade80", "#166534 55%", "#052e16") },
  { id: "library", name: "Warm Library", category: "realistic", kind: "image",
    css: lin(135, "#3b2410", "#1c1206"), src: "/wallpapers/realistic_library.webp" },

  // -------------------- surreal -------------------- //
  { id: "aurora", name: "Aurora Dream", category: "surreal", kind: "css",
    css: con("#22d3ee", "#a78bfa", "#34d399", "#22d3ee") },
  { id: "nebula", name: "Cosmic Nebula", category: "surreal", kind: "css",
    css: rad("#a21caf", "#312e81 50%", "#020617") },
  { id: "vaporwave", name: "Vaporwave Grid", category: "surreal", kind: "css",
    css: pat(grid("rgba(244,114,182,.3)"), lin(0, "#0f172a", "#831843", "#f472b6")) },
  { id: "chrome", name: "Liquid Chrome", category: "surreal", kind: "css",
    css: con("#cbd5e1", "#64748b", "#e2e8f0", "#94a3b8", "#cbd5e1") },
  { id: "dreamscape", name: "Dreamscape", category: "surreal", kind: "image",
    css: con("#7c3aed", "#0ea5e9", "#f472b6", "#7c3aed"), src: "/wallpapers/surreal_dreamscape.webp" },
  { id: "portal", name: "Portal", category: "surreal", kind: "css",
    css: rad("#f0abfc", "#7c3aed 40%", "#1e1b4b 75%", "#020617") },

  // -------------------- artistic -------------------- //
  { id: "brush", name: "Brush Strokes", category: "artistic", kind: "css",
    css: pat(diag("rgba(255,255,255,.08)"), con("#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#ef4444")) },
  { id: "bauhaus", name: "Bauhaus", category: "artistic", kind: "css",
    css: lin(45, "#ef4444 0 33%", "#facc15 33% 66%", "#2563eb 66%") },
  { id: "mondrian", name: "Mondrian", category: "artistic", kind: "css",
    css: "linear-gradient(90deg,#fff 0 60%,#111 60% 62%,#e11d48 62%), linear-gradient(0deg,#fff 0 70%,#111 70% 72%,#2563eb 72%)" },
  { id: "watercolor", name: "Watercolor", category: "artistic", kind: "css",
    css: rad("#fca5a5", "#fcd34d 30%", "#a7f3d0 60%", "#93c5fd") },
  { id: "stained", name: "Stained Glass", category: "artistic", kind: "css",
    css: con("#dc2626", "#7c3aed", "#0891b2", "#16a34a", "#ca8a04", "#dc2626") },
  { id: "meshgrad", name: "Gradient Mesh", category: "artistic", kind: "css",
    css: "radial-gradient(at 20% 20%,#f472b6,transparent 40%),radial-gradient(at 80% 0%,#60a5fa,transparent 45%),radial-gradient(at 50% 80%,#34d399,transparent 45%),#0b1020" },
  { id: "abstract", name: "Abstract Canvas", category: "artistic", kind: "image",
    css: "radial-gradient(at 30% 30%,#f472b6,transparent 45%),radial-gradient(at 70% 60%,#60a5fa,transparent 45%),#0b1020",
    src: "/wallpapers/artistic_abstract.webp" },

  // -------------------- kids -------------------- //
  { id: "crayon", name: "Crayon Doodles", category: "kids", kind: "css",
    css: pat(sparkle("rgba(255,255,255,.4)"), lin(135, "#fca5a5", "#fdba74", "#fde047", "#86efac", "#93c5fd")) },
  { id: "candy", name: "Candy Pop", category: "kids", kind: "css",
    css: pat(dots("rgba(255,255,255,.35)"), lin(135, "#f9a8d4", "#a5b4fc", "#7dd3fc")) },
  { id: "rainbow", name: "Rainbow Clouds", category: "kids", kind: "css",
    css: lin(135, "#fda4af", "#fdba74", "#fde047", "#86efac", "#7dd3fc", "#c4b5fd") },
  { id: "jungle", name: "Jungle Safari", category: "kids", kind: "css",
    css: pat(leaves("rgba(255,255,255,.18)"), lin(135, "#65a30d", "#16a34a", "#15803d")) },
  { id: "space-kids", name: "Space Rockets", category: "kids", kind: "image",
    css: rad("#a78bfa", "#1e1b4b 60%", "#020617"), src: "/wallpapers/kids_space.webp" },

  // -------------------- anime -------------------- //
  { id: "sakura", name: "Sakura Sky", category: "anime", kind: "css",
    css: pat(hearts("rgba(251,207,232,.4)"), lin(160, "#fbcfe8", "#c4b5fd", "#a5b4fc")) },
  { id: "shoujo", name: "Shoujo Sunset", category: "anime", kind: "css",
    css: lin(0, "#fde68a", "#fb7185", "#a855f7", "#312e81") },
  { id: "cyber", name: "Cyber City", category: "anime", kind: "css",
    css: pat(grid("rgba(34,211,238,.25)"), lin(0, "#020617", "#312e81", "#db2777")) },
  { id: "magical", name: "Magical Sparkle", category: "anime", kind: "css",
    css: pat(sparkle("rgba(255,255,255,.55)"), con("#a78bfa", "#f0abfc", "#7dd3fc", "#a78bfa")) },
  { id: "anime-class", name: "Anime Classroom", category: "anime", kind: "image",
    css: lin(160, "#bae6fd", "#fbcfe8", "#fde68a"), src: "/wallpapers/anime_classroom.webp" },

  // -------------------- minimal -------------------- //
  { id: "slate", name: "Midnight Slate", category: "minimal", kind: "css",
    css: lin(135, "#0b1020", "#1d2746") },
  { id: "paper", name: "Soft Paper", category: "minimal", kind: "css",
    css: pat(dots("rgba(0,0,0,.04)"), "#f8fafc") },
  { id: "darkmesh", name: "Dark Mesh", category: "minimal", kind: "css",
    css: pat(grid("rgba(255,255,255,.05)"), "#0b1020") },
  { id: "softlight", name: "Soft Light", category: "minimal", kind: "css",
    css: rad("#ffffff", "#e2e8f0 60%", "#cbd5e1") },
];

export const DEFAULT_BACKGROUND_ID = "meshgrad";

export const CATEGORIES = [
  "holiday", "seasonal", "social", "economic", "realistic",
  "surreal", "artistic", "kids", "anime", "minimal",
] as const;

const BY_ID: Record<string, Background> = Object.fromEntries(
  BACKGROUNDS.map((b) => [b.id, b])
);

export function getBackground(id: string | null | undefined): Background {
  return (id && BY_ID[id]) || BY_ID[DEFAULT_BACKGROUND_ID];
}

// Pick a date-appropriate design (holidays first, then season). Year-round.
export function seasonalBackgroundId(d: Date = new Date()): string {
  const m = d.getMonth() + 1; // 1-12
  const day = d.getDate();
  const md = m * 100 + day;
  // Fixed-window holidays.
  if (md >= 1231 || md <= 102) return "newyear";        // New Year's Eve / Day
  if (md >= 1215) return "winter-eve";                    // mid-late December
  if (m === 2 && day >= 10 && day <= 16) return "february-hearts";
  if ((m === 1 && day >= 21) || (m === 2 && day <= 12)) return "lunar"; // approx LNY
  if (m === 3 && day >= 15 && day <= 18) return "march-green";
  if (md === 422 || (m === 4 && day >= 18 && day <= 24)) return "earthday";
  if (m === 6) return "pride";
  if (m === 7 && day <= 6) return "july4";
  if (m === 10 && day >= 24) return "halloween";
  if (m === 11 && day >= 20 && day <= 30) return "thanksgiving";
  if (m === 11 || (m === 12 && day < 15)) return "autumn";
  // Seasonal fallback (northern hemisphere).
  if (m >= 3 && m <= 5) return "spring";
  if (m >= 6 && m <= 8) return "summer";
  if (m === 9 || m === 10) return "autumn";
  return "winter";
}

export function backgroundStyle(bg: Background): CSSProperties {
  if (bg.kind === "image" && bg.src) {
    return {
      backgroundImage: `linear-gradient(rgba(7,11,26,0.55), rgba(7,11,26,0.7)), url(${bg.src})`,
      backgroundSize: "cover",
      backgroundPosition: "center",
      backgroundAttachment: "fixed",
    };
  }
  return { background: bg.css, backgroundAttachment: "fixed" };
}
