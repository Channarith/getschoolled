import { useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, RefreshControl,
  StyleSheet, Text, View,
} from "react-native";

import { listAudioCourses, type AudioCourseRow } from "../api";
import { getMyList, toggleMyList } from "../storage";
import { useT } from "../i18n";

export default function MyListScreen({ onOpenCourse }: {
  onOpenCourse: (id: string) => void;
}) {
  const { t } = useT();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rows, setRows] = useState<AudioCourseRow[]>([]);

  const load = async () => {
    const ids = await getMyList();
    if (ids.length === 0) { setRows([]); setLoading(false); setRefreshing(false); return; }
    try {
      const all = await listAudioCourses(undefined, undefined, 100);
      const lookup = new Map(all.courses.map((c) => [c.id, c]));
      setRows(ids.map((id) => lookup.get(id)).filter(Boolean) as AudioCourseRow[]);
    } finally { setLoading(false); setRefreshing(false); }
  };
  useEffect(() => { void load(); }, []);

  const remove = async (id: string) => {
    await toggleMyList(id);
    setRows((r) => r.filter((c) => c.id !== id));
  };

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color="#0ea5e9" /></View>;
  }
  return (
    <FlatList
      style={styles.bg}
      contentContainerStyle={{ paddingTop: 56, paddingBottom: 24 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(); }} tintColor="#0ea5e9" />}
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.title}>{t("mylist.title")}</Text>
          <Text style={styles.sub}>{t("mylist.sub")}</Text>
        </View>
      }
      ListEmptyComponent={
        <View style={styles.empty}>
          <Text style={styles.emptyTitle}>{t("mylist.emptyTitle")}</Text>
          <Text style={styles.emptyBody}>{t("mylist.emptyBody")}</Text>
        </View>
      }
      data={rows}
      keyExtractor={(c) => c.id}
      renderItem={({ item }) => (
        <Pressable style={styles.row} onPress={() => onOpenCourse(item.id)}>
          <View style={{ flex: 1 }}>
            <Text style={styles.rowTitle}>🎧 {item.title}</Text>
            <Text style={styles.rowMeta}>
              {item.category} · {item.duration_min} {t("meta.min")} · {item.segments} {t("meta.segments")}
            </Text>
          </View>
          <Pressable onPress={() => void remove(item.id)} hitSlop={12}>
            <Text style={styles.star}>★</Text>
          </Pressable>
        </Pressable>
      )}
    />
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: "#0b1020" },
  center: { flex: 1, backgroundColor: "#0b1020", alignItems: "center", justifyContent: "center" },
  header: { paddingHorizontal: 16, paddingBottom: 12 },
  title: { color: "#e8ecf6", fontSize: 24, fontWeight: "800" },
  sub: { color: "#9aa6c2", marginTop: 4 },
  empty: { alignItems: "center", paddingHorizontal: 28, paddingTop: 60 },
  emptyTitle: { color: "#e8ecf6", fontSize: 18, fontWeight: "700" },
  emptyBody: { color: "#9aa6c2", marginTop: 8, textAlign: "center" },
  row: {
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: "#151c34", borderRadius: 12,
    padding: 14, marginHorizontal: 12, marginBottom: 10,
  },
  rowTitle: { color: "#e8ecf6", fontSize: 15, fontWeight: "700" },
  rowMeta: { color: "#9aa6c2", fontSize: 12, marginTop: 4 },
  star: { color: "#fbbf24", fontSize: 26, fontWeight: "800", paddingHorizontal: 6 },
});
