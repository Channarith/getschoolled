/**
 * Salareen Live Room — mobile WebRTC video/audio class.
 *
 * Uses @livekit/react-native for actual audio/video streaming plus
 * HTTP polling against the orchestrator for chat, Q&A queue, and
 * moderation state (which is the source of truth for room metadata).
 *
 * The AI host (Theodore) joins as a LiveKit agent worker and appears
 * as a remote participant in the host tile automatically.
 */

import {
  AudioSession,
  LiveKitRoom,
  useTracks,
  TrackReferenceOrPlaceholder,
  VideoTrack,
  AudioTrack,
  useParticipants,
  useLocalParticipant,
  useRoomContext,
  isTrackReference,
} from "@livekit/react-native";
import { Track } from "livekit-client";
import React, { useEffect, useState, useRef } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import {
  getLiveRoom,
  joinLiveRoom,
  liveRoomAsk,
  liveRoomBan,
  liveRoomCallNext,
  liveRoomChat,
  liveRoomDismissReport,
  liveRoomFinishTurn,
  liveRoomLeaveQueue,
  liveRoomRaiseHand,
  liveRoomReport,
  liveRoomUnban,
  liveRoomMute,
  liveRoomRecordStart,
  liveRoomRecordStop,
  liveRoomAdvance,
  type LiveRoomState,
} from "../api";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { theme } from "../theme";

