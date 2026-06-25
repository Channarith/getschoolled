import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, Linking, StyleSheet, Text,
  TextInput, View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

import {
  getJobMatch, listJobs, type JobMatch, type JobPosting,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useT } from "../i18n";
import { theme } from "../theme";

type Props = {
  onBack?: () => void;
  onOpenCourse: (id: string) => void;
};

function excerpt(text: string, max = 120): string {
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= max) return flat;
  return `${flat.slice(0, max).trim()}…`;
}

export default function CareersScreen({ onBack, onOpenCourse }: Props) {
  const { t } = useT();
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [loc, setLoc] = useState("");
  const [error, setError] = useState("");
  const [match, setMatch] = useState<JobMatch | null>(null);
  const [matchLoading, setMatchLoading] = useState(false);

  const refresh = useCallback(() => {
    setLoading(true);
    setError("");
    listJobs(q || undefined, loc || undefined)
      .then((r) => { setJobs(r.jobs); setSource(r.source); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [q, loc]);

  useEffect(() => { refresh(); }, [refresh]);

  const openJob = async (id: string) => {
    setMatchLoading(true);
    setError("");
    try {
      setMatch(await getJobMatch(id));
    } catch (e) {
      setError(String(e));
    } finally {
      setMatchLoading(false);
    }
  };

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        {onBack ? (
          <AnimatedPressable onPress={onBack} accessibilityRole="button">
            <View style={styles.backRow}>
              <Ionicons name="chevron-back" size={22} color={theme.colors.text} />
              <Text style={styles.back}>{t("careers.back")}</Text>
            </View>
          </AnimatedPressable>
        ) : null}
        <Text style={styles.kicker}>{t("home.careers")}</Text>
        <Text style={styles.title}>{t("careers.title")}</Text>
        <Text style={styles.sub}>
          {t("careers.sub")}
          {source && source !== "sample" ? ` (${source})` : ""}
        </Text>
        <GlassPanel style={styles.inputWrap} padded={false}>
          <Ionicons name="search" size={18} color={theme.colors.muted} style={{ marginLeft: 12 }} />
          <TextInput
            style={styles.input}
            placeholder={t("careers.searchRole")}
            placeholderTextColor={theme.colors.muted}
            value={q}
            onChangeText={setQ}
            onSubmitEditing={refresh}
            returnKeyType="search"
          />
        </GlassPanel>
        <GlassPanel style={styles.inputWrap} padded={false}>
          <Ionicons name="location-outline" size={18} color={theme.colors.muted} style={{ marginLeft: 12 }} />
          <TextInput
            style={styles.input}
            placeholder={t("careers.searchLocation")}
            placeholderTextColor={theme.colors.muted}
            value={loc}
            onChangeText={setLoc}
            onSubmitEditing={refresh}
            returnKeyType="search"
          />
        </GlassPanel>
      </View>

      {error ? (
        <GlassPanel style={{ marginHorizontal: theme.spacing.screenX, marginBottom: 8 }}>
          <Text style={styles.err}>{error}</Text>
        </GlassPanel>
      ) : null}

      {match ? (
        <GlassPanel style={styles.matchCard}>
          <View style={styles.matchHead}>
            <Text style={styles.matchTitle}>{match.job.title}</Text>
            <AnimatedPressable onPress={() => setMatch(null)}>
              <Ionicons name="close" size={22} color={theme.colors.muted} />
            </AnimatedPressable>
          </View>
          <Text style={styles.meta}>
            {match.job.company} · {match.job.location}
          </Text>
          <Text style={styles.coverage}>
            {t("careers.coverage", { pct: match.coverage_pct })}
          </Text>
          {match.matched_courses.slice(0, 5).map((c) => (
            <AnimatedPressable key={c.course_id} onPress={() => onOpenCourse(c.course_id)}>
              <View style={styles.courseLinkRow}>
                <Ionicons name="play-circle" size={16} color={theme.colors.brand} />
                <Text style={styles.courseLink}>{c.title}</Text>
              </View>
            </AnimatedPressable>
          ))}
          {match.job.url ? (
            <View style={{ marginTop: 12 }}>
              <PrimaryButton label={t("careers.apply")} onPress={() => Linking.openURL(match.job.url)} />
            </View>
          ) : null}
        </GlassPanel>
      ) : null}

      {loading || matchLoading ? (
        <ActivityIndicator color={theme.colors.netflix} style={{ marginTop: 24 }} />
      ) : (
        <FlatList
          data={jobs}
          keyExtractor={(j) => j.id}
          contentContainerStyle={{ padding: theme.spacing.screenX, paddingBottom: 100 }}
          renderItem={({ item }) => (
            <AnimatedPressable onPress={() => openJob(item.id)} style={{ marginBottom: 10 }}>
              <GlassPanel>
                <Text style={styles.jobTitle}>{item.title}</Text>
                <Text style={styles.meta}>
                  {item.company} · {item.location}
                  {item.employment_type ? ` · ${item.employment_type}` : ""}
                </Text>
                {item.salary_range ? (
                  <Text style={styles.salary}>{item.salary_range}</Text>
                ) : null}
                <Text style={styles.blurb}>{excerpt(item.description)}</Text>
                <Text style={styles.foot}>{t("careers.tapMatch")}</Text>
              </GlassPanel>
            </AnimatedPressable>
          )}
          ListEmptyComponent={
            <GlassPanel style={{ alignItems: "center", padding: 28 }}>
              <Text style={styles.muted}>{t("careers.empty")}</Text>
            </GlassPanel>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  header: { paddingTop: 56, paddingHorizontal: theme.spacing.screenX, paddingBottom: 8 },
  backRow: { flexDirection: "row", alignItems: "center", gap: 2, marginBottom: 12 },
  back: { color: theme.colors.text, fontSize: 16, fontWeight: "600" },
  kicker: { ...theme.typography.kicker, color: theme.colors.muted },
  title: { ...theme.typography.title, color: theme.colors.text, marginTop: 4 },
  sub: { color: theme.colors.muted, fontSize: 14, marginTop: 6, marginBottom: 12 },
  inputWrap: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  input: { flex: 1, padding: 12, color: theme.colors.text },
  err: { color: "#ff8a8a", ...theme.typography.body },
  matchCard: { marginHorizontal: theme.spacing.screenX, marginBottom: 8, borderColor: theme.colors.netflix },
  matchHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  matchTitle: { color: theme.colors.text, fontSize: 18, fontWeight: "700", flex: 1 },
  coverage: { color: theme.colors.success, marginTop: 8, fontWeight: "600" },
  courseLinkRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 8 },
  courseLink: { color: theme.colors.brand, fontSize: 14, flex: 1 },
  jobTitle: { color: theme.colors.text, fontSize: 17, fontWeight: "700" },
  meta: { color: theme.colors.muted, fontSize: 13, marginTop: 4 },
  salary: { color: theme.colors.success, fontSize: 13, marginTop: 4 },
  blurb: { color: "#cbd5e1", fontSize: 13, marginTop: 8, lineHeight: 18 },
  foot: { color: theme.colors.brand, fontSize: 12, marginTop: 8 },
  muted: { color: theme.colors.muted, textAlign: "center" },
});
