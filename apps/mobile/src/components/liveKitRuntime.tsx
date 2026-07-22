import { StyleSheet, View } from "react-native";
import Constants from "expo-constants";

import { ensureLiveKitGlobals } from "../polyfills/liveKitGlobals";
import { hasExpoNativeModule } from "../nativeModules";

// Type-only imports are erased at build time (no runtime require), so they do NOT
// pull LiveKit/WebRTC into the launch bundle.
import type { VideoView as LKVideoView } from "@livekit/react-native";

export type LiveKitRN = typeof import("@livekit/react-native");
export type LiveKitClient = typeof import("livekit-client");

// `@livekit/react-native` + `@livekit/react-native-webrtc` touch NativeModules
// (WebRTCModule) at require-time and registerGlobals() patches getUserMedia.
// Expo Go does not ship those natives — requiring them redboxes the whole app.
// Gate before any require so live rooms degrade to emoji tiles instead.
let rnMod: LiveKitRN | null = null;
let clientMod: LiveKitClient | null = null;
let unavailable = false;

/** True when a native binary with LiveKit/WebRTC is present (dev client / EAS). */
export function isLiveKitNativeAvailable(): boolean {
  // Expo Go (store client) never includes WebRTC / LiveKit native modules.
  if (Constants.appOwnership === "expo") return false;
  if (Constants.executionEnvironment === "storeClient") return false;
  return hasExpoNativeModule("WebRTCModule");
}

/**
 * Lazily load LiveKit. Returns null in Expo Go / when WebRTC is missing so
 * callers can fall back without a redbox.
 */
export function loadLiveKit(): { rn: LiveKitRN; client: LiveKitClient } | null {
  if (unavailable) return null;
  if (rnMod && clientMod) return { rn: rnMod, client: clientMod };
  if (!isLiveKitNativeAvailable()) {
    unavailable = true;
    return null;
  }
  try {
    // Hermes (iOS + Android) lacks TextEncoder/TextDecoder/DOMException at
    // module-eval time; install them before any LiveKit require.
    ensureLiveKitGlobals();
    rnMod = require("@livekit/react-native") as LiveKitRN;
    // Skip autoConfigureAudioSession — iosCategoryEnforce wraps getUserMedia and
    // can throw asynchronously when WebRTC is partially present. We configure
    // AVAudioSession ourselves via liveKitAudio.ts.
    rnMod.registerGlobals({ autoConfigureAudioSession: false });
    clientMod = require("livekit-client") as LiveKitClient;
    return { rn: rnMod, client: clientMod };
  } catch {
    unavailable = true;
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
 *
 * Sized with flex:1 inside the seat's top video window (not a floating PiP).
 * zOrder=0 keeps Android SurfaceView from punching through above the slide.
 */
export function LiveKitVideoView({
  track,
  mirror = false,
  zOrder = 0,
}: {
  track: object | null;
  /** Mirror local self-view so it feels like a front camera. */
  mirror?: boolean;
  /**
   * Android SurfaceView z-order. 0 = below RN layer (default for in-card
   * tiles — parent must be backgroundColor:transparent for video to show
   * through). 1 = above RN layer (use for full-screen tiles where the video
   * is the sole content and no RN views need to overlay it).
   */
  zOrder?: number;
}) {
  const VideoView: typeof LKVideoView | undefined = rnMod?.VideoView;
  if (!track || !VideoView) return null;
  return (
    <View style={styles.surface} pointerEvents="none">
      <VideoView
        style={styles.surface}
        videoTrack={track as never}
        objectFit="cover"
        mirror={mirror}
        zOrder={zOrder}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  surface: { flex: 1, width: "100%", height: "100%" },
});
