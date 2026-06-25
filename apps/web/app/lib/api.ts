// Client for the orchestrator (Teaching Director) API.
// Base URL is configurable so the SAME UI runs against local or cloud backends.

import type { MascotResolve } from "./mascot";

// Are we running on a deployed host (not local dev)? On localhost the UI talks
// to each service on its own port; when deployed it shares ONE origin with the
// backends and reaches them through same-origin path prefixes that the edge
// gateway / ingress rewrites to each service (see infra/compose/edge.conf and
// infra/k8s ingress).
function isDeployedHost(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host !== "localhost" && host !== "127.0.0.1" && host !== "::1";
}

// Resolve a service base URL. Precedence:
//   1. An explicit NEXT_PUBLIC_*_URL build-time override (absolute URL).
//   2. Deployed: a SAME-ORIGIN relative path prefix (e.g. "/identity"), so the
//      browser hits the gateway on whatever host/IP/domain served the page -
//      no DNS or build-time host baking required. The gateway strips the prefix
//      and forwards to the matching service.
//   3. Local dev: the service's localhost port.
function serviceUrl(
  env: string | undefined,
  deployedPrefix: string,
  localDefault: string,
): string {
  if (env) return env;
  if (isDeployedHost()) return deployedPrefix;
  return localDefault;
}

export const ORCHESTRATOR_URL = serviceUrl(
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL, "/orchestrator", "http://localhost:8000");

export const CURRICULUM_URL = serviceUrl(
  process.env.NEXT_PUBLIC_CURRICULUM_URL, "/curriculum", "http://localhost:8005");

export const MEMORY_URL = serviceUrl(
  process.env.NEXT_PUBLIC_MEMORY_URL, "/memory", "http://localhost:8004");

export const IDENTITY_URL = serviceUrl(
  process.env.NEXT_PUBLIC_IDENTITY_URL, "/identity", "http://localhost:8008");

export const BILLING_URL = serviceUrl(
  process.env.NEXT_PUBLIC_BILLING_URL, "/billing", "http://localhost:8006");

export const INTEGRATIONS_URL = serviceUrl(
  process.env.NEXT_PUBLIC_INTEGRATIONS_URL, "/integrations", "http://localhost:8007");

export const SPEECH_URL = serviceUrl(
  process.env.NEXT_PUBLIC_SPEECH_URL, "/speech", "http://localhost:8002");

export const PERCEPTION_URL = serviceUrl(
  process.env.NEXT_PUBLIC_PERCEPTION_URL, "/perception", "http://localhost:8003");

// All backend services keyed by name -> base URL (each exposes /version + /health).
export const SERVICE_URLS: Record<string, string> = {
  orchestrator: ORCHESTRATOR_URL,
  speech: SPEECH_URL,
  perception: PERCEPTION_URL,
  memory: MEMORY_URL,
  curriculum: CURRICULUM_URL,
  billing: BILLING_URL,
  integrations: INTEGRATIONS_URL,
  identity: IDENTITY_URL,
};

// --- account / session (token in localStorage) --------------------------- //
const TOKEN_KEY = "aoep_token";
const PREVIEW_KEY = "aoep_preview";

// Fired whenever auth/preview state changes so the nav (and other components)
// can re-gate immediately without a full reload.
export const AUTH_EVENT = "aoep-auth-change";

export function notifyAuthChange(): void {
  try {
    window.dispatchEvent(new Event(AUTH_EVENT));
  } catch {
    /* no window (SSR) */
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* ignore */
  }
  notifyAuthChange();
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
  notifyAuthChange();
}

// Legacy preview flag (no longer unlocks the catalog). Kept so older sessions
// can clear the bit on sign-out; nav and catalog pages require a real token.
export function getPreview(): boolean {
  try {
    return localStorage.getItem(PREVIEW_KEY) === "1";
  } catch {
    return false;
  }
}

export function setPreview(on: boolean): void {
  try {
    if (on) localStorage.setItem(PREVIEW_KEY, "1");
    else localStorage.removeItem(PREVIEW_KEY);
  } catch {
    /* ignore */
  }
  notifyAuthChange();
}

// Admin unlock: hides operator-only tools (e.g. the Homework grader) from
// learners/preview/paying customers behind a password. The real enforcement is
// server-side (those endpoints are internal-only); this gates the UI surface.
const ADMIN_KEY = "aoep_admin";

export function isAdminUnlocked(): boolean {
  try {
    return localStorage.getItem(ADMIN_KEY) === "1";
  } catch {
    return false;
  }
}

export function unlockAdmin(password: string): boolean {
  const expected = process.env.NEXT_PUBLIC_ADMIN_UNLOCK || "88888888";
  if (password === expected) {
    try { localStorage.setItem(ADMIN_KEY, "1"); } catch { /* ignore */ }
    notifyAuthChange();
    return true;
  }
  return false;
}

export function lockAdmin(): void {
  try { localStorage.removeItem(ADMIN_KEY); } catch { /* ignore */ }
  notifyAuthChange();
}

