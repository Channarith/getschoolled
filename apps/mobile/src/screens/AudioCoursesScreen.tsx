import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";
import { getAudioCategories, listAudioCourses, type AudioCourseRow } from "../api";
import { getMyList, recordInterest, toggleMyList } from "../storage";

type Props = {
  onOpen: (id: string) => void;
  initialCategory?: string;
};

export default function AudioCoursesScreen({ onOpen, initialCategory }: Props) {
  const [rows, setRows] = useState<AudioCourseRow[]>([]);
  const [cats, setCats] = useState<{ category: string; count: number }[]>([]);
  const [cat, setCat] = useState<string>(initialCategory || "");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savedSet, setSavedSet] = useState<Set<string>>(new Set());

  useEffect(() => { setCat(initialCategory || ""); }, [initialCategory]);
  useEffect(() => { getAudioCategories().then((r) => setCats(r.categories)).catch(() => {}); }, []);
  useEffect(() => { void getMyList().then((ids) => setSavedSet(new Set(ids))); }, []);

  useEffect(() => {
    setLoading(true);
    listAudioCourses(cat || undefined, q || undefined)
      .then((r) => setRows(r.courses))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [cat, q]);

  const chips = useMemo(() => [{ category: "", count: 0 }, ...cats], [cats]);

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
      <Text style={styles.h1}>🚗 Drive Mode</Text>
      <Text style={styles.sub}>Audio-only classes for the road — eyes free.</Text>
      <TextInput style={styles.input} placeholder="Search…" placeholderTextColor="#9aa6c2"
        value={q} onChangeText={setQ} />
      <FlatList
        horizontal showsHorizontalScrollIndicator={false} data={chips}
        keyExtractor={(c) => c.category || "all"} style={{ maxHeight: 44, marginBottom: 8 }}
        renderItem={({ item }) => (
          <Pressable onPress={() => setCat(item.category)}
            style={[styles.chip, cat === item.category && styles.chipOn]}>
            <Text style={styles.chipText}>{item.category || "All"}</Text>
          </Pressable>
        )}
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
                <Text style={styles.meta}>{item.category} · {item.duration_min} min · {item.segments} segments</Text>
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
