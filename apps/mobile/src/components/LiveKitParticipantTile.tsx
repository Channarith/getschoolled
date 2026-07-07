import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { registerGlobals, VideoView } from "@livekit/react-native";
import { Room, RoomEvent, Track } from "livekit-client";

import { theme } from "../theme";

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
    let cancelled = false;
    let room: Room | null = null;
    (async () => {
      try {
        registerGlobals();
        room = new Room();
        await room.connect(media.url, media.token, { autoSubscribe: true });
        if (cancelled) {
          room.disconnect();
          return;
        }
        if (canPublish) {
          await room.localParticipant.setCameraEnabled(true);
          await room.localParticipant.setMicrophoneEnabled(true);
        }
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

  if (livekitReady && track) {
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
