// API client for the Salareen mobile app (curriculum, identity, memory).

import type { MascotResolve } from "./mascot";
import { CURRICULUM_URL, DEPLOY_MODE, failoverUrlFor, IDENTITY_URL, MEMORY_URL, ORCHESTRATOR_URL, BILLING_URL, SPEECH_URL } from "./config";
import { getToken } from "./storage";

export { CURRICULUM_URL, IDENTITY_URL, MEMORY_URL, ORCHESTRATOR_URL, BILLING_URL, SPEECH_URL };

export type AudioCourseRow = {
  id: string; title: string; category: string; subject: string; level: string;
  duration_min: number; tags: string[]; segments: number; drive_safe: boolean;
};
export type AudioSegment = { heading: string; text: string };
export type AudioCourse = {
  id: string; title: string; category: string; subject: string; level: string;
  duration_min: number; tags: string[]; drive_safe: boolean;
  segments: AudioSegment[]; locale?: string;
  // Actual language of the spoken body text (may differ from the requested
  // training locale when it falls back to English). Use this for TTS voice.
  body_locale?: string; training_locale?: string;
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
  preferred_language?: string;
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
  profile_score?: string;
  profile_score_version?: string;
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
    const hint = DEPLOY_MODE === "local"
      ? "Start backends on your Mac (make run-identity :8008, curriculum :8005)."
      : "Check network/VPN; primary is www.salareen.com with Vultr IP failover.";
    return new Error(`Cannot reach backend at ${base}. ${hint} (${msg})`);
  }
  return err instanceof Error ? err : new Error(msg);
}

function isNetworkError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return /network request failed|failed to connect|ECONNREFUSED|timed out|aborted/i.test(msg);
}

function shouldFailoverOnStatus(status: number): boolean {
  return status === 408 || status === 502 || status === 503 || status === 504;
}

async function get<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  const fallback = failoverUrlFor(base);
  const bases = fallback ? [base, fallback] : [base];
  let lastErr: unknown;
  const headers: Record<string, string> = {
    ...authHeaders(),
    ...((init?.headers as Record<string, string> | undefined) || {}),
  };
  const merged: RequestInit = { ...init, headers };

  for (let i = 0; i < bases.length; i++) {
    const tryBase = bases[i];
    try {
      let res: Response;
      try {
        res = await fetch(`${tryBase}${path}`, merged);
      } catch (err) {
        lastErr = err;
        if (i < bases.length - 1 && isNetworkError(err)) {
          continue;
        }
        throw networkError(base, err);
      }
      if (i < bases.length - 1 && shouldFailoverOnStatus(res.status)) {
        lastErr = new Error(`${res.status} ${res.statusText}`);
        continue;
      }
      return jsonOrThrow<T>(res);
    } catch (err) {
      lastErr = err;
      if (i < bases.length - 1 && isNetworkError(err)) {
        continue;
      }
      throw err instanceof Error && !isNetworkError(err) ? err : networkError(base, lastErr);
    }
  }
  throw networkError(base, lastErr);
}

/** True when the service responds over HTTP (401 without a token is OK). */
export async function checkServiceReachable(base: string, timeoutMs = 5000): Promise<boolean> {
  const fallback = failoverUrlFor(base);
  const bases = fallback ? [base, fallback] : [base];

  for (const tryBase of bases) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(`${tryBase}/auth/me`, { method: "GET", signal: ctrl.signal });
      if (res.status >= 200 && res.status < 600) {
        return true;
      }
    } catch {
      // try failover base
    } finally {
      clearTimeout(timer);
    }
  }
  return false;
}

export function listAudioCourses(
  category?: string, q?: string, limit = 60, locale?: string, trainingLocale?: string,
) {
  const p = new URLSearchParams({ limit: String(limit) });
  if (category) p.set("category", category);
  if (q) p.set("q", q);
  if (locale) p.set("locale", locale);
  if (trainingLocale) p.set("training_locale", trainingLocale);
  return get<{ total: number; locale?: string; courses: AudioCourseRow[] }>(
    CURRICULUM_URL, `/audio/courses?${p.toString()}`);
}

export function getAudioCourse(id: string, locale?: string, trainingLocale?: string) {
  const p = new URLSearchParams();
  if (locale) p.set("locale", locale);
  if (trainingLocale) p.set("training_locale", trainingLocale);
  const qs = p.toString();
  return get<AudioCourse>(
    CURRICULUM_URL, `/audio/courses/${encodeURIComponent(id)}${qs ? `?${qs}` : ""}`);
}

export function getAudioCategories(locale?: string) {
  const p = new URLSearchParams();
  if (locale) p.set("locale", locale);
  const qs = p.toString();
  return get<{ categories: CategoryRow[]; locale?: string }>(
    CURRICULUM_URL, `/audio/categories${qs ? `?${qs}` : ""}`);
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

export async function getHomeRails(kids = false, locale?: string): Promise<HomeRail[]> {
  try {
    const p = new URLSearchParams({ kids: kids ? "true" : "false" });
    if (locale) p.set("locale", locale);
    const r = await get<{ rails: HomeRail[] }>(
      CURRICULUM_URL, `/home?${p.toString()}`);
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

export type LoginResult =
  | { token: string; account: Account }
  | { requires_2fa: true; mfa_token: string };

export async function login(email: string, password: string): Promise<LoginResult> {
  return get(IDENTITY_URL, "/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function verify2faLogin(mfaToken: string, code: string):
  Promise<{ token: string; account: Account }> {
  return get(IDENTITY_URL, "/auth/2fa/verify", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ mfa_token: mfaToken, code }),
  });
}

export async function forgotPassword(email: string): Promise<{ sent: boolean; reset_token?: string }> {
  return get(IDENTITY_URL, "/auth/forgot-password", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(token: string, newPassword: string): Promise<{ reset: boolean }> {
  return get(IDENTITY_URL, "/auth/reset-password", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

export async function changePassword(current: string, next: string): Promise<{ changed: boolean }> {
  return get(IDENTITY_URL, "/auth/password", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ current_password: current, new_password: next }),
  });
}

export async function setup2fa(): Promise<{ secret: string; otpauth_uri: string }> {
  return get(IDENTITY_URL, "/auth/2fa/setup", {
    method: "POST",
    headers: authHeaders(),
  });
}

export async function confirm2fa(code: string): Promise<{ enabled: boolean }> {
  return get(IDENTITY_URL, "/auth/2fa/confirm", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ code }),
  });
}

