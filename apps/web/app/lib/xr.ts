/**
 * WebXR helpers for Salareen immersive labs (Quest Browser / desktop WebXR).
 * Sends normalized action observations only — never raw video frames.
 */

export type XrClientKind = "webxr" | "unity_openxr" | "fallback";

export type XrObservation = {
  seq: number;
  action: string;
  target_id?: string;
  hand?: string;
  confidence?: number;
  hold_ms?: number;
  ts_ms?: number;
  pose?: Record<string, number>;
};

export type XrCapability = {
  supported: boolean;
  immersiveVr: boolean;
  reason: string;
};

export async function detectXrCapability(): Promise<XrCapability> {
  if (typeof navigator === "undefined" || !(navigator as Navigator & { xr?: XRSystem }).xr) {
    return { supported: false, immersiveVr: false, reason: "WebXR not available in this browser" };
  }
  try {
    const xr = (navigator as Navigator & { xr: XRSystem }).xr;
    const immersiveVr = await xr.isSessionSupported("immersive-vr");
    return {
      supported: true,
      immersiveVr,
      reason: immersiveVr ? "immersive-vr available" : "WebXR present but immersive-vr unsupported",
    };
  } catch (err) {
    return {
      supported: false,
      immersiveVr: false,
      reason: err instanceof Error ? err.message : "WebXR capability check failed",
    };
  }
}

export async function requestImmersiveVrSession(): Promise<XRSession | null> {
  const cap = await detectXrCapability();
  if (!cap.immersiveVr) return null;
  const xr = (navigator as Navigator & { xr: XRSystem }).xr;
  return xr.requestSession("immersive-vr", {
    requiredFeatures: ["local-floor"],
    optionalFeatures: ["hand-tracking", "bounded-floor"],
  });
}

/** Heuristic demo observations that exercise the shared rubric (deterministic). */
export function demoPassObservations(): XrObservation[] {
  const now = Date.now();
  return [
    { seq: 1, action: "approach", target_id: "station", confidence: 0.95, ts_ms: now, hold_ms: 0 },
    { seq: 2, action: "grab", target_id: "tool", confidence: 0.9, ts_ms: now + 500, hold_ms: 600 },
    { seq: 3, action: "confirm", target_id: "finish", confidence: 0.92, ts_ms: now + 1200, hold_ms: 200 },
  ];
}

export function demoNeedsWorkObservations(): XrObservation[] {
  const now = Date.now();
  return [
    { seq: 1, action: "approach", target_id: "station", confidence: 0.8, ts_ms: now },
    // Missing grab / confirm → needs_work
  ];
}

export function normalizeControllerAction(
  action: string,
  targetId = "",
  opts: Partial<XrObservation> = {},
): XrObservation {
  return {
    seq: opts.seq ?? 0,
    action: (action || "").trim().toLowerCase(),
    target_id: targetId,
    hand: opts.hand || "",
    confidence: opts.confidence ?? 0.85,
    hold_ms: opts.hold_ms ?? 0,
    ts_ms: opts.ts_ms ?? Date.now(),
    pose: opts.pose || {},
  };
}