// Set the admin flag from a server-confirmed signal (e.g. account.is_admin on
// login) without requiring the password prompt.
export function applyAdmin(isAdmin: boolean): void {
  if (isAdmin) {
    try { localStorage.setItem(ADMIN_KEY, "1"); } catch { /* ignore */ }
    notifyAuthChange();
  }
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export type Account = {
  id: string;
  email: string;
  display_name: string;
  tier: string;
  region: string;
  is_admin?: boolean;
};

export async function signup(email: string, password: string, displayName: string):
  Promise<{ token: string; account: Account }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/signup`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName }),
    })
  );
}

export async function login(email: string, password: string):
  Promise<{ token: string; account: Account }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/login`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
  );
}

export async function getMe(): Promise<Account> {
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/auth/me`, { headers: authHeaders(), cache: "no-store" }));
}

export async function changePassword(current: string, next: string): Promise<{ changed: boolean }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/password`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ current_password: current, new_password: next }),
    })
  );
}

export async function setMembershipTier(tier: string): Promise<{ tier: string }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/membership/tier`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ tier }),
    })
  );
}

export type Enrollment = {
  course_id: string; title: string; status: string; score: number | null;
};

export type Portfolio = {
  account: Account;
  tier: string;
  enrollments: Enrollment[];
  by_status: Record<string, Enrollment[]>;
  counts: Record<string, number>;
};

export async function getPortfolio(): Promise<Portfolio> {
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/portfolio`, { headers: authHeaders(), cache: "no-store" }));
}

export async function enrollCourse(courseId: string, title: string, status = "enrolled"):
  Promise<Enrollment> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/enrollments`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ course_id: courseId, title, status }),
    })
  );
}

// Update an enrollment's status. On the FIRST transition to "passed" the
// identity service awards reward points (scaled by level + score + hands-on),
// and returns the new points_balance. Idempotent: re-passing doesn't re-award.
export async function setEnrollmentStatus(
  courseId: string,
  status: "enrolled" | "in_progress" | "passed" | "failed",
  opts: { score?: number; level?: string; hands_on?: boolean } = {}
): Promise<Enrollment & { points_balance: number }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/enrollments/${encodeURIComponent(courseId)}/status`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ status, ...opts }),
    })
  );
}

// --- student sub-profiles + Foresight recommendations -------------------- //
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

export async function listStudents(): Promise<{ students: StudentProfile[] }> {
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/students`, { headers: authHeaders(), cache: "no-store" }));
}

export async function createStudent(displayName: string, ageBand = "adult", interests: string[] = []):
  Promise<StudentProfile> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ display_name: displayName, age_band: ageBand, interests }),
    })
  );
}

export async function setStudentMastery(studentId: string, skill: string, value: number):
  Promise<StudentProfile> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students/${studentId}/mastery`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ skill, value }),
    })
  );
}

export type ForesightRec = {
  course_id: string; title: string; score: number; covers_gaps: string[]; reason: string;
};
export type ForesightResult = {
  student_id: string; difficulty: string; gaps: string[];
  recommendations: ForesightRec[];
  relational_map: { nodes: { id: string; kind: string }[]; edges: { src: string; dst: string; rel: string; weight: number }[] };
};

export async function recommendForProfile(args: {
  student_id?: string; mastery: Record<string, number>;
  completed_course_ids?: string[]; interests?: string[]; top_n?: number;
}): Promise<ForesightResult> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/recommend`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(args),
    })
  );
}

// --- catalog browse / search ---------------------------------------------- //
export type CatalogCourse = {
  course_id: string; title: string; subject: string; category: string;
  language: string; audio_language: string; media_format: string; level: string;
  duration_min: number; hands_on: boolean; preview: string; description: string;
  tags: string[]; access_tier: string; delivery_mode: string;
  maturity_rating?: string; price_usd?: number; thumbnail?: string | null;
  popularity?: number;
  source?: string; format?: string; deep_link?: string; global_id?: string;
};

export type LearnableItem = {
  id: string; source: string; source_id: string; title: string; subtitle?: string;
  category: string; subject: string; format: string; level: string; language: string;
  duration_min: number; tags: string[]; maturity_rating: string; hands_on: boolean;
  drive_safe: boolean; access_tier: string; preview: string; deep_link: string;
  popularity?: number; thumbnail?: string | null;
};

export type LearnSearchResult = {
  total: number; offset: number; limit: number; items: LearnableItem[];
};

export type HomeRail = { key: string; title: string; courses: CatalogCourse[] };

export async function getHomeFeed(kids = false): Promise<HomeRail[]> {
  const r = await jsonOrThrow<{ rails: HomeRail[] }>(
    await fetch(`${CURRICULUM_URL}/home${kids ? "?kids=true" : ""}`, { cache: "no-store" })
  );
  return r.rails;
}

export async function bumpCourseView(courseId: string): Promise<void> {
  try {
    await fetch(`${CURRICULUM_URL}/courses/${encodeURIComponent(courseId)}/view`, { method: "POST" });
  } catch {
    /* popularity signal is best-effort */
  }
}

export type Program = {
  program_id: string; title: string; audience: string; description: string;
  course_ids: string[]; delivery_mode: string;
};

export async function getPrograms(audience?: string): Promise<Program[]> {
  const qs = audience ? `?audience=${encodeURIComponent(audience)}` : "";
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/programs${qs}`, { cache: "no-store" }));
}

