import { useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";

import { listAudioCourses, type AudioCourseRow } from "../api";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import StudioCourseSection from "../components/StudioCourseSection";
import type { StudioCourseId } from "../studioCourses";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { theme } from "../theme";

const CATEGORY_EMOJI: Record<string, string> = {
  Business: "💼", Technology: "💻", Leadership: "👔",
  Compliance: "⚖️", Safety: "🦺", "Personal Finance": "💰",
  AI: "🤖", Management: "📊", Wellness: "🧘", Communication: "🗣️",
};

interface CorporateScreenProps {
  onOpenCourse: (id: string) => void;
  onOpenStudio?: (courseId: StudioCourseId) => void;
  onBack: () => void;
}

export default function CorporateScreen({ onOpenCourse, onOpenStudio, onBack }: CorporateScreenProps) {
  const { locale } = useT();
  useAndroidBackTo(onBack);
  const [courses, setCourses] = useState<AudioCourseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = async (alive?: { current: boolean }) => {
    setError("");
    try {
      // The audio catalog has no "corporate" category (that audience exists
      // only for programs on web) — "Business & Career" is the corporate
      // training shelf. The old value matched zero rows in every locale.
      const result = await listAudioCourses("Business & Career", undefined, 80, locale);
      if (!alive || alive.current) setCourses(result.courses);
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
      <View style={styles.header}>
        <PrimaryButton label="← Back" onPress={onBack} variant="ghost" />
        <View style={styles.headerText}>
          <Text style={styles.title}>💼 Corporate Training</Text>
          <Text style={styles.subtitle}>
            Professional skills — compliance, safety, AI, leadership
          </Text>
        </View>
      </View>

      {loading && !refreshing ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginTop: 32 }} />
      ) : null}
      {onOpenStudio ? <StudioCourseSection onOpen={onOpenStudio} /> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); void load(); }}
            tintColor={theme.colors.accent}
          />
        }
      >
        {!loading && courses.length === 0 ? (
          <Text style={styles.empty}>No corporate courses available.</Text>
        ) : null}
        {courses.map((course) => (
          <GlassPanel key={course.id} style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.categoryBadge} numberOfLines={2}>{course.category}</Text>
              <Text style={styles.duration}>{course.duration_min} min</Text>
            </View>
            <Text style={styles.cardEmoji}>
              {CATEGORY_EMOJI[course.category] ?? "📋"}
            </Text>
            <Text style={styles.cardTitle}>{course.title}</Text>
            <View style={styles.cardActions}>
              <PrimaryButton
                label="Start Course"
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
    backgroundColor: "#0a1628",
    paddingHorizontal: 16,
    paddingBottom: 18,
    gap: 10,
  },
  headerText: { gap: 4, paddingHorizontal: 4 },
  title: { color: "#fff", fontSize: 22, fontWeight: "800" },
  subtitle: { color: "#8899bb", fontSize: 13, lineHeight: 18 },
  list: { gap: 14, padding: 16, paddingBottom: 32 },
  card: { gap: 10 },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 },
  categoryBadge: {
    flexShrink: 1,
    fontSize: 11, fontWeight: "700", color: theme.colors.accent, lineHeight: 15,
    backgroundColor: "rgba(110,168,254,0.15)",
    paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999, overflow: "hidden",
  },
  duration: { color: theme.colors.muted, fontSize: 12, flexShrink: 0 },
  cardEmoji: { fontSize: 30 },
  cardTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "700", lineHeight: 22 },
  cardActions: { marginTop: 4 },
  empty: { color: theme.colors.muted, textAlign: "center", marginTop: 40, fontSize: 15 },
  error: { color: "#f87171", fontSize: 13, margin: 16 },
});
