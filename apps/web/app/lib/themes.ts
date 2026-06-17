// Audience-tailored landing-page templates.
//
// Each Theme is a self-contained design (palette, fonts, hero copy, background
// art, layout flavor) so the front page can be re-skinned per audience —
// corporate, cultural heritage, culinary, kids/gamified, academic — without
// code changes. Add a new audience by adding a Theme here.

export type ThemePalette = {
  bg: string;
  panel: string;
  accent: string;
  accent2: string;
  text: string;
  muted: string;
  border: string;
};

export type Theme = {
  id: string;
  name: string;
  audience: string;
  font: string;
  radius: string;
  palette: ThemePalette;
  // Background: an image under /public/themes plus an overlay gradient for
  // legibility, or just a gradient when background is null.
  background: string | null;
  overlay: string;
  hero: {
    title: string;
    subtitle: string;
    badge: string;
  };
  cards: { title: string; body: string; href: string; cta: string }[];
  gamified: boolean;
  decoration: string; // small emoji/motif accent used in the UI
};

const COMMON_CARDS = (cta: string): Theme["cards"] => [
  {
    title: "Join a Live Class",
    body: "Enter a class, watch the AI teacher present, and ask questions answered from the lesson.",
    href: "/class",
    cta,
  },
  {
    title: "Teacher Dashboard",
    body: "See the agent roster and platform capabilities at a glance.",
    href: "/dashboard",
    cta: "Open dashboard",
  },
  {
    title: "Consent & Privacy",
    body: "Vision features are opt-in and consent-gated (FERPA/GDPR/BIPA).",
    href: "/consent",
    cta: "Manage consent",
  },
];

export const THEMES: Record<string, Theme> = {
  corporate: {
    id: "corporate",
    name: "Corporate",
    audience: "Enterprise & professional training",
    font: "'Inter', ui-sans-serif, system-ui, sans-serif",
    radius: "10px",
    palette: {
      bg: "#0b1020",
      panel: "rgba(21,28,52,0.82)",
      accent: "#6ea8fe",
      accent2: "#8be9c0",
      text: "#e8ecf6",
      muted: "#9aa6c2",
      border: "#2a3461",
    },
    background: "/themes/corporate.png",
    overlay:
      "linear-gradient(90deg, rgba(7,11,24,0.92) 0%, rgba(7,11,24,0.65) 55%, rgba(7,11,24,0.35) 100%)",
    hero: {
      title: "Enterprise learning, delivered by an AI instructor",
      subtitle:
        "Scalable, measurable, on-brand training for your whole organization — live classes, analytics, and entitlements.",
      badge: "For teams & enterprises",
    },
    cards: COMMON_CARDS("Enter classroom"),
    gamified: false,
    decoration: "▣",
  },

  khmer: {
    id: "khmer",
    name: "Khmer Heritage",
    audience: "Cambodian / Khmer-language learning",
    font: "'Georgia', 'Times New Roman', serif",
    radius: "14px",
    palette: {
      bg: "#1a0f08",
      panel: "rgba(54,28,14,0.78)",
      accent: "#e8b54d",
      accent2: "#d98246",
      text: "#fdefd6",
      muted: "#d7b48a",
      border: "#6b4423",
    },
    background: "/themes/khmer.png",
    overlay:
      "linear-gradient(180deg, rgba(20,10,4,0.55) 0%, rgba(20,10,4,0.35) 40%, rgba(20,10,4,0.85) 100%)",
    hero: {
      title: "សិក្សា — Learn in your language, rooted in your culture",
      subtitle:
        "Khmer-first classes with an AI teacher, honoring heritage while opening a world of knowledge.",
      badge: "Khmer heritage edition",
    },
    cards: COMMON_CARDS("ចូលរៀន · Enter class"),
    gamified: false,
    decoration: "🛕",
  },

  culinary: {
    id: "culinary",
    name: "Culinary",
    audience: "Cooking & culinary classes",
    font: "'Georgia', serif",
    radius: "16px",
    palette: {
      bg: "#241712",
      panel: "rgba(58,36,26,0.8)",
      accent: "#e2703a",
      accent2: "#8aa05a",
      text: "#fbeddb",
      muted: "#d9b79c",
      border: "#7a4a32",
    },
    background: "/themes/culinary.png",
    overlay:
      "linear-gradient(90deg, rgba(28,16,10,0.9) 0%, rgba(28,16,10,0.55) 60%, rgba(28,16,10,0.2) 100%)",
    hero: {
      title: "Cook along with your own AI chef-instructor",
      subtitle:
        "Hands-on culinary classes with step-by-step guidance, technique videos, and live Q&A.",
      badge: "Culinary studio",
    },
    cards: COMMON_CARDS("Start cooking"),
    gamified: false,
    decoration: "🍳",
  },

  kids: {
    id: "kids",
    name: "Kids & Gamified",
    audience: "Children & young learners",
    font: "'Comic Sans MS', 'Baloo 2', ui-rounded, system-ui, sans-serif",
    radius: "22px",
    palette: {
      bg: "#0a2a4a",
      panel: "rgba(255,255,255,0.92)",
      accent: "#ff5d8f",
      accent2: "#2ec4b6",
      text: "#15324a",
      muted: "#5b7088",
      border: "#ffd23f",
    },
    background: "/themes/kids.png",
    overlay:
      "linear-gradient(180deg, rgba(135,206,250,0.25) 0%, rgba(135,206,250,0.1) 50%, rgba(10,42,74,0.45) 100%)",
    hero: {
      title: "Learning is an adventure! 🚀",
      subtitle:
        "Play, explore, and earn badges as a friendly AI teacher guides you level by level.",
      badge: "Adventure mode",
    },
    cards: COMMON_CARDS("Start the adventure"),
    gamified: true,
    decoration: "⭐",
  },

  academic: {
    id: "academic",
    name: "Academic",
    audience: "Universities & rigorous study",
    font: "'Georgia', serif",
    radius: "8px",
    palette: {
      bg: "#10141c",
      panel: "rgba(24,30,40,0.85)",
      accent: "#9db4d6",
      accent2: "#c8a96a",
      text: "#eef1f6",
      muted: "#9aa3b2",
      border: "#333c4d",
    },
    background: null,
    overlay:
      "radial-gradient(1200px 600px at 70% -10%, rgba(157,180,214,0.18), transparent), linear-gradient(180deg, #0c1018, #10141c)",
    hero: {
      title: "Deep, rigorous learning with an AI tutor",
      subtitle:
        "Structured courses, assessments, and a mastery graph that adapts to how you learn.",
      badge: "Academic edition",
    },
    cards: COMMON_CARDS("Enter lecture"),
    gamified: false,
    decoration: "📚",
  },
};

export const DEFAULT_THEME_ID = "corporate";

export function getTheme(id: string | null | undefined): Theme {
  if (id && THEMES[id]) return THEMES[id];
  return THEMES[DEFAULT_THEME_ID];
}

export function themeList(): Theme[] {
  return Object.values(THEMES);
}
