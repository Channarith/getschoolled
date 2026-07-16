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
  // True once an initial connect attempt has failed (bad/expired token, wrong
  // LiveKit secret, endpoint unreachable). We surface this so the UI can show a
  // calm "live A/V unavailable" note instead of a silent break, and we do NOT
  // retry — retrying a doomed token is what produced the endless "WebSocket is
  // closed / abort connection attempt / cannot send signal request" console storm.
  const [connectFailed, setConnectFailed] = useState(false);
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
      setConnectFailed(false);
      setTiles([]);
      setAudioTracks([]);
      return;
    }

    let cancelled = false;
    setConnectFailed(false);
    const room = new Room({
      adaptiveStream: true,
      dynacast: true,
      // Bound reconnection. livekit-client otherwise retries a dropped socket
      // ~10 times with backoff — against a mis-keyed / unreachable LiveKit that
      // becomes an endless "WebSocket closed → reconnecting → attempt N" storm
      // in the console (the class runs fine over AI narration + polling). Allow
      // a couple of quick retries to ride out a real network blip, then give up
      // and surface the calm "unavailable" state instead of looping forever.
      reconnectPolicy: {
        nextRetryDelayInMs: (ctx) => (ctx.retryCount >= 2 ? null : 300 * (ctx.retryCount + 1)),
      },
    });
    roomRef.current = room;

    // The socket dropped and reconnection was exhausted (or never succeeded).
    // Mark the failure once and stop; don't tear down again if this is our own
    // cleanup disconnect.
    room.on(RoomEvent.Disconnected, () => {
      if (cancelled) return;
      setConnected(false);
      setConnectFailed(true);
      setTiles([]);
      setAudioTracks([]);
    });

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
        // Initial connect failed. Tear the room down so the SDK stops trying to
        // reconnect (which floods the console) and mark the failure once. The
        // room keeps working over the AI-narration + polling path.
        void room.disconnect().catch(() => undefined);
        if (!cancelled) {
          setConnected(false);
          setConnectFailed(true);
        }
      });

    return () => {
      cancelled = true;
      void room.disconnect().catch(() => undefined);
      roomRef.current = null;
      setTiles([]);
      setAudioTracks([]);
      setConnected(false);
    };
  }, [media?.url, media?.token, media?.identity, canPublish]);

  return {
    tiles,
    audioTracks,
    connected,
    connectFailed,
    livekitAvailable: Boolean(media?.url && media?.token),
  };
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
