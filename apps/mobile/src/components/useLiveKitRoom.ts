import { useCallback, useEffect, useRef, useState } from "react";
import { Platform } from "react-native";

import type { LiveKitMedia } from "../api";
import { ensureCameraPermission } from "./cameraPermission";
import { loadLiveKit } from "./liveKitRuntime";

import type {
  Room as LKRoom,
  LocalParticipant,
  RemoteParticipant,
} from "livekit-client";

/** Just the fields we need to map a LiveKit identity to our roster tile. */
type RosterEntry = { id: string; identity?: string };

type TileTrack = { participantId: string; track: object };

/** Always use the front / selfie camera for live-class profile tiles. */
const SELFIE_CAMERA = { facingMode: "user" as const };

/**
 * Single shared LiveKit connection for a mobile live room.
 *
 * Mirrors the web ``useLiveKitRoom``: it connects ONCE (not once-per-tile, which
 * spun up N rooms and showed an arbitrary track under the wrong seat) and keeps a
 * map of participant id -> their published video track. ``trackFor(id)`` then
 * lets every seat render ITS OWN person's camera in the top of their profile
 * card — never as a floating PiP over the slide.
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

  // When connect races ahead of the roster, tracks may be keyed by LiveKit
  // identity. Remap them onto participant ids once the roster catches up so
  // SeatTile's trackFor(p.id) resolves.
  useEffect(() => {
    if (!participants.length) return;
    setTracks((prev) => {
      let changed = false;
      const byId = new Map<string, object>();
      for (const t of prev) {
        const match = participants.find(
          (p) => p.id === t.participantId || p.identity === t.participantId,
        );
        const key = match?.id ?? t.participantId;
        if (key !== t.participantId) changed = true;
        byId.set(key, t.track);
      }
      if (!changed && byId.size === prev.length) return prev;
      return Array.from(byId.entries()).map(([participantId, track]) => ({
        participantId,
        track,
      }));
    });
  }, [participants]);

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
    const { Room, RoomEvent, Track, ParticipantEvent } = lk.client;

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
      // Participant-level events (RoomEvent string constants match, but prefer
      // ParticipantEvent when available so we don't miss remote cameras).
      const subEvt = ParticipantEvent?.TrackSubscribed ?? RoomEvent.TrackSubscribed;
      const unsubEvt = ParticipantEvent?.TrackUnsubscribed ?? RoomEvent.TrackUnsubscribed;
      p.on(subEvt, (t: { kind: string }) => {
        if (t.kind === Track.Kind.Video) upsert(idFor(p.identity), t as object);
      });
      p.on(unsubEvt, (t: { kind: string }) => {
        if (t.kind === Track.Kind.Video) upsert(idFor(p.identity), null);
      });
    };

    void (async () => {
      try {
        // LiveKit docs: iOS needs an active AVAudioSession before mic/camera.
        if (Platform.OS === "ios") await AudioSession.startAudioSession();
        room = new Room({ videoCaptureDefaults: SELFIE_CAMERA });
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
        // the room. Android must grant CAMERA at runtime first or publish fails.
        try {
          if (await ensureCameraPermission()) {
            await room.localParticipant.setCameraEnabled(true, SELFIE_CAMERA);
          }
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
    const { Track } = loadLiveKit()?.client ?? {};
    try {
      if (enabled) {
        const allowed = await ensureCameraPermission();
        if (!allowed) return false;
      }
      await room.localParticipant.setCameraEnabled(
        enabled,
        enabled ? SELFIE_CAMERA : undefined,
      );
      // Immediately refresh the local tile map — LocalTrackPublished can race
      // the roster identity remap and leave the "You" seat without a track.
      const pid = idFor(room.localParticipant.identity);
      const cam = Track
        ? room.localParticipant.getTrackPublication(Track.Source.Camera)
        : undefined;
      setTracks((prev) => {
        const rest = prev.filter(
          (t) =>
            t.participantId !== pid
            && t.participantId !== room.localParticipant.identity,
        );
        if (enabled && cam?.track) {
          return [...rest, { participantId: pid, track: cam.track as object }];
        }
        return rest;
      });
      return true;
    } catch {
      return false;
    }
  }, [idFor]);

  const trackFor = useCallback(
    (participantId: string, identity?: string): object | null => {
      const hit = tracks.find(
        (t) =>
          t.participantId === participantId
          || (identity != null && identity !== "" && t.participantId === identity),
      );
      return hit?.track ?? null;
    },
    [tracks],
  );

  return { trackFor, setCameraEnabled, connected };
}
