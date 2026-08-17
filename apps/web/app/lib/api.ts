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

export const WEBCAM_URL = serviceUrl(
  process.env.NEXT_PUBLIC_WEBCAM_URL, "/webcam", "http://localhost:8300");

// All backend services keyed by name -> base URL (each exposes /version + /health).
export const SERVICE_URLS: Record<string, string> = {
  orchestrator: ORCHESTRATOR_URL,
  speech: SPEECH_URL,
  perception: PERCEPTION_URL,
  webcam: WEBCAM_URL,
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
/** Fired when the post-login legal disclaimer is accepted (see DisclaimerGate). */
export const DISCLAIMER_ACCEPTED_EVENT = "aoep-disclaimer-accepted";

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

// Stable per-browser learner id for the adaptive teaching loop. The memory
// service keys mastery/behavior by (student_id, topic), so a persisted id lets
// quizzes adapt to this learner across reloads. A real deployment would use the
// authenticated account id; this keeps the loop working without the identity
// service running.
const STUDENT_KEY = "aoep_student_id";

export function getStudentId(): string {
  try {
    let id = localStorage.getItem(STUDENT_KEY);
    if (!id) {
      id =
        (typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `stu-${Date.now()}-${Math.random().toString(36).slice(2)}`);
      localStorage.setItem(STUDENT_KEY, id);
    }
    return id;
  } catch {
    return "anon-student";
  }
}

// "Preview" lets a signed-out visitor browse the catalog before creating an
// account. It is persisted so the choice survives navigation/reload, and gates
// the content nav tabs (hidden until the visitor logs in OR opts into preview).
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

export type Subscription = {
  tier: string;
  display_name: string;
  price_usd: number;
  billing_interval: string;
  ads: boolean;
  subscription_started_at: number | null;
  billing_anchor_day: number | null;
  next_billing_at: number | null;
};

export type Account = {
  id: string;
  email: string;
  display_name: string;
  tier: string;
  region: string;
  membership_class?: "standard" | "vip";
  preferred_language?: string;
  subscription?: Subscription;
  is_admin?: boolean;
  onboarding_completed_at?: number | null;
  login_count?: number;
  billing_validated?: boolean;
  card_last4?: string | null;
};

export type OnboardingStatus = {
  completed: boolean;
  completed_at: number | null;
  tier: string;
  membership_class: string;
  billing_required: boolean;
  billing_validated: boolean;
};

export type LoginEvent = {
  ts: number;
  success: boolean;
  ip: string;
  user_agent: string;
  country_hint: string;
  method?: string;
};

export type AdSlotPayload = {
  show: boolean;
  slot_id?: string;
  network?: string;
  width?: number;
  height?: number;
  label?: string;
  click_url?: string;
  image_url?: string;
  house?: boolean;
  client_id?: string;
  script_url?: string;
  data_ad_slot?: string;
};

export async function getOnboardingStatus(): Promise<OnboardingStatus> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/onboarding-status`, { headers: authHeaders(), cache: "no-store" }),
  );
}

export async function setup2fa(): Promise<{ secret: string; otpauth_uri: string }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/2fa/setup`, { method: "POST", headers: authHeaders() })
  );
}

export async function confirm2fa(code: string): Promise<{ enabled: boolean }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/2fa/confirm`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ code }),
    })
  );
}

export async function disable2fa(code: string): Promise<{ enabled: boolean }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/2fa/disable`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ code }),
    })
  );
}

export async function getLoginHistory(): Promise<{ events: LoginEvent[] }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/login-history`, { headers: authHeaders(), cache: "no-store" }),
  );
}

export async function getSecuritySummary(): Promise<{
  totp_enabled: boolean;
  passkeys: { credential_id: string; label: string }[];
  oauth_linked: boolean;
  recent_logins: LoginEvent[];
}> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/security`, { headers: authHeaders(), cache: "no-store" })
  );
}

export async function submitOnboardingProfile(body: {
  display_name?: string;
  phone?: string;
  region?: string;
}): Promise<{ ok: boolean }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/onboarding/profile`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    }),
  );
}

export async function submitOnboardingBilling(body: Record<string, unknown>): Promise<{ validated: boolean; card_last4: string }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/onboarding/billing`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    }),
  );
}

export async function selectOnboardingPlan(tier: string): Promise<{ tier: string; membership_class: string }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/onboarding/plan`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ tier }),
    }),
  );
}

export async function completeOnboarding(body: { learner_name?: string; age_band?: string }): Promise<{ completed: boolean }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/onboarding/complete`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    }),
  );
}

export async function getBillingPlans(): Promise<Record<string, unknown>> {
  return jsonOrThrow(await fetch(`${BILLING_URL}/plans`, { cache: "no-store" }));
}

export async function getAdSlot(slotId: string, tier: string): Promise<AdSlotPayload> {
  return jsonOrThrow(
    await fetch(`${BILLING_URL}/ads/slot/${encodeURIComponent(slotId)}?tier=${encodeURIComponent(tier)}`, {
      cache: "no-store",
    }),
  );
}

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

export async function verify2faLogin(mfaToken: string, code: string):
  Promise<{ token: string; account: Account }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/2fa/verify`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ mfa_token: mfaToken, code }),
    })
  );
}

export async function forgotPassword(email: string): Promise<{ sent: boolean; reset_token?: string }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/forgot-password`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ email }),
    })
  );
}

export async function resetPassword(token: string, newPassword: string): Promise<{ reset: boolean }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/reset-password`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ token, new_password: newPassword }),
    })
  );
}

export async function loginWithGoogle(idToken: string): Promise<{ token: string; account: Account }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/oauth/google`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ id_token: idToken }),
    })
  );
}

export async function loginWithFacebook(accessToken: string): Promise<{ token: string; account: Account }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/oauth/facebook`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ access_token: accessToken }),
    })
  );
}

export async function loginWithApple(identityToken: string): Promise<{ token: string; account: Account }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/auth/oauth/apple`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ identity_token: identityToken }),
    })
  );
}

export type OAuthProviderStatus = {
  sandbox_enabled: boolean;
  google: { enabled: boolean; mode: "sandbox" | "live" | "disabled"; reason: string };
  facebook: { enabled: boolean; mode: "sandbox" | "live" | "disabled"; reason: string };
  apple: { enabled: boolean; mode: "sandbox" | "live" | "disabled"; reason: string };
};

export async function getOAuthProviderStatus(): Promise<OAuthProviderStatus> {
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/auth/oauth/providers`, { cache: "no-store" }));
}

export async function getMe(): Promise<Account> {
  // No token → the visitor is signed out. Skip the request that is guaranteed to
  // 401 (avoids the console error + a pointless round-trip on every guest load
  // and nav click). Callers already treat a rejection as "signed out".
  if (!getToken()) throw new Error("401 Not authenticated");
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/auth/me`, { headers: authHeaders(), cache: "no-store" }));
}

/** Persist the signed-in learner's preferred language so it follows them across
 * devices and the AI teacher answers in it. Best-effort; safe to ignore errors. */
export async function setAccountLanguage(language: string): Promise<{ preferred_language: string }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/account/language`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ language }),
    })
  );
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

export async function subscribeToPlan(tier: string): Promise<{
  tier: string;
  membership_class: string;
  subscription: Subscription;
}> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/membership/subscribe`, {
      method: "POST", headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ tier }),
    })
  );
}