export type Facets = {
  categories: string[]; languages: string[]; audio_languages: string[];
  media_formats: string[]; levels: string[]; tags: string[];
  audiences?: { slug: string; label: string }[];
  sources?: string[]; formats?: string[];
};

export async function searchLearnable(params: Record<string, string>): Promise<LearnSearchResult> {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null)
  ).toString();
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/learn/search${qs ? `?${qs}` : ""}`, { cache: "no-store" })
  );
}

export async function getLearnFacets(): Promise<Facets> {
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/learn/facets`, { cache: "no-store" }));
}

export async function searchCourses(params: Record<string, string>): Promise<CatalogCourse[]> {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null)
  ).toString();
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/courses/search${qs ? `?${qs}` : ""}`, { cache: "no-store" })
  );
}

export async function getFacets(): Promise<Facets> {
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/courses/facets`, { cache: "no-store" }));
}

// --- video-ad monetization (VAST/VMAP, tier-gated) ---------------------- //
export type AdCreative = {
  id: string; title: string; advertiser: string; media_url: string;
  duration_s: number; click_url: string | null; skippable_after_s: number | null;
};
export type AdBreak = { position: "preroll" | "midroll" | "postroll"; offset_s: number; ads: AdCreative[] };
export type AdPlan = { course_id: string; tier: string; ad_free: boolean; breaks: AdBreak[] };

export async function getAdBreaks(courseId: string, tier: string): Promise<AdPlan> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/courses/${encodeURIComponent(courseId)}/ad-breaks?tier=${encodeURIComponent(tier)}`,
      { cache: "no-store" })
  );
}

// --- jobs <-> courses (career relevance) --------------------------------- //
export type JobPosting = {
  id: string; title: string; company: string; location: string; source: string;
  url: string; employment_type: string; salary_range: string; posted_days_ago: number;
  category: string; skills: string[]; nice_to_have: string[]; description: string;
};
export type CourseMatch = { course_id: string; title: string; covered_skills: string[]; match: number };
export type JobMatch = {
  job: JobPosting; required: string[]; matched_courses: CourseMatch[];
  covered: string[]; missing: string[]; coverage_pct: number; recommended_path: string[];
};

export async function listJobs(q?: string, location?: string): Promise<{ source: string; count: number; jobs: JobPosting[] }> {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (location) p.set("location", location);
  const qs = p.toString();
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/jobs${qs ? `?${qs}` : ""}`, { cache: "no-store" }));
}
export async function getJobMatch(jobId: string): Promise<JobMatch> {
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" }));
}

export type SpecializedClass = { title: string; kind: string; for: string };
export type JobParse = {
  parsed: { skills: string[]; certifications: string[]; professions: string[] };
  matched_courses: CourseMatch[]; covered: string[]; missing: string[];
  coverage_pct: number; recommended_path: string[]; specialized_classes: SpecializedClass[];
};
export async function parseJobDescription(description: string): Promise<JobParse> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/jobs/parse`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ description }),
    })
  );
}
export type CourseRelevance = {
  course_id: string; audiences: string[]; fundamental_for: string[];
  core_skill: boolean; audience_labels: string[]; tags: string[];
};
export async function getCourseRelevance(id: string): Promise<CourseRelevance> {
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/courses/${encodeURIComponent(id)}/relevance`, { cache: "no-store" }));
}

// --- audio "drive mode" courses ------------------------------------------ //
export type AudioCourseRow = {
  id: string; title: string; category: string; subject: string; level: string;
  duration_min: number; tags: string[]; format: string; visual_required: boolean;
  drive_safe: boolean; segments: number;
};
export type AudioSegment = { heading: string; text: string };
export type AudioCourse = {
  id: string; title: string; category: string; subject: string; level: string;
  duration_min: number; tags: string[]; format: string; visual_required: boolean;
  drive_safe: boolean; segments: AudioSegment[];
};

export async function getAudioCategories(): Promise<{ category: string; count: number }[]> {
  const r = await jsonOrThrow<{ categories: { category: string; count: number }[] }>(
    await fetch(`${CURRICULUM_URL}/audio/categories`, { cache: "no-store" })
  );
  return r.categories;
}
export async function listAudioCourses(params: Record<string, string> = {}): Promise<{ total: number; offset: number; limit: number; courses: AudioCourseRow[] }> {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/audio/courses${qs ? `?${qs}` : ""}`, { cache: "no-store" }));
}
export async function getAudioCourse(id: string): Promise<AudioCourse> {
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/audio/courses/${encodeURIComponent(id)}`, { cache: "no-store" }));
}