export async function disable2fa(code: string): Promise<{ enabled: boolean }> {
  return get(IDENTITY_URL, "/auth/2fa/disable", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ code }),
  });
}

export async function getSecuritySummary(): Promise<{
  totp_enabled: boolean; passkeys: number; oauth_linked: string[]; recent_logins: number;
}> {
  return get(IDENTITY_URL, "/auth/security", { headers: authHeaders() });
}

export async function getMe(): Promise<Account> {
  return get(IDENTITY_URL, "/auth/me", { headers: authHeaders() });
}

/** Persist the learner's preferred language so it follows them across devices
 * and the AI teacher answers in it. Best-effort. */
export async function setAccountLanguage(language: string): Promise<{ preferred_language: string }> {
  return get(IDENTITY_URL, "/account/language", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ language }),
  });
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

export type BugScreenshotUpload = {
  filename: string;
  content_type: string;
  data_base64: string;
};

export async function submitBugReport(payload: {
  description: string;
  category?: string;
  screen?: string;
  platform?: string;
  app_version?: string;
  user_id?: string;
  email?: string;
  snapshot?: Record<string, unknown>;
  logs?: string[];
  screenshots?: BugScreenshotUpload[];
}): Promise<{
  ok: boolean;
  id: string;
  created_at: number;
  destination?: string;
  external_url?: string;
}> {
  return get(MEMORY_URL, "/bugs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// --- Group classes + Salareen live room --- //
export type LessonRow = {
  lesson_id: string;
  title: string;
  language?: string;
  audience?: string;
};

export type GroupClassRow = {
  id: string;
  title: string;
  platform: string;
  start_time: string;
  duration_min: number;
  status: string;
  seats_left: number;
  capacity: number;
  room_size?: number;
  live_room_id?: string;
  needs_bridge: boolean;
  meeting_url?: string;
  host?: string;
  lesson_id?: string;
  registered?: number;
  marketplace_listing?: boolean;
  audit_required?: boolean;
  audit_status?: string;
  instructor_name?: string;
  instructor_account_id?: string;
  price_per_user_usd?: number;
  commission_rate?: number;
  payment_required?: boolean;
  attendee_code_required?: boolean;
  max_faces_allowed?: number;
  require_liveness?: boolean;
  recording_protection_required?: boolean;
  device_profile?: string;
  camera_ingest_mode?: string;
  camera_sources?: Array<Record<string, unknown>>;
  camera_source_count?: number;
  external_camera_ingest_supported?: boolean;
  review_count?: number;
  review_avg?: number;
  instructor_stats?: { courses_taught: number; review_count: number; review_avg: number };
};

export type GroupClassStart = {
  class: GroupClassRow;
  bridge: {
    needs_bridge: boolean;
    platform: string;
    livekit_room: string;
    live_room_id?: string;
    moderator_key?: string;
    note?: string;
    connect_endpoint?: string;
    livekit?: { room: string; token: string; url: string };
  };
  session?: { slide?: { title: string } };
};

export type ScheduleGroupClassInput = {
  title: string;
  lesson_id: string;
  start_time: string;
  platform?: string;
  meeting_url?: string;
  duration_min?: number;
  capacity?: number;
  room_size?: number;
  language?: string;
  marketplace_listing?: boolean;
  audit_required?: boolean;
  credentials_summary?: string;
  credential_photo_url?: string;
  identity_photo_url?: string;
  interview_notes?: string;
  demo_notes?: string;
  instructor_name?: string;
  price_per_user_usd?: number;
  commission_rate?: number;
  payment_required?: boolean;
  attendee_code_required?: boolean;
  max_faces_allowed?: number;
  require_liveness?: boolean;
  recording_protection_required?: boolean;
  device_profile?: string;
  camera_ingest_mode?: string;
  camera_sources?: Array<Record<string, unknown>>;
};

export type LiveRoomGeo = {
  country: string;
  state: string;
  city: string;
  latitude: number;
  longitude: number;
};

export type LiveRoomListing = {
  room_id: string;
  title: string;
  status: string;
  room_size: number;
  learner_count: number;
  seats_left: number;
  viewer_count: number;
  opened_at: string;
  host_name: string;
  creator_name: string;
  country: string;
  state: string;
  city: string;
  latitude: number;
  longitude: number;
  distance_km?: number | null;
  class_id?: string;
  moderator_key?: string;
};

export type LiveRoomBrowse = {
  rooms: LiveRoomListing[];
  total: number;
  groups?: {
    country: string;
    count: number;
    states: {
      state: string;
      count: number;
      cities: { city: string; count: number; rooms: LiveRoomListing[] }[];
    }[];
  }[];
};

export type LiveRoomState = {
  room_id: string;
  title: string;
  room_size: number;
  learner_count: number;
  seats_left: number;
  status: string;
  presenting?: boolean;
  host: { id: string; name: string; role: string };
  participants: {
    id: string;
    name: string;
    role: string;
    identity?: string;
    hand_raised: boolean;
    muted: boolean;
    muted_by_host: boolean;
    can_publish?: boolean;
    /** Moderator/admin-only learner profile fields. */
    student_id?: string;
    readiness_score?: number;
    readiness_band?: string;
    primary_style?: string;
  }[];
  chat: { id: string; from_name: string; text: string }[];
  slide: { index: number; title: string; body: string; narration: string };
  recording: { status: string };
  banned?: { identity: string; name: string; reason: string }[];
  speaking_queue?: {
    id: string; participant_id: string; name: string; question: string;
    status: string; position: number;
  }[];
  floor_participant_id?: string;
  floor_holder?: { id: string; name: string } | null;
  reports?: {
    id: string;
    reporter_name: string;
    reported_participant_id: string;
    reported_name: string;
    category: string;
    reason: string;
  }[];
  gift_feed?: { id: string; emoji: string; sender_name: string; gift_name: string; cost_points: number }[];
  viewer_count?: number;
  welcome_message?: string;
  welcome_started_at?: string;
  pre_class_welcome_seconds?: number;
  audience_profile?: {
    learner_count?: number;
    mean_readiness?: number;
    median_readiness?: number;
    band_counts?: Record<string, number>;
    dominant_styles?: string[];
    adaptation_hints?: string[];
  };
  group_game?: LiveGroupGame | null;
};

export type LiveGiftCatalogItem = { id: string; name: string; emoji: string; cost_points: number };
export type LiveGroupGameType =
  | "quiz_race" | "tic_tac_toe" | "hangman" | "multiple_choice"
  | "true_false" | "word_scramble" | "fill_blank" | "emoji_decode"
  | "lightning_round" | "team_buzzer" | "hot_seat" | "jeopardy";
export type LiveGroupGame = {
  id: string; type: LiveGroupGameType; prompt: string;
  points: number; status: string; winner_name?: string; board?: string[];
  turn?: string; masked?: string; wrong?: number; max_wrong?: number; scrambled?: string;
};

export type LiveKitMedia = { room: string; identity: string; token: string; url: string };

export async function listLessons(): Promise<LessonRow[]> {
  return get<LessonRow[]>(ORCHESTRATOR_URL, "/api/lessons");
}

export async function listGroupClasses(upcoming = true): Promise<GroupClassRow[]> {
  const r = await get<{ classes: GroupClassRow[] }>(
    ORCHESTRATOR_URL, `/api/group-classes?upcoming=${upcoming}`);
  return r.classes;
}

export async function scheduleGroupClass(input: ScheduleGroupClassInput): Promise<GroupClassRow> {
  return get(ORCHESTRATOR_URL, "/api/group-classes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function registerGroupClass(
  classId: string,
  name: string,
  email = "",
  opts?: { attendeeCode?: string; checkoutSessionId?: string; paymentStatus?: string },
): Promise<GroupClassRow> {
  return get(ORCHESTRATOR_URL, `/api/group-classes/${encodeURIComponent(classId)}/register`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      name,
      email,
      attendee_code: opts?.attendeeCode || "",
      checkout_session_id: opts?.checkoutSessionId || "",
      payment_status: opts?.paymentStatus || "unpaid",
    }),
  });
}

