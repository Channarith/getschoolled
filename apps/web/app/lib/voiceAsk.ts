/**
 * Client for POST /api/studio/voice/ask: a grounded text answer for any voice engine, which the page then speaks in the
 * learner's chosen voice. Holds the per-session counters so the cap (6 a minute, 40 a session) also shows as a friendly line.
 */
export const ASK_PER_MINUTE = 6;
export const ASK_PER_SESSION = 40;

export type AskOutcome =
  | { ok: true; answer: string; language: string }
  | { ok: false; reason: "rate" | "session" | "address" | "offline" | "empty"; message: string; retryAfterS?: number };

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
  empty: "I did not catch a question.",
} as const;

export function makeSessionId(): string {
  const bytes = new Uint8Array(12);
  try { crypto.getRandomValues(bytes); } catch { for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256); }
  return `s${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

export async function askLesson(args: {
  sessionId: string;
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
    const res = await f("/api/studio/voice/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: args.sessionId,
        question: question.slice(0, 500),
        lesson_context: args.lessonContext.slice(0, 8000),
        course_title: (args.courseTitle || "").slice(0, 200),
        language: args.language || "en",
      }),
    });
    if (res.status === 429) {
      const body = await res.json().catch(() => ({}));
      const reason = (body?.detail?.reason as string) || "rate";
      const key = reason === "session" ? "session" : "rate";
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