export async function getSubscription(): Promise<Subscription> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/membership/subscription`, { headers: authHeaders(), cache: "no-store" })
  );
}

export type ConsumerPlan = {
  tier: string;
  display_name: string;
  price_usd: number;
  billing_interval: string;
  ads: boolean;
  blurb: string;
};

export async function getConsumerPlans(): Promise<Record<string, ConsumerPlan>> {
  return jsonOrThrow(await fetch(`${BILLING_URL}/plans/consumer`, { cache: "no-store" }));
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

/** Bookmark a course to My List (status="saved"). Idempotent. */
export async function saveForLater(courseId: string, title: string): Promise<Enrollment> {
  return enrollCourse(courseId, title, "saved");
}

/** Remove a course from My List (deletes the enrollment entirely). */
export async function unsaveForLater(courseId: string): Promise<void> {
  await jsonOrThrow(
    await fetch(`${IDENTITY_URL}/enrollments/${encodeURIComponent(courseId)}`, {
      method: "DELETE", headers: authHeaders(),
    })
  );
}

// Update an enrollment's status. On the FIRST transition to "passed" the
// identity service awards reward points (scaled by level + score + hands-on),
// and returns the new points_balance. Idempotent: re-passing doesn't re-award.
export async function setEnrollmentStatus(
  courseId: string,
  status: "enrolled" | "in_progress" | "passed" | "failed",
  opts: {
    score?: number;
    level?: string;
    hands_on?: boolean;
    pass_decision_token?: string;
  } = {}
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
  profile_score?: string;
  profile_score_version?: string;
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
  cold_start?: boolean;
  fallback?: boolean;
  relational_map: { nodes: { id: string; kind: string }[]; edges: { src: string; dst: string; rel: string; weight: number }[] };
};

export async function recommendForProfile(args: {
  student_id?: string; mastery: Record<string, number>;
  completed_course_ids?: string[]; interests?: string[]; top_n?: number;
}, signal?: AbortSignal): Promise<ForesightResult> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/recommend`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(args),
      signal,
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

export async function getHomeFeed(kids = false, locale = "en", signal?: AbortSignal): Promise<HomeRail[]> {
  const qs = new URLSearchParams({ locale });
  if (kids) qs.set("kids", "true");
  const r = await jsonOrThrow<{ rails: HomeRail[] }>(
    await fetch(`${CURRICULUM_URL}/home?${qs}`, { cache: "no-store", signal }),
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

export async function searchLearnable(
  params: Record<string, string>,
  locale = "en",
  signal?: AbortSignal,
): Promise<LearnSearchResult> {
  const qs = new URLSearchParams(
    Object.entries({ ...params, locale }).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/learn/search${qs ? `?${qs}` : ""}`, { cache: "no-store", signal }),
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
export type AdPlan = { course_id?: string; tier: string; ad_free: boolean; breaks: AdBreak[] };

export async function getAdBreaks(courseId: string, tier: string): Promise<AdPlan> {
  return jsonOrThrow(
    await fetch(`${CURRICULUM_URL}/courses/${encodeURIComponent(courseId)}/ad-breaks?tier=${encodeURIComponent(tier)}`,
      { cache: "no-store" })
  );
}

/** Course-agnostic ad plan (Drive Mode audio courses aren't in the catalog). */
export async function getAdPlan(tier: string, durationMin = 30): Promise<AdPlan> {
  return jsonOrThrow(
    await fetch(`${BILLING_URL}/ads/plan?tier=${encodeURIComponent(tier)}&duration_min=${durationMin}`,
      { cache: "no-store" })
  );
}

// --- ad revenue accounting (impression/click beacons + admin report) ------ //
export type AdEventBeacon = {
  placement: string;
  network?: string;
  fmt?: "display" | "video";
  tier?: string;
  unit_id?: string;
  creative_id?: string;
  advertiser?: string;
};

/** Fire an ad impression/click beacon (best-effort; never throws). */
async function sendAdBeacon(kind: "impression" | "click", ev: AdEventBeacon): Promise<void> {
  try {
    await fetch(`${BILLING_URL}/ads/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ev),
      keepalive: true,
    });
  } catch {
    /* beacons are best-effort telemetry */
  }
}
export function recordAdImpression(ev: AdEventBeacon): void { void sendAdBeacon("impression", ev); }
export function recordAdClick(ev: AdEventBeacon): void { void sendAdBeacon("click", ev); }

export type AdRevenueRow = {
  key: string; impressions: number; clicks: number; ctr: number;
  revenue_usd: number; ecpm_usd: number;
};
export type AdRevenueReport = {
  active_network: string;
  totals: { impressions: number; clicks: number; ctr: number; revenue_usd: number; ecpm_usd: number };
  by_network: AdRevenueRow[];
  by_placement: AdRevenueRow[];
  by_day: AdRevenueRow[];
  recent: Array<{ kind: string; placement: string; network: string; fmt: string; tier: string;
    creative_id: string; advertiser: string; revenue_usd: number; ts: number }>;
};

