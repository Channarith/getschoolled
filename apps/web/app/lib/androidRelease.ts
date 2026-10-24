// Latest Android release, read from a small JSON manifest that scripts/mobile_release.sh publishes next to the APK.
// Publishing the manifest IS the update: no web redeploy, no kubectl. The manifest URL is fixed by config, and the
// APK URL inside it must be https on an allowed host, so a bad manifest can never turn the route into an open redirect.

export type AndroidManifest = {
  version: string;
  url: string;
  versionCode?: number;
  sha256?: string;
  size?: number;
  git_sha?: string;
  built_at?: string;
  min_supported?: string;
  filename?: string;
};

export const DEFAULT_MANIFEST_URL = "https://salareen-prod.sjc1.vultrobjects.com/releases/android/latest.json";
const ALLOWED_HOST_SUFFIXES = [".vultrobjects.com", "salareen.com"];
const SEMVER = /^\d+\.\d+\.\d+$/;

export function manifestUrl(env: Record<string, string | undefined>): string {
  return (env.ANDROID_MANIFEST_URL || DEFAULT_MANIFEST_URL).trim();
}

function hostAllowed(url: string, extraHost?: string): boolean {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    return false;
  }
  if (u.protocol !== "https:") return false;
  if (extraHost && u.hostname === extraHost) return true;
  return ALLOWED_HOST_SUFFIXES.some((s) => u.hostname === s.replace(/^\./, "") || u.hostname.endsWith(s));
}

export function parseManifest(raw: unknown, manifestSource: string = DEFAULT_MANIFEST_URL): AndroidManifest | null {
  if (!raw || typeof raw !== "object") return null;
  const m = raw as Record<string, unknown>;
  const version = typeof m.version === "string" ? m.version : "";
  const url = typeof m.url === "string" ? m.url : "";
  if (!SEMVER.test(version)) return null;
  let sourceHost = "";
  try {
    sourceHost = new URL(manifestSource).hostname;
  } catch {
    /* keep empty */
  }
  if (!hostAllowed(url, sourceHost)) return null;
  const sha = typeof m.sha256 === "string" && /^[0-9a-f]{64}$/i.test(m.sha256) ? m.sha256.toLowerCase() : undefined;
  return {
    version,
    url,
    versionCode: typeof m.versionCode === "number" ? m.versionCode : undefined,
    sha256: sha,
    size: typeof m.size === "number" ? m.size : undefined,
    git_sha: typeof m.git_sha === "string" ? m.git_sha : undefined,
    built_at: typeof m.built_at === "string" ? m.built_at : undefined,
    min_supported: typeof m.min_supported === "string" && SEMVER.test(m.min_supported) ? m.min_supported : undefined,
    filename: typeof m.filename === "string" ? m.filename : undefined,
  };
}

export function compareVersions(a: string, b: string): number {
  const pa = a.split(".").map((x) => parseInt(x, 10) || 0);
  const pb = b.split(".").map((x) => parseInt(x, 10) || 0);
  for (let i = 0; i < 3; i += 1) {
    if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) > (pb[i] || 0) ? 1 : -1;
  }
  return 0;
}

type Cache = { at: number; value: AndroidManifest | null };
const cache: Cache = { at: 0, value: null };

export async function fetchManifest(
  env: Record<string, string | undefined> = process.env,
  fetchImpl: typeof fetch = fetch,
  now: number = Date.now(),
  ttlMs = 60_000,
  timeoutMs = 3_000,
): Promise<AndroidManifest | null> {
  if (cache.at && now - cache.at < ttlMs) return cache.value;
  const url = manifestUrl(env);
  try {
    const res = await fetchImpl(url, { cache: "no-store", signal: AbortSignal.timeout(timeoutMs) });
    if (!res.ok) throw new Error(`manifest HTTP ${res.status}`);
    cache.value = parseManifest(await res.json(), url);
  } catch {
    // keep serving the last good manifest if there is one; otherwise callers fall back to the staged file / env URL
    if (!cache.value) cache.value = null;
  }
  cache.at = now;
  return cache.value;
}

export function resetManifestCacheForTests(): void {
  cache.at = 0;
  cache.value = null;
}
