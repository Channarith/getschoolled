"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getLiveRoom,
  getLiveGiftCatalog,
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
  liveRoomReaction,
  liveRoomSendGift,
  liveRoomFollowHost,
  type LiveGiftCatalogItem,
  type LiveParticipant,
  type LiveRoomJoin,
  type LiveRoomState,
} from "../../lib/api";
import { friendlyError } from "../../lib/errors";
import { LiveKitVideoTile, useLiveKitRoom } from "../../components/LiveKitRoomGrid";
import { useLiveRoomSocket } from "../../lib/liveRoomSocket";

const REACTIONS = ["❤️", "👏", "🔥", "😂", "🎉", "👍"] as const;

const ROOM_STORAGE_KEY = "salareen-live-participant";
const MODERATOR_STORAGE_KEY = "salareen-live-moderator";

function gridLayout(roomSize: number): { cols: number; rows: number } {
  if (roomSize <= 4) return { cols: 2, rows: 2 };
  if (roomSize <= 6) return { cols: 3, rows: 2 };
  return { cols: 3, rows: 3 };
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function ParticipantTile({
  p,
  large,
  localStream,
  liveKitTrack,
  hasFloor,
}: {
  p: LiveParticipant;
  large?: boolean;
  localStream?: MediaStream | null;
  liveKitTrack?: MediaStreamTrack | null;
  hasFloor?: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const isHost = p.role === "host";

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    if (liveKitTrack) {
      el.srcObject = new MediaStream([liveKitTrack]);
      return;
    }
    if (localStream) el.srcObject = localStream;
  }, [localStream, liveKitTrack]);

  const hasVideo = Boolean(liveKitTrack || localStream);

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
          : p.hand_raised
            ? "2px solid #fbbf24"
            : "1px solid rgba(255,255,255,0.12)",
        minHeight: large ? 220 : 110,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
    >
      {hasVideo ? (
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: 0.85,
          }}
        />
      ) : (
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
          {isHost ? "🎓" : initials(p.name)}
        </div>
      )}
      <div
        style={{
          position: "relative",
          padding: "8px 10px",
          background: "linear-gradient(transparent, rgba(0,0,0,0.75))",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
        }}
      >
        <span style={{ fontWeight: 600 }}>
          {isHost ? "Host · " : ""}
          {p.name}
        </span>
        <span style={{ display: "flex", gap: 4 }}>
          {hasFloor && <span title="Speaking now">🎤</span>}
          {p.hand_raised && !hasFloor && <span title="In Q&A queue">✋</span>}
          {(p.muted || p.muted_by_host) && <span title="Muted">🔇</span>}
        </span>
      </div>
    </div>
  );
}

