// API client for the AI Classroom mobile app.
//
// Points at the curriculum service. On a physical device, localhost won't reach
// your machine - set the URL in app.json (expo.extra.curriculumUrl) to your LAN
// IP (e.g. http://192.168.1.20:8005) or your deployed backend.

import Constants from "expo-constants";

const CURRICULUM_URL: string =
  (Constants.expoConfig?.extra?.curriculumUrl as string) || "http://localhost:8005";

export type AudioCourseRow = {
  id: string; title: string; category: string; subject: string; level: string;
  duration_min: number; tags: string[]; segments: number; drive_safe: boolean;
};
export type AudioSegment = { heading: string; text: string };
export type AudioCourse = {
  id: string; title: string; category: string; subject: string; level: string;
  duration_min: number; tags: string[]; drive_safe: boolean; segments: AudioSegment[];
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${CURRICULUM_URL}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export function listAudioCourses(category?: string, q?: string) {
  const p = new URLSearchParams({ limit: "60" });
  if (category) p.set("category", category);
  if (q) p.set("q", q);
  return get<{ total: number; courses: AudioCourseRow[] }>(`/audio/courses?${p.toString()}`);
}

export function getAudioCategories() {
  return get<{ categories: { category: string; count: number }[] }>("/audio/categories");
}

export function getAudioCourse(id: string) {
  return get<AudioCourse>(`/audio/courses/${encodeURIComponent(id)}`);
}
