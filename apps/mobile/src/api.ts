// API client for the Salareen mobile app (curriculum, identity, memory).

import type { MascotResolve } from "./mascot";
import { CURRICULUM_URL, IDENTITY_URL, MEMORY_URL } from "./config";
import { getToken } from "./storage";

export { CURRICULUM_URL, IDENTITY_URL, MEMORY_URL };

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

export type CategoryRow = {
  category: string; category_id?: string; count: number;
};

export type HomeRail = {
  key: string; title: string; reason?: string;
  courses: { course_id: string; title: string; category?: string;
             tags?: string[]; level?: string; popularity?: number;
             source?: string; format?: string; deep_link?: string }[];
};

export type LearnableItem = {
  id: string; source: string; source_id: string; title: string; subtitle?: string;
  category: string; subject: string; format: string; level: string; language: string;
  duration_min: number; tags: string[]; preview: string; deep_link: string;
  drive_safe?: boolean;
};

export type LearnSearchResult = {
  total: number; offset: number; limit: number; items: LearnableItem[];
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

export type Account = {
  id: string; email: string; display_name: string;
  tier: string; region: string; is_admin?: boolean;
};

export type StudentProfile = {
  id: string; display_name: string; age_band: string;
  mastery: Record<string, number>; completed_course_ids: string[]; interests: string[];
  primary_style?: string; learning_pace?: string; learning_structure?: string;
  session_length?: string; group_preference?: string; reading_level?: string;
  motivation?: string; accessibility?: Record<string, boolean>;
  accommodations_notes?: string; learner_category?: string;
  onboarding_completed_at?: number | null;
  onboarding_answers?: Record<string, unknown>;
};

export type SurveyQuestion = {
  id: string; type: "choice" | "bool" | "text" | "rating";
  prompt: string; required?: boolean; options?: string[];
};

export type SurveyTemplate = {
  version: string; title: string; subtitle?: string; questions: SurveyQuestion[];
};

export type JobPosting = {
  id: string; title: string; company: string; location: string; source: string;
  url: string; employment_type: string; salary_range: string; posted_days_ago: number;
  category: string; skills: string[]; nice_to_have: string[]; description: string;
};
export type CourseMatch = {
  course_id: string; title: string; covered_skills: string[]; match: number;
};
export type JobMatch = {
  job: JobPosting; required: string[]; matched_courses: CourseMatch[];
  covered: string[]; missing: string[]; coverage_pct: number; recommended_path: string[];
};

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || j.message || detail;
    } catch { /* ignore */ }
    throw new Error(`${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function networkError(base: string, err: unknown): Error {
  const msg = err instanceof Error ? err.message : String(err);
  if (/network request failed|failed to connect|ECONNREFUSED|timed out|aborted/i.test(msg)) {
    return new Error(
      `Cannot reach backend at ${base}. Start it on your Mac (make run-identity for login on :8008). (${msg})`,
    );
  }
  return err instanceof Error ? err : new Error(msg);
}

async function get<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, init);
  } catch (err) {
    throw networkError(base, err);
  }
  return jsonOrThrow<T>(res);
}

/** True when the service responds over HTTP (401 without a token is OK). */
export async function checkServiceReachable(base: string, timeoutMs = 5000): Promise<boolean> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${base}/auth/me`, { method: "GET", signal: ctrl.signal });
    return res.status >= 200 && res.status < 600;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

export function listAudioCourses(category?: string, q?: string, limit = 60, locale?: string) {
  const p = new URLSearchParams({ limit: String(limit) });
  if (category) p.set("category", category);
  if (q) p.set("q", q);
  if (locale) p.set("locale", locale);
  return get<{ total: number; locale?: string; courses: AudioCourseRow[] }>(
    CURRICULUM_URL, `/audio/courses?${p.toString()}`);
}

export function getAudioCategories(locale?: string) {
  const p = new URLSearchParams();
  if (locale) p.set("locale", locale);
  const qs = p.toString();
  return get<{ categories: CategoryRow[]; locale?: string }>(
    CURRICULUM_URL, `/audio/categories${qs ? `?${qs}` : ""}`);
}

