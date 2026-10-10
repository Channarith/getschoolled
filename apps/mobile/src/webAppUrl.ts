/** Web app origin for demos, studio, vision arcade, and Worlds.
 *
 * Cloud builds always use https://www.salareen.com. A localhost override in
 * app.json must not win in cloud mode — that would point a shipped app at a
 * developer machine.
 */

export const CLOUD_WEB_ORIGIN = "https://www.salareen.com";

const LOOPBACK = /localhost|127\.0\.0\.1|0\.0\.0\.0|10\.0\.2\.2/i;

export function isLoopbackUrl(url: string): boolean {
  return LOOPBACK.test(url);
}

export function resolveWebAppUrl(opts: {
  deployMode: "local" | "cloud" | string;
  platform: string;
  configured?: string;
  cloudBase?: string;
}): string {
  const cloud = (opts.cloudBase || CLOUD_WEB_ORIGIN).replace(/\/$/, "");
  const configured = (opts.configured || "").trim();
  if (opts.deployMode !== "local") {
    if (configured.startsWith("http") && !isLoopbackUrl(configured)) {
      return configured.replace(/\/$/, "");
    }
    return cloud;
  }
  if (configured.startsWith("http")) {
    const url = configured.replace(/\/$/, "");
    if (opts.platform === "android") {
      return url
        .replace("://localhost", "://10.0.2.2")
        .replace("://127.0.0.1", "://10.0.2.2");
    }
    return url;
  }
  const host = opts.platform === "android" ? "10.0.2.2" : "localhost";
  return `http://${host}:3000`;
}

/** Worlds is a Next.js page on the web app, not a curriculum-service route. */
export function worldsPageUrl(webAppUrl: string): string {
  return `${webAppUrl.replace(/\/$/, "")}/worlds`;
}
