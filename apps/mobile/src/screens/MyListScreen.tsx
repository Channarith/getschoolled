import { useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, RefreshControl,
  StyleSheet, Text, View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import { listAudioCourses, type AudioCourseRow } from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import { getMyList, toggleMyList } from "../storage";
import { useT } from "../i18n";
import { categoryGradient, theme } from "../theme";

export default function MyListScreen({ onOpenCourse }: {
  onOpenCourse: (id: string) => void;
}) {
  const { t, locale } = useT();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rows, setRows] = useState<AudioCourseRow[]>([]);

  const load = async () => {
    const ids = await getMyList();
    if (ids.length === 0) { setRows([]); setLoading(false); setRefreshing(false); return; }
    try {
      const all = await listAudioCourses(undefined, undefined, 100, locale);
      const lookup = new Map(all.courses.map((c) => [c.id, c]));
      setRows(ids.map((id) => lookup.get(id)).filter(Boolean) as AudioCourseRow[]);
    } finally { setLoading(false); setRefreshing(false); }
  };
  useEffect(() => { void load(); }, [locale]); // eslint-disable-line react-hooks/exhaustive-deps

  const remove = async (id: string) => {
    await toggleMyList(id);
    setRows((r) => r.filter((c) => c.id !== id));
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.netflix} size="large" />
      </View>
    );
  }
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
          <Text style={styles.kicker}>{t("tab.mylist")}</Text>
          <Text style={styles.title}>{t("mylist.title")}</Text>
          <Text style={styles.sub}>{t("mylist.sub")}</Text>
        </View>
      }
      ListEmptyComponent={
        <GlassPanel style={styles.empty}>
          <Ionicons name="bookmark-outline" size={36} color={theme.colors.muted} />
          <Text style={styles.emptyTitle}>{t("mylist.emptyTitle")}</Text>
          <Text style={styles.emptyBody}>{t("mylist.emptyBody")}</Text>
        </GlassPanel>
      }
      data={rows}
      keyExtractor={(c) => c.id}
      renderItem={({ item }) => {
        const [c1, c2] = categoryGradient(item.category);
        return (
          <AnimatedPressable onPress={() => onOpenCourse(item.id)} style={styles.rowWrap}>
            <GlassPanel style={styles.row} padded={false}>
              <LinearGradient colors={[c1, c2]} style={styles.thumb}>
                <Ionicons name="headset" size={22} color="#fff" />
              </LinearGradient>
              <View style={{ flex: 1 }}>
                <Text style={styles.rowTitle} numberOfLines={2}>{item.title}</Text>
                <Text style={styles.rowMeta}>
                  {item.category} · {item.duration_min} {t("meta.min")} · {item.segments} {t("meta.segments")}
                </Text>
              </View>
              <AnimatedPressable onPress={() => void remove(item.id)} hitSlop={12} style={styles.removeBtn}>
                <Ionicons name="bookmark" size={22} color={theme.colors.gold} />
              </AnimatedPressable>
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
  header: { paddingHorizontal: theme.spacing.screenX, paddingBottom: 16 },
  kicker: { ...theme.typography.kicker, color: theme.colors.muted },
  title: { ...theme.typography.title, color: theme.colors.text, marginTop: 4 },
  sub: { color: theme.colors.muted, marginTop: 6, ...theme.typography.body },
  empty: { alignItems: "center", marginHorizontal: theme.spacing.screenX, marginTop: 40, padding: 28, gap: 8 },
  emptyTitle: { color: theme.colors.text, fontSize: 18, fontWeight: "700", marginTop: 8 },
  emptyBody: { color: theme.colors.muted, textAlign: "center", ...theme.typography.body },
  rowWrap: { marginHorizontal: theme.spacing.screenX, marginBottom: 10 },
  row: {
    flexDirection: "row", alignItems: "center", gap: 12, padding: 12,
  },
  thumb: {
    width: 52, height: 52, borderRadius: theme.radius.sm,
    alignItems: "center", justifyContent: "center",
  },
  rowTitle: { color: theme.colors.text, fontSize: 15, fontWeight: "700" },
  rowMeta: { color: theme.colors.muted, fontSize: 12, marginTop: 4 },
  removeBtn: { padding: 4 },
});