export async function checkoutGroupClass(
  classId: string,
  name: string,
  email = "",
): Promise<{ checkout: { session_id: string; url: string; provider: string; method: string; payment_status: string } }> {
  return get(ORCHESTRATOR_URL, `/api/group-classes/${encodeURIComponent(classId)}/checkout`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ name, email }),
  });
}

export async function confirmGroupClassPayment(
  classId: string,
  checkoutSessionId: string,
): Promise<{ class: GroupClassRow; attendee_code: string; payment_status: string }> {
  return get(ORCHESTRATOR_URL, `/api/group-classes/${encodeURIComponent(classId)}/confirm-payment`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ checkout_session_id: checkoutSessionId }),
  });
}

export async function reviewGroupClass(
  classId: string,
  rating: number,
  comment = "",
): Promise<{ class: GroupClassRow; review: { reviewer_name: string; rating: number; comment: string; created_at: string } }> {
  return get(ORCHESTRATOR_URL, `/api/group-classes/${encodeURIComponent(classId)}/review`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ rating, comment }),
  });
}

export async function submitTeachRequest(input: {
  title: string;
  lesson_id: string;
  start_time: string;
  duration_min?: number;
  language?: string;
  description?: string;
  instructor_name?: string;
  credentials_summary: string;
  credential_photo_url?: string;
  identity_photo_url?: string;
  interview_notes?: string;
  demo_notes?: string;
  price_per_user_usd?: number;
  capacity?: number;
  room_size?: number;
  commission_rate?: number;
  max_faces_allowed?: number;
  require_liveness?: boolean;
  recording_protection_required?: boolean;
  device_profile?: string;
  camera_ingest_mode?: string;
  camera_sources?: Array<Record<string, unknown>>;
}): Promise<GroupClassRow> {
  return get(ORCHESTRATOR_URL, "/api/group-classes/teach-request", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
}

export async function updateGroupClassCameraSources(
  classId: string,
  input: {
    device_profile?: string;
    camera_ingest_mode?: string;
    camera_sources: Array<Record<string, unknown>>;
  },
): Promise<GroupClassRow> {
  return get(ORCHESTRATOR_URL, `/api/group-classes/${encodeURIComponent(classId)}/camera-sources`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
}

export async function startGroupClass(
  classId: string,
  location?: LiveRoomGeo,
): Promise<GroupClassStart> {
  return get(ORCHESTRATOR_URL, `/api/group-classes/${encodeURIComponent(classId)}/start`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(location ?? {}),
  });
}

export async function listLiveRooms(opts?: {
  lat?: number;
  lng?: number;
  radius_km?: number;
  country?: string;
  city?: string;
  grouped?: boolean;
}): Promise<LiveRoomBrowse> {
  const q = new URLSearchParams();
  if (opts?.lat) q.set("lat", String(opts.lat));
  if (opts?.lng) q.set("lng", String(opts.lng));
  if (opts?.radius_km) q.set("radius_km", String(opts.radius_km));
  if (opts?.country) q.set("country", opts.country);
  if (opts?.city) q.set("city", opts.city);
  if (opts?.grouped === false) q.set("grouped", "false");
  const qs = q.toString();
  return get(ORCHESTRATOR_URL, `/api/live-rooms${qs ? `?${qs}` : ""}`);
}

export async function createLiveRoom(
  title: string,
  creatorName: string,
  location?: LiveRoomGeo,
  roomSize = 6,
): Promise<{ room: LiveRoomState; listing: LiveRoomListing }> {
  return get(ORCHESTRATOR_URL, "/api/live-rooms", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      title,
      creator_name: creatorName,
      room_size: roomSize,
      location: location ?? {},
    }),
  });
}

