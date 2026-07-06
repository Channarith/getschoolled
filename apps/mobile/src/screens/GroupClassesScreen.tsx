import { useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";

import { listGroupClasses, startGroupClass, type GroupClassRow } from "../api";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { theme } from "../theme";

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

const PLATFORM_LABEL: Record<string, string> = {
  salareen: "Salareen",
  zoom: "Zoom",
  teams: "Teams",
  meet: "Meet",
};

export default function GroupClassesScreen({
  onOpenRoom,
  onBack,
}: {
  onOpenRoom: (roomId: string, moderatorKey?: string) => void;
  onBack: () => void;
}) {
  const [rows, setRows] = useState<GroupClassRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
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
      setRefreshing(false);
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
      onOpenRoom(roomId, started.bridge.moderator_key);
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
      <Text style={styles.lead}>
        Schedule or join live Salareen rooms — Theodore hosts multi-learner classes on one scrollable page.
      </Text>
      {loading && !refreshing ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginTop: 24 }} />
      ) : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(); }} />
        }
      >
        {rows.length === 0 && !loading ? (
          <Text style={styles.meta}>No upcoming classes — schedule one on the web app.</Text>
        ) : null}
        {rows.map((gc) => (
          <GlassPanel key={gc.id} style={styles.card}>
            <View style={styles.badgeRow}>
              <Text style={styles.badge}>{PLATFORM_LABEL[gc.platform] ?? gc.platform}</Text>
              {gc.status === "live" ? <Text style={styles.liveBadge}>● LIVE</Text> : null}
            </View>
            <Text style={styles.cardTitle}>{gc.title}</Text>
            <Text style={styles.meta}>{fmtTime(gc.start_time)}</Text>
            <Text style={styles.meta}>
              {gc.seats_left}/{gc.capacity} seats
              {gc.room_size ? ` · ${gc.room_size}-seat room` : ""}
            </Text>
            {gc.platform === "salareen" ? (
              <PrimaryButton
                label={gc.status === "live" ? "Join live room" : "Start & join"}
                onPress={() => (gc.status === "live" ? handleJoin(gc) : handleStart(gc))}
                loading={busyId === gc.id}
              />
            ) : (
              <Text style={styles.meta}>External link — open Group Classes on web to join.</Text>
            )}
          </GlassPanel>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingHorizontal: 16, paddingTop: 8, gap: 8 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 20, fontWeight: "700", flex: 1 },
  lead: { color: theme.colors.muted, fontSize: 13, lineHeight: 18, marginBottom: 4 },
  list: { gap: 12, paddingBottom: 32 },
  card: { gap: 8 },
  badgeRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  badge: {
    fontSize: 11,
    fontWeight: "700",
    color: theme.colors.accent,
    backgroundColor: "rgba(110,168,254,0.15)",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
    overflow: "hidden",
  },
  liveBadge: { fontSize: 11, fontWeight: "700", color: "#f87171" },
  cardTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "600", lineHeight: 22 },
  meta: { color: theme.colors.muted, fontSize: 13, lineHeight: 18 },
  error: { color: "#f87171", fontSize: 13 },
});