// ---------------------------------------------------------------------------
// In-room participant grid (uses LiveKit hooks)
// ---------------------------------------------------------------------------
function ParticipantGrid({
  httpRoom,
  myParticipantId,
  moderatorKey,
  onBan,
}: {
  httpRoom: LiveRoomState;
  myParticipantId: string;
  moderatorKey: string;
  onBan: (id: string, name: string) => void;
}) {
  const participants = useParticipants();
  const { localParticipant } = useLocalParticipant();

  const cameraTrackRefs = useTracks(
    [{ source: Track.Source.Camera, withPlaceholder: true }],
    { onlySubscribed: false }
  );

  // Build a map from LiveKit identity → camera track ref
  const trackMap = new Map<string, TrackReferenceOrPlaceholder>();
  for (const ref of cameraTrackRefs) {
    trackMap.set(ref.participant.identity, ref);
  }

  const hostP = httpRoom.host;
  const learners = httpRoom.participants.filter((p) => p.role !== "host");

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.gridScroll}>
      {/* AI host tile */}
      {hostP && (
        <View key="host" style={[styles.tile, styles.hostTile]}>
          {(() => {
            const ref = trackMap.get("theodore-ai");
            if (ref && isTrackReference(ref)) {
              return <VideoTrack trackRef={ref} style={styles.tileVideo} />;
            }
            return <Text style={styles.tileEmoji}>🎓</Text>;
          })()}
          <Text style={styles.tileName} numberOfLines={1}>
            {hostP.name}
          </Text>
        </View>
      )}

      {/* Learner tiles */}
      {learners.map((p) => {
        const isMe = p.id === myParticipantId;
        const speaking = p.id === httpRoom.floor_participant_id;
        const ref = trackMap.get(p.identity);

        return (
          <View
            key={p.id}
            style={[styles.tile, speaking && styles.speakingTile]}
          >
            {ref && isTrackReference(ref) ? (
              <VideoTrack
                trackRef={ref}
                style={styles.tileVideo}
                mirror={isMe}
              />
            ) : (
              <Text style={styles.tileEmoji}>
                {speaking ? "🎤" : "👤"}
              </Text>
            )}
            <Text style={styles.tileName} numberOfLines={1}>
              {p.name}
              {p.hand_raised && !speaking ? " ✋" : ""}
              {p.muted || p.muted_by_host ? " 🔇" : ""}
            </Text>
            {moderatorKey && !isMe && p.role !== "host" && (
              <PrimaryButton
                label="Block"
                variant="ghost"
                onPress={() => onBan(p.id, p.name)}
              />
            )}
          </View>
        );
      })}
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Inner room component (inside <LiveKitRoom> context)
// ---------------------------------------------------------------------------
function RoomInner({
  roomId,
  participantId,
  moderatorKey,
  httpRoom,
  setRoom,
  onBack,
}: {
  roomId: string;
  participantId: string;
  moderatorKey: string;
  httpRoom: LiveRoomState;
  setRoom: (r: LiveRoomState) => void;
  onBack: () => void;
}) {
  const { localParticipant } = useLocalParticipant();
  const room = useRoomContext();

  const [micEnabled, setMicEnabled] = useState(true);
  const [camEnabled, setCamEnabled] = useState(false);
  const [chat, setChat] = useState("");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const me = httpRoom.participants.find((p) => p.id === participantId);
  const hasFloor = httpRoom.floor_participant_id === participantId;
  const inQueue = Boolean(
    httpRoom.speaking_queue?.some(
      (e) =>
        e.participant_id === participantId &&
        (e.status === "waiting" || e.status === "speaking")
    )
  );
  const myPos =
    httpRoom.speaking_queue?.find(
      (e) => e.participant_id === participantId && e.status === "waiting"
    )?.position ?? 0;
  const modKey = moderatorKey;

  const toggleMic = async () => {
    await localParticipant.setMicrophoneEnabled(!micEnabled);
    setMicEnabled((v) => !v);
  };

  const toggleCam = async () => {
    await localParticipant.setCameraEnabled(!camEnabled);
    setCamEnabled((v) => !v);
  };

  const handleBan = async (id: string, name: string) => {
    if (!modKey) return;
    Alert.prompt(`Block ${name}?`, "Optional reason:", async (reason) => {
      if (reason === null) return;
      try { setRoom(await liveRoomBan(roomId, id, modKey)); }
      catch (e) { setError((e as Error).message); }
    });
  };

  return (
    <View style={{ flex: 1 }}>
      {/* Subscribe all remote audio */}
      {useTracks([{ source: Track.Source.Microphone, withPlaceholder: false }]).map(
        (ref) =>
          isTrackReference(ref) && ref.participant.identity !== localParticipant.identity ? (
            <AudioTrack key={ref.participant.identity} trackRef={ref} />
          ) : null
      )}

      {/* Header */}
      <View style={styles.header}>
        <PrimaryButton label="← Leave" onPress={onBack} variant="ghost" />
        <Text style={styles.title} numberOfLines={1}>{httpRoom.title}</Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <TouchableOpacity onPress={() => void toggleMic()} style={[styles.mediaBtn, micEnabled && styles.mediaBtnActive]}>
            <Text style={{ fontSize: 20 }}>{micEnabled ? "🎙️" : "🔇"}</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => void toggleCam()} style={[styles.mediaBtn, camEnabled && styles.mediaBtnActive]}>
            <Text style={{ fontSize: 20 }}>{camEnabled ? "📹" : "📷"}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {/* Slide */}
      <GlassPanel style={styles.slide}>
        <Text style={styles.meta}>Slide {(httpRoom.slide?.index ?? 0) + 1}</Text>
        <Text style={styles.cardTitle}>{httpRoom.slide?.title}</Text>
        <Text style={styles.meta}>{httpRoom.slide?.narration || httpRoom.slide?.body}</Text>
      </GlassPanel>

      {/* Video grid */}
      <ParticipantGrid
        httpRoom={httpRoom}
        myParticipantId={participantId}
        moderatorKey={modKey}
        onBan={handleBan}
      />

      {/* Q&A queue */}
      {(httpRoom.speaking_queue?.length ?? 0) > 0 && (
        <GlassPanel style={styles.slide}>
          <Text style={styles.cardTitle}>Q&A queue</Text>
          {httpRoom.floor_holder && (
            <Text style={styles.meta}>🎤 Now: {httpRoom.floor_holder.name}</Text>
          )}
          {(httpRoom.speaking_queue ?? [])
            .filter((e) => e.status === "waiting")
            .map((e) => (
              <Text key={e.id} style={styles.meta}>
                #{e.position} {e.name}{e.question ? ` — ${e.question}` : ""}
              </Text>
            ))}
          {myPos > 0 && !hasFloor && (
            <Text style={styles.meta}>You are #{myPos} in line.</Text>
          )}
        </GlassPanel>
      )}

      {/* Chat */}
      <ScrollView style={styles.chatBox}>
        {(httpRoom.chat ?? []).map((m) => (
          <Text key={m.id} style={styles.chatLine}>
            <Text style={styles.chatName}>{m.from_name}: </Text>
            {m.text}
          </Text>
        ))}
      </ScrollView>

      {/* Chat input */}
      <View style={styles.controls}>
        <TextInput
          value={chat}
          onChangeText={setChat}
          placeholder="Chat…"
          placeholderTextColor={theme.colors.muted}
          style={[styles.input, { flex: 1 }]}
        />
        <PrimaryButton
          label="Send"
          onPress={async () => {
            if (!chat.trim() || !participantId) return;
            setBusy(true);
            try { setRoom(await liveRoomChat(roomId, participantId, chat.trim())); setChat(""); }
            catch (e) { setError((e as Error).message); }
            finally { setBusy(false); }
          }}
          loading={busy}
        />
      </View>

      {/* Ask input */}
      <View style={styles.controls}>
        <TextInput
          value={question}
          onChangeText={setQuestion}
          placeholder="Ask Theodore…"
          placeholderTextColor={theme.colors.muted}
          style={[styles.input, { flex: 1 }]}
        />
        <PrimaryButton
          label="Ask"
          onPress={async () => {
            if (!question.trim() || !participantId) return;
            setBusy(true);
            try {
              const res = await liveRoomAsk(roomId, participantId, question.trim());
              setRoom(res.room);
              if (res.queued) setError(`Queue position #${res.queue_position ?? myPos}`);
              else setError("");
              setQuestion("");
            } catch (e) { setError((e as Error).message); }
            finally { setBusy(false); }
          }}
          loading={busy}
        />
      </View>

      {/* Control buttons */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, padding: 8 }}>
        <PrimaryButton
          label={hasFloor ? "You're speaking" : inQueue ? `Leave queue (#${myPos})` : "✋ Raise hand"}
          variant="ghost"
          onPress={async () => {
            if (!participantId) return;
            try {
              if (inQueue && !hasFloor) setRoom(await liveRoomLeaveQueue(roomId, participantId));
              else setRoom(await liveRoomRaiseHand(roomId, participantId, question.trim()));
            } catch (e) { setError((e as Error).message); }
          }}
        />
        {hasFloor && (
          <PrimaryButton
            label="Done speaking"
            onPress={async () => {
              try { setRoom(await liveRoomFinishTurn(roomId, participantId, modKey)); }
              catch (e) { setError((e as Error).message); }
            }}
          />
        )}
        <PrimaryButton
          label={me?.muted || me?.muted_by_host ? "🔊 Unmute" : "🔇 Mute"}
          variant="ghost"
          onPress={async () => {
            try {
              setRoom(await liveRoomMute(roomId, participantId, !(me?.muted || me?.muted_by_host)));
            } catch (e) { setError((e as Error).message); }
          }}
        />
        {modKey && (
          <>
            <PrimaryButton
              label="Call next"
              onPress={async () => { try { setRoom(await liveRoomCallNext(roomId, modKey)); } catch (e) { setError((e as Error).message); } }}
            />
            <PrimaryButton
              label="▶ Next slide"
              variant="ghost"
              onPress={async () => { try { setRoom(await liveRoomAdvance(roomId)); } catch (e) { setError((e as Error).message); } }}
            />
            <PrimaryButton
              label={httpRoom.recording?.status === "recording" ? "⏹ Stop REC" : "🔴 Record"}
              variant="ghost"
              onPress={async () => {
                try {
                  if (httpRoom.recording?.status === "recording") setRoom(await liveRoomRecordStop(roomId));
                  else setRoom(await liveRoomRecordStart(roomId));
                } catch (e) { setError((e as Error).message); }
              }}
            />
          </>
        )}
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main exported screen — handles join flow then <LiveKitRoom> wrapper
// ---------------------------------------------------------------------------
const STORAGE: Record<string, { participantId: string; identity: string }> = {};
const MOD_STORAGE: Record<string, string> = {};

