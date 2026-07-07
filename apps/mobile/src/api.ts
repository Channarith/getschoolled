// API client for the Salareen mobile app (curriculum, identity, memory).

import type { MascotResolve } from "./mascot";
import { CURRICULUM_URL, DEPLOY_MODE, failoverUrlFor, IDENTITY_URL, MEMORY_URL, ORCHESTRATOR_URL } from "./config";
import { getToken } from "./storage";

export { CURRICULUM_URL, IDENTITY_URL, MEMORY_URL, ORCHESTRATOR_URL };

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

export type TeachingAnswer = {
  text: string;
  citations?: string[];
  grounded?: boolean;
};

export type TeachingSessionView = {
  session: { session_id: string; lesson_id: string };
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

  for (let i = 0; i < bases.length; i++) {
    const tryBase = bases[i];
    try {
      let res: Response;
      try {
        res = await fetch(`${tryBase}${path}`, init);
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

/** Start a solo teaching session for course-grounded Drive Mode Q&A. */
export async function startTeachingSession(
  lessonId: string,
  studentId?: string,
): Promise<TeachingSessionView> {
  return get(ORCHESTRATOR_URL, "/api/sessions", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      lesson_id: lessonId,
      class_type: "solo",
      student_id: studentId ?? null,
    }),
  });
}

/** Ask a question against an active teaching session (RAG + LLM when configured). */
export async function askTeachingSession(
  sessionId: string,
  text: string,
  language = "en",
): Promise<TeachingAnswer> {
  return get(ORCHESTRATOR_URL, `/api/sessions/${encodeURIComponent(sessionId)}/ask`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ text, language }),
  });
}

const teachingSessionCache: Record<string, string> = {};

/**
 * Course-aware Q&A for Drive Mode. Tries orchestrator RAG/LLM first; returns
 * empty string when the lesson is unknown so the caller can use local fallback.
 */
export async function askCourseQuestion(
  courseId: string,
  question: string,
  seg: number,
  language = "en",
): Promise<string> {
  let sessionId = teachingSessionCache[courseId];
  if (!sessionId) {
    try {
      const view = await startTeachingSession(courseId);
      sessionId = view.session.session_id;
      teachingSessionCache[courseId] = sessionId;
    } catch {
      return "";
    }
  }
  const segHint = `[Student is on segment ${seg + 1} of the audio course.] `;
  try {
    const answer = await askTeachingSession(sessionId, segHint + question, language);
    return answer.text?.trim() || "";
  } catch {
    delete teachingSessionCache[courseId];
    return "";
  }
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

// --- Group classes + Salareen live room --- //
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
};

export type LiveRoomState = {
  room_id: string;
  title: string;
  room_size: number;
  learner_count: number;
  seats_left: number;
  status: string;
  host: { id: string; name: string; role: string };
  participants: { id: string; name: string; role: string; hand_raised: boolean; muted: boolean; muted_by_host: boolean }[];
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
};

export async function listGroupClasses(upcoming = true): Promise<GroupClassRow[]> {
  const r = await get<{ classes: GroupClassRow[] }>(
    ORCHESTRATOR_URL, `/api/group-classes?upcoming=${upcoming}`);
  return r.classes;
}

export async function startGroupClass(classId: string): Promise<{ class: GroupClassRow; bridge: { livekit_room: string; live_room_id?: string; moderator_key?: string } }> {
  return get(ORCHESTRATOR_URL, `/api/group-classes/${encodeURIComponent(classId)}/start`, {
    method: "POST",
    headers: { "content-type": "application/json" },
  });
}

export async function getLiveRoom(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  const q = moderatorKey
    ? `?moderator_key=${encodeURIComponent(moderatorKey)}`
    : "";
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}${q}`);
}

export async function joinLiveRoom(roomId: string, name: string, identity = ""):
  Promise<{ participant: { id: string; name: string; identity: string }; room: LiveRoomState }> {
  return get(ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/join`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, identity }),
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
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ moderator_key: moderatorKey }),
    });
  return r.room;
}

export async function liveRoomFinishTurn(
  roomId: string, participantId: string, moderatorKey = "",
): Promise<LiveRoomState> {
  const r = await get<{ room: LiveRoomState }>(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/queue/finish-turn`, {
      method: "POST",
      headers: { "content-type": "application/json" },
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

export async function liveRoomAsk(roomId: string, participantId: string, question: string):
  Promise<{ room: LiveRoomState; queued: boolean; queue_position?: number }> {
  return get(
    ORCHESTRATOR_URL, `/api/live-rooms/${encodeURIComponent(roomId)}/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, question }),
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
      headers: { "content-type": "application/json" },
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
      headers: { "content-type": "application/json" },
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
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ report_id: reportId, moderator_key: moderatorKey }),
    },
  );
  return r.room;
}