// --- language learning ---------------------------------------------------- //
export type LangInfo = { code: string; name: string; native: string; flag: string; tier: string; phrase_count: number };
export type LangSkill = { id: string; name: string; icon: string; desc: string };
export type LangCourse = {
  code: string; name: string; native: string; flag: string; tier: string;
  skills: LangSkill[]; phrase_count: number; grammar_tip: string; culture_note: string;
};
export type LangItem = { id: string; prompt: string; options: string[]; answer_index: number; explain: string; audio_prompt?: string };
export type LangExercise = { skill: string; language: string; items?: LangItem[];
  pairs?: { id: string; term: string; match: string }[]; target?: string; roman?: string;
  en?: string; mouth_tip?: string; tip?: string; note?: string };
export type Pronounce = { score: number; stars: number; passed: boolean; target: string;
  heard: string; missed_words: string[]; feedback: string; mouth_tip: string };

export async function getLearnLanguages(): Promise<{ languages: LangInfo[]; count: number }> {
  return jsonOrThrow(await fetch(`${SPEECH_URL}/learn/languages`, { cache: "no-store" }));
}
export async function getLangCourse(code: string): Promise<LangCourse> {
  return jsonOrThrow(await fetch(`${SPEECH_URL}/learn/${code}/course`, { cache: "no-store" }));
}
export async function newLangExercise(language: string, skill: string, n = 5): Promise<LangExercise> {
  return jsonOrThrow(
    await fetch(`${SPEECH_URL}/learn/exercise`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ language, skill, n }),
    })
  );
}
export async function pronounce(target: string, heard: string, mouthOpenness?: number): Promise<Pronounce> {
  return jsonOrThrow(
    await fetch(`${SPEECH_URL}/learn/pronounce`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ target, heard, mouth_openness: mouthOpenness ?? null }),
    })
  );
}
export async function languagePractice(
  language: string, skill: string, correct: number, total: number
): Promise<{ xp: number; balance: number }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/language/practice`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ language, skill, correct, total }),
    })
  );
}

// --- learning games / arcade --------------------------------------------- //
export type GameTypeInfo = { id: string; name: string; desc: string };
export type AgeGroupInfo = { id: string; name: string; range: string };
export type GamesCatalog = { subjects: string[]; game_types: GameTypeInfo[]; age_groups: AgeGroupInfo[] };
export type GameItem = { id: string; prompt: string; options: string[] };
export type GameTerm = { id: string; term: string };
export type GameOption = { id: string; text: string };
export type GameRound = {
  game_id: string; subject: string; game_type: string; time_limit_s: number;
  items?: GameItem[]; terms?: GameTerm[]; options?: GameOption[];
};
export type GameItemResult = { id: string; correct: boolean; answer_index?: number; explain: string };
export type GameScore = {
  game_id: string; subject: string; game_type: string; correct: number; total: number;
  accuracy: number; base_points: number; speed_bonus: number; accuracy_bonus: number;
  points: number; results: GameItemResult[];
};
export type GameSubmit = {
  result: GameScore; points_earned: number; balance: number;
  rank: number | null; subject_rank: number | null;
};
export type Leader = { rank: number; name: string; score: number; game_points: number; games_played: number };

export async function getGamesCatalog(): Promise<GamesCatalog> {
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/games`, { cache: "no-store" }));
}

export async function newGame(
  subject: string, gameType: string, ageGroup = "teen", n = 5
): Promise<GameRound> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/games/new`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ subject, game_type: gameType, age_group: ageGroup, n }),
    })
  );
}

export async function submitGame(
  gameId: string, answers: Record<string, number | string>, elapsedS?: number
): Promise<GameSubmit> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/games/submit`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ game_id: gameId, answers, elapsed_s: elapsedS ?? null }),
    })
  );
}

export async function getLeaderboard(subject?: string, ageGroup?: string): Promise<{ leaders: Leader[] }> {
  const p = new URLSearchParams();
  if (subject) p.set("subject", subject);
  if (ageGroup) p.set("age_group", ageGroup);
  const qs = p.toString();
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/games/leaderboard${qs ? `?${qs}` : ""}`, { cache: "no-store" }));
}

// --- rewards (points for completion -> discounts / prizes) --------------- //
export type LedgerEntry = { delta: number; reason: string; ref: string; ts: number };
export type Redemption = {
  prize_id: string; kind: string; cost_points: number;
  voucher_code: string | null; percent: number | null;
  raffle_entry_id: string | null; detail: Record<string, unknown>;
};
export type RewardsSummary = { balance: number; ledger: LedgerEntry[]; redemptions: Redemption[] };
export type RewardPrize = {
  id: string; name: string; kind: string; cost_points: number; detail: Record<string, unknown>;
};

export async function getRewards(): Promise<RewardsSummary> {
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/rewards`, { headers: authHeaders(), cache: "no-store" }));
}

