import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator, FlatList, RefreshControl, ScrollView,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
} from "react-native";

import { listLessons, type LessonRow } from "../api";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { theme } from "../theme";

export type LiveClassMode = "solo" | "group";

type Props = {
  onStart: (lessonId: string, title: string, classType: LiveClassMode) => void;
  onOpenLiveRooms: () => void;
  onBack: () => void;
};

// Audience display config
const AUDIENCE_LABELS: Record<string, string> = {
  all: "All",
  general: "General",
  kids: "👶 Kids",
  professional: "Professional",
  corporate: "Corporate",
  enterprise: "Enterprise",
};

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity
      onPress={onPress}
      style={[chipStyles.chip, active && chipStyles.chipActive]}
      activeOpacity={0.7}
    >
      <Text style={[chipStyles.chipText, active && chipStyles.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

const chipStyles = StyleSheet.create({
  chip: {
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingHorizontal: 14,
    paddingVertical: 6,
    marginRight: 8,
    backgroundColor: "rgba(255,255,255,0.04)",
  },
  chipActive: {
    borderColor: theme.colors.accent,
    backgroundColor: "rgba(110,168,254,0.15)",
  },
  chipText: { color: theme.colors.muted, fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#fff" },
});

function StarRating({ score, count }: { score: number; count: number }) {
  const stars = "★".repeat(Math.round(score)) + "☆".repeat(5 - Math.round(score));
  return (
    <Text style={{ color: "#f5c518", fontSize: 11 }}>
      {stars} <Text style={{ color: theme.colors.muted }}>({count})</Text>
    </Text>
  );
}

export default function LiveClassScreen({ onStart, onOpenLiveRooms, onBack }: Props) {
  const { t, locale } = useT();
  useAndroidBackTo(onBack);
  const classType: LiveClassMode = "solo";
  const [lessons, setLessons] = useState<LessonRow[]>([]);
  const [lessonId, setLessonId] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [langFilter, setLangFilter] = useState<string>("all");
  const [audienceFilter, setAudienceFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"default" | "language" | "level">("default");
  const mountedRef = useRef(true);
  const loadAliveRef = useRef<{ current: boolean }>({ current: false });

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const load = async (aliveObj: { current: boolean }) => {
    setError("");
    try {
      const rows = await listLessons();
      if (!aliveObj.current) return;
      setLessons(rows);
      if (rows.length && !lessonId) setLessonId(rows[0].lesson_id);
    } catch (e) {
      if (!aliveObj.current) return;
      setError((e as Error).message);
    } finally {
      if (aliveObj.current) { setLoading(false); setRefreshing(false); }
    }
  };

  useEffect(() => {
    const alive = { current: true };
    loadAliveRef.current = alive;
    void load(alive);
    return () => { alive.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Derive available filter options from the loaded lessons
  const availableLangs = useMemo(() => {
    const langs = new Set(lessons.map(l => l.language || "en"));
    return ["all", ...Array.from(langs).sort()];
  }, [lessons]);

  const availableAudiences = useMemo(() => {
    const auds = new Set(lessons.map(l => l.audience || "general"));
    return ["all", ...Array.from(auds).sort()];
  }, [lessons]);

  // Filtered + sorted lessons
  const filtered = useMemo(() => {
    let list = lessons;
    const ql = q.trim().toLowerCase();
    if (ql) {
      list = list.filter(l =>
        l.title.toLowerCase().includes(ql) ||
        (l.audience || "").toLowerCase().includes(ql) ||
        (l.track || "").toLowerCase().includes(ql) ||
        (l.role || "").toLowerCase().includes(ql) ||
        (l.level || "").toLowerCase().includes(ql)
      );
    }
    if (langFilter !== "all") list = list.filter(l => (l.language || "en") === langFilter);
    if (audienceFilter !== "all") list = list.filter(l => (l.audience || "general") === audienceFilter);
    if (sortBy === "language") list = [...list].sort((a, b) => (a.language || "en").localeCompare(b.language || "en"));
    else if (sortBy === "level") list = [...list].sort((a, b) => (a.level || "").localeCompare(b.level || ""));
    return list;
  }, [lessons, q, langFilter, audienceFilter, sortBy]);

  // Group by track (or audience if no track)
  const grouped = useMemo(() => {
    const groups: Record<string, LessonRow[]> = {};
    for (const l of filtered) {
      const key = l.track || AUDIENCE_LABELS[l.audience || "general"] || "General";
      if (!groups[key]) groups[key] = [];
      groups[key].push(l);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const selected = lessons.find(l => l.lesson_id === lessonId);

  function start() {
    if (!lessonId || !selected) return;
    onStart(lessonId, selected.title, classType);
  }

  return (
    <View style={styles.wrap}>
      {/* Header */}
      <View style={styles.header}>
        <PrimaryButton label={t("liveClass.back")} onPress={onBack} variant="ghost" />
        <Text style={styles.kicker}>{t("liveClass.kicker")}</Text>
        <Text style={styles.title}>{t("liveClass.title")}</Text>
        <Text style={styles.sub}>{t("liveClass.sub")}</Text>
        <View style={styles.liveRoomsAction}>
          <PrimaryButton label={t("live.browseCta")} onPress={onOpenLiveRooms} variant="ghost" />
        </View>
      </View>

      {/* Search bar */}
      <View style={styles.searchWrap}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search lessons, topics, roles…"
          placeholderTextColor={theme.colors.muted}
          value={q}
          onChangeText={setQ}
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
      </View>

      {/* Language chips */}
      {availableLangs.length > 2 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow} contentContainerStyle={{ paddingHorizontal: theme.spacing.screenX }}>
          {availableLangs.map(lang => (
            <Chip
              key={lang}
              label={lang === "all" ? "All Languages" : lang === (locale || "en") ? `${lang} ★` : lang}
              active={langFilter === lang}
              onPress={() => setLangFilter(lang)}
            />
          ))}
        </ScrollView>
      ) : null}

      {/* Audience chips (includes Kids) */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow} contentContainerStyle={{ paddingHorizontal: theme.spacing.screenX }}>
        {availableAudiences.map(aud => (
          <Chip
            key={aud}
            label={aud === "all" ? "All" : (AUDIENCE_LABELS[aud] ?? aud)}
            active={audienceFilter === aud}
            onPress={() => setAudienceFilter(aud)}
          />
        ))}
      </ScrollView>

      {/* Sort row */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow} contentContainerStyle={{ paddingHorizontal: theme.spacing.screenX }}>
        <Chip label="Default" active={sortBy === "default"} onPress={() => setSortBy("default")} />
        <Chip label="By Language" active={sortBy === "language"} onPress={() => setSortBy("language")} />
        <Chip label="By Level" active={sortBy === "level"} onPress={() => setSortBy("level")} />
      </ScrollView>

      {loading ? (
        <ActivityIndicator color={theme.colors.netflix} style={{ marginTop: 24 }} />
      ) : error ? (
        <GlassPanel style={{ margin: theme.spacing.screenX }}>
          <Text style={styles.err}>{error}</Text>
        </GlassPanel>
      ) : filtered.length === 0 ? (
        <GlassPanel style={{ margin: theme.spacing.screenX }}>
          <Text style={styles.sub}>No lessons match your filters.</Text>
        </GlassPanel>
      ) : (
        <ScrollView
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                loadAliveRef.current.current = false;
                const alive = { current: true };
                loadAliveRef.current = alive;
                void load(alive);
              }}
              tintColor={theme.colors.netflix}
            />
          }
        >
          {grouped.map(([groupName, items]) => (
            <View key={groupName}>
              <Text style={styles.groupHeader}>{groupName}</Text>
              {items.map(l => {
                const on = l.lesson_id === lessonId;
                const isKids = (l.audience || "").toLowerCase() === "kids";
                return (
                  <TouchableOpacity
                    key={l.lesson_id}
                    onPress={() => setLessonId(l.lesson_id)}
                    activeOpacity={0.7}
                    style={[styles.lessonRow, on && styles.lessonRowOn]}
                  >
                    <View style={styles.lessonMeta}>
                      {isKids ? <Text style={styles.kidsBadge}>👶 Kids</Text> : null}
                      {l.language && l.language !== "en" ? <Text style={styles.langBadge}>{l.language.toUpperCase()}</Text> : null}
                      {l.level ? <Text style={styles.levelBadge}>{l.level}</Text> : null}
                    </View>
                    <Text style={[styles.lessonTitle, on && styles.lessonTitleOn]} numberOfLines={2}>{l.title}</Text>
                    {l.role ? <Text style={styles.lessonRole}>{l.role}</Text> : null}
                    {l.summary ? <Text style={styles.lessonSummary} numberOfLines={2}>{l.summary}</Text> : null}
                    {l.audience && l.audience !== "general" && !isKids ? (
                      <Text style={styles.lessonAudience}>{l.audience}</Text>
                    ) : null}
                  </TouchableOpacity>
                );
              })}
            </View>
          ))}

          <View style={{ marginTop: 20, marginBottom: 8 }}>
            <PrimaryButton
              label={selected ? `Start: ${selected.title}` : t("liveClass.startSolo")}
              onPress={start}
              disabled={!lessonId}
              variant="netflix"
            />
          </View>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1 },
  header: { paddingHorizontal: theme.spacing.screenX, paddingTop: 56, marginBottom: 12 },
  liveRoomsAction: { marginTop: 14 },
  kicker: { color: theme.colors.muted, fontSize: 11, fontWeight: "800", letterSpacing: 1.2, marginTop: 8 },
  title: { color: theme.colors.text, fontSize: 26, fontWeight: "800", marginTop: 4 },
  sub: { color: theme.colors.muted, fontSize: 14, lineHeight: 20, marginTop: 8 },
  searchWrap: {
    marginHorizontal: theme.spacing.screenX,
    marginBottom: 10,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: "rgba(255,255,255,0.06)",
    paddingHorizontal: 12,
  },
  searchInput: { color: theme.colors.text, fontSize: 14, paddingVertical: 10 },
  chipRow: { flexGrow: 0, marginBottom: 8 },
  groupHeader: {
    color: theme.colors.muted,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.8,
    marginTop: 16,
    marginBottom: 8,
    marginHorizontal: theme.spacing.screenX,
    textTransform: "uppercase",
  },
  list: { paddingBottom: 32 },
  lessonRow: {
    marginHorizontal: theme.spacing.screenX,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: "rgba(255,255,255,0.04)",
    padding: 14,
    marginBottom: 8,
  },
  lessonRowOn: { borderColor: theme.colors.accent, backgroundColor: "rgba(110,168,254,0.1)" },
  lessonMeta: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 6 },
  kidsBadge: { fontSize: 11, color: "#a78bfa", fontWeight: "700" },
  langBadge: { fontSize: 11, color: theme.colors.accent, fontWeight: "700", backgroundColor: "rgba(110,168,254,0.12)", borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  levelBadge: { fontSize: 11, color: theme.colors.muted, fontWeight: "600", backgroundColor: "rgba(255,255,255,0.07)", borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  lessonTitle: { color: theme.colors.text, fontSize: 15, fontWeight: "700" },
  lessonTitleOn: { color: "#fff" },
  lessonRole: { color: theme.colors.accent, fontSize: 12, marginTop: 3, fontWeight: "600" },
  lessonSummary: { color: theme.colors.muted, fontSize: 12, marginTop: 4, lineHeight: 17 },
  lessonAudience: { color: theme.colors.muted, fontSize: 11, marginTop: 4, textTransform: "capitalize" },
  err: { color: theme.colors.netflix, fontSize: 13 },
});
