import { NextRequest, NextResponse } from "next/server";

const IDENTITY_ORIGIN = process.env.IDENTITY_ORIGIN || "http://identity:8000";
const MEMORY_ORIGIN = process.env.MEMORY_ORIGIN || "http://memory:8000";
const ADMIN_SECRET = process.env.ADMIN_SECRET || "dev-admin-secret";

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

export async function PUT(
  request: NextRequest,
  { params }: { params: { key: string } },
) {
  if (!(await isOperatorAdmin(request))) {
    return NextResponse.json({ detail: "admin access required" }, { status: 403 });
  }
  const body = await request.text();
  const r = await fetch(`${MEMORY_ORIGIN}/admin/flags/${encodeURIComponent(params.key)}`, {
    method: "PUT",
    headers: {
      "X-Admin-Secret": ADMIN_SECRET,
      "content-type": request.headers.get("content-type") || "application/json",
    },
    body,
    cache: "no-store",
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") || "application/json" },
  });
}
