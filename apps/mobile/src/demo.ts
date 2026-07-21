import { Dimensions } from "react-native";

export type DemoCourse = {
  id: string;
  title: string;
  category: string;
  emoji: string;
  duration_min: number;
  segments: number;
  level: string;
  gradientStart: string;
  gradientEnd: string;
  description: string;
};

export const DEMO_COURSES: DemoCourse[] = [
  {
    id: "demo-sexual-harassment",
    title: "Sexual Harassment Prevention",
    category: "Compliance",
    emoji: "🛡️",
    duration_min: 45,
    segments: 8,
    level: "All Levels",
    gradientStart: "#6366f1",
    gradientEnd: "#8b5cf6",
    description: "Understand workplace rights, recognize harassment, and build a respectful culture.",
  },
  {
    id: "demo-drivers-ed",
    title: "Driver's Education",
    category: "Safety",
    emoji: "🚗",
    duration_min: 60,
    segments: 12,
    level: "Beginner",
    gradientStart: "#f59e0b",
    gradientEnd: "#f97316",
    description: "Master road rules, safe driving techniques, and defensive driving strategies.",
  },
  {
    id: "demo-fire-safety",
    title: "Fire Safety",
    category: "Workplace Safety",
    emoji: "🔥",
    duration_min: 30,
    segments: 6,
    level: "All Levels",
    gradientStart: "#ef4444",
    gradientEnd: "#dc2626",
    description: "Learn evacuation procedures, fire prevention, and how to use extinguishers.",
  },
  {
    id: "demo-food-safety",
    title: "Food Safety Handler Certification",
    category: "Food & Beverage",
    emoji: "🍽️",
    duration_min: 45,
    segments: 9,
    level: "All Levels",
    gradientStart: "#10b981",
    gradientEnd: "#059669",
    description: "Proper food handling, storage, hygiene, and contamination prevention.",
  },
  {
    id: "demo-osha",
    title: "OSHA Safety Training",
    category: "Workplace Safety",
    emoji: "⚠️",
    duration_min: 60,
    segments: 10,
    level: "All Levels",
    gradientStart: "#f97316",
    gradientEnd: "#ea580c",
    description: "Federal safety regulations, hazard identification, and compliance requirements.",
  },
];

export const DEMO_FEATURES = [
  {
    id: "solo",
    emoji: "🤖",
    title: "Solo AI Session",
    subtitle: "Ask Theodore anything",
    description: "1:1 AI tutor that adapts to your pace, answers questions, and guides you through any course.",
    color: "#6366f1",
  },
  {
    id: "drive",
    emoji: "🎧",
    title: "On-the-Go Mode",
    subtitle: "Learn hands-free",
    description: "Full audio-only mode. Learn while commuting, exercising, or anywhere without looking at a screen.",
    color: "#f59e0b",
  },
  {
    id: "arcade",
    emoji: "🎮",
    title: "Arcade Games",
    subtitle: "Test your knowledge",
    description: "Instant knowledge games — spot the difference, creature catch, card match and more.",
    color: "#10b981",
  },
  {
    id: "languages",
    emoji: "🗣️",
    title: "Language Practice",
    subtitle: "Speak with confidence",
    description: "AI pronunciation coach listens, scores your accent, and coaches you in real-time.",
    color: "#ec4899",
  },
];
