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

export type AudioStream = { participantId: string; track: MediaStreamTrack };

export function useLiveKitRoom(
  media: LiveKitMedia | null | undefined,
  participants: LiveParticipant[],
  canPublish: boolean,
) {
  const [tiles, setTiles] = useState<TileStream[]>([]);
  // Remote audio tracks, played through hidden <audio> elements so you can HEAR
  // other participants. (The video tiles stay muted; a muted <video> can't play
  // sound, which is why audio was previously silent.) Local mic is never played
  // back here — that would echo your own voice.
  const [audioTracks, setAudioTracks] = useState<AudioStream[]>([]);
  const [connected, setConnected] = useState(false);
  const roomRef = useRef<Room | null>(null);
  // Keep the latest participant roster in a ref. It is only used to map a
  // LiveKit identity to our internal participant id (for the display tile). We
  // deliberately DO NOT put ``participants`` in the connect effect's deps: that
  // array gets a fresh reference on every ~3s poll, which would tear down and
  // reconnect the LiveKit room on every tick (a new session each time), causing
  // an endless "disconnect from room / abort connection attempt" storm.
  const participantsRef = useRef<LiveParticipant[]>(participants);
  useEffect(() => {
    participantsRef.current = participants;
  }, [participants]);

  useEffect(() => {
    if (!media?.url || !media.token) {
      setConnected(false);
      setTiles([]);
      setAudioTracks([]);
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

    const upsertAudio = (participantId: string, track: MediaStreamTrack | null) => {
      setAudioTracks((prev) => {
        const rest = prev.filter((a) => a.participantId !== participantId);
        return track ? [...rest, { participantId, track }] : rest;
      });
    };

    const attachParticipant = (
      p: RemoteParticipant | LocalParticipant,
      isLocal: boolean,
    ) => {
      const pid = identityFor(participantsRef.current, p.identity) ?? p.identity;
      p.trackPublications.forEach((pub) => {
        if (pub.kind === Track.Kind.Video && pub.track) {
          upsert(pid, p.name || p.identity, isLocal, pub.track.mediaStreamTrack);
        } else if (pub.kind === Track.Kind.Audio && pub.track && !isLocal) {
          upsertAudio(pid, pub.track.mediaStreamTrack);
        }
      });
      p.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Video) {
          upsert(pid, p.name || p.identity, isLocal, track.mediaStreamTrack);
        } else if (track.kind === Track.Kind.Audio && !isLocal) {
          upsertAudio(pid, track.mediaStreamTrack);
        }
      });
      p.on(RoomEvent.TrackUnsubscribed, (track) => {
        if (track.kind === Track.Kind.Video) {
          upsert(pid, p.name || p.identity, isLocal, null);
        } else if (track.kind === Track.Kind.Audio) {
          upsertAudio(pid, null);
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
      setAudioTracks([]);
      setConnected(false);
    };
  }, [media?.url, media?.token, media?.identity, canPublish]);

  return { tiles, audioTracks, connected, livekitAvailable: Boolean(media?.url && media?.token) };
}

/** Hidden audio sink for a remote participant's mic (autoplays, NOT muted). */
export function LiveKitAudio({ track }: { track: MediaStreamTrack }) {
  const ref = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.srcObject = new MediaStream([track]);
    void el.play().catch(() => undefined); // some browsers need a user gesture
  }, [track]);
  return <audio ref={ref} autoPlay style={{ display: "none" }} />;
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
