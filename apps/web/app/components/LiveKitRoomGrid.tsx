"use client";

import { useEffect, useRef, useState } from "react";
import {
  Room,
  RoomEvent,
  Track,
  type LocalParticipant,
  type RemoteParticipant,
} from "livekit-client";

import type { LiveParticipant } from "../lib/api";

export type LiveKitMedia = {
  url: string;
  token: string;
  identity: string;
  room: string;
};

type TileStream = {
  participantId: string;
  name: string;
  isLocal: boolean;
  track: MediaStreamTrack | null;
};

function identityFor(participants: LiveParticipant[], identity: string): string | null {
  const p = participants.find((x) => x.identity === identity);
  return p?.id ?? null;
}

export function useLiveKitRoom(
  media: LiveKitMedia | null | undefined,
  participants: LiveParticipant[],
  canPublish: boolean,
) {
  const [tiles, setTiles] = useState<TileStream[]>([]);
  const [connected, setConnected] = useState(false);
  const roomRef = useRef<Room | null>(null);

  useEffect(() => {
    if (!media?.url || !media.token) {
      setConnected(false);
      setTiles([]);
      return;
    }

    let cancelled = false;
    const room = new Room({ adaptiveStream: true, dynacast: true });
    roomRef.current = room;

    const upsert = (
      participantId: string,
      name: string,
      isLocal: boolean,
      track: MediaStreamTrack | null,
    ) => {
      setTiles((prev) => {
        const rest = prev.filter((t) => t.participantId !== participantId);
        if (!track) return rest;
        return [...rest, { participantId, name, isLocal, track }];
      });
    };

    const attachParticipant = (
      p: RemoteParticipant | LocalParticipant,
      isLocal: boolean,
    ) => {
      const pid = identityFor(participants, p.identity) ?? p.identity;
      p.trackPublications.forEach((pub) => {
        if (pub.kind === Track.Kind.Video && pub.track) {
          upsert(pid, p.name || p.identity, isLocal, pub.track.mediaStreamTrack);
        }
      });
      p.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Video) {
          upsert(pid, p.name || p.identity, isLocal, track.mediaStreamTrack);
        }
      });
      p.on(RoomEvent.TrackUnsubscribed, (track) => {
        if (track.kind === Track.Kind.Video) {
          upsert(pid, p.name || p.identity, isLocal, null);
        }
      });
    };

    room
      .connect(media.url, media.token, { autoSubscribe: true })
      .then(async () => {
        if (cancelled) return;
        setConnected(true);
        attachParticipant(room.localParticipant, true);
        room.remoteParticipants.forEach((p) => attachParticipant(p, false));
        room.on(RoomEvent.ParticipantConnected, (p) => attachParticipant(p, false));
        if (canPublish) {
          await room.localParticipant.setCameraEnabled(true);
          await room.localParticipant.setMicrophoneEnabled(true);
        } else {
          await room.localParticipant.setCameraEnabled(false);
          await room.localParticipant.setMicrophoneEnabled(false);
        }
      })
      .catch(() => {
        if (!cancelled) setConnected(false);
      });

    return () => {
      cancelled = true;
      room.disconnect();
      roomRef.current = null;
      setTiles([]);
      setConnected(false);
    };
  }, [media?.url, media?.token, media?.identity, canPublish, participants]);

  return { tiles, connected, livekitAvailable: Boolean(media?.url && media?.token) };
}

export function LiveKitVideoTile({
  track,
  name,
  large,
}: {
  track: MediaStreamTrack | null;
  name: string;
  large?: boolean;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !track) return;
    el.srcObject = new MediaStream([track]);
  }, [track]);

  if (!track) return null;
  return (
    <video
      ref={ref}
      autoPlay
      playsInline
      muted
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        objectFit: "cover",
        opacity: 0.9,
        borderRadius: large ? 16 : 12,
      }}
    />
  );
}
