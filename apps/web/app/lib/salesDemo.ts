export const SALES_DEMO_FLAGS = {
  enabled: "sales_demo.enabled",
  featuredCourses: "sales_demo.featured_courses",
  fullAppCta: "sales_demo.full_app_cta",
  exclusive: "sales_demo.exclusive",
  // When loginEnabled=false the Log in button + /login form are hidden.
  // Admins can still sign in via /login?override=1 (lock-out guard).
  loginEnabled: "sales_demo.login_enabled",
  // When restrictSignedIn=true, signed-in NON-admin accounts stay in the
  // demo-only showcase (no full nav / full home). Admins always see the
  // full site.
  restrictSignedIn: "sales_demo.restrict_signed_in",
} as const;

/** Query param that forces the sign-in form to render even when
 *  sales_demo.login_enabled is off. The admin lock-out escape hatch. */
export const LOGIN_OVERRIDE_PARAM = "override";

/** Feature cards shown on /demo when sales_demo.exclusive (demo-only mode) is on. */
export const DEMO_ONLY_FEATURE_IDS = ["solo", "drive", "arcade"] as const;

export const SALES_DEMO_COURSES = [
  {
    id: "demo-sexual-harassment",
    title: "Sexual Harassment Prevention",
    category: "Compliance",
    emoji: "🛡️",
    duration: "45 min",
    description: "Recognize harassment, understand workplace rights, and build a respectful culture.",
    colors: ["#6366f1", "#8b5cf6"],
  },
  {
    id: "demo-drivers-ed",
    title: "Driver's Education",
    category: "Safety",
    emoji: "🚗",
    duration: "60 min",
    description: "Master road rules, defensive driving, and safe decision-making.",
    colors: ["#f59e0b", "#f97316"],
  },
  {
    id: "demo-fire-safety",
    title: "Fire Safety",
    category: "Workplace Safety",
    emoji: "🔥",
    duration: "30 min",
    description: "Learn evacuation, prevention, and extinguisher procedures.",
    colors: ["#ef4444", "#dc2626"],
  },
  {
    id: "demo-food-safety",
    title: "Food Safety Handler Certification",
    category: "Food & Beverage",
    emoji: "🍽️",
    duration: "45 min",
    description: "Practice proper food handling, storage, hygiene, and contamination prevention.",
    colors: ["#10b981", "#059669"],
  },
  {
    id: "demo-osha",
    title: "OSHA Safety Training",
    category: "Workplace Safety",
    emoji: "⚠️",
    duration: "60 min",
    description: "Explore federal safety regulations, hazards, and compliance.",
    colors: ["#f97316", "#ea580c"],
  },
] as const;

export const SALES_DEMO_FEATURES = [
  {
    id: "course-studio",
    flagKey: "sales_demo.course_studio",
    href: "/demo/drivers-ed",
    emoji: "🎓",
    title: "Driver's Education demo",
    subtitle: "Serenity · 10 minutes, free",
    description: "Serenity (holographic AI teacher + xAI) presents the free 10-minute demo. The full course, and Food Health & Safety, are paid unless you are an admin.",
  },
  {
    id: "solo",
    flagKey: "sales_demo.solo_ai",
    href: "/demo/drivers-ed",
    emoji: "🤖",
    title: "Serenity · Solo AI",
    subtitle: "Driver's Ed · 10-min demo",
    description: "Serenity walks you through the free 10-minute driver's ed demo with Salane Voice.",
  },
  {
    id: "drive",
    flagKey: "sales_demo.drive_mode",
    href: "/demo/on-the-go",
    emoji: "🎧",
    title: "Serenity · On-the-Go",
    subtitle: "Audio only · 10-min demo",
    description: "Serenity teaches the same driver's ed demo by ear (xAI when configured). The free trial stops at 10 minutes.",
  },
  {
    id: "arcade",
    flagKey: "sales_demo.arcade_games",
    href: "/demo/arcade",
    emoji: "🎮",
    title: "Vision Play",
    subtitle: "Machine vision for kids",
    description: "Machine vision: faces, hands, movement, and listening. The camera stays in the browser.",
  },
  {
    id: "languages",
    flagKey: "sales_demo.language_practice",
    href: "/languages",
    emoji: "🗣️",
    title: "Language Practice",
    subtitle: "Speak with confidence",
    description: "AI pronunciation coaching with listening, scoring, and real-time guidance.",
  },
] as const;
