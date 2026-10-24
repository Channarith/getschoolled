import fs from "fs";
import path from "path";
import { NextResponse } from "next/server";
import { fetchManifest } from "../../lib/androidRelease";

/**
 * Same-origin Android APK download.
 *
 * Direct links to Object Storage often open in a new browser tab and fail on
 * phones (the browser tries to "view" the APK). Serving through this route with
 * Content-Disposition: attachment makes:
 *   - Android Chrome/Samsung Internet: download then offer Install/Open
 *   - Desktop browsers: save the file locally
 *
 * Resolution order (first hit wins):
 *   1. apps/web/public/downloads/salareen-latest.apk  — staged into the image
 *      by `scripts/stage_apk_for_web.sh` before `docker build` (preferred:
 *      no CORS, no outbound bandwidth, works even when object storage is down).
 *   2. ANDROID_APK_URL (runtime) / NEXT_PUBLIC_ANDROID_APK_URL / the built-in
 *      default — redirect to the Object Storage file. That file is stored with
 *      Content-Disposition: attachment, so phones download it instead of
 *      trying to view it.
 *
 * This lives at /download/android, not under /api: the ingress sends every
 * /api/ path to the orchestrator except /api/admin/, so a web route under
 * /api/download never received the request.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const STAGED_APK_RELATIVE = path.join("public", "downloads", "salareen-latest.apk");

function stagedApkPath(): string | null {
  // process.cwd() is the Next.js app dir in dev and /app in the Docker image.
  const candidates = [
    path.join(process.cwd(), STAGED_APK_RELATIVE),
    path.join(process.cwd(), "apps", "web", STAGED_APK_RELATIVE),
  ];
  for (const p of candidates) {
    try {
      if (fs.existsSync(p) && fs.statSync(p).size > 1024 * 1024) {
        return p;
      }
    } catch {
      /* try next */
    }
  }
  return null;
}

function stagedApkFilename(): string {
  // Report the versioned filename (e.g. salareen-0.62.6-6206-release.apk) when
  // available, so the downloaded file is self-describing even though the URL
  // is the stable /downloads/salareen-latest.apk slug.
  const dir = path.dirname(stagedApkPath() || "");
  try {
    if (dir) {
      const manifest = path.join(dir, "latest.json");
      if (fs.existsSync(manifest)) {
        const parsed = JSON.parse(fs.readFileSync(manifest, "utf8")) as { filename?: string };
        if (parsed.filename && parsed.filename.toLowerCase().endsWith(".apk")) {
          return parsed.filename;
        }
      }
    }
  } catch {
    /* fall through to default */
  }
  return "salareen.apk";
}

// Same file the /download page names as its fallback. Next inlines
// NEXT_PUBLIC_* at build time, so a value set only on the running pod would
// be ignored; ANDROID_APK_URL is read at request time.
const DEFAULT_APK_URL =
  "https://salareen-prod.sjc1.vultrobjects.com/releases/android/v0.94.9/app-release.apk";

function apkSourceUrl(): string {
  return (process.env.ANDROID_APK_URL || process.env.NEXT_PUBLIC_ANDROID_APK_URL || DEFAULT_APK_URL).trim();
}

export async function GET(request: Request): Promise<Response> {
  // The published manifest wins: a staged file baked into an old image must never shadow a newer release.
  const manifest = await fetchManifest();
  if (manifest) {
    return NextResponse.redirect(manifest.url, 302);
  }
  // Prefer the staged local file. This is the path the user asked us to wire
  // up ("Download APK is broken on Get the Salareen app page") — the stage
  // script drops a real signed APK next to the Next.js public assets so the
  // "Download APK" button never 404s even if the Object Storage URL goes down.
  const staged = stagedApkPath();
  if (staged) {
    const filename = stagedApkFilename();
    const stat = fs.statSync(staged);
    const stream = fs.createReadStream(staged);
    // Node Readable → Web ReadableStream for NextResponse.
    const web = new ReadableStream({
      start(controller) {
        stream.on("data", (chunk: Buffer | string) => {
          controller.enqueue(typeof chunk === "string" ? new TextEncoder().encode(chunk) : chunk);
        });
        stream.on("end", () => controller.close());
        stream.on("error", (err) => controller.error(err));
      },
      cancel() {
        stream.destroy();
      },
    });
    const headers = new Headers();
    headers.set("Content-Type", "application/vnd.android.package-archive");
    headers.set(
      "Content-Disposition",
      `attachment; filename="${filename}"; filename*=UTF-8''${encodeURIComponent(filename)}`,
    );
    headers.set("Content-Length", String(stat.size));
    headers.set("Cache-Control", "public, max-age=300");
    headers.set("X-Content-Type-Options", "nosniff");
    headers.set("Accept-Ranges", "bytes");
    return new NextResponse(web, { status: 200, headers });
  }

  const source = apkSourceUrl();
  if (!/^https:\/\//i.test(source)) {
    return NextResponse.json({ detail: "Android APK download is not configured" }, { status: 404 });
  }
  return NextResponse.redirect(source, 302);
}
