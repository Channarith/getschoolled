export const SALES_DEMO_FLAGS = {
  enabled: "sales_demo.enabled",
  featuredCourses: "sales_demo.featured_courses",
  fullAppCta: "sales_demo.full_app_cta",
  exclusive: "sales_demo.exclusive",
} as const;

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
    subtitle: "10 minutes, free",
    description: "Anyone can take the 10-minute driver's ed demo. The full course, and Food Health & Safety, are paid unless you are an admin.",
  },
  {
    id: "solo",
    flagKey: "sales_demo.solo_ai",
    href: "/class",
    emoji: "🤖",
    title: "Solo AI Session",
    subtitle: "Ask Theodore anything",
    description: "A 1:1 tutor that adapts pacing and guides learners through any course.",
  },
  {
    id: "drive",
    flagKey: "sales_demo.drive_mode",
    href: "/drive",
    emoji: "🎧",
    title: "On-the-Go Mode",
    subtitle: "Learn hands-free",
    description: "Audio-first learning for commuting, exercising, and screen-free study.",
  },
  {
    id: "arcade",
    flagKey: "sales_demo.arcade_games",
    href: "/demo/arcade",
    emoji: "🎮",
    title: "Vision arcade",
    subtitle: "Machine vision for kids",
    description: "Children play webcam games from the children lab: faces, hands, and movement. The camera stays in the browser.",
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
