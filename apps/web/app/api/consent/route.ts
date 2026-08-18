import { NextRequest, NextResponse } from "next/server";

// Server-side BFF for user consent recording (HIGH-16).
// The memory service /consent endpoint requires X-Internal-Token, which the
// browser cannot supply.  This route authenticates the caller as a signed-in
// user, resolves their student_id from /auth/me, and forwards to memory with
// the server-held internal token so the consent is durably stored.

const IDENTITY_ORIGIN = process.env.IDENTITY_ORIGIN || "http://identity:8000";
const MEMORY_ORIGIN = process.env.MEMORY_ORIGIN || "http://memory:8000";
const INTERNAL_TOKEN = process.env.INTERNAL_TOKEN || "dev-internal-token";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const auth = request.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ detail: "authentication required" }, { status: 401 });
  }

  // Verify the user's session and extract their account/student id.
  let studentId: string;
  try {
    const meRes = await fetch(`${IDENTITY_ORIGIN}/auth/me`, {
      headers: { Authorization: auth },
      cache: "no-store",
    });
    if (!meRes.ok) {
      return NextResponse.json({ detail: "invalid or expired session" }, { status: 401 });
    }
    const me = (await meRes.json()) as { id?: string; students?: Record<string, unknown> };
    // Use the account id as the primary student id for consent records.
    studentId = me.id ?? "";
    if (!studentId) {
      return NextResponse.json({ detail: "could not resolve student identity" }, { status: 401 });
    }
  } catch {
    return NextResponse.json({ detail: "identity service unavailable" }, { status: 502 });
  }

  // Forward to memory service, overriding any client-supplied student_id with
  // the verified id from the session token.
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ detail: "invalid request body" }, { status: 400 });
  }
  body = { ...body, student_id: studentId };

  try {
    const memRes = await fetch(`${MEMORY_ORIGIN}/consent`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "X-Internal-Token": INTERNAL_TOKEN,
      },
      body: JSON.stringify(body),
    });
    const data = await memRes.json();
    return NextResponse.json(data, { status: memRes.status });
  } catch {
    return NextResponse.json({ detail: "memory service unavailable" }, { status: 502 });
  }
}
