import { useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { listAudioCourses, type AudioCourseRow } from "../api";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { theme } from "../theme";

const CATEGORY_EMOJI: Record<string, string> = {
  Science: "🔬", Math: "🔢", History: "📜", Art: "🎨",
  Music: "🎵", Languages: "🌍", Stories: "📚", Geography: "🗺️",
  Technology: "💻", Nature: "🌿", Animals: "🐾", Sports: "⚽",
  Cooking: "🍳", Mindfulness: "✨", Wellness: "🌈",
};

interface KidsScreenProps {
  onOpenCourse: (id: string) => void;
  onBack: () => void;
}

export default function KidsScreen({ onOpenCourse, onBack }: KidsScreenProps) {
  const { locale } = useT();
  useAndroidBackTo(onBack);
  const [courses, setCourses] = useState<AudioCourseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = async (alive?: { current: boolean }) => {
    setError("");
    try {
      const result = await listAudioCourses(undefined, undefined, 80, locale);
      // Filter to kid-friendly courses by checking tags for "kids" keyword.
      // Falls back to beginner-level courses if no explicit kids tag is present.
      const tagged = result.courses.filter((c) =>
        c.tags.some((tag) => tag.toLowerCase() === "kids") ||
        c.tags.some((tag) => tag.toLowerCase() === "children")
      );
      const beginner = result.courses.filter((c) => c.level === "beginner");
      const kidsContent = tagged.length > 0
        ? tagged
        : beginner.length > 0
          ? beginner.slice(0, 24)
          : result.courses.slice(0, 20);
      if (!alive || alive.current) setCourses(kidsContent);
    } catch (e) {
      if (!alive || alive.current) setError(String(e));
    } finally {
      if (!alive || alive.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  };

  useEffect(() => {
    const alive = { current: true };
    setLoading(true);
    void load(alive);
    return () => { alive.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale]);

  return (
    <View style={styles.wrap}>
      <LinearGradient
        colors={["#7c3aed", "#db2777"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.header}
      >
        <PrimaryButton label="← Back" onPress={onBack} variant="ghost" />
        <Text style={styles.title}>🎓 Kids Academy</Text>
        <Text style={styles.subtitle}>Learning adventures for young explorers!</Text>
      </LinearGradient>

      {loading && !refreshing ? (
        <ActivityIndicator color="#db2777" style={{ marginTop: 32 }} />
      ) : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); void load(); }}
            tintColor="#db2777"
          />
        }
      >
        {!loading && courses.length === 0 ? (
          <Text style={styles.empty}>
            🌟 No kids courses available yet. Check back soon!
          </Text>
        ) : null}
        {courses.map((course) => (
          <GlassPanel key={course.id} style={styles.card}>
            <Text style={styles.cardEmoji}>
              {CATEGORY_EMOJI[course.category] ?? "⭐"}
            </Text>
            <Text style={styles.cardTitle}>{course.title}</Text>
            <View style={styles.cardMeta}>
              <Text style={styles.categoryBadge}>{course.category}</Text>
              <Text style={styles.duration}>⏱ {course.duration_min} min</Text>
            </View>
            <View style={styles.cardActions}>
              <PrimaryButton
                label="Learn Now 🚀"
                onPress={() => onOpenCourse(course.id)}
                variant="brand"
              />
            </View>
          </GlassPanel>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingTop: 56 },
  header: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 22,
    gap: 8,
  },
  title: { color: "#fff", fontSize: 24, fontWeight: "900", marginTop: 4 },
  subtitle: { color: "rgba(255,255,255,0.85)", fontSize: 13, lineHeight: 18 },
  list: { gap: 16, padding: 16, paddingBottom: 32 },
  card: { gap: 10 },
  cardEmoji: { fontSize: 40 },
  cardTitle: { color: theme.colors.text, fontSize: 17, fontWeight: "800", lineHeight: 24 },
  cardMeta: { flexDirection: "row", gap: 10, alignItems: "center" },
  categoryBadge: {
    fontSize: 12, fontWeight: "700", color: "#db2777",
    backgroundColor: "rgba(219,39,119,0.15)",
    paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999,
  },
  duration: { color: theme.colors.muted, fontSize: 13 },
  cardActions: { marginTop: 4 },
  empty: {
    color: theme.colors.muted, textAlign: "center",
    marginTop: 40, fontSize: 15, lineHeight: 22,
  },
  error: { color: "#f87171", fontSize: 13, margin: 16 },
});
