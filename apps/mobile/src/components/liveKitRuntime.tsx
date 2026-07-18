import { StyleSheet, View } from "react-native";

import { ensureLiveKitGlobals } from "../polyfills/liveKitGlobals";

// Type-only imports are erased at build time (no runtime require), so they do NOT
// pull LiveKit/WebRTC into the launch bundle.
import type { VideoView as LKVideoView } from "@livekit/react-native";

export type LiveKitRN = typeof import("@livekit/react-native");
export type LiveKitClient = typeof import("livekit-client");

// `@livekit/react-native` runs polyfills + WebRTC global setup at IMPORT time and
// pulls in a large native dependency graph. Importing it eagerly during app
// launch can throw and crash the whole app on startup. Load it lazily the first
// time a live room actually mounts, and cache the modules. Guarded so a load
// failure degrades to the emoji fallback instead of taking down the app.
let rnMod: LiveKitRN | null = null;
let clientMod: LiveKitClient | null = null;

export function loadLiveKit(): { rn: LiveKitRN; client: LiveKitClient } | null {
  if (rnMod && clientMod) return { rn: rnMod, client: clientMod };
  try {
    // Hermes (iOS + Android) lacks TextEncoder/TextDecoder/DOMException at
    // module-eval time; install them before any LiveKit require.
    ensureLiveKitGlobals();
    rnMod = require("@livekit/react-native") as LiveKitRN;
    // WebRTC globals + URL/streams shims must exist before livekit-client runs.
    rnMod.registerGlobals();
    clientMod = require("livekit-client") as LiveKitClient;
    return { rn: rnMod, client: clientMod };
  } catch {
    rnMod = null;
    clientMod = null;
    return null;
  }
}

/** True once the LiveKit modules are loaded (VideoView is available to render). */
export function liveKitLoaded(): boolean {
  return Boolean(rnMod && clientMod);
}

/**
 * Presentational video surface for one LiveKit video track. Renders nothing when
 * there is no track or the SDK failed to load, so callers can fall back to an
 * avatar/emoji. It does NOT own a room connection — the shared useLiveKitRoom
 * hook connects once and hands each tile its participant's track.
 */
export function LiveKitVideoView({ track }: { track: object | null }) {
  const VideoView: typeof LKVideoView | undefined = rnMod?.VideoView;
  if (!track || !VideoView) return null;
  return (
    <View style={StyleSheet.absoluteFillObject} pointerEvents="none">
      <VideoView
        style={StyleSheet.absoluteFillObject}
        videoTrack={track as never}
        objectFit="cover"
      />
    </View>
  );
}
