import { NextRequest, NextResponse } from "next/server";

const IDENTITY_ORIGIN = process.env.IDENTITY_ORIGIN || "http://identity:8000";
const MEMORY_ORIGIN = process.env.MEMORY_ORIGIN || "http://memory:8000";
const ADMIN_SECRET = process.env.ADMIN_SECRET || "dev-admin-secret";

export async function isOperatorAdmin(request: NextRequest): Promise<boolean> {
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

// Proxy an admin read to the memory service. Operator-admins authenticated by
// their identity session get the server-side secret attached; everyone else
// falls back to the X-Admin-Secret header they supplied.
export async function proxyMemoryAdmin(
  request: NextRequest,
  path: string,
): Promise<NextResponse> {
  const operatorAdmin = await isOperatorAdmin(request);
  const clientSecret = request.headers.get("x-admin-secret") || "";
  if (!operatorAdmin && !clientSecret) {
    return NextResponse.json({ detail: "admin access required" }, { status: 403 });
  }
  const secret = operatorAdmin ? ADMIN_SECRET : clientSecret;
  const r = await fetch(`${MEMORY_ORIGIN}${path}`, {
    headers: { "X-Admin-Secret": secret },
    cache: "no-store",
  });
  const contentType = r.headers.get("content-type") || "application/json";
  const body = await r.arrayBuffer();
  return new NextResponse(body, {
    status: r.status,
    headers: { "content-type": contentType },
  });
}
