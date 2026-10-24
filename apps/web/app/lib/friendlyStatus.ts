// Small helpers shared by the error screens and the API client.

export const FRIENDLY_ERROR_EVENT = "salareen:friendly-error";

/** "503 Service Unavailable" (the shape jsonOrThrow throws) -> 503, anything else -> null. */
export function statusFromError(error: unknown): number | null {
  const message = error instanceof Error ? error.message : String(error ?? "");
  const match = /^\s*(\d{3})\b/.exec(message);
  if (match) return Number(match[1]);
  if (/failed to fetch|networkerror|load failed|network request failed/i.test(message)) return 0;
  return null;
}

/** Tell the page a call failed for a reason the learner can do nothing about (network, 5xx). */
export function reportFriendlyFailure(status: number): void {
  if (typeof window === "undefined") return;
  // 501 is "not built yet", 4xx and a plain 500 are the caller's to handle; only outages interrupt.
  if (status !== 502 && status !== 503 && status !== 504) return;
  window.dispatchEvent(new CustomEvent(FRIENDLY_ERROR_EVENT, { detail: { status } }));
}
