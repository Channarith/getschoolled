/**
 * LiveKit iOS/Android audio routing for Salareen live rooms.
 *
 * The AI teacher (Theodore) does NOT publish LiveKit audio — the app narrates
 * slides via expo-speech / neural TTS. LiveKit's default WebRTC session on iOS
 * often lands on playAndRecord + voiceChat (earpiece) or soloAmbient (silent
 * with the mute switch), which makes teacher narration inaudible. Keep the
 * session on loudspeaker playback while the mic is off, and re-assert that
 * route before every TTS utterance.
 */

import { Platform } from "react-native";

export type AppleLiveRoomAudioConfig = {
  audioCategory: "playback" | "playAndRecord";
  audioCategoryOptions: (
    | "mixWithOthers"
    | "defaultToSpeaker"
    | "allowBluetooth"
    | "allowBluetoothA2DP"
  )[];
  audioMode: "spokenAudio" | "videoChat";
};

/**
 * Structural AudioSession handle. Callers cast from `@livekit/react-native`'s
 * AudioSession — we avoid importing that module here (eager native load).
 */
export type LiveKitAudioSession = {
  configureAudio: (config: Record<string, unknown>) => Promise<void>;
  startAudioSession: () => Promise<void>;
  stopAudioSession: () => Promise<void>;
  setAppleAudioConfiguration: (config: AppleLiveRoomAudioConfig) => Promise<void>;
  selectAudioOutput: (deviceId: string) => Promise<void>;
};

/** Cast the LiveKit AudioSession class/object into our structural handle. */
export function asLiveKitAudioSession(session: object): LiveKitAudioSession {
  return session as LiveKitAudioSession;
}

/**
 * AVAudioSession category/mode for a live room.
 * Mic off (typical learner): playback + spokenAudio → loudspeaker, TTS can mix.
 * Mic on (floor holder): playAndRecord + defaultToSpeaker + videoChat.
 */
export function appleConfigForLiveRoom(micEnabled: boolean): AppleLiveRoomAudioConfig {
  if (micEnabled) {
    return {
      audioCategory: "playAndRecord",
      audioCategoryOptions: [
        "defaultToSpeaker",
        "allowBluetooth",
        "allowBluetoothA2DP",
        "mixWithOthers",
      ],
      audioMode: "videoChat",
    };
  }
  return {
    audioCategory: "playback",
    audioCategoryOptions: ["mixWithOthers"],
    audioMode: "spokenAudio",
  };
}

const MEDIA_ANDROID_OPTS: Record<string, unknown> = {
  manageAudioFocus: true,
  audioMode: "normal",
  audioFocusMode: "gain",
  audioStreamType: "music",
  audioAttributesUsageType: "media",
  audioAttributesContentType: "speech",
};

let session: LiveKitAudioSession | null = null;
let micPublishing = false;

/** True while a live-room LiveKit audio session is owned by this bridge. */
export function liveKitAudioActive(): boolean {
  return session != null;
}

/**
 * Configure + start LiveKit audio for speaker-first live class playback.
 * Call before `room.connect`. Safe to call on Android (configure only).
 */
export async function beginLiveKitAudio(
  audioSession: LiveKitAudioSession,
  opts?: { micEnabled?: boolean; androidMediaOptions?: Record<string, unknown> },
): Promise<void> {
  session = audioSession;
  micPublishing = Boolean(opts?.micEnabled);
  try {
    await audioSession.configureAudio({
      ios: { defaultOutput: "speaker" },
      android: {
        preferredOutputList: ["speaker", "bluetooth", "headset", "earpiece"],
        audioTypeOptions: opts?.androidMediaOptions ?? MEDIA_ANDROID_OPTS,
      },
    });
  } catch {
    /* configure is best-effort */
  }
  if (Platform.OS === "ios") {
    try {
      await audioSession.startAudioSession();
    } catch {
      /* start is best-effort */
    }
  }
  await applyLiveKitAudioRoute(micPublishing);
}

/** Re-apply speaker/mic category after connect, mic toggles, or camera publish. */
export async function applyLiveKitAudioRoute(micEnabled: boolean): Promise<void> {
  micPublishing = micEnabled;
  if (!session) return;
  if (Platform.OS === "ios") {
    try {
      await session.setAppleAudioConfiguration(appleConfigForLiveRoom(micEnabled));
    } catch {
      /* ignore */
    }
    try {
      await session.selectAudioOutput("force_speaker");
    } catch {
      /* ignore — older OS / already on speaker */
    }
    return;
  }
  try {
    await session.selectAudioOutput("speaker");
  } catch {
    /* ignore */
  }
}

/**
 * Called before teacher TTS so narration isn't left on the earpiece after
 * LiveKit/WebRTC grabbed the shared AVAudioSession.
 */
export async function ensureLiveRoomNarrationRoute(): Promise<void> {
  if (!session) return;
  await applyLiveKitAudioRoute(micPublishing);
}

/** Tear down the LiveKit audio session when leaving the room. */
export async function endLiveKitAudio(): Promise<void> {
  const s = session;
  session = null;
  micPublishing = false;
  if (s && Platform.OS === "ios") {
    try {
      await s.stopAudioSession();
    } catch {
      /* ignore */
    }
  }
}