export async function getRewardsCatalog(): Promise<{ prizes: RewardPrize[] }> {
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/rewards/catalog`, { cache: "no-store" }));
}

export async function redeemReward(prizeId: string):
  Promise<{ redemption: Redemption; balance: number }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/rewards/redeem`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ prize_id: prizeId }),
    })
  );
}

export type Slide = {
  index: number;
  title: string;
  body: string;
  narration: string;
};

export type Lesson = {
  lesson_id: string;
  title: string;
  language: string;
  audience?: string;
  slides: Slide[];
};

export type SessionState = {
  session_id: string;
  class_type: string;
  lesson_id: string;
  current_slide: number;
  history: { role: string; text: string }[];
};

export type SessionView = {
  session: SessionState;
  lesson: Lesson;
  slide: Slide;
};

export type Answer = {
  text: string;
  citations: string[];
  language: string;
  understood?: string[];
  grounded?: boolean;
  hallucination_risk?: number;
  unsupported?: string[];
  // Set when the AI teacher grants points for this question; the client redeems
  // grant_token at /rewards/grant (server-verified).
  reward?: { points: number; reason: string; grant_token: string } | null;
};

// Redeem an AI-agent reward voucher to the current account. The identity
// service verifies the agent's HMAC signature before crediting.
export async function grantReward(grant: string):
  Promise<{ earned: number; balance: number; reason: string }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/rewards/grant`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ grant }),
    })
  );
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (j.detail != null) {
        detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      }
    } catch {
      /* non-JSON body */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

export async function listLessons(): Promise<Lesson[]> {
  return jsonOrThrow(await fetch(`${ORCHESTRATOR_URL}/api/lessons`, { cache: "no-store" }));
}

export async function startSession(
  lessonId: string,
  classType: string
): Promise<SessionView> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/sessions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ lesson_id: lessonId, class_type: classType }),
    })
  );
}

// --- scheduled group classes (AI presents via Zoom/Teams/Meet/Salareen) --- //
export type GroupClass = {
  id: string;
  title: string;
  lesson_id: string;
  platform: string;
  meeting_url: string;
  start_time: string;
  duration_min: number;
  host: string;
  capacity: number;
  language: string;
  description: string;
  status: string;
  seats_left: number;
  registered: number;
  needs_bridge: boolean;
  session_id: string;
};

export type ScheduleGroupClassInput = {
  title: string;
  lesson_id: string;
  start_time: string;
  platform?: string;
  meeting_url?: string;
  duration_min?: number;
  host?: string;
  capacity?: number;
  language?: string;
  description?: string;
};

export type GroupClassStart = {
  class: GroupClass;
  session: SessionView;
  bridge: {
    needs_bridge: boolean;
    platform: string;
    livekit_room: string;
    meeting_ref?: string;
    join_url?: string;
    connect_endpoint?: string;
    note?: string;
    livekit?: { room: string; token: string; url: string };
  };
};

export async function listGroupClasses(upcoming = true): Promise<GroupClass[]> {
  const r = await jsonOrThrow<{ classes: GroupClass[] }>(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes?upcoming=${upcoming}`, { cache: "no-store" })
  );
  return r.classes;
}

export async function scheduleGroupClass(input: ScheduleGroupClassInput): Promise<GroupClass> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    })
  );
}

export async function registerGroupClass(
  classId: string,
  name: string,
  email = ""
): Promise<GroupClass> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/register`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, email }),
    })
  );
}

export async function startGroupClass(classId: string): Promise<GroupClassStart> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/start`, {
      method: "POST",
      headers: { "content-type": "application/json" },
    })
  );
}

export async function advance(sessionId: string): Promise<Slide> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/sessions/${sessionId}/advance`, {
      method: "POST",
    })
  );
}

export type LegalNotice = {
  id: string;
  title: string;
  version: string;
  summary: string;
  path: string;
};

export async function getLegalNotices(): Promise<{ required: string[]; notices: LegalNotice[] }> {
  return jsonOrThrow(await fetch(`${MEMORY_URL}/legal/notices`, { cache: "no-store" }));
}

export async function acceptLegal(userId: string, noticeIds: string[]): Promise<{
  all_required_accepted: boolean;
  outstanding: string[];
}> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/legal/accept`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ user_id: userId, notice_ids: noticeIds }),
    })
  );
}

export async function getCompliance(region: string): Promise<Record<string, unknown>> {
  return jsonOrThrow(await fetch(`${MEMORY_URL}/compliance/${region}`, { cache: "no-store" }));
}

// --- administrative feature flags --------------------------------------- //
export type FlagSpec = {
  key: string; type: string; category: string; description: string;
  admin_only: boolean; options: string[]; default: unknown; enabled: boolean;
  value: unknown; rollout_pct: number | null; tiers: string[] | null;
  overrides: Record<string, unknown>; updated_at: number; updated_by: string;
};