// --- Arcade / learning games (identity service) --- //
export type GameTypeInfo = { id: string; name: string; desc: string };
export type AgeGroupInfo = { id: string; name: string; range: string };
export type SubjectInfo = { id: string; name: string };
export type GamesCatalog = {
  subjects: string[];
  subjects_localized?: SubjectInfo[];
  game_types: GameTypeInfo[];
  age_groups: AgeGroupInfo[];
};
export type GameItem = {
  id: string; prompt: string; options: string[];
  kind?: string; meta?: Record<string, unknown>;
};
export type GameTerm = { id: string; term: string };
export type GameOption = { id: string; text: string };
export type GameRound = {
  game_id: string; subject: string; game_type: string; time_limit_s: number;
  age_group?: string;
  items?: GameItem[]; terms?: GameTerm[]; options?: GameOption[];
  versus?: string; ai_skill?: number; ai_name?: string;
};
export type GameItemResult = {
  id: string; correct: boolean; answer_index?: number; explain: string;
};
export type GameScore = {
  game_id: string; subject: string; game_type: string; correct: number; total: number;
  accuracy: number; base_points: number; speed_bonus: number; accuracy_bonus: number;
  points: number; results: GameItemResult[];
  ai_correct?: number; ai_total?: number; versus_outcome?: string; versus_bonus?: number;
};
export type GameSubmit = {
  result: GameScore; points_earned: number; balance: number;
  rank: number | null; subject_rank: number | null;
};

export function getGamesCatalog(locale = "en"): Promise<GamesCatalog> {
  const q = locale ? `?locale=${encodeURIComponent(locale)}` : "";
  return get<GamesCatalog>(IDENTITY_URL, `/games${q}`);
}

export function newGame(
  subject: string, gameType: string, ageGroup = "teen", n = 5,
): Promise<GameRound> {
  return get<GameRound>(IDENTITY_URL, "/games/new", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ subject, game_type: gameType, age_group: ageGroup, n }),
  });
}

export function submitGame(
  gameId: string, answers: Record<string, number | string>, elapsedS?: number,
): Promise<GameSubmit> {
  return get<GameSubmit>(IDENTITY_URL, "/games/submit", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ game_id: gameId, answers, elapsed_s: elapsedS ?? null }),
  });
}

// --- Lesson teaching sessions (orchestrator) --- //
export type LessonSlide = {
  index: number; title: string; body: string; narration: string;
};
export type LessonDetail = {
  lesson_id: string; title: string; language?: string; summary?: string;
  slides: LessonSlide[];
};
export type LessonSessionState = {
  session_id: string; class_type: string; lesson_id: string; current_slide: number;
};
export type LessonSessionView = {
  session: LessonSessionState;
  lesson: LessonDetail;
  slide: LessonSlide;
};
export type LessonAnswer = {
  text: string; citations: string[]; language: string;
  grounded: boolean; hallucination_risk: number;
};

export function startLessonSession(
  lessonId: string,
  studentId?: string,
  classType: "solo" | "group" = "group",
): Promise<LessonSessionView> {
  return get<LessonSessionView>(ORCHESTRATOR_URL, "/api/sessions", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      lesson_id: lessonId,
      class_type: classType,
      student_id: studentId ?? null,
    }),
  });
}

export function advanceLessonSession(sessionId: string): Promise<LessonSlide> {
  return get<LessonSlide>(
    ORCHESTRATOR_URL, `/api/sessions/${encodeURIComponent(sessionId)}/advance`, {
      method: "POST",
    });
}

export function askLessonSession(
  sessionId: string, text: string, language = "en",
): Promise<LessonAnswer> {
  return get<LessonAnswer>(
    ORCHESTRATOR_URL, `/api/sessions/${encodeURIComponent(sessionId)}/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, language }),
    });
}

export async function getLiveRoom(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  const q = moderatorKey
    ? `?moderator_key=${encodeURIComponent(moderatorKey)}`
    : "";
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}${q}`);
}

/** Open a private 1:1 (AI + you) Salareen live room for a lesson and return its
 * id. Reuses the group-class live-room UI (video tiles, chat, Q&A), sized for two
 * seats — so mobile Solo 1:1 has the same features as group lessons. */
