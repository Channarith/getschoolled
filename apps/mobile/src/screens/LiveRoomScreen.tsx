import { useEffect, useState } from "react";
import {
  ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  getLiveRoom, joinLiveRoom, liveRoomAsk, liveRoomBan, liveRoomChat, liveRoomRaiseHand,
  liveRoomUnban, type LiveRoomState,
} from "../api";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { theme } from "../theme";

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
  const [room, setRoom] = useState<LiveRoomState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [chat, setChat] = useState("");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [wasBlocked, setWasBlocked] = useState(false);
  const modKey = moderatorKey || MOD_STORAGE[roomId] || "";

  const refresh = async () => {
    try {
      setRoom(await getLiveRoom(roomId));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    if (moderatorKey) MOD_STORAGE[roomId] = moderatorKey;
  }, [moderatorKey, roomId]);

  useEffect(() => {
    void refresh().finally(() => setLoading(false));
  }, [roomId]);

  useEffect(() => {
    if (!participantId) return;
    const t = setInterval(() => void refresh(), 3000);
    return () => clearInterval(t);
  }, [participantId, roomId]);

  async function handleJoin() {
    if (!name.trim()) {
      setError("Enter your name");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const ident = STORAGE[roomId]?.identity || `mobile-${name.trim().toLowerCase()}`;
      const joined = await joinLiveRoom(roomId, name.trim(), ident);
      setParticipantId(joined.participant.id);
      STORAGE[roomId] = { participantId: joined.participant.id, identity: joined.participant.identity };
      setRoom(joined.room);
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

  useEffect(() => {
    if (!participantId || !room) return;
    const stillHere = room.participants.some((p) => p.id === participantId);
    if (!stillHere) setWasBlocked(true);
  }, [room, participantId]);

  const me = room?.participants.find((p) => p.id === participantId);

  if (wasBlocked) {
    return (
      <View style={styles.wrap}>
        <Text style={styles.title}>Removed from class</Text>
        <Text style={styles.meta}>You were blocked from this live room.</Text>
        <PrimaryButton label="Back" onPress={onBack} />
      </View>
    );
  }

  if (!participantId) {
    return (
      <View style={styles.wrap}>
        <PrimaryButton label="← Back" onPress={onBack} variant="ghost" />
        <Text style={styles.title}>Salareen Live Room</Text>
        <Text style={styles.meta}>Theodore hosts · grid up to {room?.room_size ?? 6} seats</Text>
        {loading ? <ActivityIndicator color={theme.colors.accent} /> : null}
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

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label="← Leave" onPress={onBack} variant="ghost" />
        <Text style={styles.title} numberOfLines={1}>{room?.title ?? "Live class"}</Text>
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <GlassPanel style={styles.slide}>
        <Text style={styles.meta}>Slide {(room?.slide.index ?? 0) + 1}</Text>
        <Text style={styles.cardTitle}>{room?.slide.title}</Text>
        <Text style={styles.meta}>{room?.slide.narration || room?.slide.body}</Text>
      </GlassPanel>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.gridScroll}>
        {(room?.participants ?? []).map((p) => (
          <View key={p.id} style={[styles.tile, p.role === "host" && styles.hostTile]}>
            <Text style={styles.tileEmoji}>{p.role === "host" ? "🎓" : "👤"}</Text>
            <Text style={styles.tileName} numberOfLines={1}>{p.name}</Text>
            {p.hand_raised ? <Text>✋</Text> : null}
            {modKey && p.role !== "host" && p.id !== participantId ? (
              <PrimaryButton
                label="Block"
                variant="ghost"
                onPress={async () => {
                  setRoom(await liveRoomBan(roomId, p.id, modKey));
                }}
              />
            ) : null}
          </View>
        ))}
      </ScrollView>

      {modKey && (room?.banned?.length ?? 0) > 0 ? (
        <GlassPanel style={styles.slide}>
          <Text style={styles.cardTitle}>Blocked</Text>
          {(room?.banned ?? []).map((b) => (
            <View key={b.identity} style={styles.controls}>
              <Text style={styles.meta}>{b.name}</Text>
              <PrimaryButton
                label="Unblock"
                variant="ghost"
                onPress={async () => {
                  setRoom(await liveRoomUnban(roomId, b.identity, modKey));
                }}
              />
            </View>
          ))}
        </GlassPanel>
      ) : null}

      <ScrollView style={styles.chatBox}>
        {(room?.chat ?? []).map((m) => (
          <Text key={m.id} style={styles.chatLine}>
            <Text style={styles.chatName}>{m.from_name}: </Text>
            {m.text}
          </Text>
        ))}
      </ScrollView>

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
            try {
              setRoom(await liveRoomChat(roomId, participantId, chat.trim()));
              setChat("");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
          loading={busy}
        />
      </View>
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
              setRoom(await liveRoomAsk(roomId, participantId, question.trim()));
              setQuestion("");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
          loading={busy}
        />
      </View>
      <PrimaryButton
        label={me?.hand_raised ? "Lower hand" : "Raise hand"}
        variant="ghost"
        onPress={async () => {
          if (!participantId) return;
          setRoom(await liveRoomRaiseHand(roomId, participantId));
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 16, gap: 10 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 18, fontWeight: "700", flex: 1 },
  meta: { color: theme.colors.muted, fontSize: 13 },
  joinCard: { gap: 10, marginTop: 12 },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 10,
    padding: 10,
    color: theme.colors.text,
    backgroundColor: "rgba(0,0,0,0.2)",
  },
  slide: { gap: 6 },
  cardTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "600" },
  gridScroll: { maxHeight: 100 },
  tile: {
    width: 88,
    height: 88,
    marginRight: 8,
    borderRadius: 12,
    backgroundColor: "rgba(99,102,241,0.35)",
    alignItems: "center",
    justifyContent: "center",
    padding: 6,
  },
  hostTile: { backgroundColor: "rgba(124,58,237,0.5)", width: 100 },
  tileEmoji: { fontSize: 22 },
  tileName: { color: theme.colors.text, fontSize: 11, marginTop: 4 },
  chatBox: { flex: 1, maxHeight: 180, backgroundColor: "rgba(0,0,0,0.25)", borderRadius: 10, padding: 8 },
  chatLine: { color: theme.colors.text, fontSize: 13, marginBottom: 6 },
  chatName: { color: "#c4b5fd", fontWeight: "600" },
  controls: { flexDirection: "row", gap: 8, alignItems: "center" },
  error: { color: "#f87171" },
});