export async function evaluateFlags(
  subject?: string, tier?: string
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (subject) qs.set("subject", subject);
  if (tier) qs.set("tier", tier);
  const r = await jsonOrThrow<{ flags: Record<string, unknown> }>(
    await fetch(`${MEMORY_URL}/flags/evaluate?${qs.toString()}`, { cache: "no-store" })
  );
  return r.flags;
}

export async function getFlag(key: string, subject?: string): Promise<unknown> {
  const qs = subject ? `?subject=${encodeURIComponent(subject)}` : "";
  const r = await jsonOrThrow<{ value: unknown }>(
    await fetch(`${MEMORY_URL}/flags/${encodeURIComponent(key)}${qs}`, { cache: "no-store" })
  );
  return r.value;
}

// --- locale-specific Bayon Buddy mascots (27 languages) ----------------- //

export type MascotCatalogEntry = {
  locale: string; region: string; cultural_theme: string; path: string;
};

export async function getMascotCatalog(): Promise<{ count: number; mascots: MascotCatalogEntry[] }> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/mascots/catalog`, { cache: "no-store" }),
  );
}

export async function resolveMascot(
  locale: string, subject?: string, tier?: string,
): Promise<MascotResolve> {
  const qs = new URLSearchParams({ locale });
  if (subject) qs.set("subject", subject);
  if (tier) qs.set("tier", tier);
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/mascots/resolve?${qs.toString()}`, { cache: "no-store" }),
  );
}

export async function adminListFlags(secret: string): Promise<FlagSpec[]> {
  const r = await jsonOrThrow<{ flags: FlagSpec[] }>(
    await fetch(`${MEMORY_URL}/admin/flags`, {
      cache: "no-store", headers: { "X-Admin-Secret": secret },
    })
  );
  return r.flags;
}

/** Feature flags for a logged-in operator admin (via Next.js BFF; no secret prompt). */
export async function adminListFlagsSession(): Promise<FlagSpec[]> {
  const r = await jsonOrThrow<{ flags: FlagSpec[] }>(
    await fetch("/api/admin/flags", { cache: "no-store", headers: authHeaders() })
  );
  return r.flags;
}

export async function adminSetFlagSession(
  key: string,
  patch: { enabled?: boolean; value?: unknown; rollout_pct?: number; tiers?: string[] | null; clear_value?: boolean }
): Promise<FlagSpec> {
  return jsonOrThrow(
    await fetch(`/api/admin/flags/${encodeURIComponent(key)}`, {
      method: "PUT",
      headers: { ...authHeaders(), "content-type": "application/json" },
      body: JSON.stringify(patch),
    })
  );
}

export async function adminListAccounts(): Promise<{ accounts: Account[]; count: number }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/admin/accounts`, { headers: authHeaders(), cache: "no-store" })
  );
}

export async function adminSetFlag(
  secret: string, key: string,
  patch: { enabled?: boolean; value?: unknown; rollout_pct?: number; tiers?: string[] | null; clear_value?: boolean }
): Promise<FlagSpec> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/admin/flags/${encodeURIComponent(key)}`, {
      method: "PUT",
      headers: { "content-type": "application/json", "X-Admin-Secret": secret },
      body: JSON.stringify(patch),
    })
  );
}

// --- end-of-class survey (gated by engagement.post_class_survey flag) ---- //
export type SurveyQuestion = {
  id: string; type: string; prompt: string; options: string[]; required: boolean;
};
export type SurveyTemplate = {
  version: string; title: string; subtitle?: string; questions: SurveyQuestion[];
  categories?: string[];
};

export async function getPostClassSurvey(
  subject?: string, tier?: string
): Promise<{ enabled: boolean; template: SurveyTemplate | null }> {
  const qs = new URLSearchParams();
  if (subject) qs.set("subject", subject);
  if (tier) qs.set("tier", tier);
  return jsonOrThrow(await fetch(`${MEMORY_URL}/survey/post-class?${qs.toString()}`, { cache: "no-store" }));
}

export async function submitPostClassSurvey(payload: {
  course_id: string; overall: number; class_type?: string; subject?: string;
  student_id?: string | null; clarity?: number | null; pace?: string | null;
  would_recommend?: boolean | null; suggestion?: string;
}): Promise<{ id: string; recorded: boolean }> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/survey/post-class`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

// --- one-time onboarding learning survey (post-signup) ------------------- //
export async function getOnboardingSurvey(
  subject?: string, tier?: string
): Promise<{ enabled: boolean; template: SurveyTemplate | null }> {
  const qs = new URLSearchParams();
  if (subject) qs.set("subject", subject);
  if (tier) qs.set("tier", tier);
  return jsonOrThrow(await fetch(`${MEMORY_URL}/survey/onboarding?${qs.toString()}`, { cache: "no-store" }));
}

export async function submitOnboardingSurveyAnalytics(payload: {
  account_id: string; student_id: string; answers: Record<string, unknown>;
}): Promise<{ id: string; recorded: boolean; learner_category: string }> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/survey/onboarding`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function submitLearningProfile(
  studentId: string, answers: Record<string, unknown>
): Promise<{ student: StudentProfile; learner_category: string; recorded: boolean }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students/${encodeURIComponent(studentId)}/learning-profile`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ answers }),
    })
  );
}

export async function skipLearningProfile(
  studentId: string,
): Promise<{ student: StudentProfile; skipped: boolean }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students/${encodeURIComponent(studentId)}/learning-profile/skip`, {
      method: "POST",
      headers: authHeaders(),
    })
  );
}

