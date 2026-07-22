import { useEffect, useState } from "react";
import { Platform, StyleSheet, Text, View } from "react-native";

import { theme } from "../theme";
import { loadLiveKit } from "./liveKitRuntime";

// Type-only imports are erased at build time (no runtime require), so they do NOT
// pull LiveKit/WebRTC into the launch bundle.
import type { Room as LKRoom } from "livekit-client";
import type { VideoView as LKVideoView } from "@livekit/react-native";

export type LiveKitMedia = {
  url: string;
  token: string;
  identity: string;
  room: string;
};

type Props = {
  media: LiveKitMedia | null | undefined;
  canPublish: boolean;
  participantName: string;
  fallbackEmoji: string;
  large?: boolean;
};

/** Always use the front / selfie camera for live-class profile tiles. */
const SELFIE_CAMERA = { facingMode: "user" as const };

/** LiveKit video tile with emoji fallback when connection fails (offline/dev). */
export default function LiveKitParticipantTile({
  media,
  canPublish,
  participantName,
  fallbackEmoji,
  large,
}: Props) {
  const [livekitReady, setLivekitReady] = useState(false);
  const [track, setTrack] = useState<object | null>(null);
  const [VideoView, setVideoView] = useState<typeof LKVideoView | undefined>(undefined);

  useEffect(() => {
    if (!media?.url || !media.token) {
      setLivekitReady(false);
      setTrack(null);
      return;
    }
    const lk = loadLiveKit();
    if (!lk) {
      setLivekitReady(false);
      setTrack(null);
      return;
    }
    const { AudioSession } = lk.rn;
    const { Room, RoomEvent, Track } = lk.client;
    setVideoView(() => lk.rn.VideoView);

    let cancelled = false;
    let room: LKRoom | null = null;
    void (async () => {
      try {
        // LiveKit docs: iOS needs an active AVAudioSession before mic/camera.
        if (Platform.OS === "ios") {
          await AudioSession.startAudioSession();
        }
        room = new Room({ videoCaptureDefaults: SELFIE_CAMERA });
        await room.connect(media.url, media.token, { autoSubscribe: true });
        if (cancelled) {
          room.disconnect();
          return;
        }
        // Everyone's camera turns on (video-call feel); the mic follows the
        // one-speaker mutex (canPublish = you hold the floor). Best-effort so a
        // denied/absent camera never breaks the tile.
        try {
          await room.localParticipant.setCameraEnabled(true, SELFIE_CAMERA);
        } catch { /* no camera / permission denied */ }
        try {
          await room.localParticipant.setMicrophoneEnabled(canPublish);
        } catch { /* mic unavailable */ }
        const pub = room.localParticipant.getTrackPublication(Track.Source.Camera);
        if (pub?.track) {
          setTrack(pub.track);
          setLivekitReady(true);
        }
        room.on(RoomEvent.TrackSubscribed, (t) => {
          if (t.kind === Track.Kind.Video) {
            setTrack(t);
            setLivekitReady(true);
          }
        });
      } catch {
        setLivekitReady(false);
        setTrack(null);
      }
    })();
    return () => {
      cancelled = true;
      room?.disconnect();
      if (Platform.OS === "ios") {
        void AudioSession.stopAudioSession().catch(() => {});
      }
    };
  }, [media?.url, media?.token, canPublish]);

  if (livekitReady && track && VideoView) {
    return (
      <View style={[styles.tile, large && styles.large]}>
        <VideoView style={StyleSheet.absoluteFillObject} videoTrack={track as never} />
        <Text style={styles.name} numberOfLines={1}>{participantName}</Text>
      </View>
    );
  }

  return (
    <View style={[styles.tile, large && styles.large]}>
      <Text style={styles.emoji}>{fallbackEmoji}</Text>
      <Text style={styles.name} numberOfLines={1}>{participantName}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tile: {
    width: 120,
    height: 140,
    borderRadius: 12,
    marginRight: 8,
    backgroundColor: "rgba(30,27,75,0.9)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  large: { width: 160, height: 180 },
  emoji: { fontSize: 96 },
  name: {
    position: "absolute",
    bottom: 6,
    left: 6,
    right: 6,
    color: theme.colors.text,
    fontSize: 11,
    fontWeight: "600",
  },
});
