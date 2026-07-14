// Foreground-location permission helper.
//
// iOS logs a CoreLocation "Performance Diagnostics" FAULT — "This method can
// cause UI unresponsiveness if invoked on the main thread. Instead, consider
// waiting for the `-locationManagerDidChangeAuthorization:` callback and checking
// `authorizationStatus` first." — when authorization is probed synchronously.
//
// expo-location reads authorizationStatus on the iOS main thread, so we minimize
// how OFTEN that native probe happens:
//   1) Cache a granted result for the session, so re-mounts of the live-room
//      browse / group-classes screens and driving-detection restarts don't
//      re-probe CoreLocation every time (the RECURRENCE the diagnostic flags).
//   2) Only PROMPT when status is still undetermined (Apple's guidance: check
//      first, request only if needed).
// The calls are already awaited off the render frame by their callers (effects /
// user actions). It is a NON-FATAL warning; the definitive removal is an
// expo-location/SDK upgrade that moves the native probe off the main thread.

type LocationModule = typeof import("expo-location");

// Session cache: once foreground location is granted it stays granted for the
// app session, so we can skip re-probing CoreLocation on every caller.
let grantedThisSession = false;

export async function ensureForegroundLocationPermission(
  Location: LocationModule,
): Promise<boolean> {
  if (grantedThisSession) return true;  // already granted this session — no re-probe
  try {
    const current = await Location.getForegroundPermissionsAsync();
    if (current.status === "granted") {
      grantedThisSession = true;
      return true;
    }
    // Already denied and the OS won't show the prompt again — don't re-probe.
    if (current.canAskAgain === false) return false;
    const requested = await Location.requestForegroundPermissionsAsync();
    if (requested.status === "granted") {
      grantedThisSession = true;
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/** Test-only: clear the session grant cache between cases. */
export function __resetLocationPermissionCacheForTests(): void {
  grantedThisSession = false;
}
