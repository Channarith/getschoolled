// API client for the AI Classroom mobile app.
//
// Targets the curriculum service. On a physical device, "localhost" points at
// the phone, so set the URL in app.json (expo.extra.curriculumUrl) to your
// machine's LAN IP (e.g. http://192.168.1.20:8005) or your deployed backend.

import Constants from "expo-constants";

import type { MascotResolve } from "./mascot";

export const CURRICULUM_URL: string =
  (Constants.expoConfig?.extra?.curriculumUrl as string) || "http://localhost:8005";

export const MEMORY_URL: string =
  (Constants.expoConfig?.extra?.memoryUrl as string) || "http://localhost:8004";

export type AudioCourseRow = {
  id: string; title: string; category: string; subject: string; level: string;
  duration_min: number; tags: string[]; segments: number; drive_safe: boolean;
};
export type AudioSegment = { heading: string; text: string };
export type AudioCourse = {
  id: string; title: string; category: string; subject: string; level: string;
  duration_min: number; tags: string[]; drive_safe: boolean;
  segments: AudioSegment[]; locale?: string;
};

// `category_id` is the canonical English identifier (use as a filter
// value); `category` is the localized display label (render in UI).
// Older clients receive only `category`; the API accepts either form
// in filter params so missing `category_id` is harmless.
export type CategoryRow = {
  category: string; category_id?: string; count: number;
};

export type HomeRail = {
  rail_id: string; title: string; reason?: string;
  courses: { course_id: string; title: string; category?: string;
             tags?: string[]; level?: string; popularity?: number }[];
};

export type NotificationItem = {
  id: string;
  kind: "new_class" | "continue" | "recommended" | "reminder" | "streak" | "system";
  title: string; body: string;
  course_id?: string | null;
  deep_link?: string | null;
  created_at: string;
  icon: "bell" | "sparkle" | "flame" | "play" | "trophy" | "gift";
};

export type NotificationFeed = {
  student_id: string;
  generated_at: string;
  unread: number;
  items: NotificationItem[];
};

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${CURRICULUM_URL}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export function listAudioCourses(category?: string, q?: string, limit = 60,
                                 locale?: string) {
  const p = new URLSearchParams({ limit: String(limit) });
  if (category) p.set("category", category);
  if (q) p.set("q", q);
  if (locale) p.set("locale", locale);
  return get<{ total: number; locale?: string; courses: AudioCourseRow[] }>(
    `/audio/courses?${p.toString()}`);
}

export function getAudioCategories(locale?: string) {
  const p = new URLSearchParams();
  if (locale) p.set("locale", locale);
  const qs = p.toString();
  return get<{ categories: CategoryRow[]; locale?: string }>(
    `/audio/categories${qs ? `?${qs}` : ""}`);
}

export function getAudioCourse(id: string, locale?: string) {
  const p = new URLSearchParams();
  if (locale) p.set("locale", locale);
  const qs = p.toString();
  return get<AudioCourse>(
    `/audio/courses/${encodeURIComponent(id)}${qs ? `?${qs}` : ""}`);
}

export function getNotificationsFeed(opts: {
  studentId?: string;
  interests?: string[];
  inProgress?: string[];
  completed?: string[];
  streakDays?: number;
  limit?: number;
  locale?: string;
} = {}) {
  const p = new URLSearchParams();
  if (opts.studentId) p.set("student_id", opts.studentId);
  if (opts.interests?.length) p.set("interests", opts.interests.join(","));
  if (opts.inProgress?.length) p.set("in_progress", opts.inProgress.join(","));
  if (opts.completed?.length) p.set("completed", opts.completed.join(","));
  if (typeof opts.streakDays === "number") p.set("streak_days", String(opts.streakDays));
  if (typeof opts.limit === "number") p.set("limit", String(opts.limit));
  if (opts.locale) p.set("locale", opts.locale);
  const qs = p.toString();
  return get<NotificationFeed>(`/notifications/feed${qs ? `?${qs}` : ""}`);
}

// Optional: Netflix-style home rails from the catalog (adaptive courses, not
// audio-only). Falls back to an empty list if the catalog is empty / offline.
export async function getHomeRails(kids = false): Promise<HomeRail[]> {
  try {
    const r = await get<{ rails: HomeRail[] }>(`/home?kids=${kids ? "true" : "false"}`);
    return r.rails || [];
  } catch {
    return [];
  }
}

// --- feature flags + locale mascots (memory service) -------------------- //

async function memoryGet<T>(path: string): Promise<T> {
  const res = await fetch(`${MEMORY_URL}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export async function getFlag(key: string): Promise<unknown> {
  const r = await memoryGet<{ value: unknown }>(`/flags/${encodeURIComponent(key)}`);
  return r.value;
}

export async function resolveMascot(locale: string): Promise<MascotResolve> {
  const qs = new URLSearchParams({ locale });
  return memoryGet<MascotResolve>(`/mascots/resolve?${qs.toString()}`);
}
