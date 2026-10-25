// The demo WebView holds camera and microphone permission for whatever page it shows (iOS mediaCapturePermissionGrantType
// "grant", Android's WebChromeClient). So it may only ever show OUR pages: a link or redirect to anywhere else must open in the
// system browser, which asks for permissions per site.

const TRUSTED_HOSTS = ["salareen.com"];

function hostOf(url: string): string {
  const m = /^https?:\/\/([^/?#]*)/i.exec(url.trim());
  if (!m) return "";
  const authority = m[1];
  const afterUser = authority.slice(authority.lastIndexOf("@") + 1);   // "a:b@host" -> host: the part before "@" is user info, not the host
  return afterUser.replace(/:\d*$/, "").toLowerCase();
}

export function trustedHostsFor(baseUrl: string): string[] {
  const own = hostOf(baseUrl);
  return own && !TRUSTED_HOSTS.includes(own) ? [...TRUSTED_HOSTS, own] : [...TRUSTED_HOSTS];
}

/** True when the WebView may load this URL: https on salareen.com (or a subdomain), the configured app host, or an internal blank page. */
export function isTrustedNavigation(url: string, baseUrl: string): boolean {
  const u = String(url || "").trim();
  if (u === "about:blank" || u.startsWith("about:srcdoc")) return true;
  const host = hostOf(u);
  if (!host) return false;
  const base = String(baseUrl || "").trim().toLowerCase();
  const baseIsPlainHttp = base.startsWith("http://");   // a developer's LAN server: same host only, and only when the build points at it
  if (/^http:\/\//i.test(u) && !baseIsPlainHttp) return false;
  if (!/^https?:\/\//i.test(u)) return false;
  return trustedHostsFor(baseUrl).some((t) => host === t || host.endsWith("." + t));
}