export async function startSoloLiveRoom(lessonId: string, creatorName = ""): Promise<{ room_id: string }> {
  return get(ORCHESTRATOR_URL, "/api/live-rooms/solo", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ lesson_id: lessonId, creator_name: creatorName }),
  });
}

export async function getLearningExperience(studentId: string): Promise<{
  lx_score_ema: number | null;
  lx_target: number;
  lx_trend: string;
  recent_samples: number[];
  wellness_state: string;
  readiness_score?: number;
  readiness_band?: string;
  readiness_dimensions?: Record<string, number>;
  primary_style?: string;
  course_history_summary?: Record<string, unknown>;
}> {
  return get(IDENTITY_URL, `/students/${encodeURIComponent(studentId)}/learning-experience`, {
    headers: authHeaders(),
  });
}

export async function joinLiveRoom(
  roomId: string,
  name: string,
  identity = "",
  language = "",
  opts?: {
    studentId?: string;
    readinessScore?: number;
    readinessBand?: string;
    primaryStyle?: string;
    attendeeCode?: string;
  },
):
  Promise<{
    participant: { id: string; name: string; identity: string };
    room: LiveRoomState;
    media?: LiveKitMedia;
    gift_balance?: number;
    host_follower_count?: number;
    following_host?: boolean;
    is_admin?: boolean;
    moderator_key?: string;
  }> {
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/join`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      name,
      identity,
      language,
      student_id: opts?.studentId || "",
      readiness_score: opts?.readinessScore || 0,
      readiness_band: opts?.readinessBand || "",
      primary_style: opts?.primaryStyle || "",
      attendee_code: opts?.attendeeCode || "",
    }),
  });
}

/** Start the AI presentation (class admin / moderator key / platform admin via
 * Bearer token). Idempotent server-side. Without this a group class never
 * enters "presenting", so slides never auto-advance and it's stuck on slide 1. */
export async function liveRoomStartPresentation(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/start-presentation`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ moderator_key: moderatorKey }),
    });
  return r.room;
}

export async function liveRoomMediaToken(
  roomId: string,
  participantId: string,
): Promise<{ media: LiveKitMedia; can_publish: boolean }> {
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/media-token`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ participant_id: participantId }),
  });
}

export async function leaveLiveRoom(roomId: string, participantId: string): Promise<LiveRoomState> {
  return get<LiveRoomState>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/leave`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId }),
    });
}

export async function liveRoomChat(roomId: string, participantId: string, text: string): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, text }),
    });
  return r.room;
}

export async function liveRoomRaiseHand(roomId: string, participantId: string, question = ""): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/raise-hand`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, question }),
    });
  return r.room;
}

export async function liveRoomCallNext(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/queue/call-next`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ moderator_key: moderatorKey }),
    });
  return r.room;
}

/** Advance to the next slide (moderator key or platform-admin token). */
export async function liveRoomAdvance(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/advance`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ moderator_key: moderatorKey }),
    });
  return r.room;
}

/** End the class for everyone (moderator key or platform-admin token). */
export async function liveRoomEnd(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  return get<LiveRoomState>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/end`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ moderator_key: moderatorKey }),
    });
}

/** Delete a live session entirely (platform admin only). */
export async function deleteLiveRoom(roomId: string): Promise<{ deleted: boolean; room_id: string }> {
  return get(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}`, {
      method: "DELETE",
      headers: { "content-type": "application/json", ...authHeaders() },
    });
}

export async function liveRoomFinishTurn(
  roomId: string, participantId: string, moderatorKey = "",
): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/queue/finish-turn`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ participant_id: participantId, moderator_key: moderatorKey }),
    });
  return r.room;
}

export async function liveRoomLeaveQueue(roomId: string, participantId: string): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/queue/leave`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId }),
    });
  return r.room;
}

export async function liveRoomAsk(roomId: string, participantId: string, question: string, language = ""):
  Promise<{ room: LiveRoomState; queued: boolean; queue_position?: number }> {
  return get(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, question, language }),
    });
}

/** Streaming ask: hits /ask-stream so the AI host (Theodore) answer streams to
 * the whole room over the WebSocket (host_delta frames the screen renders +
 * speaks live). React Native's fetch can't read the SSE body incrementally, so
 * we await the full response and parse the final queued/done event for the
 * result. Falls back to the blocking /ask on any error. */
export async function liveRoomAskStream(
  roomId: string, participantId: string, question: string, language = "",
): Promise<{ room?: LiveRoomState; queued: boolean; queue_position?: number; text?: string }> {
  try {
    const resp = await fetch(
      `${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/ask-stream`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ participant_id: participantId, question, language }),
      },
    );
    if (!resp.ok) throw new Error(`ask-stream ${resp.status}`);
    const body = await resp.text();
    let out: { room?: LiveRoomState; queued: boolean; queue_position?: number; text?: string } = { queued: false };
    for (const frame of body.split("\n\n")) {
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      let ev: { type?: string; text?: string; queue_position?: number; room?: LiveRoomState };
      try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
      if (ev.type === "queued") {
        out = { queued: true, queue_position: ev.queue_position ?? 0, room: ev.room };
      } else if (ev.type === "done") {
        out = { queued: false, room: ev.room, text: ev.text ?? "" };
      }
    }
    return out;
  } catch {
    const r = await liveRoomAsk(roomId, participantId, question, language);
    return { room: r.room, queued: r.queued, queue_position: r.queue_position };
  }
}

/** Heartbeat the room clock so a mobile-only group class still auto-starts (when
 * full / past the scheduled time), auto-advances slides, and auto-ends when its
 * allotted time is up. Idempotent server-side; any joined client may call it. */
export async function liveRoomTick(
  roomId: string,
  participantId = "",
  moderatorKey = "",
):
  Promise<{ room: LiveRoomState; auto_started?: boolean; auto_ended?: boolean }> {
  const params: string[] = [];
  if (participantId) params.push(`pid=${encodeURIComponent(participantId)}`);
  if (moderatorKey) params.push(`moderator_key=${encodeURIComponent(moderatorKey)}`);
  const q = params.length ? `?${params.join("&")}` : "";
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/tick${q}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
  });
}

export async function liveRoomBan(
  roomId: string,
  participantId: string,
  moderatorKey: string,
  reason = "",
): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/ban`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ participant_id: participantId, moderator_key: moderatorKey, reason }),
    });
  return r.room;
}

