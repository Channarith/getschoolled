import { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";

import { listGroupClasses, startGroupClass, type GroupClassRow } from "../api";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { theme } from "../theme";

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function GroupClassesScreen({
  onOpenRoom,
  onBack,
}: {
  onOpenRoom: (roomId: string) => void;
  onBack: () => void;
}) {
  const [rows, setRows] = useState<GroupClassRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const load = async () => {
    setError("");
    try {
      setRows(await listGroupClasses(true));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  async function handleJoin(gc: GroupClassRow) {
    if (gc.platform !== "salareen") return;
    const roomId = gc.live_room_id || `class-${gc.id}`;
    onOpenRoom(roomId);
  }

  async function handleStart(gc: GroupClassRow) {
    setBusyId(gc.id);
    try {
      const started = await startGroupClass(gc.id);
      const roomId = started.bridge.live_room_id || started.bridge.livekit_room || `class-${gc.id}`;
      onOpenRoom(roomId);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId("");
    }
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label="← Back" onPress={onBack} variant="ghost" />
        <Text style={styles.title}>Group Classes</Text>
      </View>
      {loading && <ActivityIndicator color={theme.colors.accent} />}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <ScrollView contentContainerStyle={styles.list}>
        {rows.map((gc) => (
          <GlassPanel key={gc.id} style={styles.card}>
            <Text style={styles.cardTitle}>{gc.title}</Text>
            <Text style={styles.meta}>
              {fmtTime(gc.start_time)} · {gc.platform}
              {gc.room_size ? ` · ${gc.room_size}-seat` : ""}
            </Text>
            <Text style={styles.meta}>
              {gc.seats_left} seats left · {gc.status === "live" ? "● LIVE" : "scheduled"}
            </Text>
            {gc.platform === "salareen" ? (
              <View style={styles.row}>
                <PrimaryButton
                  label={gc.status === "live" ? "Join room" : "Start & join"}
                  onPress={() => (gc.status === "live" ? handleJoin(gc) : handleStart(gc))}
                  loading={busyId === gc.id}
                />
              </View>
            ) : (
              <Text style={styles.meta}>Join via {gc.platform} link on web.</Text>
            )}
          </GlassPanel>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 16, gap: 12 },
  header: { flexDirection: "row", alignItems: "center", gap: 12 },
  title: { color: theme.colors.text, fontSize: 22, fontWeight: "700" },
  list: { gap: 12, paddingBottom: 24 },
  card: { gap: 8 },
  cardTitle: { color: theme.colors.text, fontSize: 17, fontWeight: "600" },
  meta: { color: theme.colors.muted, fontSize: 13 },
  row: { flexDirection: "row", gap: 8, marginTop: 4 },
  error: { color: "#f87171" },
});