export default function LiveRoomScreen({
  roomId,
  onBack,
  moderatorKey = "",
}: {
  roomId: string;
  onBack: () => void;
  moderatorKey?: string;
}) {
  const [name, setName] = useState("");
  const [participantId, setParticipantId] = useState("");
  const [liveKitToken, setLiveKitToken] = useState("");
  const [liveKitUrl, setLiveKitUrl] = useState("");
  const [room, setRoom] = useState<LiveRoomState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [wasBlocked, setWasBlocked] = useState(false);

  const modKey = moderatorKey || MOD_STORAGE[roomId] || "";

  useEffect(() => {
    if (moderatorKey) MOD_STORAGE[roomId] = moderatorKey;
  }, [moderatorKey, roomId]);

  // Initial room load
  useEffect(() => {
    getLiveRoom(roomId, modKey)
      .then(setRoom)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [roomId, modKey]);

  // Poll while in room
  useEffect(() => {
    if (!participantId) return;
    const t = setInterval(async () => {
      try { setRoom(await getLiveRoom(roomId, modKey)); }
      catch { /* offline — keep stale */ }
    }, 2500);
    return () => clearInterval(t);
  }, [participantId, roomId, modKey]);

  // Ban detection
  useEffect(() => {
    if (!participantId || !room) return;
    const stillHere = room.participants.some((p) => p.id === participantId);
    if (!stillHere) setWasBlocked(true);
  }, [room, participantId]);

  // Audio session setup for iOS
  useEffect(() => {
    AudioSession.startAudioSession();
    return () => { void AudioSession.stopAudioSession(); };
  }, []);

  async function handleJoin() {
    if (!name.trim()) { setError("Enter your name"); return; }
    setBusy(true);
    setError("");
    try {
      const ident = STORAGE[roomId]?.identity || `mobile-${name.trim().toLowerCase().replace(/\s+/g, "-")}`;
      const joined = await joinLiveRoom(roomId, name.trim(), ident);
      setParticipantId(joined.participant.id);
      STORAGE[roomId] = { participantId: joined.participant.id, identity: joined.participant.identity };
      setRoom(joined.room);
      // Store LiveKit credentials from join response
      if (joined.media?.token) setLiveKitToken(joined.media.token);
      if (joined.media?.url) setLiveKitUrl(joined.media.url);
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.toLowerCase().includes("block") || msg.toLowerCase().includes("removed")) {
        setWasBlocked(true);
      }
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  if (wasBlocked) {
    return (
      <View style={styles.wrap}>
        <Text style={styles.title}>Removed from class</Text>
        <Text style={styles.meta}>You were blocked from this live room.</Text>
        <PrimaryButton label="Back" onPress={onBack} />
      </View>
    );
  }

  // Join screen
  if (!participantId || !liveKitToken) {
    return (
      <View style={styles.wrap}>
        <PrimaryButton label="← Back" onPress={onBack} variant="ghost" />
        <Text style={styles.title}>Salareen Live Room</Text>
        <Text style={styles.meta}>Theodore (AI) hosts · grid up to {room?.room_size ?? 6} seats · real video + audio</Text>
        {loading && <ActivityIndicator color={theme.colors.accent} />}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <GlassPanel style={styles.joinCard}>
          <TextInput
            value={name}
            onChangeText={setName}
            placeholder="Your name"
            placeholderTextColor={theme.colors.muted}
            style={styles.input}
          />
          <PrimaryButton label={busy ? "Joining…" : "Enter room"} onPress={() => void handleJoin()} loading={busy} />
        </GlassPanel>
      </View>
    );
  }

  const lkServerUrl =
    liveKitUrl ||
    process.env.EXPO_PUBLIC_LIVEKIT_URL ||
    "wss://livekit.salareen.com";

  return (
    <LiveKitRoom
      serverUrl={lkServerUrl}
      token={liveKitToken}
      connect={true}
      audio={true}
      video={false}
      style={{ flex: 1 }}
    >
      {room && (
        <RoomInner
          roomId={roomId}
          participantId={participantId}
          moderatorKey={modKey}
          httpRoom={room}
          setRoom={setRoom}
          onBack={onBack}
        />
      )}
    </LiveKitRoom>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 16, gap: 10 },
  header: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 8 },
  title: { color: theme.colors.text, fontSize: 18, fontWeight: "700", flex: 1 },
  meta: { color: theme.colors.muted, fontSize: 13 },
  joinCard: { gap: 10, marginTop: 12 },
  input: { borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10, padding: 10, color: theme.colors.text, backgroundColor: "rgba(0,0,0,0.2)" },
  slide: { gap: 6, marginBottom: 8 },
  cardTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "600" },
  gridScroll: { maxHeight: 130 },
  tile: { width: 100, height: 120, marginRight: 8, borderRadius: 12, backgroundColor: "rgba(99,102,241,0.35)", alignItems: "center", justifyContent: "center", padding: 6, overflow: "hidden" },
  hostTile: { backgroundColor: "rgba(124,58,237,0.5)", width: 110 },
  speakingTile: { borderWidth: 2, borderColor: "#34d399" },
  tileVideo: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0 },
  tileEmoji: { fontSize: 26 },
  tileName: { color: theme.colors.text, fontSize: 11, marginTop: 2, textAlign: "center" },
  chatBox: { flex: 1, maxHeight: 160, backgroundColor: "rgba(0,0,0,0.25)", borderRadius: 10, padding: 8, marginBottom: 4 },
  chatLine: { color: theme.colors.text, fontSize: 13, marginBottom: 6 },
  chatName: { color: "#c4b5fd", fontWeight: "600" },
  controls: { flexDirection: "row", gap: 8, alignItems: "center", marginBottom: 4 },
  error: { color: "#f87171" },
  mediaBtn: { padding: 8, borderRadius: 8, backgroundColor: "rgba(255,255,255,0.1)" },
  mediaBtnActive: { backgroundColor: "#1d4ed8" },
});
