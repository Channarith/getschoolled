import type { LiveKitMedia } from "../api";

/** True when the client can open a LiveKit WebSocket (url + JWT both present). */
export function isLiveKitMediaUsable(
  media: LiveKitMedia | null | undefined,
): media is LiveKitMedia & { url: string; token: string } {
  return Boolean(media?.url?.trim() && media?.token?.trim());
}

/** Server minted a JWT but suppressed the signalling URL (misconfigured LiveKit). */
export function isLiveKitMediaDowngraded(
  media: LiveKitMedia | null | undefined,
): boolean {
  return Boolean(media?.token?.trim() && !media?.url?.trim());
}
