import { NextRequest, NextResponse } from "next/server";
import { proxyMemoryAdmin } from "../adminProxy";

export async function GET(request: NextRequest): Promise<NextResponse> {
  return proxyMemoryAdmin(request, "/admin/survey/insights");
}
