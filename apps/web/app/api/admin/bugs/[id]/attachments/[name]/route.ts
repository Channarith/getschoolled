import { NextRequest, NextResponse } from "next/server";
import { proxyMemoryAdmin } from "../../../../adminProxy";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; name: string }> },
): Promise<NextResponse> {
  const { id, name } = await params;
  return proxyMemoryAdmin(
    request,
    `/admin/bugs/${encodeURIComponent(id)}/attachments/${encodeURIComponent(name)}`,
  );
}