export default function LiveRoomPage({ params }: { params: { roomId: string } }) {
  const roomId = decodeURIComponent(params.roomId);
  const [displayName, setDisplayName] = useState("");
  const [joinInfo, setJoinInfo] = useState<LiveRoomJoin | null>(null);
  const [room, setRoom] = useState<LiveRoomState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [chatDraft, setChatDraft] = useState("");
  const [askDraft, setAskDraft] = useState("");
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [moderatorKey, setModeratorKey] = useState("");
  const [wasRemoved, setWasRemoved] = useState(false);
  const [giftBalance, setGiftBalance] = useState(0);
  const [giftCatalog, setGiftCatalog] = useState<LiveGiftCatalogItem[]>([]);
  const [showGifts, setShowGifts] = useState(false);
  const [followingHost, setFollowingHost] = useState(false);
  const [followerCount, setFollowerCount] = useState(0);
  const leftVoluntarily = useRef(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const viewerSetterRef = useRef<(n: number) => void>(() => {});

  const applyRoom = useCallback((next: LiveRoomState) => {
    setRoom(next);
    if (typeof next.viewer_count === "number") {
      viewerSetterRef.current(next.viewer_count);
    }
  }, []);

  const socket = useLiveRoomSocket(roomId, Boolean(joinInfo), applyRoom);
  viewerSetterRef.current = socket.setViewerCount;

  const me = useMemo(() => {
    const id = joinInfo?.participant.id;
    if (!id || !room) return joinInfo?.participant ?? null;
    return room.participants.find((p) => p.id === id) ?? joinInfo.participant;
  }, [joinInfo, room]);
  const hasFloor = me?.id === room?.floor_participant_id;

  const { tiles: liveKitTiles, livekitAvailable } = useLiveKitRoom(
    joinInfo?.media,
    room?.participants ?? joinInfo?.room.participants ?? [],
    Boolean(hasFloor && me?.can_publish),
  );

  const trackFor = useCallback(
    (participantId: string) =>
      liveKitTiles.find((t) => t.participantId === participantId)?.track ?? null,
    [liveKitTiles],
  );

  const layout = useMemo(() => gridLayout(room?.room_size ?? 6), [room?.room_size]);
  const myQueuePos = useMemo(() => {
    if (!me || !room?.speaking_queue) return 0;
    const entry = room.speaking_queue.find(
      (e) => e.participant_id === me.id && e.status === "waiting"
    );
    return entry?.position ?? 0;
  }, [me, room?.speaking_queue]);
  const inQueue = Boolean(room?.speaking_queue?.some(
    (e) => e.participant_id === me?.id && (e.status === "waiting" || e.status === "speaking")
  ));

  const refresh = useCallback(async () => {
    try {
      const mod =
        moderatorKey ||
        sessionStorage.getItem(`${MODERATOR_STORAGE_KEY}:${roomId}`) ||
        "";
      setRoom(await getLiveRoom(roomId, mod));
    } catch (e) {
      setError(friendlyError(e, "Offline"));
    }
  }, [roomId, moderatorKey]);

  useEffect(() => {
    const stored = sessionStorage.getItem(`${ROOM_STORAGE_KEY}:${roomId}`);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as { name: string; participantId: string; identity: string };
        setDisplayName(parsed.name);
      } catch {
        /* ignore */
      }
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
      localStream?.getTracks().forEach((t) => t.stop());
    }
  }, [room, joinInfo, roomId, localStream]);

  useEffect(() => {
    if (!joinInfo || socket.connected) return;
    const timer = setInterval(() => void refresh(), 3000);
    return () => clearInterval(timer);
  }, [joinInfo, refresh, socket.connected]);

  useEffect(() => {
    void getLiveGiftCatalog()
      .then((c) => setGiftCatalog(c.gifts))
      .catch(() => setGiftCatalog([]));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [room?.chat.length]);

  async function enableCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      setLocalStream(stream);
    } catch {
      /* camera optional */
    }
  }

  async function handleJoin() {
    const name = displayName.trim();
    if (!name) {
      setError("Enter your name to join.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const stored = sessionStorage.getItem(`${ROOM_STORAGE_KEY}:${roomId}`);
      let identity = "";
      if (stored) {
        try {
          identity = (JSON.parse(stored) as { identity?: string }).identity ?? "";
        } catch {
          identity = "";
        }
      }
      const info = await joinLiveRoom(roomId, name, identity || `web-${name.toLowerCase().replace(/\s+/g, "-")}`);
      setJoinInfo(info);
      setRoom(info.room);
      setGiftBalance(info.gift_balance ?? 500);
      setFollowingHost(Boolean(info.following_host));
      setFollowerCount(info.host_follower_count ?? 0);
      sessionStorage.setItem(
        `${ROOM_STORAGE_KEY}:${roomId}`,
        JSON.stringify({
          name,
          participantId: info.participant.id,
          identity: info.participant.identity,
        })
      );
      await enableCamera();
    } catch (e) {
      const msg = friendlyError(e, "Could not join room");
      if (msg.toLowerCase().includes("block") || msg.toLowerCase().includes("removed") || msg.includes("403")) {
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
      await leaveLiveRoom(roomId, me.id);
      sessionStorage.removeItem(`${ROOM_STORAGE_KEY}:${roomId}`);
      localStream?.getTracks().forEach((t) => t.stop());
      window.location.href = "/group-classes";
    } catch (e) {
      setError(friendlyError(e, "Could not leave"));
    } finally {
      setBusy(false);
    }
  }

  async function sendChat() {
    if (!me || !chatDraft.trim()) return;
    setBusy(true);
    try {
      setRoom(await liveRoomChat(roomId, me.id, chatDraft.trim()));
      setChatDraft("");
    } catch (e) {
      setError(friendlyError(e, "Chat failed"));
    } finally {
      setBusy(false);
    }
  }

  async function askQuestion() {
    if (!me || !askDraft.trim()) return;
    setBusy(true);
    try {
      const res = await liveRoomAsk(roomId, me.id, askDraft.trim());
      setRoom(res.room);
      if (res.queued) {
        setError(`You're #${res.queue_position ?? myQueuePos} in the Q&A queue. Theodore will call on you in turn.`);
      } else {
        setError("");
      }
      setAskDraft("");
    } catch (e) {
      setError(friendlyError(e, "Question failed"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleHand() {
    if (!me) return;
    setBusy(true);
    try {
      if (inQueue && !hasFloor) {
        setRoom(await liveRoomLeaveQueue(roomId, me.id));
      } else {
        setRoom(await liveRoomRaiseHand(roomId, me.id, askDraft.trim()));
      }
    } catch (e) {
      setError(friendlyError(e, "Could not update queue"));
    } finally {
      setBusy(false);
    }
  }

  async function callNext() {
    if (!moderatorKey) return;
    setBusy(true);
    try {
      setRoom(await liveRoomCallNext(roomId, moderatorKey));
      setError("");
    } catch (e) {
      setError(friendlyError(e, "Could not call next"));
    } finally {
      setBusy(false);
    }
  }

  async function finishTurn() {
    setBusy(true);
    try {
      const pid = room?.floor_participant_id || me?.id || "";
      setRoom(await liveRoomFinishTurn(roomId, pid, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Could not end turn"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleMute() {
    if (!me) return;
    setBusy(true);
    try {
      setRoom(await liveRoomMute(roomId, me.id, !me.muted));
    } catch (e) {
      setError(friendlyError(e, "Could not toggle mute"));
    } finally {
      setBusy(false);
    }
  }

  async function hostAdvance() {
    setBusy(true);
    try {
      setRoom(await liveRoomAdvance(roomId));
    } catch (e) {
      setError(friendlyError(e, "Advance failed"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleRecording() {
    setBusy(true);
    try {
      if (room?.recording.status === "recording") {
        setRoom(await liveRoomRecordStop(roomId));
      } else {
        setRoom(await liveRoomRecordStart(roomId));
      }
    } catch (e) {
      setError(friendlyError(e, "Recording failed"));
    } finally {
      setBusy(false);
    }
  }

  async function banLearner(participantId: string, name: string) {
    if (!moderatorKey) return;
    const reason = window.prompt(`Block ${name}? Optional reason:`) ?? "";
    if (reason === null) return;
    setBusy(true);
    try {
      setRoom(await liveRoomBan(roomId, participantId, reason, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Ban failed"));
    } finally {
      setBusy(false);
    }
  }

  async function unbanLearner(identity: string) {
    if (!moderatorKey) return;
    setBusy(true);
    try {
      setRoom(await liveRoomUnban(roomId, identity, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Unban failed"));
    } finally {
      setBusy(false);
    }
  }

  async function reportLearner(participantId: string, name: string) {
    if (!me?.id) return;
    const reason =
      window.prompt(`Report ${name} — what happened? (required)`)?.trim() ?? "";
    if (!reason) return;
    const category =
      window.prompt(
        "Category: spam, harassment, inappropriate, disruptive, or other",
        "other"
      )?.trim().toLowerCase() || "other";
    setBusy(true);
    try {
      await liveRoomReport(roomId, me.id, participantId, reason, category);
      window.alert("Report submitted. A moderator will review it.");
    } catch (e) {
      setError(friendlyError(e, "Report failed"));
    } finally {
      setBusy(false);
    }
  }

  async function dismissReport(reportId: string) {
    if (!moderatorKey) return;
    setBusy(true);
    try {
      setRoom(await liveRoomDismissReport(roomId, reportId, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Dismiss failed"));
    } finally {
      setBusy(false);
    }
  }

  if (wasRemoved) {
    return (
      <main className="container" style={{ maxWidth: 480 }}>
        <h1>Removed from class</h1>
        <p className="muted">
          You were blocked from this live room and cannot rejoin until a moderator lifts the ban.
        </p>
        <button onClick={() => { window.location.href = "/group-classes"; }}>Back to Group Classes</button>
      </main>
    );
  }

  if (!joinInfo) {
    return (
      <main className="container" style={{ maxWidth: 480 }}>
        <h1>Salareen Live Room</h1>
        <p className="muted">
          Join Theodore&apos;s multi-user class — up to {room?.room_size ?? 6} seats in the grid.
        </p>
        {room && (
          <div className="card" style={{ marginBottom: 12 }}>
            <strong>{room.title}</strong>
            <div className="muted">
              {room.learner_count}/{room.learner_capacity} learners · {room.seats_left} seats left
            </div>
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

  const learners = (room?.participants ?? []).filter((p) => p.role !== "host");
  const host = room?.host;
  const emptySlots = Math.max(0, (room?.learner_capacity ?? 0) - learners.length);

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #0f0720 0%, #1a0a2e 40%, #2d1b4e 100%)",
        color: "#f8fafc",
        padding: "12px 16px 24px",
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div>
          <div style={{ fontSize: 12, color: "#c4b5fd" }}>Salareen Live · {roomId}</div>
          <h2 style={{ margin: "4px 0 0", fontSize: 20 }}>{room?.title ?? "Live class"}</h2>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13, flexWrap: "wrap" }}>
          {room?.recording.status === "recording" && (
            <span style={{ color: "#fca5a5", fontWeight: 600 }}>● REC</span>
          )}
          <span className="muted" style={{ color: "#ddd6fe" }}>
            👁 {socket.viewerCount || room?.viewer_count || room?.learner_count || 0}
          </span>
          <span className="muted" style={{ color: "#ddd6fe" }}>
            ❤️ {socket.followerCount || followerCount} followers
          </span>
          {socket.connected ? (
            <span style={{ color: "#34d399", fontSize: 11 }}>● live</span>
          ) : (
            <span style={{ color: "#fcd34d", fontSize: 11 }}>polling</span>
          )}
          {me ? (
            <button
              type="button"
              onClick={async () => {
                try {
                  const r = await liveRoomFollowHost(
                    roomId,
                    me.identity,
                    followingHost,
                  );
                  setFollowingHost(r.following);
                  setFollowerCount(r.follower_count);
                  socket.setFollowerCount(r.follower_count);
                } catch (e) {
                  setError(friendlyError(e, "Follow failed"));
                }
              }}
              style={{
                fontSize: 12,
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,0.2)",
                background: followingHost ? "rgba(236,72,153,0.35)" : "transparent",
                color: "#fce7f3",
                cursor: "pointer",
              }}
            >
              {followingHost ? "Following host" : "Follow host"}
            </button>
          ) : null}
        </div>
      </header>

      {socket.presenceToast ? (
        <div
          style={{
            position: "fixed",
            top: 72,
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(15,7,32,0.92)",
            border: "1px solid rgba(167,139,250,0.4)",
            borderRadius: 999,
            padding: "8px 16px",
            fontSize: 13,
            zIndex: 50,
          }}
        >
          {socket.presenceToast.kind === "join" ? "👋" : "👋"} {socket.presenceToast.name}{" "}
          {socket.presenceToast.kind === "join" ? "joined" : "left"}
        </div>
      ) : null}

      {socket.giftOverlay ? (
        <div
          style={{
            position: "fixed",
            top: "40%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            fontSize: 64,
            zIndex: 60,
            textAlign: "center",
            pointerEvents: "none",
          }}
        >
          <div>{socket.giftOverlay.emoji}</div>
          <div style={{ fontSize: 14, marginTop: 8, color: "#fce7f3" }}>
            {socket.giftOverlay.label}
          </div>
        </div>
      ) : null}

      <div
        style={{
          position: "fixed",
          inset: 0,
          pointerEvents: "none",
          overflow: "hidden",
          zIndex: 40,
        }}
      >
        {socket.floatingReactions.map((r) => (
          <span
            key={r.id}
            style={{
              position: "absolute",
              left: `${r.x}%`,
              bottom: 80,
              fontSize: 28,
              animation: "live-float-up 2.2s ease-out forwards",
            }}
          >
            {r.emoji}
          </span>
        ))}
      </div>

      <style jsx global>{`
        @keyframes live-float-up {
          0% {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
          100% {
            opacity: 0;
            transform: translateY(-180px) scale(1.2);
          }
        }
      `}</style>

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
        <section>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: largeHostColumn(layout.cols),
              gridTemplateRows: `repeat(${layout.rows}, minmax(100px, 1fr))`,
              gap: 8,
              marginBottom: 12,
            }}
          >
            {host && (
              <div style={{ gridRow: `span ${layout.rows}`, minHeight: 220 }}>
                <ParticipantTile
                  p={host}
                  large
                  liveKitTrack={trackFor(host.id)}
                />
              </div>
            )}
            {learners.map((p) => (
              <div key={p.id} style={{ position: "relative" }}>
                <ParticipantTile
                  p={p}
                  localStream={!livekitAvailable && p.id === me?.id ? localStream : null}
                  liveKitTrack={trackFor(p.id)}
                  hasFloor={p.id === room?.floor_participant_id}
                />
                {moderatorKey && p.id !== me?.id ? (
                  <button
                    type="button"
                    onClick={() => void banLearner(p.id, p.name)}
                    disabled={busy}
                    title={`Block ${p.name}`}
                    style={{
                      position: "absolute",
                      top: 6,
                      right: 6,
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 6,
                      background: "rgba(220,38,38,0.9)",
                      color: "#fff",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    Block
                  </button>
                ) : null}
                {p.role !== "host" && p.id !== me?.id ? (
                  <button
                    type="button"
                    onClick={() => void reportLearner(p.id, p.name)}
                    disabled={busy}
                    title={`Report ${p.name}`}
                    style={{
                      position: "absolute",
                      top: 6,
                      left: 6,
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 6,
                      background: "rgba(245,158,11,0.9)",
                      color: "#1c1917",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    Report
                  </button>
                ) : null}
              </div>
            ))}
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

          {(room?.speaking_queue?.length ?? 0) > 0 && (
            <div
              style={{
                marginBottom: 12,
                padding: 12,
                borderRadius: 12,
                background: "rgba(52,211,153,0.08)",
                border: "1px solid rgba(52,211,153,0.25)",
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600, color: "#6ee7b7", marginBottom: 8 }}>
                Q&A queue — take turns
              </div>
              {room?.floor_holder ? (
                <div style={{ fontSize: 13, marginBottom: 8, color: "#a7f3d0" }}>
                  🎤 Now speaking: <strong>{room.floor_holder.name}</strong>
                </div>
              ) : null}
              <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#d1fae5" }}>
                {(room?.speaking_queue ?? [])
                  .filter((e) => e.status === "waiting")
                  .map((e) => (
                    <li key={e.id} style={{ marginBottom: 4 }}>
                      #{e.position} {e.name}
                      {e.question ? ` — "${e.question}"` : ""}
                    </li>
                  ))}
              </ol>
              {myQueuePos > 0 && !hasFloor ? (
                <div style={{ marginTop: 8, fontSize: 12, color: "#fcd34d" }}>
                  You are #{myQueuePos} in line.
                </div>
              ) : null}
            </div>
          )}

          {room?.slide && (
            <div
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 12,
                padding: 14,
              }}
            >
              <div style={{ fontSize: 12, color: "#c4b5fd", marginBottom: 4 }}>
                Slide {room.slide.index + 1}
              </div>
              <strong>{room.slide.title}</strong>
              <p style={{ margin: "8px 0 0", color: "#e9d5ff", fontSize: 14, lineHeight: 1.5 }}>
                {room.slide.narration || room.slide.body}
              </p>
            </div>
          )}
        </section>

        <aside
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            minHeight: 420,
          }}
        >
          <div
            style={{
              flex: 1,
              background: "rgba(0,0,0,0.35)",
              borderRadius: 12,
              border: "1px solid rgba(255,255,255,0.08)",
              padding: 10,
              overflowY: "auto",
              maxHeight: 320,
              minHeight: 200,
            }}
          >
            {(room?.chat ?? []).map((m) => (
              <div key={m.id} style={{ marginBottom: 8, fontSize: 13, lineHeight: 1.4 }}>
                <span style={{ color: m.from_id === "system" ? "#a78bfa" : "#fbbf24", fontWeight: 600 }}>
                  {m.from_name}:
                </span>{" "}
                <span style={{ color: "#e2e8f0" }}>{m.text}</span>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            {REACTIONS.map((emoji) => (
              <button
                key={emoji}
                type="button"
                disabled={busy || !me}
                onClick={async () => {
                  if (!me) return;
                  socket.pushReaction(emoji);
                  try {
                    applyRoom(await liveRoomReaction(roomId, me.id, emoji));
                  } catch (e) {
                    setError(friendlyError(e, "Reaction failed"));
                  }
                }}
                style={{
                  fontSize: 18,
                  padding: "4px 8px",
                  borderRadius: 8,
                  border: "1px solid rgba(255,255,255,0.12)",
                  background: "rgba(255,255,255,0.06)",
                  cursor: "pointer",
                }}
              >
                {emoji}
              </button>
            ))}
            <button
              type="button"
              disabled={!me}
              onClick={() => setShowGifts((v) => !v)}
              style={{
                marginLeft: "auto",
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: 8,
                background: "#db2777",
                color: "#fff",
                border: "none",
                cursor: "pointer",
              }}
            >
              🎁 Gifts ({giftBalance} pts)
            </button>
          </div>

          {showGifts ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                gap: 6,
                padding: 8,
                background: "rgba(0,0,0,0.35)",
                borderRadius: 10,
              }}
            >
              {giftCatalog.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  disabled={busy || !me || giftBalance < g.cost_points}
                  onClick={async () => {
                    if (!me) return;
                    setBusy(true);
                    try {
                      const res = await liveRoomSendGift(roomId, me.id, g.id);
                      applyRoom(res.room);
                      setGiftBalance(res.sender_balance);
                      setShowGifts(false);
                    } catch (e) {
                      setError(friendlyError(e, "Gift failed"));
                    } finally {
                      setBusy(false);
                    }
                  }}
                  style={{
                    padding: 8,
                    borderRadius: 8,
                    border: "1px solid rgba(255,255,255,0.1)",
                    background: "rgba(255,255,255,0.05)",
                    color: "#fce7f3",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  <div style={{ fontSize: 22 }}>{g.emoji}</div>
                  {g.name}
                  <div>{g.cost_points} pts</div>
                </button>
              ))}
            </div>
          ) : null}

          <div style={{ display: "flex", gap: 6 }}>
            <input
              value={chatDraft}
              onChange={(e) => setChatDraft(e.target.value)}
              placeholder="Say something…"
              style={{ flex: 1, borderRadius: 8, border: "1px solid #4c1d95", padding: "8px 10px", background: "#1e1033", color: "#fff" }}
              onKeyDown={(e) => e.key === "Enter" && void sendChat()}
              disabled={busy || me?.muted || me?.muted_by_host}
            />
            <button onClick={() => void sendChat()} disabled={busy} style={{ background: "#7c3aed", color: "#fff" }}>
              Chat
            </button>
          </div>

          <div style={{ display: "flex", gap: 6 }}>
            <input
              value={askDraft}
              onChange={(e) => setAskDraft(e.target.value)}
              placeholder="Ask Theodore a question…"
              style={{ flex: 1, borderRadius: 8, border: "1px solid #4c1d95", padding: "8px 10px", background: "#1e1033", color: "#fff" }}
              onKeyDown={(e) => e.key === "Enter" && void askQuestion()}
              disabled={busy}
            />
            <button onClick={() => void askQuestion()} disabled={busy} style={{ background: "#db2777", color: "#fff" }}>
              Ask
            </button>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button onClick={() => void toggleHand()} disabled={busy} title="Join or leave Q&A queue">
              {hasFloor
                ? "🎤 You're speaking"
                : inQueue
                  ? `✋ Leave queue (#${myQueuePos})`
                  : "✋ Join Q&A queue"}
            </button>
            {hasFloor ? (
              <button onClick={() => void finishTurn()} disabled={busy} style={{ background: "#059669", color: "#fff" }}>
                Done speaking
              </button>
            ) : null}
            {moderatorKey ? (
              <>
                <button onClick={() => void callNext()} disabled={busy} style={{ background: "#0d9488", color: "#fff" }}>
                  Call next
                </button>
                {room?.floor_participant_id ? (
                  <button onClick={() => void finishTurn()} disabled={busy}>
                    End turn
                  </button>
                ) : null}
              </>
            ) : null}
            <button onClick={() => void toggleMute()} disabled={busy || (!hasFloor && inQueue)}>
              {me?.muted || me?.muted_by_host ? "🔊 Unmute" : "🔇 Mute"}
            </button>
            <button onClick={() => void hostAdvance()} disabled={busy} title="Next slide (host)">
              ▶ Next slide
            </button>
            <button onClick={() => void toggleRecording()} disabled={busy}>
              {room?.recording.status === "recording" ? "⏹ Stop REC" : "🔴 Record"}
            </button>
            <button onClick={() => void handleLeave()} disabled={busy} style={{ marginLeft: "auto" }}>
              Leave
            </button>
          </div>

          {moderatorKey && (room?.reports?.length ?? 0) > 0 ? (
            <div
              style={{
                marginTop: 8,
                padding: 10,
                borderRadius: 10,
                background: "rgba(245,158,11,0.12)",
                border: "1px solid rgba(251,191,36,0.35)",
                fontSize: 12,
              }}
            >
              <strong style={{ color: "#fcd34d" }}>User reports</strong>
              {(room?.reports ?? []).map((rep) => (
                <div
                  key={rep.id}
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginTop: 8,
                    gap: 8,
                  }}
                >
                  <span>
                    <strong>{rep.reported_name}</strong> ({rep.category}) — {rep.reason}
                    <br />
                    <span style={{ opacity: 0.75 }}>from {rep.reporter_name}</span>
                  </span>
                  <span style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => void banLearner(rep.reported_participant_id, rep.reported_name)}
                      disabled={busy}
                    >
                      Block
                    </button>
                    <button type="button" onClick={() => void dismissReport(rep.id)} disabled={busy}>
                      Dismiss
                    </button>
                  </span>
                </div>
              ))}
            </div>
          ) : null}

          {moderatorKey && (room?.banned?.length ?? 0) > 0 ? (
            <div
              style={{
                marginTop: 8,
                padding: 10,
                borderRadius: 10,
                background: "rgba(220,38,38,0.12)",
                border: "1px solid rgba(248,113,113,0.35)",
                fontSize: 12,
              }}
            >
              <strong style={{ color: "#fca5a5" }}>Blocked users</strong>
              {(room?.banned ?? []).map((b) => (
                <div key={b.identity} style={{ display: "flex", justifyContent: "space-between", marginTop: 6, gap: 8 }}>
                  <span>{b.name} — {b.reason}</span>
                  <button type="button" onClick={() => void unbanLearner(b.identity)} disabled={busy}>
                    Unblock
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </aside>
      </div>
    </main>
  );
}

function largeHostColumn(cols: number): string {
  if (cols <= 2) return "1.2fr 1fr";
  return "1.3fr repeat(2, 1fr)";
}