export async function getAdRevenue(days = 0): Promise<AdRevenueReport> {
  return jsonOrThrow(
    await fetch(`${BILLING_URL}/ads/revenue${days ? `?days=${days}` : ""}`, { cache: "no-store" })
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

export async function listJobs(q?: string, location?: string, limit = 500): Promise<{ source: string; count: number; jobs: JobPosting[] }> {
  const p = new URLSearchParams({ limit: String(limit) });
  if (q) p.set("q", q);
  if (location) p.set("location", location);
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/jobs?${p.toString()}`, { cache: "no-store" }));
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
  // Actual language of the spoken body text (may differ from the requested
  // training locale when it falls back to English). Use this for TTS voice.
  body_locale?: string; locale?: string; training_locale?: string;
};

export async function getAudioCategories(locale = "en"): Promise<{ category: string; count: number }[]> {
  const r = await jsonOrThrow<{ categories: { category: string; count: number }[] }>(
    await fetch(`${CURRICULUM_URL}/audio/categories?locale=${encodeURIComponent(locale)}`, { cache: "no-store" }),
  );
  return r.categories;
}
export async function listAudioCourses(
  params: Record<string, string> = {},
  locale = "en",
  trainingLocale?: string,
): Promise<{ total: number; offset: number; limit: number; courses: AudioCourseRow[] }> {
  const qs = new URLSearchParams(
    Object.entries({
      ...params,
      locale,
      ...(trainingLocale ? { training_locale: trainingLocale } : {}),
    }).filter(([, v]) => v),
  ).toString();
  return jsonOrThrow(await fetch(`${CURRICULUM_URL}/audio/courses${qs ? `?${qs}` : ""}`, { cache: "no-store" }));
}
export async function getAudioCourse(
  id: string, locale = "en", trainingLocale?: string,
): Promise<AudioCourse> {
  const p = new URLSearchParams({ locale });
  if (trainingLocale) p.set("training_locale", trainingLocale);
  return jsonOrThrow(
    await fetch(
      `${CURRICULUM_URL}/audio/courses/${encodeURIComponent(id)}?${p.toString()}`,
      { cache: "no-store" },
    ),
  );
}

// --- language learning ---------------------------------------------------- //
export type LangInfo = { code: string; name: string; native: string; flag: string; tier: string;
  phrase_count: number; vocabulary_count?: number; dialogue_count?: number;
  slang_count?: number; song_count?: number };
export type LangSkill = { id: string; name: string; icon: string; desc: string };
export type LangCourse = {
  code: string; name: string; native: string; flag: string; tier: string;
  skills: LangSkill[]; phrase_count: number; vocabulary_count?: number;
  dialogue_count?: number; slang_count?: number; song_count?: number;
  grammar_tip: string; culture_note: string;
};
export type LangItem = { id: string; prompt: string; options: string[]; answer_index: number; explain: string; audio_prompt?: string };
export type LangTurn = { speaker: string; target: string; roman?: string; en: string };
export type LangDialogue = { id: string; situation_en: string; turns: LangTurn[] };
export type LangSlang = { phrase: string; meaning: string; region: string; kind: string; register?: string };
export type LangVerse = { verse_no: number; target: string; roman?: string; en: string;
  explain_en: string; tts_text?: string };
export type LangSong = { song_id: string; title_en: string; title_target?: string; license: string;
  source_url?: string; source_note?: string; verses: LangVerse[] };
export type LangMediaOption = { id: string; target: string; roman?: string; en: string };
export type LangMediaSegment = { id: string; start_sec: number; end_sec: number;
  duration_sec: number; tts_text: string; question: string;
  options: LangMediaOption[]; answer_id: string };
export type LangStoryRun = { text: string; word_id?: string; target?: string;
  roman?: string; en?: string };
export type LangStoryPage = { page_number: number; title: string; text: string;
  translation_en: string; runs: LangStoryRun[] };
export type LangWordExplanation = { found: boolean; word_id: string; target: string;
  roman?: string; meaning: string; category: string; explanation: string;
  pronunciation_tip: string; examples: { page: number; target: string; en: string }[] };
export type LangMusicVideoSection = {
  id: string; section_no: number; start_sec: number; end_sec: number; duration_sec: number;
  target: string; roman?: string; tts_text?: string; prompt: string;
  en?: string; explain_en?: string; paraphrases_en?: string[];
};
export type LangExercise = { skill: string; language: string; items?: LangItem[];
  pairs?: { id: string; term: string; match: string }[]; target?: string; roman?: string;
  en?: string; mouth_tip?: string; tip?: string; note?: string;
  dialogues?: LangDialogue[]; entries?: LangSlang[]; songs?: LangSong[];
  title?: string; title_target?: string; instructions?: string; media_type?: string;
  media_url?: string; license?: string; source_url?: string; source_note?: string;
  study_words?: LangMediaOption[]; segments?: LangMediaSegment[];
  story_id?: string; page_count?: number; pages?: LangStoryPage[];
  video_id?: string; sections?: LangMusicVideoSection[] };
export type Pronounce = { score: number; stars: number; passed: boolean; target: string;
  heard: string; missed_words: string[]; feedback: string; mouth_tip: string };
export type MusicVideoScore = {
  score: number; stars: number; passed: boolean; point: number;
  translation: string; reference_en: string; explain_en: string;
  best_match: string; retrieved: string[]; coverage: number; similarity: number;
  feedback: string; section_id: string; video_id: string; section_no?: number;
};

export async function getLearnLanguages(): Promise<{ languages: LangInfo[]; count: number }> {
  return jsonOrThrow(await fetch(`${SPEECH_URL}/learn/languages`, { cache: "no-store" }));
}

export type CatalogVoice = {
  id: string; label: string; language: string; locale: string;
  accent: string; gender: string; dialect: string;
};
export type VoiceGroup = { language: string; voices: CatalogVoice[] };
export async function getTtsVoices(): Promise<{ groups: VoiceGroup[] }> {
  return jsonOrThrow(await fetch(`${SPEECH_URL}/tts/voices`, { cache: "no-store" }));
}

export type Instructor = {
  id: string; label: string; emoji: string; description: string;
  voice_style: string; tone_hint: string;
};
export async function getTtsInstructors(): Promise<{ instructors: Instructor[] }> {
  return jsonOrThrow(await fetch(`${SPEECH_URL}/tts/instructors`, { cache: "no-store" }));
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
export async function explainLangWord(language: string, wordId: string): Promise<LangWordExplanation> {
  return jsonOrThrow(
    await fetch(`${SPEECH_URL}/learn/explain-word`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ language, word_id: wordId }),
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
export async function scoreMusicVideoTranslation(
  language: string, videoId: string, sectionId: string, translation: string,
): Promise<MusicVideoScore> {
  return jsonOrThrow(
    await fetch(`${SPEECH_URL}/learn/music-video/score`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({
        language, video_id: videoId, section_id: sectionId, translation,
      }),
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
export type SubjectInfo = { id: string; name: string };
export type AgeGroupInfo = { id: string; name: string; range: string };
export type GamesCatalog = {
  subjects: string[];
  subjects_localized?: SubjectInfo[];
  game_types: GameTypeInfo[];
  age_groups: AgeGroupInfo[];
};
export type GameItem = { id: string; prompt: string; options: string[]; kind?: string; meta?: Record<string, unknown> };
export type GameTerm = { id: string; term: string };
export type GameOption = { id: string; text: string };
export type GameRound = {
  game_id: string; subject: string; game_type: string; time_limit_s: number;
  age_group?: string;
  items?: GameItem[]; terms?: GameTerm[]; options?: GameOption[];
  versus?: string; ai_skill?: number; ai_name?: string;
};
export type GameItemResult = { id: string; correct: boolean; answer_index?: number; explain: string };
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
export type Leader = { rank: number; name: string; score: number; game_points: number; games_played: number };

export async function getGamesCatalog(locale = "en"): Promise<GamesCatalog> {
  const q = locale ? `?locale=${encodeURIComponent(locale)}` : "";
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/games${q}`, { cache: "no-store" }));
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
  id: string; name: string; kind: string; kind_label?: string;
  cost_points: number; detail: Record<string, unknown>;
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
  // "teach" (normal) or "say_aloud" (repeat-after-me checkpoint). When
  // say_aloud is set, the player pauses to listen to and score the learner.
  kind?: string;
  say_aloud?: string;
};

export type Lesson = {
  lesson_id: string;
  title: string;
  language: string;
  audience?: string;
  // Optional catalog metadata for programme cards (Corporate training).
  track?: string;
  level?: string;
  role?: string;
  delivery?: string;
  fit?: string;
  summary?: string;
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

// Re-engagement beat: the Director's REENGAGING action rendered as a short,
// slide-grounded recap plus a low-stakes prompt to pull a drifting learner back
// in. Returned by POST /api/sessions/{id}/reengage.
export type Reengagement = {
  text: string;
  prompt?: string | null;
  citations: string[];
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

// Use a timestamp-based approach to detect truly invalid tokens (as opposed to
// concurrent 401s from a pod restart, which would falsely clear a valid token
// when multiple in-flight requests race to see a 401).
let _lastSuccessfulAuthTime = 0;
let _pendingAuthClear = false;
// Track 401s per session — only clear the token after 2 consecutive rejections
// to avoid clearing a valid token on a transient network error or pod restart.
let _consecutive401s = 0;

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    if (res.status === 401 && getToken()) {
      // Only schedule a token clear once. A concurrent 401 burst (e.g. from a
      // pod restart) won't fire a second clear — only a sustained absence of
      // successful calls will actually clear the token.
      if (!_pendingAuthClear) {
        _pendingAuthClear = true;
        setTimeout(() => {
          // If still no successful auth after 3 seconds, the token is truly invalid
          if (getToken() && Date.now() - _lastSuccessfulAuthTime > 3000) {
            clearToken();
          }
          _pendingAuthClear = false;
        }, 3000);
      }
      _consecutive401s += 1;
      if (_consecutive401s >= 2) {
        // Two consecutive 401s with a stored token means the token is genuinely
        // invalid (expired, signing key rotated). Clear it to return to sign-in.
        clearToken();
        _consecutive401s = 0;
      }
    } else if (res.ok) {
      _consecutive401s = 0;
    }
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
  _lastSuccessfulAuthTime = Date.now();
  _pendingAuthClear = false;
  _consecutive401s = 0;  // successful call resets the counter
  return (await res.json()) as T;
}

export async function listLessons(): Promise<Lesson[]> {
  return jsonOrThrow(await fetch(`${ORCHESTRATOR_URL}/api/lessons`, { cache: "no-store" }));
}

export type LessonAccreditation = {
  lesson_id: string;
  certifiable: boolean;
  requires_registered_account: boolean;
  certification_body: string;
  ceu_credits: number;
};

/** Whether a lesson awards accreditation and requires a registered account (HARD RULE). */
export async function getLessonAccreditation(
  lessonId: string
): Promise<LessonAccreditation> {
  return jsonOrThrow(
    await fetch(
      `${ORCHESTRATOR_URL}/api/lessons/${encodeURIComponent(lessonId)}/accreditation`,
      { cache: "no-store" }
    )
  );
}

export async function startSession(
  lessonId: string,
  classType: string,
  studentId?: string
): Promise<SessionView> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/sessions`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        lesson_id: lessonId,
        class_type: classType,
        student_id: studentId ?? null,
      }),
    })
  );
}

// --- adaptive quiz + grade (per-student difficulty) ---------------------- //
export type QuizItemView = {
  item_id: string;
  topic: string;
  prompt: string;
  options: string[];
  answer_index: number;
  difficulty: string;
};

export type QuizGrade = {
  item_id: string;
  correct: boolean;
  mastery_target: number;
  difficulty: string;
};

// Fetch an adaptive quiz. When studentId is set, the orchestrator picks
// difficulty from this learner's mastery signals (memory service); otherwise it
// stays MEDIUM. Pass topic == lessonId so quiz/grade and the live loop's
// slide/question signals aggregate under the same key.
export async function getQuiz(args: {
  topic: string;
  passages: string[];
  studentId?: string;
  classType?: string;
  maxItems?: number;
}): Promise<{ items: QuizItemView[] }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/assessment/quiz`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        topic: args.topic,
        passages: args.passages,
        max_items: args.maxItems ?? 3,
        student_id: args.studentId ?? null,
        class_type: args.classType ?? "group",
      }),
    })
  );
}

