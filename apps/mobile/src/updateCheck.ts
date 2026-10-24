// "Update available" check. No OTA and no EAS: the app only learns that a newer NATIVE build exists and links to it
// (Android: the APK download route; iOS: the TestFlight / App Store link). Pure logic is separate from storage so it
// can be tested without React Native.

export type PlatformUpdate = { version: string; url: string; min_supported?: string | null };
export type AppVersionInfo = { web?: string; android?: PlatformUpdate | null; ios?: PlatformUpdate | null };

export type UpdateDecision = { prompt: boolean; force: boolean; latest: string; url: string };

export function parseVersion(v: string): [number, number, number] {
  const m = /(\d+)\.(\d+)\.(\d+)/.exec(v || "");
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : [0, 0, 0];
}

export function compareVersions(a: string, b: string): number {
  const pa = parseVersion(a);
  const pb = parseVersion(b);
  for (let i = 0; i < 3; i += 1) {
    if (pa[i] !== pb[i]) return pa[i] > pb[i] ? 1 : -1;
  }
  return 0;
}

/** Same rule as aoep_shared.mobile_release.update_decision (tested on both sides). */
export function decideUpdate(
  current: string,
  info: AppVersionInfo | null | undefined,
  platform: "ios" | "android" | string,
  dismissed = "",
  baseUrl = "",
): UpdateDecision {
  const none: UpdateDecision = { prompt: false, force: false, latest: "", url: "" };
  const entry = platform === "ios" ? info?.ios : platform === "android" ? info?.android : null;
  if (!entry || !entry.version || !entry.url) return none;
  const newer = compareVersions(entry.version, current) > 0;
  const minimum = entry.min_supported || "";
  const force = Boolean(minimum) && compareVersions(current, minimum) < 0;
  const url = /^https?:\/\//i.test(entry.url) ? entry.url : `${baseUrl.replace(/\/$/, "")}${entry.url.startsWith("/") ? "" : "/"}${entry.url}`;
  return { prompt: newer && (force || dismissed !== entry.version), force, latest: entry.version, url };
}

export async function fetchAppVersion(
  baseUrl: string,
  fetchImpl: typeof fetch = fetch,
  timeoutMs = 4000,
): Promise<AppVersionInfo | null> {
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const res = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/app-version`, { signal: controller?.signal });
    if (!res.ok) return null;
    return (await res.json()) as AppVersionInfo;
  } catch {
    return null;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export const UPDATE_COPY: Record<string, { title: string; body: string; update: string; later: string }> = {
  en: {
    title: "A new Salareen is ready",
    body: "Install the latest version to get the newest games, courses and fixes.",
    update: "Update now",
    later: "Not now",
  },
  es: {
    title: "Hay una nueva versión de Salareen",
    body: "Instala la última versión para tener los juegos, cursos y mejoras más recientes.",
    update: "Actualizar ahora",
    later: "Ahora no",
  },
  km: {
    title: "មាន Salareen កំណែថ្មី",
    body: "ដំឡើងកំណែចុងក្រោយ ដើម្បីទទួលបានហ្គេម មេរៀន និងការកែលម្អថ្មីៗ។",
    update: "ធ្វើបច្ចុប្បន្នភាពឥឡូវនេះ",
    later: "កុំទាន់",
  },
};
