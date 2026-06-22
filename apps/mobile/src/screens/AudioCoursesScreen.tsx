import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";
import {
  getAudioCategories, listAudioCourses,
  type AudioCourseRow, type CategoryRow,
} from "../api";
import { getMyList, recordInterest, toggleMyList } from "../storage";
import { useT } from "../i18n";

type Props = {
  onOpen: (id: string) => void;
  initialCategory?: string;
};

export default function AudioCoursesScreen({ onOpen, initialCategory }: Props) {
  const { t, locale } = useT();
  const [rows, setRows] = useState<AudioCourseRow[]>([]);
  const [cats, setCats] = useState<CategoryRow[]>([]);
  const [cat, setCat] = useState<string>(initialCategory || "");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savedSet, setSavedSet] = useState<Set<string>>(new Set());

  useEffect(() => { setCat(initialCategory || ""); }, [initialCategory]);
  useEffect(() => {
    getAudioCategories(locale).then((r) => setCats(r.categories)).catch(() => {});
  }, [locale]);
  useEffect(() => { void getMyList().then((ids) => setSavedSet(new Set(ids))); }, []);

  useEffect(() => {
    setLoading(true);
    listAudioCourses(cat || undefined, q || undefined, 60, locale)
      .then((r) => setRows(r.courses))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [cat, q, locale]);

  // The browse chips list "All" + every category. We thread `category_id`
  // (canonical English) through onPress so filtering survives a locale
  // switch - the user clicks "Idiomas" in Spanish but the request still
  // sends category=Languages, and the server returns localized results.
  const chips = useMemo<CategoryRow[]>(
    () => [{ category: "", category_id: "", count: 0 }, ...cats],
    [cats],
  );

  const onToggleSave = async (id: string) => {
    const saved = await toggleMyList(id);
    setSavedSet((s) => {
      const next = new Set(s);
      if (saved) next.add(id); else next.delete(id);
      return next;
    });
  };

  return (
    <View style={styles.container}>
      <Text style={styles.h1}>{t("drive.title")}</Text>
      <Text style={styles.sub}>{t("drive.subtitle")}</Text>
      <TextInput style={styles.input} placeholder={t("drive.search")} placeholderTextColor="#9aa6c2"
        value={q} onChangeText={setQ} />
      <FlatList
        horizontal showsHorizontalScrollIndicator={false} data={chips}
        keyExtractor={(c) => c.category_id || c.category || "all"}
        style={{ maxHeight: 44, marginBottom: 8 }}
        renderItem={({ item }) => {
          const id = item.category_id || item.category;
          return (
            <Pressable onPress={() => setCat(id)}
              style={[styles.chip, cat === id && styles.chipOn]}>
              <Text style={styles.chipText}>{item.category || t("drive.all")}</Text>
            </Pressable>
          );
        }}
      />
      {error ? <Text style={styles.err}>{error}</Text> : null}
      {loading ? <ActivityIndicator color="#0ea5e9" /> : (
        <FlatList
          data={rows} keyExtractor={(c) => c.id}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Pressable onPress={() => { void recordInterest(item.category); onOpen(item.id); }}
                         style={{ flex: 1 }}>
                <Text style={styles.title}>🎧 {item.title}</Text>
                <Text style={styles.meta}>
                  {item.category} · {item.duration_min} {t("meta.min")} · {item.segments} {t("meta.segments")}
                </Text>
              </Pressable>
              <Pressable onPress={() => void onToggleSave(item.id)} hitSlop={12}>
                <Text style={[styles.star, savedSet.has(item.id) && styles.starOn]}>
                  {savedSet.has(item.id) ? "★" : "☆"}
                </Text>
              </Pressable>
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0b1020", padding: 16, paddingTop: 56 },
  h1: { color: "#e8ecf6", fontSize: 28, fontWeight: "800" },
  sub: { color: "#9aa6c2", marginBottom: 12 },
  input: { backgroundColor: "#1d2746", color: "#e8ecf6", borderRadius: 10, padding: 12, marginBottom: 10 },
  chip: { backgroundColor: "#151c34", borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8, marginRight: 8 },
  chipOn: { backgroundColor: "#0ea5e9" },
  chipText: { color: "#e8ecf6" },
  card: { flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: "#151c34", borderRadius: 14, padding: 16, marginBottom: 10 },
  title: { color: "#e8ecf6", fontSize: 17, fontWeight: "700" },
  meta: { color: "#9aa6c2", marginTop: 4 },
  err: { color: "#ff6b6b", marginBottom: 8 },
  star: { color: "#5d6890", fontSize: 24, fontWeight: "800", paddingHorizontal: 6 },
  starOn: { color: "#fbbf24" },
});