// Grade an answered item. When studentId + topic are set, the outcome updates
// this learner's mastery (BKT) so the NEXT quiz adapts its difficulty.
export async function gradeQuiz(args: {
  item: QuizItemView;
  chosenIndex: number;
  studentId?: string;
  topic?: string;
}): Promise<QuizGrade> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/assessment/grade`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        item_id: args.item.item_id,
        options: args.item.options,
        answer_index: args.item.answer_index,
        chosen_index: args.chosenIndex,
        difficulty: args.item.difficulty,
        topic: args.topic ?? args.item.topic,
        student_id: args.studentId ?? null,
      }),
    })
  );
}

// --- policy checkpoints (server-held keys + profile format shells) -------- //
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
  presentation_format: "text" | "audio" | "video_aid" | "game" | string;
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

export async function getAssessmentPolicy(sessionId: string): Promise<AssessmentPolicy> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/assessment/policy/${encodeURIComponent(sessionId)}`, {
      cache: "no-store",
    }),
  );
}

export async function startAssessmentCheckpoint(args: {
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
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/assessment/checkpoints/start`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
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
    }),
  );
}

export async function submitAssessmentCheckpoint(
  runId: string,
  chosenIndices: number[],
): Promise<AssessmentSubmitResult> {
  return jsonOrThrow(
    await fetch(
      `${ORCHESTRATOR_URL}/assessment/checkpoints/${encodeURIComponent(runId)}/submit`,
      {
        method: "POST",
        headers: { "content-type": "application/json", ...authHeaders() },
        body: JSON.stringify({ chosen_indices: chosenIndices }),
      },
    ),
  );
}

export async function recordAssessmentAttempt(
  studentId: string,
  attemptToken: string,
): Promise<{ student_id: string; attempt_id: string; recorded: boolean; attempt_count: number }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students/${encodeURIComponent(studentId)}/assessment-attempt`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ attempt_token: attemptToken }),
    }),
  );
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
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students/${encodeURIComponent(studentId)}/assessment-pass`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ decision_token: decisionToken }),
    }),
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
  room_size?: number;
  learner_capacity?: number;
  live_room_id?: string;
  marketplace_listing?: boolean;
  audit_required?: boolean;
  audit_status?: string;
  instructor_name?: string;
  instructor_account_id?: string;
  created_by_account_id?: string;
  price_per_user_usd?: number;
  commission_rate?: number;
  payment_required?: boolean;
  attendee_code_required?: boolean;
  presentation_filename?: string;
  host_checked_in_at?: string;
  practice_session?: boolean;
  host_payout_usd?: number;
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

export type ScheduleGroupClassInput = {
  title: string;
  lesson_id: string;
  start_time: string;
  platform?: string;
  meeting_url?: string;
  duration_min?: number;
  host?: string;
  capacity?: number;
  room_size?: number;
  language?: string;
  description?: string;
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
  is_student_session?: boolean;
  presentation_filename?: string;
  max_faces_allowed?: number;
  require_liveness?: boolean;
  recording_protection_required?: boolean;
  device_profile?: string;
  camera_ingest_mode?: string;
  camera_sources?: Array<Record<string, unknown>>;
};

export async function uploadHostPresentation(
  file: File,
  opts?: { title?: string; language?: string },
): Promise<{ lesson_id: string; title: string; slide_count: number; presentation_filename: string }> {
  const body = new FormData();
  body.append("file", file);
  if (opts?.title) body.append("title", opts.title);
  if (opts?.language) body.append("language", opts.language);
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/upload-presentation`, {
      method: "POST",
      headers: authHeaders(),
      body,
    }),
  );
}

export type GroupClassStart = {
  class: GroupClass;
  session: SessionView;
  bridge: {
    needs_bridge: boolean;
    platform: string;
    livekit_room: string;
    live_room_id?: string;
    join_path?: string;
    room_size?: number;
    meeting_ref?: string;
    join_url?: string;
    connect_endpoint?: string;
    note?: string;
    livekit?: { room: string; token: string; url: string };
    moderator_key?: string;
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
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    })
  );
}

export async function registerGroupClass(
  classId: string,
  name: string,
  email = "",
  opts?: { attendeeCode?: string; checkoutSessionId?: string; paymentStatus?: string },
): Promise<GroupClass> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/register`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        name,
        email,
        attendee_code: opts?.attendeeCode || "",
        checkout_session_id: opts?.checkoutSessionId || "",
        payment_status: opts?.paymentStatus || "unpaid",
      }),
    })
  );
}

export async function checkoutGroupClass(
  classId: string,
  name: string,
  email = "",
  opts?: { payment_method?: string; voucher_code?: string },
): Promise<{ checkout: { session_id: string; url: string; provider: string; method: string; payment_status: string; voucher_description?: string }; registration?: Record<string, unknown>; free?: boolean }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/checkout`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ name, email, payment_method: opts?.payment_method ?? "card", voucher_code: opts?.voucher_code ?? "" }),
    })
  );
}

export type VoucherValidateResult = {
  valid: boolean;
  code?: string;
  kind?: string;
  description?: string;
  original_price?: number;
  final_price?: number;
  savings?: number;
  error?: string;
};

export async function validateVoucher(
  code: string,
  priceUsd: number,
  classId: string,
): Promise<VoucherValidateResult> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/vouchers/validate`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ code, price_usd: priceUsd, class_id: classId }),
    })
  );
}

export async function confirmGroupClassPayment(
  classId: string,
  checkoutSessionId: string,
): Promise<{ class: GroupClass; attendee_code: string; payment_status: string }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/confirm-payment`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ checkout_session_id: checkoutSessionId }),
    })
  );
}

export async function reviewGroupClass(
  classId: string,
  rating: number,
  comment = "",
): Promise<{ class: GroupClass; review: { reviewer_name: string; rating: number; comment: string; created_at: string } }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/review`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ rating, comment }),
    })
  );
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
}): Promise<GroupClass> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/teach-request`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    })
  );
}

export async function auditGroupClass(
  classId: string,
  approved: boolean,
  interviewNotes = "",
  demoNotes = "",
): Promise<GroupClass> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/audit`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ approved, interview_notes: interviewNotes, demo_notes: demoNotes }),
    })
  );
}

export async function updateGroupClassCameraSources(
  classId: string,
  input: {
    device_profile?: string;
    camera_ingest_mode?: string;
    camera_sources: Array<Record<string, unknown>>;
  },
): Promise<GroupClass> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/camera-sources`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    })
  );
}

