import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";
import {
  getLearnFacets, searchLearnable,
  type LearnableItem,
} from "../api";
import { getMyList, recordInterest, toggleMyList } from "../storage";
import { useT } from "../i18n";

type Props = {
  onOpen: (id: string) => void;
  initialCategory?: string;
};

const FORMAT_EMOJI: Record<string, string> = {
  audio: "🎧",
  live_class: "🎓",
  interactive: "🌍",
  game: "🎮",
  program: "📚",
  video: "▶",
};

export default function AudioCoursesScreen({ onOpen, initialCategory }: Props) {
  const { t } = useT();
  const [rows, setRows] = useState<LearnableItem[]>([]);
  const [cats, setCats] = useState<string[]>([]);
  const [formats, setFormats] = useState<string[]>([]);
  const [cat, setCat] = useState<string>(initialCategory || "");
  const [format, setFormat] = useState<string>("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savedSet, setSavedSet] = useState<Set<string>>(new Set());
  const [total, setTotal] = useState(0);

  useEffect(() => { setCat(initialCategory || ""); }, [initialCategory]);
  useEffect(() => {
    getLearnFacets()
      .then((f) => {
        setCats(f.categories || []);
        setFormats(f.formats || []);
      })
      .catch(() => {});
  }, []);
  useEffect(() => { void getMyList().then((ids) => setSavedSet(new Set(ids))); }, []);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = { limit: "80" };
    if (cat) params.category = cat;
    if (format) params.format = format;
    if (q) params.q = q;
    searchLearnable(params)
      .then((r) => { setRows(r.items); setTotal(r.total); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [cat, format, q]);

  const chips = useMemo(() => ["", ...cats], [cats]);

  const onToggleSave = async (id: string) => {
    const saved = await toggleMyList(id);
    setSavedSet((s) => {
      const next = new Set(s);
      if (saved) next.add(id); else next.delete(id);
      return next;
    });
  };

  const openItem = (item: LearnableItem) => {
    if (item.format === "audio") {
      void recordInterest(item.category);
      onOpen(item.source_id);
      return;
    }
    Alert.alert(
      item.title,
      `${item.format} content opens in the Salareen web app (${item.deep_link || "salareen.com"}).`,
    );
  };

  return (
    <View style={styles.container}>
      <Text style={styles.h1}>{t("drive.title")}</Text>
      <Text style={styles.sub}>Search live classes, audio, languages, and games</Text>
      <TextInput style={styles.input} placeholder={t("drive.search")} placeholderTextColor="#9aa6c2"
        value={q} onChangeText={setQ} />
      <FlatList
        horizontal showsHorizontalScrollIndicator={false} data={formats}
        keyExtractor={(f) => f}
        style={{ maxHeight: 44, marginBottom: 8 }}
        renderItem={({ item }) => (
          <Pressable onPress={() => setFormat(format === item ? "" : item)}
            style={[styles.chip, format === item && styles.chipOn]}>
            <Text style={styles.chipText}>{item}</Text>
          </Pressable>
        )}
      />
      <FlatList
        horizontal showsHorizontalScrollIndicator={false} data={chips}
        keyExtractor={(c) => c || "all"}
        style={{ maxHeight: 44, marginBottom: 8 }}
        renderItem={({ item }) => (
          <Pressable onPress={() => setCat(item)}
            style={[styles.chip, cat === item && styles.chipOn]}>
            <Text style={styles.chipText}>{item || t("drive.all")}</Text>
          </Pressable>
        )}
      />
      <Text style={styles.count}>{total} results</Text>
      {error ? <Text style={styles.err}>{error}</Text> : null}
      {loading ? <ActivityIndicator color="#0ea5e9" /> : (
        <FlatList
          data={rows} keyExtractor={(c) => c.id}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Pressable onPress={() => openItem(item)} style={{ flex: 1 }}>
                <Text style={styles.title}>
                  {FORMAT_EMOJI[item.format] || "📖"} {item.title}
                </Text>
                <Text style={styles.meta}>
                  {item.format} · {item.category || item.subject}
                  {item.duration_min ? ` · ${item.duration_min} ${t("meta.min")}` : ""}
                </Text>
              </Pressable>
              {item.format === "audio" && (
                <Pressable onPress={() => void onToggleSave(item.source_id)} hitSlop={12}>
                  <Text style={[styles.star, savedSet.has(item.source_id) && styles.starOn]}>
                    {savedSet.has(item.source_id) ? "★" : "☆"}
                  </Text>
                </Pressable>
              )}
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
  count: { color: "#9aa6c2", fontSize: 12, marginBottom: 8 },
  card: { flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: "#151c34", borderRadius: 14, padding: 16, marginBottom: 10 },
  title: { color: "#e8ecf6", fontSize: 17, fontWeight: "700" },
  meta: { color: "#9aa6c2", marginTop: 4 },
  err: { color: "#ff6b6b", marginBottom: 8 },
  star: { color: "#5d6890", fontSize: 24, fontWeight: "800", paddingHorizontal: 6 },
  starOn: { color: "#fbbf24" },
});
