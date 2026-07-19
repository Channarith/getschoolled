import { useCallback, useEffect, useRef, useState } from "react";

import type { LiveKitMedia } from "../api";
import {
  applyLiveKitAudioRoute,
  asLiveKitAudioSession,
  beginLiveKitAudio,
  endLiveKitAudio,
} from "./liveKitAudio";
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

function friendlyConnectError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err || "");
  const lower = raw.toLowerCase();
  if (!raw.trim()) return "Could not connect to live video.";
  if (lower.includes("permission") || lower.includes("notallowed")) {
    return "Camera or microphone permission was denied.";
  }
  if (lower.includes("network") || lower.includes("websocket") || lower.includes("failed to fetch")) {
    return "Live video network error. Check your connection and try again.";
  }
  if (lower.includes("token") || lower.includes("unauthorized") || lower.includes("403")) {
    return "Live video session expired. Leave and rejoin the class.";
  }
  return raw.length > 160 ? `${raw.slice(0, 157)}…` : raw;
}

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
  const [connectError, setConnectError] = useState("");
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
      if (connectEnabled && (!media?.url || !media.token)) {
        setConnectError("Live video credentials are missing. Leave and rejoin the class.");
      } else {
        setConnectError("");
      }
      return;
    }
    const lk = loadLiveKit();
    if (!lk) {
      setConnected(false);
      setTracks([]);
      setConnectError("Live video is unavailable in this build. Reinstall the Salareen app.");
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
        setConnectError("");
        // Speaker-first session BEFORE connect so iOS doesn't land on earpiece /
        // soloAmbient (which silences AI teacher TTS). Learners keep playback
        // category until they hold the floor.
        const mediaPreset = (lk.rn as { AndroidAudioTypePresets?: { media?: Record<string, unknown> } })
          .AndroidAudioTypePresets?.media;
        await beginLiveKitAudio(asLiveKitAudioSession(AudioSession), {
          micEnabled: canPublishRef.current,
          androidMediaOptions: mediaPreset,
        });
        if (cancelled) return;
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
        setConnectError("");
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
        // Camera/mic getUserMedia can reset AVAudioSession — re-assert speaker.
        await applyLiveKitAudioRoute(canPublishRef.current);
        const cam = room.localParticipant.getTrackPublication(Track.Source.Camera);
        if (cam?.track) upsert(idFor(room.localParticipant.identity), cam.track);
      } catch (err) {
        if (cancelled) return;
        setConnected(false);
        setTracks([]);
        setConnectError(friendlyConnectError(err));
        try {
          room?.disconnect();
        } catch {
          /* ignore */
        }
        if (roomRef.current === room) roomRef.current = null;
      }
    })();

    return () => {
      cancelled = true;
      room?.disconnect();
      if (roomRef.current === room) roomRef.current = null;
      setConnected(false);
      setTracks([]);
      void endLiveKitAudio();
    };
  }, [connectEnabled, media?.url, media?.token, media?.identity, idFor]);

  // Toggle the mic without reconnecting when the floor flips.
  useEffect(() => {
    const room = roomRef.current;
    if (!room || !connected) return;
    void (async () => {
      try {
        await room.localParticipant.setMicrophoneEnabled(canPublish);
      } catch {
        /* mic unavailable */
      }
      // iosCategoryEnforce sets bare playAndRecord on getUserMedia(audio) —
      // restore defaultToSpeaker / playback so teacher TTS stays audible.
      await applyLiveKitAudioRoute(canPublish);
    })();
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

  /** True when the LiveKit Room object exists (may briefly lead React `connected`). */
  const hasRoom = useCallback(() => roomRef.current != null, []);

  /**
   * Wait briefly for an in-flight connect, then try the camera toggle.
   * Prefer this over gating purely on React `connected` — join used to race a
   * media-token refresh that left the UI disconnected while connect completed.
   */
  const ensureCameraToggle = useCallback(async (enabled: boolean): Promise<"ok" | "not_ready" | "denied"> => {
    if (roomRef.current) {
      const ok = await setCameraEnabled(enabled);
      return ok ? "ok" : "denied";
    }
    // Give an in-flight connect up to ~2s before failing closed.
    for (let i = 0; i < 8; i += 1) {
      await new Promise<void>((resolve) => {
        setTimeout(resolve, 250);
      });
      if (roomRef.current) {
        const ok = await setCameraEnabled(enabled);
        return ok ? "ok" : "denied";
      }
    }
    return "not_ready";
  }, [setCameraEnabled]);

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

  return {
    trackFor,
    setCameraEnabled,
    ensureCameraToggle,
    hasRoom,
    connected,
    connectError,
  };
}
