import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, RefreshControl,
  StyleSheet, Text, View,
} from "react-native";

import { getNotificationsFeed, type NotificationItem } from "../api";
import {
  getInterests, getMyList, getReadIds, getStreak,
  listContinue, markAllRead, markRead, getSettings,
} from "../storage";
import { ensurePermissions, scheduleAlertsFor } from "../notifications";

const ICONS: Record<NotificationItem["icon"], string> = {
  bell: "🔔", sparkle: "✨", flame: "🔥",
  play: "▶", trophy: "🏆", gift: "🎁",
};

function relTime(iso: string): string {
  const d = new Date(iso).getTime();
  const now = Date.now();
  const m = Math.max(1, Math.round((now - d) / 60000));
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export default function NotificationsScreen({ onOpenCourse, onUnreadChange }: {
  onOpenCourse: (id: string) => void;
  onUnreadChange?: (unread: number) => void;
}) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [readSet, setReadSet] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [scheduled, setScheduled] = useState(0);

  const load = useCallback(async () => {
    setError("");
    try {
      const [interests, inProgress, completed, streak, read, settings] = await Promise.all([
        getInterests(), listContinue(), getMyList(), getStreak(), getReadIds(), getSettings(),
      ]);
      const feed = await getNotificationsFeed({
        studentId: settings.studentId,
        interests, inProgress: inProgress.map((c) => c.id),
        completed, streakDays: streak.days,
      });
      setItems(feed.items);
      setReadSet(new Set(read));
      try {
        const granted = await ensurePermissions();
        if (granted) {
          await scheduleAlertsFor(feed.items, settings);
        }
      } catch {}
    } catch (e) {
      setError(`Could not load notifications (${String(e)}).`);
    } finally {
      setLoading(false); setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const onItemPress = async (i: NotificationItem) => {
    await markRead(i.id);
    setReadSet((prev) => {
      const next = new Set(prev);
      next.add(i.id);
      const stillUnread = items.filter((it) => !next.has(it.id)).length;
      onUnreadChange?.(stillUnread);
      return next;
    });
    if (i.course_id) onOpenCourse(i.course_id);
  };

  const onMarkAllRead = async () => {
    const all = items.map((i) => i.id);
    await markAllRead(all);
    setReadSet(new Set(all));
    onUnreadChange?.(0);
  };

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color="#0ea5e9" /></View>;
  }

  const unread = items.filter((i) => !readSet.has(i.id)).length;
  return (
    <FlatList
      style={styles.bg}
      contentContainerStyle={{ paddingTop: 56, paddingBottom: 24 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(); }} tintColor="#0ea5e9" />}
      ListHeaderComponent={
        <View style={styles.header}>
          <View style={{ flexDirection: "row", alignItems: "baseline", gap: 8 }}>
            <Text style={styles.title}>Alerts</Text>
            {unread > 0 ? <Text style={styles.unread}>{unread} new</Text> : null}
          </View>
          {error ? <Text style={styles.err}>{error}</Text> : null}
          <Text style={styles.sub}>
            {scheduled
              ? `${scheduled} alerts scheduled on your device.`
              : "Personalized inbox + on-device daily reminders. Manage in Settings."}
          </Text>
          {items.length > 0 ? (
            <Pressable onPress={onMarkAllRead} style={styles.markAll}>
              <Text style={styles.markAllText}>Mark all as read</Text>
            </Pressable>
          ) : null}
        </View>
      }
      ListEmptyComponent={
        <View style={styles.empty}>
          <Text style={styles.emptyTitle}>You're all caught up</Text>
          <Text style={styles.emptyBody}>New classes and recommendations show up here.</Text>
        </View>
      }
      data={items}
      keyExtractor={(i) => i.id}
      renderItem={({ item }) => {
        const isRead = readSet.has(item.id);
        return (
          <Pressable style={[styles.row, !isRead && styles.rowUnread]} onPress={() => void onItemPress(item)}>
            <Text style={styles.icon}>{ICONS[item.icon] || "🔔"}</Text>
            <View style={{ flex: 1 }}>
              <Text style={[styles.itemTitle, !isRead && styles.itemTitleUnread]}>{item.title}</Text>
              <Text style={styles.itemBody}>{item.body}</Text>
              <Text style={styles.itemTime}>{relTime(item.created_at)}</Text>
            </View>
            {!isRead ? <View style={styles.dot} /> : null}
          </Pressable>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: "#0b1020" },
  center: { flex: 1, backgroundColor: "#0b1020", alignItems: "center", justifyContent: "center" },
  header: { paddingHorizontal: 16, paddingBottom: 8 },
  title: { color: "#e8ecf6", fontSize: 24, fontWeight: "800" },
  unread: { color: "#0ea5e9", fontWeight: "700" },
  sub: { color: "#9aa6c2", marginTop: 6 },
  err: { color: "#ff6b6b", marginTop: 6 },
  markAll: { alignSelf: "flex-start", marginTop: 10, backgroundColor: "#1d2746", paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999 },
  markAllText: { color: "#0ea5e9", fontWeight: "700", fontSize: 12 },
  empty: { alignItems: "center", paddingHorizontal: 28, paddingTop: 60 },
  emptyTitle: { color: "#e8ecf6", fontSize: 18, fontWeight: "700" },
  emptyBody: { color: "#9aa6c2", marginTop: 8, textAlign: "center" },
  row: {
    flexDirection: "row", alignItems: "flex-start", gap: 12,
    backgroundColor: "#151c34", borderRadius: 12,
    padding: 14, marginHorizontal: 12, marginBottom: 10,
  },
  rowUnread: { borderLeftWidth: 3, borderLeftColor: "#0ea5e9" },
  icon: { fontSize: 22, marginTop: 2 },
  itemTitle: { color: "#c5cce0", fontSize: 14, fontWeight: "600" },
  itemTitleUnread: { color: "#e8ecf6", fontWeight: "800" },
  itemBody: { color: "#9aa6c2", fontSize: 12, marginTop: 4, lineHeight: 16 },
  itemTime: { color: "#5d6890", fontSize: 11, marginTop: 6 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: "#0ea5e9", marginTop: 6 },
});