export function groupClassCalendarUrl(classId: string, name = "", email = ""): string {
  const qs = new URLSearchParams();
  if (name) qs.set("name", name);
  if (email) qs.set("email", email);
  const suffix = qs.toString();
  return `${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/calendar.ics${suffix ? `?${suffix}` : ""}`;
}

export async function startGroupClass(classId: string): Promise<GroupClassStart> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/group-classes/${encodeURIComponent(classId)}/start`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
    })
  );
}

// --- Salareen live room (built-in multi-user grid) --- //
export type LiveParticipant = {
  id: string;
  name: string;
  role: string;
  identity: string;
  muted: boolean;
  muted_by_host: boolean;
  hand_raised: boolean;
  can_publish: boolean;
  language?: string;
  joined_at: string;
  is_admin?: boolean;
  /** Moderator/admin-only learner profile fields. */
  student_id?: string;
  readiness_score?: number;
  readiness_band?: string;
  primary_style?: string;
};

export type LiveRoomChatMessage = {
  id: string;
  from_id: string;
  from_name: string;
  text: string;
  sent_at: string;
};

export type LiveRoomState = {
  room_id: string;
  class_id: string;
  session_id: string;
  lesson_id: string;
  title: string;
  room_size: number;
  learner_capacity: number;
  learner_count: number;
  seats_left: number;
  status: string;
  host: LiveParticipant;
  /** True when a person teaches this class, so there is no Theodore in the room. */
  human_taught?: boolean;
  human_host_name?: string;
  participants: LiveParticipant[];
  chat: LiveRoomChatMessage[];
  recording: { status: string; started_at?: string; stopped_at?: string; recording_id?: string; note?: string };
  slide: { index: number; title: string; body: string; narration: string };
  raised_hands: LiveParticipant[];
  banned?: { identity: string; name: string; reason: string; banned_at: string; banned_by: string }[];
  speaking_queue?: {
    id: string;
    participant_id: string;
    name: string;
    question: string;
    status: string;
    position: number;
    enqueued_at: string;
  }[];
  floor_participant_id?: string;
  floor_holder?: LiveParticipant | null;
  reports?: {
    id: string;
    reporter_participant_id: string;
    reporter_name: string;
    reported_participant_id: string;
    reported_name: string;
    reported_identity: string;
    category: string;
    reason: string;
    status: string;
    reported_at: string;
  }[];
  gift_feed?: {
    id: string;
    gift_id: string;
    gift_name: string;
    emoji: string;
    cost_points: number;
    sender_name: string;
    recipient_name: string;
    sent_at: string;
  }[];
  reactions?: { id: string; emoji: string; participant_name: string; sent_at: string }[];
  viewer_count?: number;
  admin_participant_id?: string;
  presenting?: boolean;
  scheduled_start?: string;
  duration_seconds?: number;
  ended_at?: string;
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
  presence_policy?: {
    enabled: boolean;
    grace_seconds: number;
    stale_seconds: number;
    require_liveness: boolean;
    max_faces_allowed: number;
  };
  presence?: {
    hold_active: boolean;
    hold_participant_id: string;
    hold_participant_name: string;
    hold_reason: string;
    hold_started_at: string;
    signals: {
      participant_id: string;
      participant_name: string;
      present: boolean;
      face_count: number;
      liveness_state: string;
      liveness_score: number;
      reason: string;
      source: string;
      observed_at: string;
      absent_started_at: string;
      last_live_at: string;
      hold_started_at: string;
      updated_at: string;
      verified_live?: boolean;
      hold_reason?: string;
    }[];
  };
  group_game?: LiveGroupGame | null;
};

export type LiveGiftCatalogItem = {
  id: string;
  name: string;
  emoji: string;
  cost_points: number;
};

export type LiveRoomJoin = {
  participant: LiveParticipant;
  room: LiveRoomState;
  media: { room: string; identity: string; token: string; url: string };
  gift_balance?: number;
  host_follower_count?: number;
  following_host?: boolean;
  is_admin?: boolean;
  moderator_key?: string;
};

export async function getLiveRoom(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  const q = moderatorKey
    ? `?moderator_key=${encodeURIComponent(moderatorKey)}`
    : "";
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}${q}`, {
      cache: "no-store",
      headers: authHeaders(),
    })
  );
}

/** Open a private 1:1 (AI + you) Salareen live room for a lesson and return its
 * id. Reuses the group-class live-room UI, just sized for two seats. */
export async function startSoloLiveRoom(lessonId: string, creatorName = ""): Promise<{ room_id: string }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/solo`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ lesson_id: lessonId, creator_name: creatorName }),
    })
  );
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
): Promise<LiveRoomJoin> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/join`, {
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
    })
  );
}

export async function leaveLiveRoom(roomId: string, participantId: string): Promise<LiveRoomState> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/leave`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId }),
    })
  );
}

export async function liveRoomChat(roomId: string, participantId: string, text: string): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, text }),
    })
  );
  return r.room;
}

export async function liveRoomRaiseHand(
  roomId: string,
  participantId: string,
  question = ""
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/raise-hand`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, question }),
    })
  );
  return r.room;
}

export async function liveRoomJoinQueue(
  roomId: string,
  participantId: string,
  question = ""
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/queue/join`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, question }),
    })
  );
  return r.room;
}

export async function liveRoomLeaveQueue(roomId: string, participantId: string): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/queue/leave`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId }),
    })
  );
  return r.room;
}

export async function liveRoomCallNext(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/queue/call-next`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ moderator_key: moderatorKey }),
    })
  );
  return r.room;
}

export type LiveKitMediaToken = {
  media: { room: string; identity: string; token: string; url: string };
  can_publish: boolean;
};

/** Fetch a fresh LiveKit token reflecting the participant's CURRENT publish
 * right (used to (re)gain publishing when granted the floor — the hard mutex). */
export async function liveRoomMediaToken(
  roomId: string,
  participantId: string,
): Promise<LiveKitMediaToken> {
  return jsonOrThrow<LiveKitMediaToken>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/media-token`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId }),
    })
  );
}

export async function liveRoomCallOn(
  roomId: string,
  participantId: string,
  moderatorKey = ""
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/queue/call-on`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ participant_id: participantId, moderator_key: moderatorKey }),
    })
  );
  return r.room;
}

export async function liveRoomFinishTurn(
  roomId: string,
  participantId: string,
  moderatorKey = ""
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/queue/finish-turn`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ participant_id: participantId, moderator_key: moderatorKey }),
    })
  );
  return r.room;
}

export async function liveRoomMute(
  roomId: string,
  participantId: string,
  muted: boolean,
  byHost = false,
  moderatorKey = "",
  // Who is performing the mute. For a self-mute this is the participant
  // themselves; the server rejects a learner muting a *different* participant.
  actorId = participantId
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/mute`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        participant_id: participantId,
        muted,
        by_host: byHost,
        moderator_key: moderatorKey,
        actor_id: actorId,
      }),
    })
  );
  return r.room;
}

export async function liveRoomBan(
  roomId: string,
  participantId: string,
  reason = "",
  moderatorKey = ""
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/ban`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        participant_id: participantId,
        reason,
        moderator_key: moderatorKey,
      }),
    })
  );
  return r.room;
}

export async function liveRoomUnban(
  roomId: string,
  identity: string,
  moderatorKey = ""
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/unban`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ identity, moderator_key: moderatorKey }),
    })
  );
  return r.room;
}

export async function liveRoomReport(
  roomId: string,
  reporterParticipantId: string,
  reportedParticipantId: string,
  reason: string,
  category = "other"
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/report`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        reporter_participant_id: reporterParticipantId,
        reported_participant_id: reportedParticipantId,
        reason,
        category,
      }),
    })
  );
  return r.room;
}

export async function liveRoomDismissReport(
  roomId: string,
  reportId: string,
  moderatorKey = ""
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(
      `${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/reports/dismiss`,
      {
        method: "POST",
        headers: { "content-type": "application/json", ...authHeaders() },
        body: JSON.stringify({ report_id: reportId, moderator_key: moderatorKey }),
      }
    )
  );
  return r.room;
}

