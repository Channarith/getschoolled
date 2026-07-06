"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getLiveRoom,
  joinLiveRoom,
  leaveLiveRoom,
  liveRoomAdvance,
  liveRoomAsk,
  liveRoomChat,
  liveRoomMute,
  liveRoomRaiseHand,
  liveRoomRecordStart,
  liveRoomRecordStop,
  type LiveParticipant,
  type LiveRoomJoin,
  type LiveRoomState,
} from "../../lib/api";
import { friendlyError } from "../../lib/errors";

const ROOM_STORAGE_KEY = "salareen-live-participant";

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
}: {
  p: LiveParticipant;
  large?: boolean;
  localStream?: MediaStream | null;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const isHost = p.role === "host";

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !localStream) return;
    el.srcObject = localStream;
  }, [localStream]);

  return (
    <div
      style={{
        position: "relative",
        borderRadius: large ? 16 : 12,
        overflow: "hidden",
        background: isHost
          ? "linear-gradient(145deg, #4c1d95 0%, #7c3aed 55%, #db2777 100%)"
          : "linear-gradient(145deg, #1e1b4b 0%, #312e81 100%)",
        border: p.hand_raised ? "2px solid #fbbf24" : "1px solid rgba(255,255,255,0.12)",
        minHeight: large ? 220 : 110,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
    >
      {localStream ? (
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
          {p.hand_raised && <span title="Hand raised">✋</span>}
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
  const chatEndRef = useRef<HTMLDivElement>(null);

  const me = useMemo(() => {
    const id = joinInfo?.participant.id;
    if (!id || !room) return joinInfo?.participant ?? null;
    return room.participants.find((p) => p.id === id) ?? joinInfo.participant;
  }, [joinInfo, room]);
  const layout = useMemo(() => gridLayout(room?.room_size ?? 6), [room?.room_size]);

  const refresh = useCallback(async () => {
    try {
      setRoom(await getLiveRoom(roomId));
    } catch (e) {
      setError(friendlyError(e, "Offline"));
    }
  }, [roomId]);

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
    void refresh();
  }, [roomId, refresh]);

  useEffect(() => {
    if (!joinInfo) return;
    const timer = setInterval(() => void refresh(), 2500);
    return () => clearInterval(timer);
  }, [joinInfo, refresh]);

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
      setError(friendlyError(e, "Could not join room"));
    } finally {
      setBusy(false);
    }
  }

  async function handleLeave() {
    if (!me) return;
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
      setRoom(await liveRoomAsk(roomId, me.id, askDraft.trim()));
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
      setRoom(await liveRoomRaiseHand(roomId, me.id));
    } catch (e) {
      setError(friendlyError(e, "Could not update hand"));
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
        <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
          {room?.recording.status === "recording" && (
            <span style={{ color: "#fca5a5", fontWeight: 600 }}>● REC</span>
          )}
          <span className="muted" style={{ color: "#ddd6fe" }}>
            👥 {room?.learner_count ?? 0} learners
          </span>
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
                <ParticipantTile p={host} large />
              </div>
            )}
            {learners.map((p) => (
              <ParticipantTile
                key={p.id}
                p={p}
                localStream={p.id === me?.id ? localStream : null}
              />
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
            <button onClick={() => void toggleHand()} disabled={busy} title="Raise hand">
              {me?.hand_raised ? "✋ Lower hand" : "✋ Raise hand"}
            </button>
            <button onClick={() => void toggleMute()} disabled={busy}>
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
        </aside>
      </div>
    </main>
  );
}

function largeHostColumn(cols: number): string {
  if (cols <= 2) return "1.2fr 1fr";
  return "1.3fr repeat(2, 1fr)";
}
