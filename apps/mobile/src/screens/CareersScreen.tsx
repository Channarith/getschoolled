import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, Linking, Pressable, StyleSheet, Text,
  TextInput, View,
} from "react-native";

import {
  getJobMatch, listJobs, type JobMatch, type JobPosting,
} from "../api";
import { useT } from "../i18n";

type Props = {
  onBack: () => void;
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
        <Pressable onPress={onBack} accessibilityRole="button">
          <Text style={styles.back}>{t("careers.back")}</Text>
        </Pressable>
        <Text style={styles.title}>{t("careers.title")}</Text>
        <Text style={styles.sub}>
          {t("careers.sub")}
          {source && source !== "sample" ? ` (${source})` : ""}
        </Text>
        <TextInput
          style={styles.input}
          placeholder={t("careers.searchRole")}
          placeholderTextColor="#6b7280"
          value={q}
          onChangeText={setQ}
          onSubmitEditing={refresh}
          returnKeyType="search"
        />
        <TextInput
          style={styles.input}
          placeholder={t("careers.searchLocation")}
          placeholderTextColor="#6b7280"
          value={loc}
          onChangeText={setLoc}
          onSubmitEditing={refresh}
          returnKeyType="search"
        />
      </View>

      {error ? <Text style={styles.err}>{error}</Text> : null}

      {match ? (
        <View style={styles.matchCard}>
          <View style={styles.matchHead}>
            <Text style={styles.matchTitle}>{match.job.title}</Text>
            <Pressable onPress={() => setMatch(null)}>
              <Text style={styles.close}>✕</Text>
            </Pressable>
          </View>
          <Text style={styles.meta}>
            {match.job.company} · {match.job.location}
          </Text>
          <Text style={styles.coverage}>
            {t("careers.coverage", { pct: match.coverage_pct })}
          </Text>
          {match.matched_courses.slice(0, 5).map((c) => (
            <Pressable key={c.course_id} onPress={() => onOpenCourse(c.course_id)}>
              <Text style={styles.courseLink}>▶ {c.title}</Text>
            </Pressable>
          ))}
          {match.job.url ? (
            <Pressable onPress={() => Linking.openURL(match.job.url)}>
              <Text style={styles.apply}>{t("careers.apply")}</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}

      {loading || matchLoading ? (
        <ActivityIndicator color="#0ea5e9" style={{ marginTop: 24 }} />
      ) : (
        <FlatList
          data={jobs}
          keyExtractor={(j) => j.id}
          contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
          renderItem={({ item }) => (
            <Pressable style={styles.card} onPress={() => openJob(item.id)}>
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
            </Pressable>
          )}
          ListEmptyComponent={
            <Text style={styles.muted}>{t("careers.empty")}</Text>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0b1020" },
  header: { paddingTop: 56, paddingHorizontal: 16, paddingBottom: 8 },
  back: { color: "#0ea5e9", fontSize: 16, marginBottom: 8 },
  title: { color: "#e8ecf6", fontSize: 24, fontWeight: "800" },
  sub: { color: "#9aa6c2", fontSize: 14, marginTop: 6, marginBottom: 12 },
  input: {
    backgroundColor: "#141c33", borderRadius: 10, padding: 12,
    color: "#e8ecf6", marginBottom: 8, borderWidth: 1, borderColor: "#1d2746",
  },
  err: { color: "#f87171", paddingHorizontal: 16, marginBottom: 8 },
  card: {
    backgroundColor: "#141c33", borderRadius: 12, padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: "#1d2746",
  },
  jobTitle: { color: "#e8ecf6", fontSize: 17, fontWeight: "700" },
  meta: { color: "#9aa6c2", fontSize: 13, marginTop: 4 },
  salary: { color: "#16a34a", fontSize: 13, marginTop: 4 },
  blurb: { color: "#cbd5e1", fontSize: 13, marginTop: 8, lineHeight: 18 },
  foot: { color: "#0ea5e9", fontSize: 12, marginTop: 8 },
  muted: { color: "#9aa6c2", textAlign: "center", marginTop: 24 },
  matchCard: {
    marginHorizontal: 16, marginBottom: 8, padding: 14,
    backgroundColor: "#0f172a", borderRadius: 12, borderColor: "#0ea5e9", borderWidth: 1,
  },
  matchHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  matchTitle: { color: "#e8ecf6", fontSize: 18, fontWeight: "700", flex: 1 },
  close: { color: "#9aa6c2", fontSize: 20, paddingLeft: 8 },
  coverage: { color: "#16a34a", marginTop: 8, fontWeight: "600" },
  courseLink: { color: "#0ea5e9", marginTop: 6, fontSize: 14 },
  apply: { color: "#7c3aed", marginTop: 10, fontWeight: "700" },
});