export async function liveRoomAdvance(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/advance`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ moderator_key: moderatorKey }),
    })
  );
  return r.room;
}

export async function liveRoomStartPresentation(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/start-presentation`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ moderator_key: moderatorKey }),
    })
  );
  return r.room;
}

/** Close a live session (status=ended). Moderator-key holder or platform admin. */
export async function liveRoomEnd(roomId: string, moderatorKey = ""): Promise<LiveRoomState> {
  return jsonOrThrow<LiveRoomState>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/end`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ moderator_key: moderatorKey }),
    })
  );
}

/** Delete a live session entirely (platform admin only — admin@salareen.com). */
export async function deleteLiveRoom(roomId: string): Promise<{ deleted: boolean; room_id: string }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}`, {
      method: "DELETE",
      headers: { "content-type": "application/json", ...authHeaders() },
    })
  );
}

/** Heartbeat the room clock + presence (auto-start/advance/end, and prune
 * learners who closed the tab without leaving). Pass the caller's participantId
 * so their presence stays fresh; any client can call this on a timer. */
export async function liveRoomTick(
  roomId: string,
  participantId = "",
  moderatorKey = "",
): Promise<LiveRoomState> {
  const qs = new URLSearchParams();
  if (participantId) qs.set("pid", participantId);
  if (moderatorKey) qs.set("moderator_key", moderatorKey);
  const query = qs.toString();
  const q = query ? `?${query}` : "";
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/tick${q}`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
    })
  );
  return r.room;
}

export async function reportLiveRoomPresence(
  roomId: string,
  payload: {
    participantId: string;
    present: boolean;
    faceCount?: number;
    livenessState?: "live" | "unknown" | "spoof" | "absent";
    livenessScore?: number;
    reason?: string;
    source?: string;
    observedAt?: string;
  }
): Promise<{ room: LiveRoomState; presence: Record<string, unknown> }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/presence-report`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        participant_id: payload.participantId,
        present: payload.present,
        face_count: payload.faceCount || 0,
        liveness_state: payload.livenessState || "unknown",
        liveness_score: payload.livenessScore || 0,
        reason: payload.reason || "",
        source: payload.source || "web-on-device",
        observed_at: payload.observedAt || "",
      }),
    })
  );
}

export async function liveRoomAsk(
  roomId: string,
  participantId: string,
  question: string,
  language = ""
): Promise<{ room: LiveRoomState; queued: boolean; queue_position?: number }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, question, language }),
    })
  );
}

// Streaming variant of liveRoomAsk: the group-class AI host (Theodore) answers
// via SSE so the asker sees/hears the reply build token-by-token. onDelta fires
// per chunk; resolves with the final { room, host answer } (or a queued result).
// Every other participant also receives the answer live via the room WebSocket
// (host_delta frames). Falls back to the blocking /ask on any transport error.
export type LiveRoomAskStreamResult = {
  queued: boolean;
  queue_position?: number;
  room?: LiveRoomState;
  text?: string;
  host_message?: { text?: string } | null;
  awaitingConfirmation?: boolean;
};

export async function liveRoomAskStream(
  roomId: string,
  participantId: string,
  question: string,
  opts: { language?: string; onDelta?: (chunk: string) => void } = {},
): Promise<LiveRoomAskStreamResult> {
  const resp = await fetch(
    `${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/ask-stream`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, question, language: opts.language ?? "" }),
    },
  );
  if (!resp.ok || !resp.body) {
    // Transport/endpoint unavailable -> blocking fallback so Q&A still works.
    const r = await liveRoomAsk(roomId, participantId, question, opts.language ?? "");
    return { queued: r.queued, queue_position: r.queue_position, room: r.room };
  }
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let result: LiveRoomAskStreamResult = { queued: false };
  for (;;) {
    const { value, done: fin } = await reader.read();
    if (fin) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      let ev: { type?: string; text?: string; [k: string]: unknown };
      try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
      if (ev.type === "delta" && ev.text) {
        opts.onDelta?.(ev.text);
      } else if (ev.type === "queued") {
        result = {
          queued: true,
          queue_position: (ev.queue_position as number) ?? 0,
          room: ev.room as LiveRoomState | undefined,
        };
      } else if (ev.type === "awaiting_confirmation") {
        result = { ...result, awaitingConfirmation: true };
      } else if (ev.type === "done") {
        result = {
          ...result,               // preserve awaitingConfirmation set by the preceding event
          queued: false,
          room: ev.room as LiveRoomState | undefined,
          text: (ev.text as string) ?? "",
          host_message: (ev.host_message as { text?: string } | null) ?? null,
        };
      }
    }
  }
  return result;
}

export async function liveRoomRecordStart(roomId: string): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/record/start`, {
      method: "POST",
      headers: { "content-type": "application/json" },
    })
  );
  return r.room;
}

export async function liveRoomRecordStop(roomId: string): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/record/stop`, {
      method: "POST",
      headers: { "content-type": "application/json" },
    })
  );
  return r.room;
}

export async function getLiveGiftCatalog(): Promise<{ gifts: LiveGiftCatalogItem[] }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/gifts/catalog`, { cache: "no-store" })
  );
}

export async function liveRoomSendGift(
  roomId: string,
  participantId: string,
  giftId: string,
  recipientParticipantId = "",
): Promise<{ room: LiveRoomState; gift: LiveRoomState["gift_feed"] extends (infer T)[] | undefined ? T : never; sender_balance: number }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/gifts/send`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        participant_id: participantId,
        gift_id: giftId,
        recipient_participant_id: recipientParticipantId,
      }),
    })
  );
}

export type LiveGroupGameType =
  | "quiz_race" | "tic_tac_toe" | "hangman" | "multiple_choice"
  | "true_false" | "word_scramble" | "fill_blank" | "emoji_decode"
  | "lightning_round" | "team_buzzer" | "hot_seat" | "jeopardy";

export type LiveGroupGame = {
  id: string;
  type: LiveGroupGameType;
  prompt: string;
  points: number;
  status: string;
  winner_name?: string;
  board?: string[];
  turn?: string;
  masked?: string;
  wrong?: number;
  max_wrong?: number;
  scrambled?: string;
};

export type LiveGroupGameCatalogItem = {
  id: LiveGroupGameType; name: string; icon: string; description: string;
};

export async function liveRoomGameCatalog(): Promise<LiveGroupGameCatalogItem[]> {
  const data = await jsonOrThrow<{ games: LiveGroupGameCatalogItem[] }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/games/catalog`, {
      headers: authHeaders(),
    }),
  );
  return data.games;
}

export async function liveRoomStartGame(
  roomId: string,
  moderatorKey: string,
  gameType: LiveGroupGame["type"],
  prompt: string,
  answer: string,
  points = 25,
): Promise<{ room: LiveRoomState; game: LiveGroupGame }> {
  return jsonOrThrow(await fetch(
    `${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/games/start`,
    {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        moderator_key: moderatorKey, game_type: gameType, prompt, answer, points,
      }),
    },
  ));
}

export async function liveRoomPlayGame(
  roomId: string,
  participantId: string,
  action: { answer?: string; cell?: number; letter?: string },
): Promise<{ room: LiveRoomState; game: LiveGroupGame; event: { correct: boolean; points: number } }> {
  return jsonOrThrow(await fetch(
    `${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/games/action`,
    {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ participant_id: participantId, ...action }),
    },
  ));
}

export async function liveRoomReaction(
  roomId: string,
  participantId: string,
  emoji: string,
): Promise<LiveRoomState> {
  const r = await jsonOrThrow<{ room: LiveRoomState }>(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/reactions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ participant_id: participantId, emoji }),
    })
  );
  return r.room;
}

export async function liveRoomFollowHost(
  roomId: string,
  identity: string,
  unfollow = false,
): Promise<{ following: boolean; follower_count: number }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/follow`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ identity, unfollow }),
    })
  );
}