export async function liveRoomUnban(
  roomId: string,
  identity: string,
  moderatorKey: string,
): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/unban`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ identity, moderator_key: moderatorKey }),
    });
  return r.room;
}

export async function liveRoomReport(
  roomId: string,
  reporterParticipantId: string,
  reportedParticipantId: string,
  reason: string,
  category = "other",
): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/report`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        reporter_participant_id: reporterParticipantId,
        reported_participant_id: reportedParticipantId,
        reason,
        category,
      }),
    });
  return r.room;
}

export async function liveRoomDismissReport(
  roomId: string,
  reportId: string,
  moderatorKey: string,
): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL,
    `/api/live-rooms/${encodeURIComponent(roomId)}/reports/dismiss`,
    {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ report_id: reportId, moderator_key: moderatorKey }),
    },
  );
  return r.room;
}

export async function getLiveGiftCatalog(): Promise<{ gifts: LiveGiftCatalogItem[] }> {
  return get(ORCHESTRATOR_URL, "/api/live-rooms/gifts/catalog");
}

export async function liveRoomSendGift(
  roomId: string,
  participantId: string,
  giftId: string,
  recipientParticipantId = "",
): Promise<{ room: LiveRoomState; sender_balance: number }> {
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/gifts/send`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      participant_id: participantId,
      gift_id: giftId,
      recipient_participant_id: recipientParticipantId,
    }),
  });
}

export async function liveRoomStartGame(
  roomId: string, moderatorKey: string, gameType: LiveGroupGame["type"],
  prompt: string, answer: string, points = 25,
): Promise<{ room: LiveRoomState; game: LiveGroupGame }> {
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/games/start`, {
    method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      moderator_key: moderatorKey, game_type: gameType, prompt, answer, points,
    }),
  });
}

export async function liveRoomPlayGame(
  roomId: string, participantId: string,
  action: { answer?: string; cell?: number; letter?: string },
): Promise<{ room: LiveRoomState; game: LiveGroupGame; event: { correct: boolean; points: number } }> {
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/games/action`, {
    method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ participant_id: participantId, ...action }),
  });
}

export async function liveRoomReaction(
  roomId: string,
  participantId: string,
  emoji: string,
): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/reactions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, emoji }),
    });
  return r.room;
}

export async function liveRoomFollowHost(
  roomId: string,
  identity: string,
  unfollow = false,
): Promise<{ following: boolean; follower_count: number }> {
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/follow`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ identity, unfollow }),
  });
}

// --- Rewards, enrollment, classroom, languages, billing (web parity) --- //

export type LedgerEntry = { delta: number; reason: string; ref: string; ts: number };
export type Redemption = {
  prize_id: string; kind: string; cost_points: number;
  voucher_code: string | null; percent: number | null;
  raffle_entry_id: string | null; detail: Record<string, unknown>;
};
export type RewardsSummary = { balance: number; ledger: LedgerEntry[]; redemptions: Redemption[] };
export type RewardPrize = {
  id: string; name: string; kind: string; kind_label?: string;
  cost_points: number; detail: Record<string, unknown>;
};
export type Leader = {
  rank: number; name: string; score: number; game_points: number; games_played: number;
};
export type Enrollment = {
  course_id: string; title: string; status: string; enrolled_at?: number;
};
export type Portfolio = {
  account: Account; students: StudentProfile[];
  enrollments: Enrollment[]; points_balance: number;
  by_status?: Record<string, Enrollment[]>;
  counts?: Record<string, number>;
  tier?: string;
};
export type ConsumerPlan = {
  tier: string; display_name: string; price_usd: number;
  billing_interval: string; ads: boolean; blurb: string;
};
export type Subscription = {
  tier: string; status: string; current_period_end?: string | null;
};
export type QuizItemView = {
  item_id: string; prompt: string; options: string[];
  answer_index: number; difficulty?: string; topic?: string;
};
export type QuizGrade = {
  correct: boolean; explanation?: string; mastery_target?: number; difficulty?: string;
};
export type Reengagement = { text: string; citations: string[]; prompt?: string };
export type LxTickResult = {
  strategy?: string; pacing?: string; difficulty?: string; wellness_nudge?: string;
};
export type LangInfo = {
  code: string; name: string; native: string; flag: string; tier: string; phrase_count: number;
};
export type LangSkill = { id: string; name: string; desc: string };
export type LangCourse = {
  code: string; name: string; native: string; flag: string; tier: string;
  skills: LangSkill[]; phrase_count: number; grammar_tip: string; culture_note: string;
};
export type LangExercise = {
  skill: string; language: string;
  items?: { id: string; prompt: string; options: string[]; answer_index: number }[];
  pairs?: { term: string; match: string }[];
  target?: string; roman?: string; en?: string; mouth_tip?: string; tip?: string; note?: string;
};
export type Pronounce = {
  score: number; stars: number; passed: boolean; target: string; heard: string;
  missed_words: string[]; feedback: string; mouth_tip?: string;
};

