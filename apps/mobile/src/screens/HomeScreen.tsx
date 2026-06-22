import { useEffect, useState } from "react";
import { ActivityIndicator, RefreshControl, ScrollView,
         StyleSheet, Text, View } from "react-native";

import {
  getAudioCategories, listAudioCourses,
  type AudioCourseRow, type CategoryRow,
} from "../api";
import {
  bumpStreak, getInterests, getMyList, getStreak, listContinue,
  recordInterest, type ContinueRow,
} from "../storage";
import Rail, { CategoryTile, CourseCard } from "../components/Rail";
import { useT } from "../i18n";

const EMOJIS_BY_CATEGORY: Record<string, string> = {
  Languages: "🌍", History: "🏛", Science: "🧪",
  "Personal Finance": "💰", Wellness: "🧘", Technology: "💻",
  Cooking: "🍳", Geography: "🗺", Sports: "🏅",
  Civics: "🏛", Business: "💼", Mindfulness: "✨",
};

export default function HomeScreen({
  onOpenCourse, onOpenCategory,
}: {
  onOpenCourse: (id: string) => void;
  onOpenCategory: (category: string) => void;
}) {
  const { t, locale } = useT();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [continueRows, setContinueRows] = useState<ContinueRow[]>([]);
  const [savedRows, setSavedRows] = useState<AudioCourseRow[]>([]);
  const [newRows, setNewRows] = useState<AudioCourseRow[]>([]);
  const [forYou, setForYou] = useState<AudioCourseRow[]>([]);
  const [trending, setTrending] = useState<AudioCourseRow[]>([]);
  const [cats, setCats] = useState<CategoryRow[]>([]);
  const [streakDays, setStreakDays] = useState(0);
  const [savedSet, setSavedSet] = useState<Set<string>>(new Set());

  const load = async () => {
    setError("");
    try {
      const [cont, savedIds, allCats, all, interests] = await Promise.all([
        listContinue(), getMyList(), getAudioCategories(locale),
        listAudioCourses(undefined, undefined, 80, locale), getInterests(),
      ]);
      // Re-resolve the persisted Continue Listening rows against the
      // freshly loaded (locale-correct) catalog so a row stored when
      // the user was in JA doesn't display its old Japanese title
      // after switching to KM. Falls back to the stored title if the
      // course is no longer in the catalog (defensive).
      const courseLookup = new Map(all.courses.map((c) => [c.id, c]));
      const refreshedContinue = cont.map((c) => {
        const fresh = courseLookup.get(c.id);
        return fresh
          ? { ...c, title: fresh.title, category: fresh.category }
          : c;
      });
      setContinueRows(refreshedContinue);
      setCats(allCats.categories);
      const savedIdSet = new Set(savedIds);
      setSavedSet(savedIdSet);
      setNewRows(all.courses.slice(0, 12));
      setTrending(all.courses.slice(12, 24));

      const interestSet = new Set(interests);
      const matches = all.courses.filter((c) =>
        interestSet.has(c.category.toLowerCase()) ||
        c.tags.some((t) => interestSet.has(t.toLowerCase()))
      );
      setForYou(matches.length ? matches.slice(0, 12) : all.courses.slice(24, 36));

      if (savedIds.length) {
        // Same idea: map saved IDs to the locale-correct catalog rows.
        setSavedRows(savedIds.map((id) => courseLookup.get(id)).filter(Boolean) as AudioCourseRow[]);
      } else { setSavedRows([]); }

      const streak = await getStreak();
      setStreakDays(streak.days);
    } catch (e) {
      setError(t("home.error", { error: String(e) }));
    } finally {
      setLoading(false); setRefreshing(false);
    }
  };

  // Reload whenever the user switches language so titles, categories,
  // and segment headings re-render in the new locale.
  useEffect(() => {
    setLoading(true);
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale]);

  const open = (id: string, category?: string) => {
    // recordInterest stores LOCALIZED labels so the personalized inbox
    // can match the user's recent interests in any language. The
    // backend's notification feed builder is case-insensitive on the
    // English subject/category, so this is a soft signal regardless.
    if (category) void recordInterest(category);
    void bumpStreak();
    onOpenCourse(id);
  };

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color="#0ea5e9" /></View>;
  }
  return (
    <ScrollView
      contentContainerStyle={{ paddingBottom: 28, paddingTop: 56 }}
      style={styles.bg}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(); }} tintColor="#0ea5e9" />}
    >
      <View style={styles.heroBox}>
        <Text style={styles.kicker}>{t("home.kicker")}</Text>
        <Text style={styles.hero}>{t("home.hero")}</Text>
        <Text style={styles.heroSub}>
          {streakDays > 0 ? t("home.subStreak", { days: streakDays }) : t("home.subDefault")}
        </Text>
      </View>

      {error ? <Text style={styles.err}>{error}</Text> : null}

      {continueRows.length > 0 ? (
        <Rail
          title={t("rail.continue")}
          subtitle={t("rail.continueSub")}
          data={continueRows}
          keyExtractor={(c) => c.id}
          renderItem={(c) => (
            <CourseCard
              emoji="▶"
              title={c.title}
              meta={t("meta.segmentOf", { i: c.segment + 1, n: c.total })}
              onPress={() => open(c.id, c.category)}
              progressPct={Math.round(((c.segment + 1) / Math.max(1, c.total)) * 100)}
            />
          )}
        />
      ) : null}

      {savedRows.length > 0 ? (
        <Rail
          title={t("rail.mylist")}
          subtitle={t("rail.mylistSub")}
          data={savedRows}
          keyExtractor={(c) => c.id}
          renderItem={(c) => (
            <CourseCard
              emoji={EMOJIS_BY_CATEGORY[c.category] || "🎧"}
              title={c.title}
              meta={`${c.category} · ${c.duration_min} ${t("meta.min")}`}
              savedBadge
              onPress={() => open(c.id, c.category)}
            />
          )}
        />
      ) : null}

      <Rail
        title={t("rail.new")}
        subtitle={t("rail.newSub")}
        data={newRows}
        keyExtractor={(c) => c.id}
        renderItem={(c) => (
          <CourseCard
            emoji={EMOJIS_BY_CATEGORY[c.category] || "🎧"}
            title={c.title}
            meta={`${c.category} · ${c.duration_min} ${t("meta.min")}`}
            savedBadge={savedSet.has(c.id)}
            onPress={() => open(c.id, c.category)}
          />
        )}
      />

      <Rail
        title={t("rail.forYou")}
        subtitle={t("rail.forYouSub")}
        data={forYou}
        keyExtractor={(c) => c.id}
        renderItem={(c) => (
          <CourseCard
            emoji={EMOJIS_BY_CATEGORY[c.category] || "🎧"}
            title={c.title}
            meta={`${c.category} · ${c.duration_min} ${t("meta.min")}`}
            savedBadge={savedSet.has(c.id)}
            onPress={() => open(c.id, c.category)}
          />
        )}
      />

      <Rail
        title={t("rail.trending")}
        data={trending}
        keyExtractor={(c) => c.id}
        renderItem={(c) => (
          <CourseCard
            emoji="📈"
            title={c.title}
            meta={`${c.category} · ${c.duration_min} ${t("meta.min")}`}
            savedBadge={savedSet.has(c.id)}
            onPress={() => open(c.id, c.category)}
          />
        )}
      />

      <Rail
        title={t("rail.categories")}
        data={cats}
        keyExtractor={(c) => c.category_id || c.category}
        renderItem={(c) => (
          <CategoryTile category={c.category} count={c.count}
            countLabel={t("meta.classes", { n: c.count })}
            onPress={() => onOpenCategory(c.category_id || c.category)} />
        )}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: "#0b1020" },
  center: { flex: 1, backgroundColor: "#0b1020", alignItems: "center", justifyContent: "center" },
  heroBox: { paddingHorizontal: 16, paddingBottom: 16 },
  kicker: { color: "#9aa6c2", fontSize: 12, fontWeight: "700", letterSpacing: 1, textTransform: "uppercase" },
  hero: { color: "#e8ecf6", fontSize: 26, fontWeight: "800", marginTop: 4 },
  heroSub: { color: "#c5cce0", marginTop: 6 },
  err: { color: "#ff6b6b", paddingHorizontal: 16, paddingBottom: 12 },
});
