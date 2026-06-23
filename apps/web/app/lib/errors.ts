// Shared error helpers for friendlier UI messages.

// A failed `fetch()` (backend down / unreachable / CORS) surfaces as
// "TypeError: Failed to fetch" (Chrome), "NetworkError ..." (Firefox), or
// "Load failed" (Safari). Detect those so the UI can show a clear "server
// unreachable" message instead of a raw TypeError.
export function isOfflineError(err: unknown): boolean {
  return /failed to fetch|networkerror|load failed|fetch failed/i.test(String(err));
}

// Map a raw error to a user-facing string: the localized offline message for
// connectivity failures, otherwise the raw text.
export function friendlyError(err: unknown, offlineMessage: string): string {
  return isOfflineError(err) ? offlineMessage : String(err);
}