export async function getRewards(): Promise<RewardsSummary> {
  return get(IDENTITY_URL, "/rewards", { headers: authHeaders() });
}

export async function getRewardsCatalog(): Promise<{ prizes: RewardPrize[] }> {
  return get(IDENTITY_URL, "/rewards/catalog");
}

export async function redeemReward(prizeId: string):
  Promise<{ redemption: Redemption; balance: number }> {
  return get(IDENTITY_URL, "/rewards/redeem", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ prize_id: prizeId }),
  });
}

export async function grantReward(grant: string):
  Promise<{ earned: number; balance: number; reason: string }> {
  return get(IDENTITY_URL, "/rewards/grant", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ grant }),
  });
}

export async function getLeaderboard(subject?: string, ageGroup?: string):
  Promise<{ leaders: Leader[] }> {
  const p = new URLSearchParams();
  if (subject) p.set("subject", subject);
  if (ageGroup) p.set("age_group", ageGroup);
  const qs = p.toString();
  return get(IDENTITY_URL, `/games/leaderboard${qs ? `?${qs}` : ""}`);
}

export async function enrollCourse(courseId: string, title: string, status = "enrolled"):
  Promise<Enrollment> {
  return get(IDENTITY_URL, "/enrollments", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ course_id: courseId, title, status }),
  });
}

export async function setEnrollmentStatus(
  courseId: string,
  status: "enrolled" | "in_progress" | "passed" | "failed",
  opts: { score?: number; level?: string; hands_on?: boolean } = {},
): Promise<Enrollment & { points_balance: number }> {
  return get(IDENTITY_URL, `/enrollments/${encodeURIComponent(courseId)}/status`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ status, ...opts }),
  });
}

export async function getPortfolio(): Promise<Portfolio> {
  return get(IDENTITY_URL, "/portfolio", { headers: authHeaders() });
}

export async function getConsumerPlans(): Promise<Record<string, ConsumerPlan>> {
  return get(BILLING_URL, "/plans/consumer");
}

export async function getSubscription(): Promise<Subscription> {
  return get(IDENTITY_URL, "/membership/subscription", { headers: authHeaders() });
}

export async function subscribeToPlan(tier: string): Promise<{
  tier: string; membership_class: string; subscription: Subscription;
}> {
  return get(IDENTITY_URL, "/membership/subscribe", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ tier }),
  });
}

export async function setStudentMastery(
  studentId: string, skill: string, value: number,
): Promise<StudentProfile> {
  return get(IDENTITY_URL, `/students/${encodeURIComponent(studentId)}/mastery`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ skill, value }),
  });
}

export function reengageLessonSession(sessionId: string): Promise<Reengagement> {
  return get(ORCHESTRATOR_URL, `/api/sessions/${encodeURIComponent(sessionId)}/reengage`, {
    method: "POST",
  });
}

export function getQuiz(args: {
  topic: string; passages: string[]; studentId?: string;
  classType?: string; maxItems?: number;
}): Promise<{ items: QuizItemView[] }> {
  return get(ORCHESTRATOR_URL, "/assessment/quiz", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      topic: args.topic,
      passages: args.passages,
      max_items: args.maxItems ?? 3,
      student_id: args.studentId ?? null,
      class_type: args.classType ?? "group",
    }),
  });
}

export function gradeQuiz(args: {
  item: QuizItemView; chosenIndex: number; studentId?: string; topic?: string;
}): Promise<QuizGrade> {
  return get(ORCHESTRATOR_URL, "/assessment/grade", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      item_id: args.item.item_id,
      options: args.item.options,
      answer_index: args.item.answer_index,
      chosen_index: args.chosenIndex,
      difficulty: args.item.difficulty,
      topic: args.topic ?? args.item.topic ?? "",
      student_id: args.studentId ?? null,
    }),
  });
}

export type AssessmentCheckpointSpec = {
  checkpoint_id: string;
  stage: "formative" | "summative" | "retention";
  after_slide_index: number;
  kind?: string;
  title?: string;
};

export type AssessmentPolicy = {
  session_id: string;
  course_id: string;
  checkpoints: AssessmentCheckpointSpec[];
  retention_intervals_days: number[];
  pass_rule: string;
};

export type AssessmentPresentedItem = {
  item_id: string;
  topic: string;
  prompt: string;
  options: string[];
  difficulty: string;
  format: string;
  audio?: { narration: string; transcript: boolean };
  video_aid?: { presenter_cue: string; captions: boolean; visual_prompt: string };
  game?: {
    kind: string;
    content_id: string;
    timed: boolean;
    points_per_correct: number;
  };
};

export type AssessmentRun = {
  run_id: string;
  student_id: string;
  course_id: string;
  checkpoint: {
    checkpoint_id: string;
    stage: string;
    pass_threshold: number;
    min_items: number;
    max_attempts: number;
  };
  attempt_number: number;
  presentation_format: string;
  items: AssessmentPresentedItem[];
  answer_key_exposed: boolean;
};

export type AssessmentSubmitResult = {
  attempt: {
    attempt_id: string;
    student_id: string;
    course_id: string;
    checkpoint_id: string;
    stage: string;
    presentation_format: string;
    score: number;
    passed: boolean;
    attempt_number: number;
  };
  course_decision: {
    student_id: string;
    course_id: string;
    passed: boolean;
    score: number;
    reason: string;
  } | null;
  attempt_result_token: string;
  pass_decision_token?: string;
  retention_result_token?: string;
};

export function getAssessmentPolicy(sessionId: string): Promise<AssessmentPolicy> {
  return get(ORCHESTRATOR_URL, `/assessment/policy/${encodeURIComponent(sessionId)}`);
}