/** True when identity exposes POST .../learning-profile (needs current deploy). */
export async function identitySupportsLearningProfile(): Promise<boolean> {
  try {
    const res = await fetch(`${IDENTITY_URL}/__meta`, { cache: "no-store" });
    if (!res.ok) return false;
    const meta = (await res.json()) as { routes?: { path?: string; methods?: string[] }[] };
    return (meta.routes ?? []).some(
      (r) =>
        r.path?.includes("learning-profile") &&
        (r.methods ?? []).includes("POST"),
    );
  } catch {
    return false;
  }
}

// --- service version / status (automation + admin visibility) ----------- //
export type ServiceVersion = {
  service: string;
  url: string;
  reachable: boolean;
  version?: string;
  git_sha?: string;
  build_time?: string;
  api_version?: string;
  deploy_mode?: string;
  error?: string;
};

export async function getServiceVersion(name: string, url: string): Promise<ServiceVersion> {
  try {
    const res = await fetch(`${url}/version`, { cache: "no-store" });
    if (!res.ok) return { service: name, url, reachable: false, error: `${res.status}` };
    const j = await res.json();
    return {
      service: name, url, reachable: true, version: j.version, git_sha: j.git_sha,
      build_time: j.build_time, api_version: j.api_version, deploy_mode: j.deploy_mode,
    };
  } catch (e) {
    return { service: name, url, reachable: false, error: String(e) };
  }
}

export async function getServiceVersions(): Promise<ServiceVersion[]> {
  return Promise.all(
    Object.entries(SERVICE_URLS).map(([name, url]) => getServiceVersion(name, url))
  );
}

// --- observability / telemetry (perf, memory, errors) -------------------- //
export type RoutePerf = {
  count: number; errors: number; p50_ms: number; p95_ms: number;
  p99_ms: number; max_ms: number; last_ms: number; error_rate: number;
};
export type TelemetrySummary = {
  service: string; url: string; reachable: boolean;
  uptime_s?: number;
  process?: { rss_mb: number; cpu_user_s: number; cpu_system_s: number; threads: number; gc_objects: number };
  totals?: { requests: number; errors: number; error_rate: number; inflight: number };
  routes?: Record<string, RoutePerf>;
  error_count?: number;
  exporters?: { sentry: boolean; otlp: boolean };
  error?: string;
};
export type TelemetryError = {
  ts: number; route: string; method: string; status: number;
  type: string; message: string; traceback: string; request_id: string;
};

export async function getTelemetrySummary(name: string, url: string): Promise<TelemetrySummary> {
  try {
    const res = await fetch(`${url}/telemetry/summary`, { cache: "no-store" });
    if (!res.ok) return { service: name, url, reachable: false, error: `${res.status}` };
    const j = await res.json();
    return { ...j, service: name, url, reachable: true };
  } catch (e) {
    return { service: name, url, reachable: false, error: String(e) };
  }
}

export async function getAllTelemetry(): Promise<TelemetrySummary[]> {
  return Promise.all(
    Object.entries(SERVICE_URLS).map(([name, url]) => getTelemetrySummary(name, url))
  );
}

export async function getServiceErrors(name: string, url: string, limit = 20): Promise<TelemetryError[]> {
  try {
    const res = await fetch(`${url}/telemetry/errors?limit=${limit}`, { cache: "no-store" });
    if (!res.ok) return [];
    const j = await res.json();
    return (j.errors ?? []) as TelemetryError[];
  } catch {
    return [];
  }
}

export async function adminSurveyInsights(secret: string): Promise<{
  data_mining_enabled: boolean;
  datamart: {
    total_responses: number;
    dimensions: Record<string, Record<string, number>>;
    cells: { course_id: string; class_type: string; rating_bucket: string; responses: number; avg_overall: number }[];
    top_suggestions: { term: string; count: number }[];
  };
}> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/admin/survey/insights`, {
      cache: "no-store", headers: { "X-Admin-Secret": secret },
    })
  );
}

export async function recordConsent(args: {
  student_id: string;
  scope: string;
  granted: boolean;
  region?: string;
  written?: boolean;
  retention_days?: number | null;
}): Promise<{ student_id: string; scope: string; granted: boolean }> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/consent`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(args),
    })
  );
}

export type ReviewItem = {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  ai_confidence: number;
  risk: number;
  status: string;
  final_payload: Record<string, unknown> | null;
  decided_by: string | null;
};

