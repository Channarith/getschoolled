import { NextResponse } from "next/server";
import { APP_VERSION } from "../lib/version";
import { fetchManifest } from "../lib/androidRelease";

// Public, cacheable description of the newest app builds. The phone app calls this to decide whether to show an
// "update available" prompt. Served at /app-version (not /api/*: the ingress sends /api/ to the orchestrator).
// iOS values come from env because TestFlight/App Store links are not files we host:
//   IOS_LATEST_VERSION, IOS_STORE_URL (TestFlight public link or App Store URL), IOS_MIN_SUPPORTED (optional).
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const android = await fetchManifest();
  const iosVersion = (process.env.IOS_LATEST_VERSION || "").trim();
  const iosUrl = (process.env.IOS_STORE_URL || "").trim();
  const body = {
    web: APP_VERSION,
    android: android
      ? { version: android.version, url: "/download/android", min_supported: android.min_supported ?? null, sha256: android.sha256 ?? null }
      : null,
    ios: iosVersion && /^https:\/\//.test(iosUrl)
      ? { version: iosVersion, url: iosUrl, min_supported: (process.env.IOS_MIN_SUPPORTED || "").trim() || null }
      : null,
  };
  return NextResponse.json(body, { headers: { "Cache-Control": "public, max-age=60", "X-Content-Type-Options": "nosniff" } });
}
