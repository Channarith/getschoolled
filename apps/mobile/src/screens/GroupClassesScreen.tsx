import { useEffect, useState } from "react";
import {
  ActivityIndicator, Linking, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";

import { getMe, listGroupClasses, startGroupClass, type GroupClassRow } from "../api";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { getToken } from "../storage";
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
  onSignIn,
}: {
  onOpenRoom: (roomId: string, moderatorKey?: string) => void;
  onBack: () => void;
  onSignIn?: () => void;
}) {
  const [rows, setRows] = useState<GroupClassRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [displayName, setDisplayName] = useState("");

  const load = async () => {
    setError("");
    try {
      setRows(await listGroupClasses(true));
      const token = await getToken();
      if (token) {
        try {
          const me = await getMe();
          setSignedIn(true);
          setDisplayName(me.display_name || me.email);
        } catch {
          setSignedIn(Boolean(token));
        }
      } else {
        setSignedIn(false);
        setDisplayName("");
      }
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

  async function openExternalMeeting(url: string) {
    if (!url) return;
    try {
      const can = await Linking.canOpenURL(url);
      if (can) await Linking.openURL(url);
      else setError(`Cannot open meeting link: ${url}`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label="← Back" onPress={onBack} variant="ghost" />
        <Text style={styles.title}>Group Classes</Text>
      </View>
      <Text style={styles.lead}>
        Join a live Salareen chat room (Bigo/Mico-style multi-learner session) or open an external meeting.
      </Text>

      <GlassPanel style={styles.authCard}>
        {signedIn ? (
          <Text style={styles.authText}>
            Signed in as {displayName}. Tap Join live room to enter the multi-user chat.
          </Text>
        ) : (
          <>
            <Text style={styles.authText}>
              Sign in to save your name and join Salareen live rooms with chat, raise-hand, and Q&A.
            </Text>
            {onSignIn ? (
              <PrimaryButton label="Sign in to connect" onPress={onSignIn} variant="brand" />
            ) : null}
          </>
        )}
      </GlassPanel>

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
              <>
                <Text style={styles.joinHint}>
                  Multi-user live room: chat, raise hand, ask Theodore, moderator tools.
                </Text>
                <PrimaryButton
                  label={gc.status === "live" ? "Join live chat room" : "Start & join live room"}
                  onPress={() => (gc.status === "live" ? handleJoin(gc) : handleStart(gc))}
                  loading={busyId === gc.id}
                  variant="netflix"
                />
              </>
            ) : gc.meeting_url ? (
              <>
                <Text style={styles.joinHint}>Opens the external meeting app (Zoom/Teams/Meet).</Text>
                <PrimaryButton
                  label="Open meeting & connect"
                  onPress={() => void openExternalMeeting(gc.meeting_url!)}
                  variant="brand"
                />
              </>
            ) : (
              <Text style={styles.meta}>Meeting link not available — check Group Classes on web.</Text>
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
  authCard: { gap: 10, marginBottom: 4 },
  authText: { color: theme.colors.text, fontSize: 13, lineHeight: 18 },
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
  joinHint: { color: theme.colors.accent, fontSize: 12, lineHeight: 16 },
  error: { color: "#f87171", fontSize: 13 },
});