export async function hilQueue(status?: string): Promise<{ autonomy: string; items: ReviewItem[] }> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return jsonOrThrow(await fetch(`${ORCHESTRATOR_URL}/api/hil/queue${q}`, { cache: "no-store" }));
}

export async function hilDecide(
  itemId: string,
  action: string,
  editedPayload?: Record<string, unknown>
): Promise<ReviewItem> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/hil/${itemId}/decision`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action, edited_payload: editedPayload ?? null }),
    })
  );
}

export async function gradeReviews(status?: string): Promise<{ autonomy: string; items: ReviewItem[] }> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/homework/grade-reviews${q}`, { cache: "no-store" }));
}

export async function gradeReviewDecide(
  itemId: string,
  action: string,
  editedPayload?: Record<string, unknown>
): Promise<ReviewItem> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/homework/grade-reviews/${itemId}/decision`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action, edited_payload: editedPayload ?? null }),
    })
  );
}

export type Disclosure = {
  is_ai: boolean;
  instructor: string;
  model_name: string;
  persona: string;
  human_of_record: string | null;
  generated_with: string;
  grounded_with_citations: boolean;
  line: string;
};

export async function getDisclosure(): Promise<Disclosure> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/disclosure`, { cache: "no-store" })
  );
}

export type HomeworkItemGrade = {
  question_id: string;
  type: string;
  correct: boolean | null;
  score: number;
  citations: { source?: string; url?: string; overlap?: number; snippet?: string }[];
  rationale: string;
};

export type HomeworkGrade = {
  score: number;
  max_score: number;
  percentage: number;
  validity_flags: string[];
  authorship_label: string | null;
  items: HomeworkItemGrade[];
};

export async function gradeHomework(args: {
  assignment: unknown;
  answers?: string[];
  submission_text?: string;
  handwritten?: boolean;
  deck_id?: string;
  subject?: string;
}): Promise<HomeworkGrade> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/homework/grade`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(args),
    })
  );
}

export async function generateHomework(args: {
  deck_id?: string;
  course_id?: string;
  title?: string;
  subject?: string;
  num_questions?: number;
}): Promise<{ assignment_id: string; title: string; subject: string; questions: unknown[] }> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/homework/generate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(args),
    })
  );
}

export type ModelCard = {
  name: string;
  base_model: string | null;
  metrics: { accuracy: number | null; by_category: Record<string, number>; fairness_gap: number | null };
  intended_use: string;
  training_data: string;
  limitations: string[];
  fairness: string;
};

export async function getModelCards(): Promise<ModelCard[]> {
  const r = await jsonOrThrow<{ model_cards: ModelCard[] }>(
    await fetch(`${CURRICULUM_URL}/model-cards`, { cache: "no-store" })
  );
  return r.model_cards;
}

export type ReportedCorrection = { id: string; status: string };

export async function reportIssue(args: {
  target_kind?: string;
  target_id?: string;
  locator?: string;
  issue: string;
  suggested?: string;
  author?: string;
}): Promise<ReportedCorrection> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/report`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(args),
    })
  );
}

export type ProvenanceVerification = {
  valid: boolean;
  content_matches: boolean | null;
  artifact_id: string;
  assertions: { label: string; data: Record<string, unknown> }[];
};

export async function verifyProvenance(
  signed: unknown,
  content?: string
): Promise<ProvenanceVerification> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/provenance/verify`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ signed, content: content ?? null }),
    })
  );
}

// --- hybrid (on-device) face recognition --------------------------------- //
// The browser runs YuNet+SFace locally (see ./vision) and sends ONLY the
// resulting embedding here; the raw camera frame never leaves the device. The
// server matches the embedding against the consented gallery and enforces the
// region/consent compliance gates.
export type WireFace = {
  embedding: number[];
  landmarks?: number[][];
  bbox?: number[];
  frame_size?: number[];
};

export type IdentifiedFace = {
  track_id: string;
  matched_student_id: string | null;
  attention: number;
  gaze_frontal: number;
  expression: string;
  identified: boolean;
};

export function visionModelUrl(name: string): string {
  return `${PERCEPTION_URL}/vision/models/${encodeURIComponent(name)}`;
}

export async function identifyEmbedding(
  faces: WireFace[],
  consentedStudentIds: string[]
): Promise<{ faces: IdentifiedFace[] }> {
  return jsonOrThrow(
    await fetch(`${PERCEPTION_URL}/identify-embedding`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ faces, consented_student_ids: consentedStudentIds }),
    })
  );
}

export async function enrollEmbedding(
  studentId: string,
  embedding: number[]
): Promise<{ student_id: string; enrollments: number }> {
  return jsonOrThrow(
    await fetch(`${PERCEPTION_URL}/enroll-embedding/${encodeURIComponent(studentId)}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ embedding }),
    })
  );
}

export async function ask(sessionId: string, text: string): Promise<Answer> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/sessions/${sessionId}/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, language: "en" }),
    })
  );
}
