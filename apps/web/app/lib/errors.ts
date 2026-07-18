// Shared error helpers for friendlier UI messages.

// A failed `fetch()` (backend down / unreachable / CORS) surfaces as
// "TypeError: Failed to fetch" (Chrome), "NetworkError ..." (Firefox), or
// "Load failed" (Safari). Detect those so the UI can show a clear "server
// unreachable" message instead of a raw TypeError.
export function isOfflineError(err: unknown): boolean {
  return /failed to fetch|networkerror|load failed|fetch failed|network connection was lost|connection (was )?lost|connection reset|broken pipe|ns_error_net|the internet connection appears to be offline/i
    .test(String(err));
}

export function isBugScreenshotTooLargeError(err: unknown): boolean {
  return /screenshot exceeds|too large to send|payload too large|413\b/i.test(String(err));
}

// Map a raw error to a user-facing string: the localized offline message for
// connectivity failures, otherwise the raw text.
export function friendlyError(err: unknown, offlineMessage: string): string {
  if (isBugScreenshotTooLargeError(err)) {
    return "Screenshot is too large to send. Try a smaller image, or send without a screenshot.";
  }
  return isOfflineError(err) ? offlineMessage : String(err);
}
