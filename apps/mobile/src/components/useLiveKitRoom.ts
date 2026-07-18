import { useCallback, useEffect, useRef, useState } from "react";
import { Platform } from "react-native";

import type { LiveKitMedia } from "../api";
import { loadLiveKit } from "./liveKitRuntime";

import type {
  Room as LKRoom,
  LocalParticipant,
  RemoteParticipant,
} from "livekit-client";

/** Just the fields we need to map a LiveKit identity to our roster tile. */
type RosterEntry = { id: string; identity?: string };

type TileTrack = { participantId: string; track: object };

/**
 * Single shared LiveKit connection for a mobile live room.
 *
 * Mirrors the web ``useLiveKitRoom``: it connects ONCE (not once-per-tile, which
 * spun up N rooms and showed an arbitrary track under the wrong seat) and keeps a
 * map of participant id -> their published video track. ``trackFor(id)`` then
 * lets every seat render ITS OWN person's camera — the local self-view under
 * "You" and each remote learner under their own name — so a group class shows
 * multiple live feeds instead of one PIP pinned to the host panel.
 */
export function useLiveKitRoom(
  media: LiveKitMedia | null | undefined,
  participants: RosterEntry[],
  /** True while this device holds the floor — gates the mic (audio mutex). */
  canPublish: boolean,
  connectEnabled = true,
) {
  const [tracks, setTracks] = useState<TileTrack[]>([]);
  const [connected, setConnected] = useState(false);
  const roomRef = useRef<LKRoom | null>(null);
  const canPublishRef = useRef(canPublish);
  canPublishRef.current = canPublish;
  // Latest roster kept in a ref so identity->id mapping is current WITHOUT the
  // connect effect depending on it (the roster gets a fresh reference every ~3s
  // poll, which would otherwise tear down and reconnect the room each tick).
  const rosterRef = useRef<RosterEntry[]>(participants);
  useEffect(() => {
    rosterRef.current = participants;
  }, [participants]);

  const idFor = useCallback((identity: string): string => {
    const p = rosterRef.current.find((x) => x.identity === identity);
    return p?.id ?? identity;
  }, []);

  useEffect(() => {
    if (!connectEnabled || !media?.url || !media.token) {
      setConnected(false);
      setTracks([]);
      return;
    }
    const lk = loadLiveKit();
    if (!lk) {
      setConnected(false);
      setTracks([]);
      return;
    }
    const { AudioSession } = lk.rn;
    const { Room, RoomEvent, Track } = lk.client;

    let cancelled = false;
    let room: LKRoom | null = null;

    const upsert = (participantId: string, track: object | null) => {
      setTracks((prev) => {
        const rest = prev.filter((t) => t.participantId !== participantId);
        return track ? [...rest, { participantId, track }] : rest;
      });
    };

    const attach = (p: RemoteParticipant | LocalParticipant) => {
      const pid = idFor(p.identity);
      p.trackPublications.forEach((pub) => {
        if (pub.kind === Track.Kind.Video && pub.track) upsert(pid, pub.track);
      });
      p.on(RoomEvent.TrackSubscribed, (t) => {
        if (t.kind === Track.Kind.Video) upsert(idFor(p.identity), t);
      });
      p.on(RoomEvent.TrackUnsubscribed, (t) => {
        if (t.kind === Track.Kind.Video) upsert(idFor(p.identity), null);
      });
    };

    void (async () => {
      try {
        // LiveKit docs: iOS needs an active AVAudioSession before mic/camera.
        if (Platform.OS === "ios") await AudioSession.startAudioSession();
        room = new Room();
        roomRef.current = room;
        // Reflect our own camera publish/unpublish into the self-view tile.
        room.on(RoomEvent.LocalTrackPublished, () => {
          const lp = room?.localParticipant;
          if (!lp) return;
          const cam = lp.getTrackPublication(Track.Source.Camera);
          upsert(idFor(lp.identity), cam?.track ?? null);
        });
        room.on(RoomEvent.LocalTrackUnpublished, () => {
          const lp = room?.localParticipant;
          if (lp) upsert(idFor(lp.identity), null);
        });
        room.on(RoomEvent.ParticipantConnected, (p) => attach(p));
        await room.connect(media.url, media.token, { autoSubscribe: true });
        if (cancelled) {
          room.disconnect();
          return;
        }
        setConnected(true);
        attach(room.localParticipant);
        room.remoteParticipants.forEach((p) => attach(p));
        // Everyone's camera turns on (video-call feel); the mic follows the
        // one-speaker mutex. Best-effort so a denied/absent camera never breaks
        // the room.
        try {
          await room.localParticipant.setCameraEnabled(true);
        } catch {
          /* no camera / permission denied */
        }
        try {
          await room.localParticipant.setMicrophoneEnabled(canPublishRef.current);
        } catch {
          /* mic unavailable */
        }
        const cam = room.localParticipant.getTrackPublication(Track.Source.Camera);
        if (cam?.track) upsert(idFor(room.localParticipant.identity), cam.track);
      } catch {
        setConnected(false);
        setTracks([]);
      }
    })();

    return () => {
      cancelled = true;
      room?.disconnect();
      roomRef.current = null;
      setConnected(false);
      setTracks([]);
      if (Platform.OS === "ios") {
        void AudioSession.stopAudioSession().catch(() => {});
      }
    };
  }, [connectEnabled, media?.url, media?.token, media?.identity, idFor]);

  // Toggle the mic without reconnecting when the floor flips.
  useEffect(() => {
    const room = roomRef.current;
    if (!room || !connected) return;
    void room.localParticipant.setMicrophoneEnabled(canPublish).catch(() => undefined);
  }, [canPublish, connected]);

  const setCameraEnabled = useCallback(async (enabled: boolean): Promise<boolean> => {
    const room = roomRef.current;
    if (!room) return false;
    try {
      await room.localParticipant.setCameraEnabled(enabled);
      return true;
    } catch {
      return false;
    }
  }, []);

  const trackFor = useCallback(
    (participantId: string): object | null =>
      tracks.find((t) => t.participantId === participantId)?.track ?? null,
    [tracks],
  );

  return { trackFor, setCameraEnabled, connected };
}
