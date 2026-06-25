import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator, Alert, FlatList, StyleSheet, Text, TextInput, View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import {
  getLearnFacets, searchLearnable,
  type LearnableItem,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import { getMyList, recordInterest, toggleMyList } from "../storage";
import { useT } from "../i18n";
import { categoryGradient, theme } from "../theme";

type Props = {
  onOpen: (id: string) => void;
  initialCategory?: string;
};

const FORMAT_ICON: Record<string, keyof typeof Ionicons.glyphMap> = {
  audio: "headset",
  live_class: "school",
  interactive: "globe",
  game: "game-controller",
  program: "library",
  video: "play-circle",
};

const FORMAT_LABELS: Record<string, string> = {
  audio: "Audio",
  live_class: "Live",
  interactive: "Interactive",
  game: "Games",
  program: "Programs",
  video: "Video",
  language: "Languages",
};

export default function AudioCoursesScreen({ onOpen, initialCategory }: Props) {
  const { t, locale } = useT();
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
    if (locale) params.locale = locale;
    searchLearnable(params)
      .then((r) => { setRows(r.items); setTotal(r.total); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [cat, format, q, locale]);

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
      <Text style={styles.kicker}>{t("tab.drive")}</Text>
      <Text style={styles.h1}>{t("drive.title")}</Text>
      <Text style={styles.sub}>Search live classes, audio, languages, and games</Text>
      <GlassPanel style={styles.searchWrap} padded={false}>
        <Ionicons name="search" size={18} color={theme.colors.muted} style={styles.searchIcon} />
        <TextInput
          style={styles.input}
          placeholder={t("drive.search")}
          placeholderTextColor={theme.colors.muted}
          value={q}
          onChangeText={setQ}
        />
      </GlassPanel>
      <FlatList
        horizontal showsHorizontalScrollIndicator={false} data={formats}
        keyExtractor={(f) => f}
        style={{ maxHeight: 52, marginBottom: 8 }}
        contentContainerStyle={{ paddingHorizontal: theme.spacing.screenX }}
        renderItem={({ item }) => {
          const on = format === item;
          const icon = FORMAT_ICON[item] || "ellipse";
          const label = FORMAT_LABELS[item] || item.replace(/_/g, " ");
          return (
            <AnimatedPressable
              onPress={() => setFormat(format === item ? "" : item)}
              style={[styles.formatChip, on && styles.formatChipOn]}
            >
              <Ionicons name={icon} size={16} color={on ? "#fff" : theme.colors.text} />
              <Text style={[styles.formatChipText, on && styles.formatChipTextOn]} numberOfLines={1}>
                {label}
              </Text>
            </AnimatedPressable>
          );
        }}
      />
      <FlatList
        horizontal showsHorizontalScrollIndicator={false} data={chips}
        keyExtractor={(c) => c || "all"}
        style={{ maxHeight: 44, marginBottom: 8 }}
        contentContainerStyle={{ paddingHorizontal: theme.spacing.screenX }}
        renderItem={({ item }) => (
          <AnimatedPressable
            onPress={() => setCat(item)}
            style={[styles.chip, cat === item && styles.chipOn]}
          >
            <Text style={[styles.chipText, cat === item && styles.chipTextOn]}>
              {item || t("drive.all")}
            </Text>
          </AnimatedPressable>
        )}
      />
      <Text style={styles.count}>{total} results</Text>
      {error ? (
        <GlassPanel style={{ marginHorizontal: theme.spacing.screenX, marginBottom: 8 }}>
          <Text style={styles.err}>{error}</Text>
        </GlassPanel>
      ) : null}
      {loading ? (
        <ActivityIndicator color={theme.colors.netflix} style={{ marginTop: 24 }} />
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(c) => c.id}
          contentContainerStyle={{ paddingHorizontal: theme.spacing.screenX, paddingBottom: 24 }}
          renderItem={({ item }) => {
            const icon = FORMAT_ICON[item.format] || "book";
            const [c1, c2] = categoryGradient(item.category || item.subject);
            const saved = item.format === "audio" && savedSet.has(item.source_id);
            return (
              <AnimatedPressable onPress={() => openItem(item)} style={{ marginBottom: 10 }}>
                <GlassPanel style={styles.cardRow} padded={false}>
                  <LinearGradient colors={[c1, c2]} style={styles.thumb}>
                    <Ionicons name={icon} size={22} color="#fff" />
                  </LinearGradient>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
                    <Text style={styles.meta}>
                      {item.format} · {item.category || item.subject}
                      {item.duration_min ? ` · ${item.duration_min} ${t("meta.min")}` : ""}
                    </Text>
                  </View>
                  {item.format === "audio" ? (
                    <AnimatedPressable
                      onPress={() => void onToggleSave(item.source_id)}
                      hitSlop={12}
                      style={styles.saveBtn}
                    >
                      <Ionicons
                        name={saved ? "bookmark" : "bookmark-outline"}
                        size={22}
                        color={saved ? theme.colors.gold : theme.colors.muted}
                      />
                    </AnimatedPressable>
                  ) : (
                    <Ionicons name="chevron-forward" size={18} color={theme.colors.muted} />
                  )}
                </GlassPanel>
              </AnimatedPressable>
            );
          }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "transparent", paddingTop: 56 },
  kicker: { ...theme.typography.kicker, color: theme.colors.muted, paddingHorizontal: theme.spacing.screenX },
  h1: { ...theme.typography.hero, color: theme.colors.text, paddingHorizontal: theme.spacing.screenX },
  sub: { color: theme.colors.muted, marginBottom: 12, paddingHorizontal: theme.spacing.screenX, ...theme.typography.body },
  searchWrap: {
    flexDirection: "row", alignItems: "center",
    marginHorizontal: theme.spacing.screenX, marginBottom: 12,
  },
  searchIcon: { marginLeft: 12 },
  input: { flex: 1, color: theme.colors.text, padding: 12, ...theme.typography.body },
  chip: {
    backgroundColor: "rgba(255,255,255,0.14)",
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginRight: 8,
  },
  chipOn: { backgroundColor: theme.colors.netflix, borderColor: theme.colors.netflix },
  chipText: { color: "#f8fafc", fontWeight: "700", fontSize: 13 },
  chipTextOn: { color: "#fff", fontWeight: "800" },
  formatChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255,255,255,0.16)",
    borderRadius: theme.radius.pill,
    borderWidth: 1.5,
    borderColor: "rgba(255,255,255,0.4)",
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
    minWidth: 72,
  },
  formatChipOn: { backgroundColor: theme.colors.netflix, borderColor: theme.colors.netflix },
  formatChipText: { color: "#f8fafc", fontWeight: "700", fontSize: 12, maxWidth: 88 },
  formatChipTextOn: { color: "#fff", fontWeight: "800" },
  count: { color: theme.colors.muted, fontSize: 12, marginBottom: 8, paddingHorizontal: theme.spacing.screenX },
  cardRow: { flexDirection: "row", alignItems: "center", gap: 12, padding: 12 },
  thumb: {
    width: 52, height: 52, borderRadius: theme.radius.sm,
    alignItems: "center", justifyContent: "center",
  },
  title: { color: theme.colors.text, fontSize: 16, fontWeight: "700" },
  meta: { color: theme.colors.muted, marginTop: 4, fontSize: 12 },
  saveBtn: { padding: 4 },
  err: { color: "#ff8a8a", ...theme.typography.body },
});