export function startAssessmentCheckpoint(args: {
  studentId: string;
  sessionId?: string;
  courseId?: string;
  checkpointId: string;
  stage?: "formative" | "summative" | "retention";
  profileScore?: string;
  deviceMode?: string;
  needsCaptions?: boolean;
  usesAssistiveTech?: boolean;
  maxItems?: number;
  retentionCheckId?: string;
}): Promise<AssessmentRun> {
  return get(ORCHESTRATOR_URL, "/assessment/checkpoints/start", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      student_id: args.studentId,
      session_id: args.sessionId ?? "",
      course_id: args.courseId ?? "",
      checkpoint_id: args.checkpointId,
      stage: args.stage ?? "formative",
      profile_score: args.profileScore ?? "",
      requested_format: "auto",
      device_mode: args.deviceMode ?? "class",
      needs_captions: Boolean(args.needsCaptions),
      uses_assistive_tech: Boolean(args.usesAssistiveTech),
      max_items: args.maxItems ?? 5,
      retention_check_id: args.retentionCheckId ?? "",
    }),
  });
}

export function submitAssessmentCheckpoint(
  runId: string,
  chosenIndices: number[],
): Promise<AssessmentSubmitResult> {
  return get(
    ORCHESTRATOR_URL,
    `/assessment/checkpoints/${encodeURIComponent(runId)}/submit`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ chosen_indices: chosenIndices }),
    },
  );
}

export async function recordAssessmentAttempt(
  studentId: string,
  attemptToken: string,
): Promise<{ student_id: string; attempt_id: string; recorded: boolean; attempt_count: number }> {
  return get(IDENTITY_URL, `/students/${encodeURIComponent(studentId)}/assessment-attempt`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ attempt_token: attemptToken }),
  });
}

export async function recordAssessmentPass(
  studentId: string,
  decisionToken: string,
): Promise<{
  student_id: string;
  course_id: string;
  passed: boolean;
  score: number;
  points_balance: number;
  retention_checks: { check_id: string; interval_days: number; due_at: number; status: string }[];
}> {
  return get(IDENTITY_URL, `/students/${encodeURIComponent(studentId)}/assessment-pass`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ decision_token: decisionToken }),
  });
}

export function directorLxTick(body: Record<string, unknown>): Promise<LxTickResult> {
  return get(ORCHESTRATOR_URL, "/director/lx-tick", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getPulseSurvey(
  subject?: string, tier?: string,
): Promise<{ enabled: boolean; template: SurveyTemplate | null }> {
  const qs = new URLSearchParams();
  if (subject) qs.set("subject", subject);
  if (tier) qs.set("tier", tier);
  const q = qs.toString();
  return get(MEMORY_URL, `/survey/pulse${q ? `?${q}` : ""}`);
}

export async function submitPulseSurvey(payload: {
  course_id: string; going_well: number; pace: string;
  class_type?: string; student_id?: string | null; slide_index?: number;
}): Promise<{ id: string; recorded: boolean }> {
  return get(MEMORY_URL, "/survey/pulse", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getPostClassSurvey(
  subject?: string, tier?: string,
): Promise<{ enabled: boolean; template: SurveyTemplate | null }> {
  const qs = new URLSearchParams();
  if (subject) qs.set("subject", subject);
  if (tier) qs.set("tier", tier);
  const q = qs.toString();
  return get(MEMORY_URL, `/survey/post-class${q ? `?${q}` : ""}`);
}

export async function submitPostClassSurvey(payload: {
  course_id: string; overall: number; class_type?: string; subject?: string;
  student_id?: string | null; clarity?: number | null; pace?: string | null;
  would_recommend?: boolean | null; suggestion?: string;
}): Promise<{ id: string; recorded: boolean }> {
  return get(MEMORY_URL, "/survey/post-class", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getLearnLanguages(): Promise<{ languages: LangInfo[]; count: number }> {
  return get(SPEECH_URL, "/learn/languages");
}

export type CatalogVoice = {
  id: string; label: string; language: string; locale: string;
  accent: string; gender: string; dialect: string;
};
export type VoiceGroup = { language: string; voices: CatalogVoice[] };
export async function getTtsVoices(): Promise<{ groups: VoiceGroup[] }> {
  return get(SPEECH_URL, "/tts/voices");
}

export type Instructor = {
  id: string; label: string; emoji: string; description: string;
  voice_style: string; tone_hint: string;
};
export async function getTtsInstructors(): Promise<{ instructors: Instructor[] }> {
  return get(SPEECH_URL, "/tts/instructors");
}

export async function getLangCourse(code: string): Promise<LangCourse> {
  return get(SPEECH_URL, `/learn/${encodeURIComponent(code)}/course`);
}

export async function newLangExercise(language: string, skill: string, n = 5):
  Promise<LangExercise> {
  return get(SPEECH_URL, "/learn/exercise", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ language, skill, n }),
  });
}

export async function pronounce(target: string, heard: string, mouthOpenness?: number):
  Promise<Pronounce> {
  return get(SPEECH_URL, "/learn/pronounce", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ target, heard, mouth_openness: mouthOpenness ?? null }),
  });
}

export async function languagePractice(
  language: string, skill: string, correct: number, total: number,
): Promise<{ xp: number; balance: number }> {
  return get(IDENTITY_URL, "/language/practice", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ language, skill, correct, total }),
  });
}

export function groupClassCalendarUrl(classId: string, name = "", email = ""): string {
  const p = new URLSearchParams();
  if (name) p.set("name", name);
  if (email) p.set("email", email);
  const qs = p.toString();
  return `${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/calendar.ics${qs ? `?${qs}` : ""}`;
}
