/**
 * Client for POST /api/studio/voice/ask: a grounded text answer for any voice engine, which the page then speaks in the
 * learner's chosen voice. Holds the per-session counters so the cap (6 a minute, 40 a session) also shows as a friendly line.
 */
export const ASK_PER_MINUTE = 6;
export const ASK_PER_SESSION = 40;

export type AskOutcome =
  | { ok: true; answer: string; language: string }
  | { ok: false; reason: "rate" | "session" | "address" | "busy" | "offline" | "empty"; message: string; retryAfterS?: number };

export class QuestionBudget {
  private stamps: number[] = [];
  private total = 0;
  private readonly now: () => number;
  constructor(now: () => number = () => Date.now()) { this.now = now; }
  check(): "ok" | "rate" | "session" {
    const t = this.now();
    this.stamps = this.stamps.filter((s) => t - s < 60_000);
    if (this.total >= ASK_PER_SESSION) return "session";
    if (this.stamps.length >= ASK_PER_MINUTE) return "rate";
    this.stamps.push(t);
    this.total += 1;
    return "ok";
  }
}

export const LIMIT_MESSAGES = {
  rate: "That is a lot of questions at once. Give me a moment, then ask again.",
  session: "We have covered a lot of questions this session. Let us carry on with the lesson.",
  offline: "I could not reach the tutor just now. Let us carry on, and ask again in a moment.",
  busy: "Sala needs a short break. Let us carry on with the lesson and ask again a little later.",
  empty: "I did not catch a question.",
} as const;

/** The server issues the session (signed, short-lived); a client-made id is refused. One token is cached and renewed on expiry. */
let cached: { token: string; until: number } | null = null;
let inflight: Promise<string | null> | null = null;

export function resetAskSession(): void { cached = null; inflight = null; }

async function sessionToken(f: typeof fetch, force = false): Promise<string | null> {
  if (!force && cached && cached.until > Date.now()) return cached.token;
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const res = await f("/api/studio/voice/session", { method: "POST", credentials: "include" });
      if (!res.ok) return null;
      const body = await res.json();
      const token = String(body?.session || "");
      if (!token) return null;
      cached = { token, until: Date.now() + Math.max(30, Number(body?.expires_in) || 0) * 1000 - 15_000 };
      return token;
    } catch { return null; } finally { inflight = null; }
  })();
  return inflight;
}

export async function askLesson(args: {
  question: string;
  lessonContext: string;
  courseTitle?: string;
  language?: string;
  fetchImpl?: typeof fetch;
}): Promise<AskOutcome> {
  const question = args.question.trim();
  if (!question) return { ok: false, reason: "empty", message: LIMIT_MESSAGES.empty };
  const f = args.fetchImpl || fetch;
  try {
    const send = async (token: string) => f("/api/studio/voice/ask", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: token,
        question: question.slice(0, 500),
        lesson_context: args.lessonContext.slice(0, 8000),
        course_title: (args.courseTitle || "").slice(0, 200),
        language: args.language || "en",
      }),
    });
    let token = await sessionToken(f);
    if (!token) return { ok: false, reason: "offline", message: LIMIT_MESSAGES.offline };
    let res = await send(token);
    if (res.status === 401) {
      token = await sessionToken(f, true);
      if (!token) return { ok: false, reason: "offline", message: LIMIT_MESSAGES.offline };
      res = await send(token);
    }
    if (res.status === 429) {
      const body = await res.json().catch(() => ({}));
      const reason = (body?.detail?.reason as string) || "rate";
      const key = reason === "session" ? "session" : reason === "rate" || reason === "address" ? "rate" : "busy";
      return { ok: false, reason: key, message: LIMIT_MESSAGES[key], retryAfterS: Number(body?.detail?.retry_after_s) || undefined };
    }
    if (!res.ok) return { ok: false, reason: "offline", message: LIMIT_MESSAGES.offline };
    const body = await res.json();
    const answer = String(body?.answer || "").trim();
    if (!answer) return { ok: false, reason: "offline", message: LIMIT_MESSAGES.offline };
    return { ok: true, answer, language: String(body?.language || args.language || "en") };
  } catch {
    return { ok: false, reason: "offline", message: LIMIT_MESSAGES.offline };
  }
}
