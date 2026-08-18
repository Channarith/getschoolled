import { NextRequest, NextResponse } from "next/server";
import { proxyMemoryAdmin } from "../adminProxy";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const limit = request.nextUrl.searchParams.get("limit") || "50";
  return proxyMemoryAdmin(request, `/admin/bugs?limit=${encodeURIComponent(limit)}`);
}
