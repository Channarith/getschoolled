// Map a failure (HTTP status, or a network exception) to one friendly screen.
// kinds: offline (no connection), network (502/503/504/timeouts), notfound (404/410),
// notimpl (501), oops (500 and other 5xx). 401/403 are handled by sign-in, not here.
export function classifyStatus(status, opts) {
  const o = opts || {};
  const code = Number(status) || 0;
  if (o.offline) return "offline";
  if (o.timeout || code === 0) return "network";
  if (code === 404 || code === 410) return "notfound";
  if (code === 501) return "notimpl";
  if (code === 502 || code === 503 || code === 504 || (code >= 520 && code <= 524)) return "network";
  if (code >= 500) return "oops";
  return null;
}

export const KIND_MOOD = { offline: "tears", network: "tears", notfound: "surprised", notimpl: "thinking", oops: "calm" };
