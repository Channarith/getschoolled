import { NextResponse } from "next/server";

/**
 * Same-origin Android APK download.
 *
 * Direct links to Object Storage often open in a new browser tab and fail on
 * phones (the browser tries to "view" the APK). Serving through this route with
 * Content-Disposition: attachment makes:
 *   - Android Chrome/Samsung Internet: download then offer Install/Open
 *   - Desktop browsers: save the file locally
 *
 * The upstream URL remains configurable via NEXT_PUBLIC_ANDROID_APK_URL.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_ANDROID_APK_URL =
  "https://salareen-prod.sjc1.vultrobjects.com/releases/android/v0.20.4/salareen-v0.20.4.apk";

function apkSourceUrl(): string {
  return (process.env.NEXT_PUBLIC_ANDROID_APK_URL || DEFAULT_ANDROID_APK_URL).trim();
}

function filenameFromUrl(url: string): string {
  try {
    const last = new URL(url).pathname.split("/").filter(Boolean).pop() || "";
    if (last.toLowerCase().endsWith(".apk")) return last;
  } catch {
    /* fall through */
  }
  return "salareen.apk";
}

export async function GET(request: Request): Promise<Response> {
  const source = apkSourceUrl();
  if (!source) {
    return NextResponse.json(
      { detail: "Android APK download is not configured" },
      { status: 404 },
    );
  }

  const filename = filenameFromUrl(source);
  const range = request.headers.get("range");

  let upstream: Response;
  try {
    upstream = await fetch(source, {
      cache: "no-store",
      headers: range ? { Range: range } : undefined,
      // Follow redirects from object storage CDNs.
      redirect: "follow",
    });
  } catch (err) {
    return NextResponse.json(
      { detail: `Could not reach APK storage: ${String(err)}` },
      { status: 502 },
    );
  }

  if (!upstream.ok && upstream.status !== 206) {
    return NextResponse.json(
      { detail: `APK storage returned HTTP ${upstream.status}` },
      { status: 502 },
    );
  }

  const headers = new Headers();
  headers.set("Content-Type", "application/vnd.android.package-archive");
  headers.set(
    "Content-Disposition",
    `attachment; filename="${filename}"; filename*=UTF-8''${encodeURIComponent(filename)}`,
  );
  headers.set("Cache-Control", "public, max-age=300");
  headers.set("X-Content-Type-Options", "nosniff");

  const length = upstream.headers.get("content-length");
  if (length) headers.set("Content-Length", length);
  const acceptRanges = upstream.headers.get("accept-ranges");
  if (acceptRanges) headers.set("Accept-Ranges", acceptRanges);
  const contentRange = upstream.headers.get("content-range");
  if (contentRange) headers.set("Content-Range", contentRange);

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers,
  });
}