export async function liveRoomFollowStatus(
  roomId: string,
  identity: string,
): Promise<{ following: boolean; follower_count: number }> {
  return jsonOrThrow(
    await fetch(
      `${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}/follow?identity=${encodeURIComponent(identity)}`,
      { cache: "no-store" },
    )
  );
}

export function liveRoomWsUrl(roomId: string): string {
  const base = ORCHESTRATOR_URL.replace(/\/$/, "");
  const path = `/api/live-rooms/${encodeURIComponent(roomId)}/ws`;
  if (/^https?:\/\//.test(base)) {
    return `${base.startsWith("https") ? "wss" : "ws"}://${base.replace(/^https?:\/\//, "")}${path}`;
  }
  // Relative same-origin prefix (e.g. "/orchestrator"): resolve against the page
  // origin so we don't dial ws://orchestrator/... (which fails).
  const proto = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss" : "ws";
  const host = typeof window !== "undefined" ? window.location.host : "";
  const prefix = base ? (base.startsWith("/") ? base : `/${base}`) : "";
  return `${proto}://${host}${prefix}${path}`;
}

export async function advance(sessionId: string): Promise<Slide> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/sessions/${sessionId}/advance`, {
      method: "POST",
    })
  );
}

// Ask the teaching brain to re-engage a drifting learner: a recap of the current
// slide plus a quick prompt. Surfaced as the "I'm lost — refocus" action.
export async function reengage(sessionId: string): Promise<Reengagement> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/sessions/${sessionId}/reengage`, {
      method: "POST",
    })
  );
}

export type ClassQuizItem = {
  item_id: string;
  prompt: string;
  options: string[];
  answer_index: number;
  difficulty?: string;
  topic?: string;
};

export async function generateClassQuiz(topic: string, passages: string[], maxItems = 3): Promise<{
  items: ClassQuizItem[];
}> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/assessment/quiz`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ topic, passages, max_items: maxItems }),
    })
  );
}

export async function gradeQuizItem(
  item: ClassQuizItem,
  chosenIndex: number,
): Promise<{ correct: boolean; mastery_target: number }> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/assessment/grade`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        item_id: item.item_id,
        options: item.options,
        answer_index: item.answer_index,
        chosen_index: chosenIndex,
        difficulty: item.difficulty ?? "medium",
        topic: item.topic ?? "",
      }),
    })
  );
}

export async function recordBehavior(event: {
  student_id: string;
  topic: string;
  quiz_correct?: boolean | null;
  response_latency_s?: number | null;
  attention?: number | null;
  asked_question?: boolean;
  saw_slide?: boolean;
}): Promise<{ recorded: boolean }> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/behavior`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(event),
    })
  );
}

export async function updateTopicMastery(
  studentId: string, topic: string, correct: boolean,
): Promise<{ mastery: number }> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/mastery`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ student_id: studentId, topic, correct }),
    })
  );
}

export type LxTickResult = {
  lx_score: number;
  lx_components: Record<string, number>;
  lx_target: number;
  teaching_strategy: string;
  improve_actions: string[];
  pacing: string;
  difficulty: string;
  reteach: boolean;
  reasons: string[];
};

export async function directorLxTick(body: Record<string, unknown>): Promise<LxTickResult> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/director/lx-tick`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    })
  );
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
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students/${encodeURIComponent(studentId)}/learning-experience`, {
      headers: authHeaders(), cache: "no-store",
    })
  );
}

export async function getStudentAdaptation(studentId: string): Promise<{
  adaptation: Record<string, unknown>;
  learning_pace: string;
}> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students/${encodeURIComponent(studentId)}/adaptation`, {
      headers: authHeaders(), cache: "no-store",
    })
  );
}

export async function recordAdaptationEvent(
  studentId: string, eventType: string, payload: Record<string, unknown>,
): Promise<{ adaptation: Record<string, unknown> }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students/${encodeURIComponent(studentId)}/adaptation`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ event_type: eventType, payload }),
    })
  );
}

