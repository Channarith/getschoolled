// Client for the orchestrator (Teaching Director) API.
// Base URL is configurable so the SAME UI runs against local or cloud backends.

export const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ?? "http://localhost:8000";

export const CURRICULUM_URL =
  process.env.NEXT_PUBLIC_CURRICULUM_URL ?? "http://localhost:8005";

export const MEMORY_URL =
  process.env.NEXT_PUBLIC_MEMORY_URL ?? "http://localhost:8004";

export const IDENTITY_URL =
  process.env.NEXT_PUBLIC_IDENTITY_URL ?? "http://localhost:8008";

// --- account / session (token in localStorage) --------------------------- //
const TOKEN_KEY = "aoep_token";

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
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
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

// --- student sub-profiles + Foresight recommendations -------------------- //
export type StudentProfile = {
  id: string; display_name: string; age_band: string;
  mastery: Record<string, number>; completed_course_ids: string[]; interests: string[];
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
};

export type Facets = {
  categories: string[]; languages: string[]; audio_languages: string[];
  media_formats: string[]; levels: string[]; tags: string[];
};

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
};

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
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

export async function adminListFlags(secret: string): Promise<FlagSpec[]> {
  const r = await jsonOrThrow<{ flags: FlagSpec[] }>(
    await fetch(`${MEMORY_URL}/admin/flags`, {
      cache: "no-store", headers: { "X-Admin-Secret": secret },
    })
  );
  return r.flags;
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
export type SurveyTemplate = { version: string; title: string; questions: SurveyQuestion[] };

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

export async function ask(sessionId: string, text: string): Promise<Answer> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/sessions/${sessionId}/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, language: "en" }),
    })
  );
}
