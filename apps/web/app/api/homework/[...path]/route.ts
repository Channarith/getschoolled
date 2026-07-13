import { NextRequest, NextResponse } from "next/server";

// Server-side proxy for the operator-only homework tool. The curriculum
// /homework/* endpoints are internal-only (they require X-Internal-Token and
// fail closed), so the browser cannot call them directly — it would 403 in any
// auth-enforced deployment. This BFF verifies the caller is a signed-in ADMIN
// (via identity /auth/me, same pattern as the admin flags BFF) and then forwards
// to curriculum with the server-held internal token. Students/guests get 403.

const IDENTITY_ORIGIN = process.env.IDENTITY_ORIGIN || "http://identity:8000";
const CURRICULUM_ORIGIN = process.env.CURRICULUM_ORIGIN || "http://curriculum:8000";
const INTERNAL_TOKEN = process.env.INTERNAL_TOKEN || "dev-internal-token";

async function isOperatorAdmin(request: NextRequest): Promise<boolean> {
  const auth = request.headers.get("authorization");
  if (!auth) return false;
  try {
    const r = await fetch(`${IDENTITY_ORIGIN}/auth/me`, {
      headers: { Authorization: auth },
      cache: "no-store",
    });
    if (!r.ok) return false;
    const me = (await r.json()) as { is_admin?: boolean };
    return Boolean(me.is_admin);
  } catch {
    return false;
  }
}

async function proxy(request: NextRequest, path: string[], method: "GET" | "POST"): Promise<NextResponse> {
  if (!(await isOperatorAdmin(request))) {
    return NextResponse.json(
      { detail: "admin access required — the homework tool is operator-only" },
      { status: 403 },
    );
  }
  const search = request.nextUrl.search || "";
  const target = `${CURRICULUM_ORIGIN}/homework/${path.join("/")}${search}`;
  const headers: Record<string, string> = { "X-Internal-Token": INTERNAL_TOKEN };
  const ct = request.headers.get("content-type");
  if (ct) headers["content-type"] = ct;   // preserve JSON / multipart boundary

  const init: RequestInit & { duplex?: "half" } = { method, headers, cache: "no-store" };
  if (method === "POST") {
    init.body = request.body;   // stream JSON or file uploads straight through
    init.duplex = "half";
  }

  try {
    const r = await fetch(target, init);
    const body = await r.text();
    return new NextResponse(body, {
      status: r.status,
      headers: { "content-type": r.headers.get("content-type") || "application/json" },
    });
  } catch (e) {
    return NextResponse.json({ detail: `homework service unavailable: ${String(e)}` }, { status: 502 });
  }
}

export async function GET(request: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(request, ctx.params.path, "GET");
}

export async function POST(request: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(request, ctx.params.path, "POST");
}