export async function recordWellnessCheckIn(
  studentId: string, state: string, reason = "",
): Promise<{ adaptation: Record<string, unknown> }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/students/${encodeURIComponent(studentId)}/wellness`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ state, reason }),
    })
  );
}

export async function getPulseSurvey(
  subject?: string, tier?: string
): Promise<{ enabled: boolean; template: SurveyTemplate | null }> {
  const qs = new URLSearchParams();
  if (subject) qs.set("subject", subject);
  if (tier) qs.set("tier", tier);
  return jsonOrThrow(await fetch(`${MEMORY_URL}/survey/pulse?${qs.toString()}`, { cache: "no-store" }));
}

export async function submitPulseSurvey(payload: {
  course_id: string;
  going_well: number;
  pace: string;
  class_type?: string;
  student_id?: string | null;
  slide_index?: number;
  teaching_strategy?: string;
  working_best?: string | null;
}): Promise<{ id: string; recorded: boolean }> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/survey/pulse`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
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
    await fetch("/api/admin/flags", {
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
    await fetch(`/api/admin/flags/${encodeURIComponent(key)}`, {
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
  interval_slides?: number;
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

export type BugScreenshotUpload = {
  filename: string;
  content_type: string;
  data_base64: string;
};

export type BugReportRow = {
  id: string;
  created_at: number;
  description: string;
  category: string;
  screen: string;
  platform: string;
  app_version: string;
  user_id: string;
  email: string;
  snapshot: Record<string, unknown>;
  logs: string[];
  attachments: string[];
  destination?: string;
  external_url?: string;
  private_issue_url?: string;
  public_issue_url?: string;
  delivery_error?: string;
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
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/bugs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function adminListBugReports(
  secret: string,
  limit = 50,
): Promise<{ count: number; reports: BugReportRow[] }> {
  return jsonOrThrow(
    await fetch(`${MEMORY_URL}/admin/bugs?limit=${limit}`, {
      cache: "no-store",
      headers: { "X-Admin-Secret": secret },
    }),
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

// Homework endpoints are operator-only (internal token, server-side). We call
// them through the same-origin BFF at /api/homework/* which verifies the caller
// is an admin and injects the internal token; the browser never holds it.
const HOMEWORK_BFF = "/api/homework";

export async function gradeReviews(status?: string): Promise<{ autonomy: string; items: ReviewItem[] }> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return jsonOrThrow(await fetch(`${HOMEWORK_BFF}/grade-reviews${q}`, {
    headers: { ...authHeaders() }, cache: "no-store",
  }));
}

export async function gradeReviewDecide(
  itemId: string,
  action: string,
  editedPayload?: Record<string, unknown>
): Promise<ReviewItem> {
  return jsonOrThrow(
    await fetch(`${HOMEWORK_BFF}/grade-reviews/${itemId}/decision`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
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
  course_id?: string;
  subject?: string;
}): Promise<HomeworkGrade> {
  return jsonOrThrow(
    await fetch(`${HOMEWORK_BFF}/grade`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(args),
    })
  );
}

export type GeneratedQuestion = {
  question_id: string;
  type: string;
  prompt: string;
  options: string[];
  answer_index: number | null;
  answer_key: string;
  rubric: string[];
};
export type GeneratedAssignment = {
  assignment_id: string;
  title: string;
  subject: string;
  source: string;
  questions: GeneratedQuestion[];
};

export async function generateHomework(args: {
  deck_id?: string;
  course_id?: string;
  content?: string;
  title?: string;
  subject?: string;
  num_questions?: number;
  locale?: string;
}): Promise<GeneratedAssignment> {
  return jsonOrThrow(
    await fetch(`${HOMEWORK_BFF}/generate`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(args),
    })
  );
}

export type ScanResult = { raw_text: string; handwritten: boolean; confidence: number; segments: string[] };

// OCR a typed/handwritten submission file (image or text) into a submission.
export async function scanHomework(file: File, opts: { hint?: string; expected?: number } = {}): Promise<ScanResult> {
  const form = new FormData();
  form.append("file", file);
  if (opts.hint) form.append("hint", opts.hint);
  if (opts.expected != null) form.append("expected", String(opts.expected));
  return jsonOrThrow(
    await fetch(`${HOMEWORK_BFF}/scan`, { method: "POST", headers: { ...authHeaders() }, body: form })
  );
}

export type AuthorshipResult = { label: string; ai_probability: number; signals: Record<string, number>; note: string };

export async function checkAuthorship(text: string, handwritten = false): Promise<AuthorshipResult> {
  return jsonOrThrow(
    await fetch(`${HOMEWORK_BFF}/authorship`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ text, handwritten }),
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

export async function ask(sessionId: string, text: string, language = "en"): Promise<Answer> {
  return jsonOrThrow(
    await fetch(`${ORCHESTRATOR_URL}/api/sessions/${sessionId}/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, language }),
    }),
  );
}

export type AskDone = {
  type: "done"; text: string; citations: string[]; grounded: boolean;
  hallucination_risk: number; understood: string[]; unsupported: string[]; corrected: boolean;
};

// Stream the conversational agent's answer (SSE) for a real-time, low-latency
// voice/chat response. onDelta fires per incremental token chunk; resolves with
// the final guarded answer (or null if the stream produced no done event).
export async function askStream(
  sessionId: string, text: string,
  opts: { language?: string; onDelta?: (chunk: string) => void; onDone?: (d: AskDone) => void } = {},
): Promise<AskDone | null> {
  const resp = await fetch(`${ORCHESTRATOR_URL}/api/sessions/${sessionId}/ask/stream`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text, language: opts.language ?? "en" }),
  });
  if (!resp.ok || !resp.body) throw new Error(`ask stream failed: ${resp.status}`);
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let done: AskDone | null = null;
  for (;;) {
    const { value, done: fin } = await reader.read();
    if (fin) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      let ev: { type?: string; text?: string; [k: string]: unknown };
      try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
      if (ev.type === "delta" && ev.text) opts.onDelta?.(ev.text);
      else if (ev.type === "done") { done = ev as unknown as AskDone; opts.onDone?.(done); }
    }
  }
  return done;
}

// ── Platform presence ────────────────────────────────────────────────────────

export async function presencePing(opts: {
  platform?: "web" | "mobile" | "sdk";
  page?: string;
  activity?: string;
}): Promise<void> {
  const tok = getToken();
  if (!tok) return;
  try {
    await fetch(`${IDENTITY_URL}/presence/ping`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${tok}` },
      body: JSON.stringify({ platform: "web", ...opts }),
    });
  } catch { /* non-critical — ignore network errors */ }
}

export async function getAdminPresence(): Promise<{
  active_count: number;
  by_platform: Record<string, number>;
  by_activity: Record<string, number>;
  users: Array<{ account_id: string; display_name: string; tier: string; platform: string; page: string; activity: string; seen_at: number }>;
  window_seconds: number;
}> {
  const tok = getToken();
  return jsonOrThrow(await fetch(`${IDENTITY_URL}/admin/presence`, {
    headers: tok ? { authorization: `Bearer ${tok}` } : {},
  }));
}

// ── Admin voucher management ────────────────────────────────────────────────

export type VoucherRecord = {
  code: string;
  kind: string;
  value: number;
  max_uses: number;
  uses: number;
  expires_at: number | null;
  class_id: string | null;
  created_at: number;
  note: string;
};

export async function adminListVouchers(): Promise<{ vouchers: VoucherRecord[] }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/vouchers/admin/list`, { headers: authHeaders(), cache: "no-store" })
  );
}

export async function adminCreateVoucher(input: {
  code: string;
  kind: string;
  value: number;
  max_uses: number;
  expires_days?: number | null;
  class_id?: string | null;
  note?: string;
}): Promise<{ created: boolean; voucher: VoucherRecord }> {
  return jsonOrThrow(
    await fetch(`${IDENTITY_URL}/vouchers/admin/create`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    })
  );
}

// -------------------------------------------------------------------------- //
// Webcam Vision Service (presence, silhouette, xAI voice)
// -------------------------------------------------------------------------- //

export type WebcamSessionInfo = {
  session_id: string;
  class_type: string;
  student_ids: string[];
};

export type FrameAnalysis = {
  session_id: string;
  participant_id: string;
  face_present: boolean;
  silhouette_present: boolean;
  silhouette_method: string;
  silhouette_absence_confidence: number;
  largest_silhouette_coverage: number;
  attention: number | null;
  presence_state: "unknown" | "present" | "away" | "absent";
  presence_event: string | null;
  away_duration_s: number;
  consecutive_absent_frames: number;
  frame_count: number;
};

export type PresenceSummary = {
  session_id: string;
  class_type: string;
  solo_status: {
    participant_id: string;
    state: string;
    attention: number;
    away_duration_s: number;
  } | null;
  group_summary: {
    total_participants: number;
    present_count: number;
    away_count: number;
    absent_count: number;
    unknown_count: number;
    quorum_met: boolean;
    average_attention: number;
    present_ratio: number;
    absent_ids: string[];
    away_ids: string[];
  } | null;
  participant_statuses: Array<{
    participant_id: string;
    state: string;
    face_present: boolean;
    silhouette_present: boolean;
    attention: number;
    away_duration_s: number;
    consecutive_absent_frames: number;
  }>;
};

export type VoiceAgentResponse = {
  session_id: string;
  participant_id: string;
  text: string;
  has_audio: boolean;
  audio_b64: string | null;
  model: string;
  fallback: boolean;
};

export async function createWebcamSession(params: {
  class_type?: string;
  student_ids?: string[];
  lesson_context?: string;
}): Promise<WebcamSessionInfo> {
  return jsonOrThrow(
    await fetch(`${WEBCAM_URL}/sessions`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(params),
    })
  );
}

export async function endWebcamSession(sessionId: string): Promise<void> {
  await fetch(`${WEBCAM_URL}/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
}

export async function submitWebcamFrame(
  sessionId: string,
  frameBlob: Blob,
  opts: { participantId?: string; facePresent?: boolean; attention?: number }
): Promise<FrameAnalysis> {
  const form = new FormData();
  form.append("file", frameBlob, "frame.jpg");
  form.append("participant_id", opts.participantId ?? "student");
  form.append("face_present", String(opts.facePresent ?? false));
  form.append("attention", String(opts.attention ?? -1));
  return jsonOrThrow(
    await fetch(`${WEBCAM_URL}/sessions/${encodeURIComponent(sessionId)}/frame`, {
      method: "POST",
      headers: authHeaders(),
      body: form,
    })
  );
}

export async function getWebcamPresence(sessionId: string): Promise<PresenceSummary> {
  return jsonOrThrow(
    await fetch(
      `${WEBCAM_URL}/sessions/${encodeURIComponent(sessionId)}/presence`,
      { headers: authHeaders(), cache: "no-store" }
    )
  );
}

export async function askVoiceAgent(
  sessionId: string,
  params: { text: string; participantId?: string; audio?: boolean; agentType?: string }
): Promise<VoiceAgentResponse> {
  return jsonOrThrow(
    await fetch(`${WEBCAM_URL}/sessions/${encodeURIComponent(sessionId)}/voice`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        participant_id: params.participantId ?? "student",
        text: params.text,
        audio: params.audio ?? false,
        agent_type: params.agentType ?? "teacher",
      }),
    })
  );
}

export function openWebcamWebSocket(
  sessionId: string
): WebSocket {
  const base = WEBCAM_URL.replace(/^https?/, (p) => (p === "https" ? "wss" : "ws"));
  return new WebSocket(`${base}/sessions/${encodeURIComponent(sessionId)}/ws`);
}
