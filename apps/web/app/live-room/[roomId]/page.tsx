"use client";

/**
 * Salareen Live Room — multi-user AI teaching session (Bigo/Mico-style grid).
 *
 * Architecture:
 *  - HTTP state (orchestrator /api/live-rooms/*): participants, chat, Q&A queue,
 *    slide sync, muting/banning — polled every 2s as a fallback and for moderation.
 *  - LiveKit WebRTC (livekit-client): actual audio/video tracks for each participant.
 *    The token minted at join time is used to connect to the LiveKit room.
 *  - AI host (Theodore): joins the room as a LiveKit agent worker; his audio is
 *    published as a remote track and appears in the host tile automatically.
 *
 * Room grid sizes: 4-seat (2×2), 6-seat (3×2), 9-seat (3×3).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ConnectionState,
  LocalParticipant,
  type Participant,
  ParticipantEvent,
  Room,
  RoomEvent,
  Track,
  type TrackPublication,
  type RemoteParticipant,
  type RemoteTrackPublication,
  createLocalVideoTrack,
  createLocalAudioTrack,
} from "livekit-client";

import {
  getLiveRoom,
  joinLiveRoom,
  leaveLiveRoom,
  liveRoomBan,
  liveRoomUnban,
  liveRoomReport,
  liveRoomDismissReport,
  liveRoomAdvance,
  liveRoomAsk,
  liveRoomChat,
  liveRoomMute,
  liveRoomRaiseHand,
  liveRoomCallNext,
  liveRoomFinishTurn,
  liveRoomLeaveQueue,
  liveRoomRecordStart,
  liveRoomRecordStop,
  type LiveParticipant,
  type LiveRoomJoin,
  type LiveRoomState,
} from "../../lib/api";
import { friendlyError } from "../../lib/errors";

// ---------------------------------------------------------------------------
// Constants & helpers
// ---------------------------------------------------------------------------
const ROOM_STORAGE_KEY = "salareen-live-participant";
const MODERATOR_STORAGE_KEY = "salareen-live-moderator";

function gridCols(roomSize: number) {
  if (roomSize <= 4) return 2;
  return 3;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

// ---------------------------------------------------------------------------
// Video tile component — renders a single participant (local or remote)
// ---------------------------------------------------------------------------
function VideoTile({
  participant,
  httpP,
  isLocal = false,
  hasFloor = false,
  isHost = false,
  large = false,
  onBan,
  onReport,
  showMod = false,
}: {
  participant?: Participant | null;
  httpP: LiveParticipant;
  isLocal?: boolean;
  hasFloor?: boolean;
  isHost?: boolean;
  large?: boolean;
  onBan?: () => void;
  onReport?: () => void;
  showMod?: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [hasVideo, setHasVideo] = useState(false);
  const [hasAudio, setHasAudio] = useState(false);

  // Attach LiveKit tracks to the video element
  useEffect(() => {
    if (!participant || !videoRef.current) return;

    const attachVideo = () => {
      const pub = isLocal
        ? (participant as LocalParticipant).getTrackPublication(Track.Source.Camera)
        : (participant as RemoteParticipant)
            .getTrackPublications()
            .find((p) => p.source === Track.Source.Camera);

      if (pub?.track && videoRef.current) {
        pub.track.attach(videoRef.current);
        setHasVideo(true);
      }
    };

    const checkAudio = () => {
      const pub = isLocal
        ? (participant as LocalParticipant).getTrackPublication(Track.Source.Microphone)
        : (participant as RemoteParticipant)
            .getTrackPublications()
            .find((p) => p.source === Track.Source.Microphone);
      setHasAudio(!!pub?.track);
    };

    participant.on(ParticipantEvent.TrackPublished, attachVideo);
    participant.on(ParticipantEvent.TrackSubscribed, attachVideo);
    participant.on(ParticipantEvent.TrackUnpublished, () => setHasVideo(false));
    participant.on(ParticipantEvent.TrackUnsubscribed, () => setHasVideo(false));
    participant.on(ParticipantEvent.TrackMuted, checkAudio);
    participant.on(ParticipantEvent.TrackUnmuted, checkAudio);

    attachVideo();
    checkAudio();

    return () => {
      participant.off(ParticipantEvent.TrackPublished, attachVideo);
      participant.off(ParticipantEvent.TrackSubscribed, attachVideo);
      participant.off(ParticipantEvent.TrackUnpublished, () => setHasVideo(false));
      participant.off(ParticipantEvent.TrackUnsubscribed, () => setHasVideo(false));
    };
  }, [participant, isLocal]);

  return (
    <div
      style={{
        position: "relative",
        borderRadius: large ? 16 : 12,
        overflow: "hidden",
        background: isHost
          ? "linear-gradient(145deg, #4c1d95 0%, #7c3aed 55%, #db2777 100%)"
          : "linear-gradient(145deg, #1e1b4b 0%, #312e81 100%)",
        border: hasFloor
          ? "2px solid #34d399"
          : httpP.hand_raised
          ? "2px solid #fbbf24"
          : "1px solid rgba(255,255,255,0.12)",
        minHeight: large ? 220 : 110,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
    >
      {/* Video track */}
      <video
        ref={videoRef}
        autoPlay
        muted={isLocal}
        playsInline
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: hasVideo ? 0.92 : 0,
          transition: "opacity 0.3s",
        }}
      />

      {/* Avatar fallback when no video */}
      {!hasVideo && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: large ? 48 : 28,
            fontWeight: 700,
            color: "rgba(255,255,255,0.9)",
          }}
        >
          {isHost ? "🎓" : initials(httpP.name)}
        </div>
      )}

      {/* Name bar */}
      <div
        style={{
          position: "relative",
          padding: "6px 10px",
          background: "linear-gradient(transparent, rgba(0,0,0,0.78))",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
        }}
      >
        <span style={{ fontWeight: 600 }}>
          {isHost ? "🎓 " : ""}
          {httpP.name}
        </span>
        <span style={{ display: "flex", gap: 3 }}>
          {hasFloor && <span title="Speaking">🎤</span>}
          {httpP.hand_raised && !hasFloor && <span title="Q&A queue">✋</span>}
          {(httpP.muted || httpP.muted_by_host) && <span title="Muted">🔇</span>}
          {!hasAudio && !isHost && <span title="No mic">🎙️</span>}
        </span>
      </div>

      {/* Moderator controls */}
      {showMod && onBan && (
        <button
          onClick={onBan}
          title={`Block ${httpP.name}`}
          style={{
            position: "absolute",
            top: 6,
            right: 6,
            fontSize: 11,
            padding: "2px 7px",
            borderRadius: 6,
            background: "rgba(220,38,38,0.9)",
            color: "#fff",
            border: "none",
            cursor: "pointer",
          }}
        >
          Block
        </button>
      )}
      {onReport && (
        <button
          onClick={onReport}
          title={`Report ${httpP.name}`}
          style={{
            position: "absolute",
            top: 6,
            left: 6,
            fontSize: 11,
            padding: "2px 7px",
            borderRadius: 6,
            background: "rgba(245,158,11,0.9)",
            color: "#1c1917",
            border: "none",
            cursor: "pointer",
          }}
        >
          Report
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function LiveRoomPage({ params }: { params: { roomId: string } }) {
  const roomId = decodeURIComponent(params.roomId);

  // HTTP state (room info, chat, Q&A)
  const [displayName, setDisplayName] = useState("");
  const [joinInfo, setJoinInfo] = useState<LiveRoomJoin | null>(null);
  const [room, setRoom] = useState<LiveRoomState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [chatDraft, setChatDraft] = useState("");
  const [askDraft, setAskDraft] = useState("");
  const [moderatorKey, setModeratorKey] = useState("");
  const [wasRemoved, setWasRemoved] = useState(false);
  const leftVoluntarily = useRef(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // LiveKit state
  const lkRoom = useRef<Room | null>(null);
  const [lkConnected, setLkConnected] = useState(false);
  const [lkParticipants, setLkParticipants] = useState<Map<string, Participant>>(new Map());
  const [localParticipant, setLocalParticipant] = useState<LocalParticipant | null>(null);
  const [micEnabled, setMicEnabled] = useState(false);
  const [camEnabled, setCamEnabled] = useState(false);
  const [connState, setConnState] = useState<ConnectionState>(ConnectionState.Disconnected);

  // Derived state
  const me = useMemo(() => {
    const id = joinInfo?.participant.id;
    if (!id || !room) return joinInfo?.participant ?? null;
    return room.participants.find((p) => p.id === id) ?? joinInfo.participant;
  }, [joinInfo, room]);

  const cols = gridCols(room?.room_size ?? 6);

  const myQueuePos = useMemo(() => {
    if (!me || !room?.speaking_queue) return 0;
    return (
      room.speaking_queue.find(
        (e) => e.participant_id === me.id && e.status === "waiting"
      )?.position ?? 0
    );
  }, [me, room]);

  const hasFloor = me?.id === room?.floor_participant_id;
  const inQueue = Boolean(
    room?.speaking_queue?.some(
      (e) =>
        e.participant_id === me?.id &&
        (e.status === "waiting" || e.status === "speaking")
    )
  );

  // ---------------------------------------------------------------------------
  // HTTP polling
  // ---------------------------------------------------------------------------
  const refresh = useCallback(async () => {
    try {
      const mod =
        moderatorKey ||
        sessionStorage.getItem(`${MODERATOR_STORAGE_KEY}:${roomId}`) ||
        "";
      setRoom(await getLiveRoom(roomId, mod));
    } catch (e) {
      // offline — keep stale state
    }
  }, [roomId, moderatorKey]);

  useEffect(() => {
    const stored = sessionStorage.getItem(`${ROOM_STORAGE_KEY}:${roomId}`);
    if (stored) {
      try {
        const p = JSON.parse(stored) as { name: string };
        setDisplayName(p.name);
      } catch { /* ignore */ }
    }
    const mod = sessionStorage.getItem(`${MODERATOR_STORAGE_KEY}:${roomId}`);
    if (mod) setModeratorKey(mod);
    void refresh();
  }, [roomId, refresh]);

  useEffect(() => {
    if (!joinInfo || !room || leftVoluntarily.current) return;
    const stillHere = room.participants.some((p) => p.id === joinInfo.participant.id);
    if (!stillHere) {
      setWasRemoved(true);
      sessionStorage.removeItem(`${ROOM_STORAGE_KEY}:${roomId}`);
      void disconnectLiveKit();
    }
  }, [room, joinInfo, roomId]);

  useEffect(() => {
    if (!joinInfo) return;
    const timer = setInterval(() => void refresh(), 2500);
    return () => clearInterval(timer);
  }, [joinInfo, refresh]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [room?.chat.length]);

  // ---------------------------------------------------------------------------
  // LiveKit connection helpers
  // ---------------------------------------------------------------------------
  const syncLkParticipants = useCallback((r: Room) => {
    const map = new Map<string, Participant>();
    map.set(r.localParticipant.identity, r.localParticipant);
    r.remoteParticipants.forEach((p) => map.set(p.identity, p));
    setLkParticipants(new Map(map));
  }, []);

  async function connectLiveKit(token: string, url: string) {
    if (lkRoom.current) return; // already connected
    const r = new Room({
      adaptiveStream: true,
      dynacast: true,
      publishDefaults: {
        simulcast: true,
        stopMicTrackOnMute: false,
      },
    });

    r.on(RoomEvent.Connected, () => {
      setLkConnected(true);
      setConnState(ConnectionState.Connected);
      setLocalParticipant(r.localParticipant);
      syncLkParticipants(r);
    });
    r.on(RoomEvent.Disconnected, () => {
      setLkConnected(false);
      setConnState(ConnectionState.Disconnected);
      setLocalParticipant(null);
      setLkParticipants(new Map());
    });
    r.on(RoomEvent.ConnectionStateChanged, (state) => {
      setConnState(state);
    });
    r.on(RoomEvent.ParticipantConnected, () => syncLkParticipants(r));
    r.on(RoomEvent.ParticipantDisconnected, () => syncLkParticipants(r));
    r.on(RoomEvent.TrackSubscribed, () => syncLkParticipants(r));
    r.on(RoomEvent.TrackUnsubscribed, () => syncLkParticipants(r));
    r.on(RoomEvent.TrackPublished, () => syncLkParticipants(r));
    r.on(RoomEvent.TrackUnpublished, () => syncLkParticipants(r));

    // Receive AI slide narration / teaching data from agent via data channel
    r.on(RoomEvent.DataReceived, (payload, participant) => {
      try {
        const msg = JSON.parse(new TextDecoder().decode(payload)) as {
          type: string;
          text?: string;
          slide?: { index: number; title: string; narration: string };
        };
        if (msg.type === "slide_sync") {
          void refresh(); // sync slide from HTTP state
        }
      } catch { /* ignore unparseable packets */ }
    });

    lkRoom.current = r;
    const lkUrl = url || process.env.NEXT_PUBLIC_LIVEKIT_URL || "wss://livekit.salareen.com";

    try {
      await r.connect(lkUrl, token);
    } catch (e) {
      console.warn("LiveKit connect failed (offline mode):", e);
      // Gracefully degrade to HTTP-only mode
    }
  }

  async function disconnectLiveKit() {
    if (!lkRoom.current) return;
    try {
      await lkRoom.current.disconnect();
    } catch { /* ignore */ }
    lkRoom.current = null;
    setLkConnected(false);
    setLocalParticipant(null);
    setLkParticipants(new Map());
  }

  async function toggleMic() {
    if (!lkRoom.current?.localParticipant) return;
    const lp = lkRoom.current.localParticipant;
    if (micEnabled) {
      await lp.setMicrophoneEnabled(false);
      setMicEnabled(false);
    } else {
      await lp.setMicrophoneEnabled(true);
      setMicEnabled(true);
    }
  }

  async function toggleCam() {
    if (!lkRoom.current?.localParticipant) return;
    const lp = lkRoom.current.localParticipant;
    if (camEnabled) {
      await lp.setCameraEnabled(false);
      setCamEnabled(false);
    } else {
      await lp.setCameraEnabled(true);
      setCamEnabled(true);
    }
  }

  // ---------------------------------------------------------------------------
  // Join/leave room
  // ---------------------------------------------------------------------------
  async function handleJoin() {
    const name = displayName.trim();
    if (!name) { setError("Enter your name to join."); return; }
    setBusy(true);
    setError("");
    try {
      const stored = sessionStorage.getItem(`${ROOM_STORAGE_KEY}:${roomId}`);
      let identity = "";
      if (stored) {
        try { identity = (JSON.parse(stored) as { identity?: string }).identity ?? ""; }
        catch { identity = ""; }
      }
      const info = await joinLiveRoom(
        roomId,
        name,
        identity || `web-${name.toLowerCase().replace(/\s+/g, "-")}`
      );
      setJoinInfo(info);
      setRoom(info.room);
      sessionStorage.setItem(
        `${ROOM_STORAGE_KEY}:${roomId}`,
        JSON.stringify({ name, participantId: info.participant.id, identity: info.participant.identity })
      );

      // Connect to LiveKit with the token from the server
      if (info.media?.token && info.media?.url) {
        await connectLiveKit(info.media.token, info.media.url);
        // Start with mic on by default
        if (lkRoom.current?.localParticipant) {
          await lkRoom.current.localParticipant.setMicrophoneEnabled(true);
          setMicEnabled(true);
        }
      }
    } catch (e) {
      const msg = friendlyError(e, "Could not join room");
      if (msg.toLowerCase().includes("block") || msg.includes("403")) {
        setWasRemoved(true);
      }
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  async function handleLeave() {
    if (!me) return;
    leftVoluntarily.current = true;
    setBusy(true);
    try {
      await disconnectLiveKit();
      await leaveLiveRoom(roomId, me.id);
      sessionStorage.removeItem(`${ROOM_STORAGE_KEY}:${roomId}`);
      window.location.href = "/group-classes";
    } catch (e) {
      setError(friendlyError(e, "Could not leave"));
    } finally {
      setBusy(false);
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (!leftVoluntarily.current) void disconnectLiveKit();
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Chat / Q&A / moderation actions
  // ---------------------------------------------------------------------------
  async function sendChat() {
    if (!me || !chatDraft.trim()) return;
    setBusy(true);
    try { setRoom(await liveRoomChat(roomId, me.id, chatDraft.trim())); setChatDraft(""); }
    catch (e) { setError(friendlyError(e, "Chat failed")); }
    finally { setBusy(false); }
  }

  async function askQuestion() {
    if (!me || !askDraft.trim()) return;
    setBusy(true);
    try {
      const res = await liveRoomAsk(roomId, me.id, askDraft.trim());
      setRoom(res.room);
      if (res.queued) {
        setError(`You're #${res.queue_position ?? myQueuePos} in the Q&A queue. Theodore will call on you.`);
      } else { setError(""); }
      setAskDraft("");
    } catch (e) { setError(friendlyError(e, "Question failed")); }
    finally { setBusy(false); }
  }

  async function toggleHand() {
    if (!me) return;
    setBusy(true);
    try {
      if (inQueue && !hasFloor) setRoom(await liveRoomLeaveQueue(roomId, me.id));
      else setRoom(await liveRoomRaiseHand(roomId, me.id, askDraft.trim()));
    } catch (e) { setError(friendlyError(e, "Queue failed")); }
    finally { setBusy(false); }
  }

  async function callNext() {
    if (!moderatorKey) return;
    setBusy(true);
    try { setRoom(await liveRoomCallNext(roomId, moderatorKey)); setError(""); }
    catch (e) { setError(friendlyError(e, "Could not call next")); }
    finally { setBusy(false); }
  }

  async function finishTurn() {
    setBusy(true);
    try {
      const pid = room?.floor_participant_id || me?.id || "";
      setRoom(await liveRoomFinishTurn(roomId, pid, moderatorKey));
    } catch (e) { setError(friendlyError(e, "End turn failed")); }
    finally { setBusy(false); }
  }

  async function httpToggleMute() {
    if (!me) return;
    setBusy(true);
    try {
      setRoom(await liveRoomMute(roomId, me.id, !me.muted));
      // Sync to LiveKit mic state
      if (lkRoom.current?.localParticipant) {
        await lkRoom.current.localParticipant.setMicrophoneEnabled(me.muted);
        setMicEnabled(me.muted);
      }
    } catch (e) { setError(friendlyError(e, "Mute failed")); }
    finally { setBusy(false); }
  }

  async function banLearner(participantId: string, name: string) {
    if (!moderatorKey) return;
    const reason = window.prompt(`Block ${name}? Optional reason:`) ?? "";
    if (reason === null) return;
    setBusy(true);
    try { setRoom(await liveRoomBan(roomId, participantId, reason, moderatorKey)); }
    catch (e) { setError(friendlyError(e, "Ban failed")); }
    finally { setBusy(false); }
  }

  async function unbanLearner(identity: string) {
    if (!moderatorKey) return;
    setBusy(true);
    try { setRoom(await liveRoomUnban(roomId, identity, moderatorKey)); }
    catch (e) { setError(friendlyError(e, "Unban failed")); }
    finally { setBusy(false); }
  }

  async function reportLearner(participantId: string, name: string) {
    if (!me?.id) return;
    const reason = window.prompt(`Report ${name} — what happened?`)?.trim() ?? "";
    if (!reason) return;
    const category = window.prompt("Category: spam, harassment, inappropriate, disruptive, other", "other")?.trim().toLowerCase() || "other";
    setBusy(true);
    try {
      await liveRoomReport(roomId, me.id, participantId, reason, category);
      window.alert("Report submitted.");
    } catch (e) { setError(friendlyError(e, "Report failed")); }
    finally { setBusy(false); }
  }

  // ---------------------------------------------------------------------------
  // Removed / banned screen
  // ---------------------------------------------------------------------------
  if (wasRemoved) {
    return (
      <main className="container" style={{ maxWidth: 480 }}>
        <h1>Removed from class</h1>
        <p className="muted">You were removed from this live room and cannot rejoin.</p>
        <button onClick={() => { window.location.href = "/group-classes"; }}>Back</button>
      </main>
    );
  }

  // ---------------------------------------------------------------------------
  // Join screen
  // ---------------------------------------------------------------------------
  if (!joinInfo) {
    return (
      <main className="container" style={{ maxWidth: 480 }}>
        <h1>Salareen Live Room</h1>
        <p className="muted">Theodore (AI) hosts · {room?.room_size ?? 6}-seat grid · actual video + audio</p>
        {room && (
          <div className="card" style={{ marginBottom: 12 }}>
            <strong>{room.title}</strong>
            <div className="muted">{room.learner_count}/{room.learner_capacity} learners · {room.seats_left} seats left</div>
          </div>
        )}
        {error && <div className="card" style={{ borderColor: "#ff6b6b", marginBottom: 12 }}>{error}</div>}
        <div className="card">
          <label>
            <div className="muted">Your display name</div>
            <input
              style={{ width: "100%", marginTop: 6 }}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Ada"
              onKeyDown={(e) => e.key === "Enter" && void handleJoin()}
            />
          </label>
          <button
            onClick={() => void handleJoin()}
            disabled={busy}
            style={{ marginTop: 12, background: "#7c3aed", color: "#fff", width: "100%" }}
          >
            {busy ? "Joining…" : "Enter live room"}
          </button>
        </div>
      </main>
    );
  }

  // ---------------------------------------------------------------------------
  // In-room layout
  // ---------------------------------------------------------------------------
  const learners = (room?.participants ?? []).filter((p) => p.role !== "host");
  const hostP = room?.host ?? null;
  const emptySlots = Math.max(0, (room?.learner_capacity ?? 0) - learners.length);

  const connBadge =
    connState === ConnectionState.Connected
      ? { label: "● Live", color: "#34d399" }
      : connState === ConnectionState.Connecting
      ? { label: "◌ Connecting…", color: "#fbbf24" }
      : { label: "○ Offline", color: "#9ca3af" };

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #0f0720 0%, #1a0a2e 40%, #2d1b4e 100%)",
        color: "#f8fafc",
        padding: "12px 16px 24px",
      }}
    >
      {/* Header */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
        <div>
          <div style={{ fontSize: 12, color: "#c4b5fd" }}>
            Salareen Live · {roomId} ·{" "}
            <span style={{ color: connBadge.color }}>{connBadge.label}</span>
          </div>
          <h2 style={{ margin: "4px 0 0", fontSize: 20 }}>{room?.title ?? "Live class"}</h2>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
          {room?.recording.status === "recording" && (
            <span style={{ color: "#fca5a5", fontWeight: 600 }}>● REC</span>
          )}
          <span style={{ color: "#ddd6fe" }}>👥 {room?.learner_count ?? 0} learners</span>
          {/* WebRTC media controls */}
          <button
            onClick={() => void toggleMic()}
            disabled={!lkConnected}
            style={{ fontSize: 18, background: micEnabled ? "#1d4ed8" : "rgba(255,255,255,0.1)", color: "#fff", border: "none", borderRadius: 8, padding: "4px 10px", cursor: "pointer" }}
            title={micEnabled ? "Mute microphone" : "Unmute microphone"}
          >
            {micEnabled ? "🎙️" : "🔇"}
          </button>
          <button
            onClick={() => void toggleCam()}
            disabled={!lkConnected}
            style={{ fontSize: 18, background: camEnabled ? "#1d4ed8" : "rgba(255,255,255,0.1)", color: "#fff", border: "none", borderRadius: 8, padding: "4px 10px", cursor: "pointer" }}
            title={camEnabled ? "Turn off camera" : "Turn on camera"}
          >
            {camEnabled ? "📹" : "📷"}
          </button>
        </div>
      </header>

      {error && (
        <div style={{ background: "rgba(239,68,68,0.2)", border: "1px solid #ef4444", borderRadius: 8, padding: 8, marginBottom: 10 }}>
          {error}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.4fr) minmax(280px, 1fr)",
          gap: 14,
          alignItems: "start",
        }}
      >
        {/* Left: video grid */}
        <section>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: cols <= 2 ? "1.2fr 1fr" : "1.3fr repeat(2, 1fr)",
              gridTemplateRows: `repeat(${cols <= 2 ? 2 : 3}, minmax(100px, 1fr))`,
              gap: 8,
              marginBottom: 12,
            }}
          >
            {/* AI host tile — full left column */}
            {hostP && (
              <div style={{ gridRow: `span ${cols <= 2 ? 2 : 3}`, minHeight: 220 }}>
                <VideoTile
                  participant={lkParticipants.get("theodore-ai") ?? null}
                  httpP={hostP}
                  isHost
                  large
                  hasFloor={!room?.floor_participant_id}
                />
              </div>
            )}

            {/* Learner tiles */}
            {learners.map((p) => {
              const lkP = lkParticipants.get(p.identity) ?? null;
              const isMe = p.id === me?.id;
              return (
                <div key={p.id} style={{ position: "relative" }}>
                  <VideoTile
                    participant={lkP ?? (isMe ? localParticipant : null)}
                    httpP={p}
                    isLocal={isMe}
                    hasFloor={p.id === room?.floor_participant_id}
                    onBan={moderatorKey && !isMe ? () => void banLearner(p.id, p.name) : undefined}
                    onReport={!isMe ? () => void reportLearner(p.id, p.name) : undefined}
                    showMod={!!moderatorKey}
                  />
                </div>
              );
            })}

            {/* Empty seats */}
            {Array.from({ length: emptySlots }).map((_, i) => (
              <div
                key={`empty-${i}`}
                style={{
                  borderRadius: 12,
                  border: "1px dashed rgba(255,255,255,0.15)",
                  minHeight: 110,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "rgba(255,255,255,0.35)",
                  fontSize: 12,
                }}
              >
                Open seat
              </div>
            ))}
          </div>

          {/* Q&A queue */}
          {(room?.speaking_queue?.length ?? 0) > 0 && (
            <div style={{ marginBottom: 12, padding: 12, borderRadius: 12, background: "rgba(52,211,153,0.08)", border: "1px solid rgba(52,211,153,0.25)" }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#6ee7b7", marginBottom: 8 }}>Q&amp;A queue — take turns</div>
              {room?.floor_holder ? (
                <div style={{ fontSize: 13, marginBottom: 8, color: "#a7f3d0" }}>
                  🎤 Now speaking: <strong>{room.floor_holder.name}</strong>
                </div>
              ) : null}
              <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#d1fae5" }}>
                {(room?.speaking_queue ?? []).filter((e) => e.status === "waiting").map((e) => (
                  <li key={e.id} style={{ marginBottom: 4 }}>
                    #{e.position} {e.name}{e.question ? ` — "${e.question}"` : ""}
                  </li>
                ))}
              </ol>
              {myQueuePos > 0 && !hasFloor && (
                <div style={{ marginTop: 8, fontSize: 12, color: "#fcd34d" }}>You are #{myQueuePos} in line.</div>
              )}
            </div>
          )}

          {/* Slide */}
          {room?.slide && (
            <div style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, padding: 14 }}>
              <div style={{ fontSize: 12, color: "#c4b5fd", marginBottom: 4 }}>Slide {room.slide.index + 1}</div>
              <strong>{room.slide.title}</strong>
              <p style={{ margin: "8px 0 0", color: "#e9d5ff", fontSize: 14, lineHeight: 1.5 }}>
                {room.slide.narration || room.slide.body}
              </p>
            </div>
          )}
        </section>

        {/* Right: chat + controls */}
        <aside style={{ display: "flex", flexDirection: "column", gap: 10, minHeight: 420 }}>
          {/* Chat */}
          <div style={{ flex: 1, background: "rgba(0,0,0,0.35)", borderRadius: 12, border: "1px solid rgba(255,255,255,0.08)", padding: 10, overflowY: "auto", maxHeight: 320, minHeight: 200 }}>
            {(room?.chat ?? []).map((m) => (
              <div key={m.id} style={{ marginBottom: 8, fontSize: 13, lineHeight: 1.4 }}>
                <span style={{ color: m.from_id === "system" ? "#a78bfa" : m.from_id === "theodore-ai" ? "#34d399" : "#fbbf24", fontWeight: 600 }}>
                  {m.from_name}:
                </span>{" "}
                <span style={{ color: "#e2e8f0" }}>{m.text}</span>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Chat input */}
          <div style={{ display: "flex", gap: 6 }}>
            <input
              value={chatDraft}
              onChange={(e) => setChatDraft(e.target.value)}
              placeholder="Say something…"
              style={{ flex: 1, borderRadius: 8, border: "1px solid #4c1d95", padding: "8px 10px", background: "#1e1033", color: "#fff" }}
              onKeyDown={(e) => e.key === "Enter" && void sendChat()}
              disabled={busy || me?.muted || me?.muted_by_host}
            />
            <button onClick={() => void sendChat()} disabled={busy} style={{ background: "#7c3aed", color: "#fff" }}>Chat</button>
          </div>

          {/* Ask input */}
          <div style={{ display: "flex", gap: 6 }}>
            <input
              value={askDraft}
              onChange={(e) => setAskDraft(e.target.value)}
              placeholder="Ask Theodore a question…"
              style={{ flex: 1, borderRadius: 8, border: "1px solid #4c1d95", padding: "8px 10px", background: "#1e1033", color: "#fff" }}
              onKeyDown={(e) => e.key === "Enter" && void askQuestion()}
              disabled={busy}
            />
            <button onClick={() => void askQuestion()} disabled={busy} style={{ background: "#db2777", color: "#fff" }}>Ask AI</button>
          </div>

          {/* Control bar */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button onClick={() => void toggleHand()} disabled={busy} title="Join / leave Q&A queue">
              {hasFloor ? "🎤 Speaking" : inQueue ? `✋ Leave queue (#${myQueuePos})` : "✋ Raise hand"}
            </button>
            {hasFloor && (
              <button onClick={() => void finishTurn()} disabled={busy} style={{ background: "#059669", color: "#fff" }}>
                Done speaking
              </button>
            )}
            {moderatorKey && (
              <>
                <button onClick={() => void callNext()} disabled={busy} style={{ background: "#0d9488", color: "#fff" }}>
                  Call next
                </button>
                {room?.floor_participant_id && (
                  <button onClick={() => void finishTurn()} disabled={busy}>End turn</button>
                )}
              </>
            )}
            <button onClick={() => void httpToggleMute()} disabled={busy}>
              {me?.muted || me?.muted_by_host ? "🔊 Unmute" : "🔇 Mute"}
            </button>
            {moderatorKey && (
              <button onClick={() => void liveRoomAdvance(roomId).then(setRoom)} disabled={busy}>
                ▶ Next slide
              </button>
            )}
            <button onClick={() => void (room?.recording.status === "recording" ? liveRoomRecordStop(roomId) : liveRoomRecordStart(roomId)).then(setRoom)} disabled={busy}>
              {room?.recording.status === "recording" ? "⏹ Stop REC" : "🔴 Record"}
            </button>
            <button onClick={() => void handleLeave()} disabled={busy} style={{ marginLeft: "auto" }}>
              Leave
            </button>
          </div>

          {/* Moderator: reports */}
          {moderatorKey && (room?.reports?.length ?? 0) > 0 && (
            <div style={{ marginTop: 8, padding: 10, borderRadius: 10, background: "rgba(245,158,11,0.12)", border: "1px solid rgba(251,191,36,0.35)", fontSize: 12 }}>
              <strong style={{ color: "#fcd34d" }}>User reports</strong>
              {(room?.reports ?? []).map((rep) => (
                <div key={rep.id} style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", marginTop: 8, gap: 8, alignItems: "center" }}>
                  <span><strong>{rep.reported_name}</strong> ({rep.category}) — {rep.reason}<br /><span style={{ opacity: 0.75 }}>from {rep.reporter_name}</span></span>
                  <span style={{ display: "flex", gap: 6 }}>
                    <button onClick={() => void banLearner(rep.reported_participant_id, rep.reported_name)} disabled={busy}>Block</button>
                    <button onClick={() => void liveRoomDismissReport(roomId, rep.id, moderatorKey).then(setRoom)} disabled={busy}>Dismiss</button>
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Moderator: banned list */}
          {moderatorKey && (room?.banned?.length ?? 0) > 0 && (
            <div style={{ marginTop: 8, padding: 10, borderRadius: 10, background: "rgba(220,38,38,0.12)", border: "1px solid rgba(248,113,113,0.35)", fontSize: 12 }}>
              <strong style={{ color: "#fca5a5" }}>Blocked users</strong>
              {(room?.banned ?? []).map((b) => (
                <div key={b.identity} style={{ display: "flex", justifyContent: "space-between", marginTop: 6, gap: 8 }}>
                  <span>{b.name} — {b.reason}</span>
                  <button onClick={() => void unbanLearner(b.identity)} disabled={busy}>Unblock</button>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}
