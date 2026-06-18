// Client for the orchestrator (Teaching Director) API.
// Base URL is configurable so the SAME UI runs against local or cloud backends.

export const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ?? "http://localhost:8000";

export const CURRICULUM_URL =
  process.env.NEXT_PUBLIC_CURRICULUM_URL ?? "http://localhost:8005";

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