export function getAudioCourse(id: string, locale?: string) {
  const p = new URLSearchParams();
  if (locale) p.set("locale", locale);
  const qs = p.toString();
  return get<AudioCourse>(
    CURRICULUM_URL, `/audio/courses/${encodeURIComponent(id)}${qs ? `?${qs}` : ""}`);
}

export function getNotificationsFeed(opts: {
  studentId?: string; interests?: string[]; inProgress?: string[];
  completed?: string[]; streakDays?: number; limit?: number; locale?: string;
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
  return get<NotificationFeed>(CURRICULUM_URL, `/notifications/feed${qs ? `?${qs}` : ""}`);
}

export async function getHomeRails(kids = false): Promise<HomeRail[]> {
  try {
    const r = await get<{ rails: HomeRail[] }>(
      CURRICULUM_URL, `/home?kids=${kids ? "true" : "false"}`);
    return r.rails || [];
  } catch {
    return [];
  }
}

export function searchLearnable(params: Record<string, string> = {}) {
  const p = new URLSearchParams(params);
  return get<LearnSearchResult>(CURRICULUM_URL, `/learn/search?${p.toString()}`);
}

export function getLearnFacets() {
  return get<{
    categories: string[]; formats: string[]; sources: string[]; levels: string[];
  }>(CURRICULUM_URL, "/learn/facets");
}

export function listJobs(q?: string, location?: string) {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (location) p.set("location", location);
  const qs = p.toString();
  return get<{ source: string; count: number; jobs: JobPosting[] }>(
    CURRICULUM_URL, `/jobs${qs ? `?${qs}` : ""}`);
}

export function getJobMatch(jobId: string) {
  return get<JobMatch>(
    CURRICULUM_URL, `/jobs/${encodeURIComponent(jobId)}`);
}

export async function signup(email: string, password: string, displayName: string):
  Promise<{ token: string; account: Account }> {
  return get(IDENTITY_URL, "/auth/signup", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
}

export async function login(email: string, password: string):
  Promise<{ token: string; account: Account }> {
  return get(IDENTITY_URL, "/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe(): Promise<Account> {
  return get(IDENTITY_URL, "/auth/me", { headers: authHeaders() });
}

export async function listStudents(): Promise<{ students: StudentProfile[] }> {
  return get(IDENTITY_URL, "/students", { headers: authHeaders() });
}

export async function createStudent(displayName: string): Promise<StudentProfile> {
  return get(IDENTITY_URL, "/students", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ display_name: displayName, age_band: "adult", interests: [] }),
  });
}

export async function getOnboardingSurvey(subject?: string, tier?: string):
  Promise<{ enabled: boolean; template: SurveyTemplate | null }> {
  const qs = new URLSearchParams();
  if (subject) qs.set("subject", subject);
  if (tier) qs.set("tier", tier);
  const q = qs.toString();
  return get(MEMORY_URL, `/survey/onboarding${q ? `?${q}` : ""}`);
}

export async function submitLearningProfile(
  studentId: string, answers: Record<string, unknown>,
): Promise<{ student: StudentProfile; learner_category: string; recorded: boolean }> {
  return get(IDENTITY_URL, `/students/${encodeURIComponent(studentId)}/learning-profile`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ answers }),
  });
}

export async function skipLearningProfile(studentId: string):
  Promise<{ student: StudentProfile; skipped: boolean }> {
  return get(IDENTITY_URL, `/students/${encodeURIComponent(studentId)}/learning-profile/skip`, {
    method: "POST",
    headers: authHeaders(),
  });
}

export async function submitOnboardingSurveyAnalytics(payload: {
  account_id: string; student_id: string; answers: Record<string, unknown>;
}): Promise<{ id: string; recorded: boolean; learner_category: string }> {
  return get(MEMORY_URL, "/survey/onboarding", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getFlag(key: string): Promise<unknown> {
  const r = await get<{ value: unknown }>(
    MEMORY_URL, `/flags/${encodeURIComponent(key)}`);
  return r.value;
}

export async function resolveMascot(locale: string): Promise<MascotResolve> {
  const qs = new URLSearchParams({ locale });
  return get(MEMORY_URL, `/mascots/resolve?${qs.toString()}`);
}
