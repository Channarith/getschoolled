import { useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";
import { getAudioCategories, listAudioCourses, type AudioCourseRow } from "../api";

export default function AudioCoursesScreen({ onOpen }: { onOpen: (id: string) => void }) {
  const [rows, setRows] = useState<AudioCourseRow[]>([]);
  const [cats, setCats] = useState<{ category: string; count: number }[]>([]);
  const [cat, setCat] = useState<string>("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => { getAudioCategories().then((r) => setCats(r.categories)).catch(() => {}); }, []);
  useEffect(() => {
    setLoading(true);
    listAudioCourses(cat || undefined, q || undefined)
      .then((r) => setRows(r.courses))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [cat, q]);

  return (
    <View style={styles.container}>
      <Text style={styles.h1}>🚗 Drive Mode</Text>
      <Text style={styles.sub}>Audio-only classes for the road — eyes free.</Text>
      <TextInput style={styles.input} placeholder="Search…" placeholderTextColor="#9aa6c2"
        value={q} onChangeText={setQ} />
      <FlatList
        horizontal showsHorizontalScrollIndicator={false} data={[{ category: "", count: 0 }, ...cats]}
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
            <Pressable style={styles.card} onPress={() => onOpen(item.id)}>
              <Text style={styles.title}>🎧 {item.title}</Text>
              <Text style={styles.meta}>{item.category} · {item.duration_min} min · {item.segments} segments</Text>
            </Pressable>
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
  card: { backgroundColor: "#151c34", borderRadius: 14, padding: 16, marginBottom: 10 },
  title: { color: "#e8ecf6", fontSize: 17, fontWeight: "700" },
  meta: { color: "#9aa6c2", marginTop: 4 },
  err: { color: "#ff6b6b", marginBottom: 8 },
});
