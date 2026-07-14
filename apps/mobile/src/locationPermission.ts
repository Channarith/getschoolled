// Foreground-location permission helper.
//
// iOS logs a CoreLocation "Performance Diagnostics" FAULT — "This method can
// cause UI unresponsiveness if invoked on the main thread. Instead, consider
// waiting for the `-locationManagerDidChangeAuthorization:` callback and checking
// `authorizationStatus` first." — when authorization is probed synchronously.
//
// Follow Apple's guidance: CHECK the current status first (the non-prompting
// getForegroundPermissionsAsync reads authorizationStatus asynchronously) and
// only PROMPT when it is still undetermined. This avoids re-requesting (and
// re-probing CoreLocation) on every call — e.g. each time the live-room
// discovery screen mounts or driving detection starts — which is what makes the
// diagnostic recur. It is a non-fatal warning; the definitive removal is an
// expo-location/SDK upgrade that moves the native probe off the main thread.

type LocationModule = typeof import("expo-location");

export async function ensureForegroundLocationPermission(
  Location: LocationModule,
): Promise<boolean> {
  try {
    const current = await Location.getForegroundPermissionsAsync();
    if (current.status === "granted") return true;
    // Already denied and the OS won't show the prompt again — don't re-probe.
    if (current.canAskAgain === false) return false;
    const requested = await Location.requestForegroundPermissionsAsync();
    return requested.status === "granted";
  } catch {
    return false;
  }
}
