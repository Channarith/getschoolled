import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { theme } from "../theme";

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

// `@livekit/react-native` runs polyfills + WebRTC global setup at IMPORT time and
// pulls in a large native/web dependency graph. Importing it eagerly executes all
// of that during app launch (via App -> LiveRoomScreen -> this tile), which can
// throw and crash the whole app on startup. Load it lazily the first time a tile
// actually mounts inside a live room, and cache the modules. Guarded so a load
// failure degrades to the emoji fallback instead of taking down the app.
type LiveKitRN = typeof import("@livekit/react-native");
type LiveKitClient = typeof import("livekit-client");

let rnMod: LiveKitRN | null = null;
let clientMod: LiveKitClient | null = null;

function loadLiveKit(): { rn: LiveKitRN; client: LiveKitClient } | null {
  if (rnMod && clientMod) return { rn: rnMod, client: clientMod };
  try {
    rnMod = require("@livekit/react-native") as LiveKitRN;
    clientMod = require("livekit-client") as LiveKitClient;
    return { rn: rnMod, client: clientMod };
  } catch {
    rnMod = null;
    clientMod = null;
    return null;
  }
}

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
    const { registerGlobals } = lk.rn;
    const { Room, RoomEvent, Track } = lk.client;

    let cancelled = false;
    let room: LKRoom | null = null;
    void (async () => {
      try {
        registerGlobals();
        room = new Room();
        await room.connect(media.url, media.token, { autoSubscribe: true });
        if (cancelled) {
          room.disconnect();
          return;
        }
        // Everyone's camera turns on (video-call feel); the mic follows the
        // one-speaker mutex (canPublish = you hold the floor). Best-effort so a
        // denied/absent camera never breaks the tile.
        try {
          await room.localParticipant.setCameraEnabled(true);
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
    };
  }, [media?.url, media?.token, canPublish]);

  const VideoView: typeof LKVideoView | undefined = rnMod?.VideoView;

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
    justifyContent: "flex-end",
    overflow: "hidden",
  },
  large: { width: 160, height: 180 },
  emoji: { fontSize: 36, marginBottom: 24 },
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
