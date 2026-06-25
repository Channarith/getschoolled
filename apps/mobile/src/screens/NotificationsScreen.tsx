import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, RefreshControl,
  StyleSheet, Text, View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { getNotificationsFeed, type NotificationItem } from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import {
  getInterests, getMyList, getReadIds, getStreak,
  listContinue, markAllRead, markRead, getSettings,
} from "../storage";
import { ensurePermissions, scheduleAlertsFor } from "../notifications";
import { useT } from "../i18n";
import { theme } from "../theme";

const ICONS: Record<NotificationItem["icon"], keyof typeof Ionicons.glyphMap> = {
  bell: "notifications",
  sparkle: "sparkles",
  flame: "flame",
  play: "play-circle",
  trophy: "trophy",
  gift: "gift",
};

function useRelTime() {
  const { t } = useT();
  return (iso: string): string => {
    const d = new Date(iso).getTime();
    const now = Date.now();
    const m = Math.max(1, Math.round((now - d) / 60000));
    if (m < 60) return t("time.minAgo", { n: m });
    const h = Math.round(m / 60);
    if (h < 24) return t("time.hAgo", { n: h });
    return t("time.dAgo", { n: Math.round(h / 24) });
  };
}

export default function NotificationsScreen({ onOpenCourse, onUnreadChange }: {
  onOpenCourse: (id: string) => void;
  onUnreadChange?: (unread: number) => void;
}) {
  const { t, locale } = useT();
  const relTime = useRelTime();
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
        completed, streakDays: streak.days, locale,
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
      setError(t("notif.error", { error: String(e) }));
    } finally {
      setLoading(false); setRefreshing(false);
    }
  }, [locale]); // eslint-disable-line react-hooks/exhaustive-deps

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
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.netflix} size="large" />
      </View>
    );
  }

  const unread = items.filter((i) => !readSet.has(i.id)).length;
  return (
    <FlatList
      style={styles.bg}
      contentContainerStyle={{ paddingTop: 56, paddingBottom: 24 }}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => { setRefreshing(true); void load(); }}
          tintColor={theme.colors.netflix}
        />
      }
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.kicker}>{t("tab.alerts")}</Text>
          <View style={{ flexDirection: "row", alignItems: "baseline", gap: 8 }}>
            <Text style={styles.title}>{t("notif.title")}</Text>
            {unread > 0 ? (
              <View style={styles.unreadBadge}>
                <Text style={styles.unreadText}>{t("notif.unread", { n: unread })}</Text>
              </View>
            ) : null}
          </View>
          {error ? (
            <GlassPanel style={{ marginTop: 10 }}>
              <Text style={styles.err}>{error}</Text>
            </GlassPanel>
          ) : null}
          <Text style={styles.sub}>
            {scheduled
              ? t("notif.subScheduled", { n: scheduled })
              : t("notif.subEmpty")}
          </Text>
          {items.length > 0 ? (
            <View style={{ marginTop: 12, maxWidth: 160 }}>
              <PrimaryButton label={t("notif.markAll")} onPress={onMarkAllRead} variant="ghost" />
            </View>
          ) : null}
        </View>
      }
      ListEmptyComponent={
        <GlassPanel style={styles.empty}>
          <Ionicons name="notifications-outline" size={36} color={theme.colors.muted} />
          <Text style={styles.emptyTitle}>{t("notif.emptyTitle")}</Text>
          <Text style={styles.emptyBody}>{t("notif.emptyBody")}</Text>
        </GlassPanel>
      }
      data={items}
      keyExtractor={(i) => i.id}
      renderItem={({ item }) => {
        const isRead = readSet.has(item.id);
        const iconName = ICONS[item.icon] || "notifications";
        return (
          <AnimatedPressable
            onPress={() => void onItemPress(item)}
            style={styles.rowWrap}
          >
            <GlassPanel
              style={[styles.row, !isRead && styles.rowUnread]}
              padded={false}
            >
              <View style={[styles.iconCircle, !isRead && styles.iconCircleUnread]}>
                <Ionicons
                  name={iconName}
                  size={20}
                  color={isRead ? theme.colors.muted : theme.colors.netflix}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.itemTitle, !isRead && styles.itemTitleUnread]}>
                  {item.title}
                </Text>
                <Text style={styles.itemBody}>{item.body}</Text>
                <Text style={styles.itemTime}>{relTime(item.created_at)}</Text>
              </View>
              {!isRead ? <View style={styles.dot} /> : null}
            </GlassPanel>
          </AnimatedPressable>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: "transparent" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { paddingHorizontal: theme.spacing.screenX, paddingBottom: 8 },
  kicker: { ...theme.typography.kicker, color: theme.colors.muted },
  title: { ...theme.typography.title, color: theme.colors.text, marginTop: 4 },
  unreadBadge: {
    backgroundColor: theme.colors.netflix,
    borderRadius: theme.radius.pill,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  unreadText: { color: "#fff", fontWeight: "700", fontSize: 11 },
  sub: { color: theme.colors.muted, marginTop: 8, ...theme.typography.body },
  err: { color: "#ff8a8a", ...theme.typography.body },
  empty: { alignItems: "center", marginHorizontal: theme.spacing.screenX, marginTop: 40, padding: 28, gap: 8 },
  emptyTitle: { color: theme.colors.text, fontSize: 18, fontWeight: "700", marginTop: 8 },
  emptyBody: { color: theme.colors.muted, textAlign: "center", ...theme.typography.body },
  rowWrap: { marginHorizontal: theme.spacing.screenX, marginBottom: 10 },
  row: {
    flexDirection: "row", alignItems: "flex-start", gap: 12, padding: 14,
  },
  rowUnread: { borderLeftWidth: 3, borderLeftColor: theme.colors.netflix },
  iconCircle: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.06)",
    alignItems: "center", justifyContent: "center",
  },
  iconCircleUnread: { backgroundColor: "rgba(229,9,20,0.15)" },
  itemTitle: { color: theme.colors.muted, fontSize: 14, fontWeight: "600" },
  itemTitleUnread: { color: theme.colors.text, fontWeight: "800" },
  itemBody: { color: theme.colors.muted, fontSize: 12, marginTop: 4, lineHeight: 16 },
  itemTime: { color: "#5d6890", fontSize: 11, marginTop: 6 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: theme.colors.netflix, marginTop: 6 },
});
