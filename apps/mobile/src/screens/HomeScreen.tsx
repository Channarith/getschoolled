import { useEffect, useState } from "react";
import {
  ActivityIndicator, Image, ImageBackground, Modal, RefreshControl, ScrollView,
  StyleSheet, Text, View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import {
  getAudioCategories, listAudioCourses,
  type AudioCourseRow, type CategoryRow,
} from "../api";
import {
  bumpStreak, getInterests, getMyList, getStreak, listContinue,
  recordInterest, type ContinueRow,
} from "../storage";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import Rail, { CategoryTile, CourseCard } from "../components/Rail";
import MascotSvg from "../components/MascotSvg";
import AdBanner from "../components/AdBanner";
import { useAuth } from "../auth/AuthContext";
import { useT } from "../i18n";
import { theme, wallpapers } from "../theme";

const LOGO_MARK = require("../../assets/salareen_mark_256.png");

const EMOJIS_BY_CATEGORY: Record<string, string> = {
  Languages: "🌍", History: "🏛", Science: "🧪",
  "Personal Finance": "💰", Wellness: "🧘", Technology: "💻",
  Cooking: "🍳", Geography: "🗺", Sports: "🏅",
  Civics: "🏛", Business: "💼", Mindfulness: "✨",
};

export default function HomeScreen({
  onOpenCourse, onOpenCategory, onOpenArcade, onOpenGroupClasses, onOpenLiveClass,
  onOpenLanguages, onOpenRewards, onOpenSearch, guestMode = false,
}: {
  onOpenCourse: (id: string) => void;
  onOpenCategory: (category: string) => void;
  onOpenArcade?: () => void;
  onOpenGroupClasses?: () => void;
  onOpenLiveClass?: () => void;
  onOpenLanguages?: () => void;
  onOpenRewards?: () => void;
  onOpenSearch?: () => void;
  guestMode?: boolean;
}) {
  const { t, locale } = useT();
  const { account } = useAuth();
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
  const [showMascot, setShowMascot] = useState(false);
  const load = async (aliveObj: { current: boolean }) => {
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
      if (!aliveObj.current) return;
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
      if (!aliveObj.current) return;
      setStreakDays(streak.days);
    } catch (e) {
      if (aliveObj.current) setError(t("home.error", { error: String(e) }));
    } finally {
      if (aliveObj.current) { setLoading(false); setRefreshing(false); }
    }
  };

  // Reload whenever the user switches language so titles, categories,
  // and segment headings re-render in the new locale.
  useEffect(() => {
    const alive = { current: true };
    setLoading(true);
    void load(alive);
    return () => { alive.current = false; };
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
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.netflix} size="large" />
      </View>
    );
  }
  return (
    <ScrollView
      contentContainerStyle={{ paddingBottom: 32 }}
      style={styles.bg}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => { setRefreshing(true); const alive = { current: true }; void load(alive); }}
          tintColor={theme.colors.netflix}
        />
      }
    >
      <ImageBackground source={wallpapers.hero} style={styles.heroBanner} imageStyle={styles.heroImage}>
        <LinearGradient
          colors={["rgba(11,16,32,0.2)", "rgba(11,16,32,0.75)", "rgba(11,16,32,0.95)"]}
          style={StyleSheet.absoluteFill}
        />
        <View style={styles.heroInner}>
          <View style={styles.heroTopRow}>
            <AnimatedPressable
              accessibilityRole="button"
              accessibilityLabel="Show Bayon Buddy mascot"
              onPress={() => setShowMascot(true)}
              style={styles.logoButton}
            >
              <Image source={LOGO_MARK} style={styles.logoImg} resizeMode="contain" />
              <Text style={styles.logoText}>Salareen</Text>
            </AnimatedPressable>
            {onOpenSearch && (
              <AnimatedPressable
                accessibilityRole="button"
                accessibilityLabel="Search"
                onPress={onOpenSearch}
                style={styles.searchButton}
              >
                <Text style={styles.searchIcon}>&#x1F50D;</Text>
              </AnimatedPressable>
            )}
          </View>
          <Text style={styles.kicker}>{t("home.kicker")}</Text>
          <Text style={styles.hero}>{t("home.hero")}</Text>
          <Text style={styles.heroSub}>
            {streakDays > 0 ? t("home.subStreak", { days: streakDays }) : t("home.subDefault")}
          </Text>
          <View style={styles.actionDock}>
            {onOpenArcade ? (
              <HomeAction
                icon="game-controller-outline"
                label={t("home.navArcade")}
                onPress={onOpenArcade}
              />
            ) : null}
            {onOpenLanguages ? (
              <HomeAction
                icon="language-outline"
                label={t("home.navLanguages")}
                onPress={onOpenLanguages}
              />
            ) : null}
            {onOpenRewards ? (
              <HomeAction
                icon="trophy-outline"
                label={t("home.navRewards")}
                onPress={onOpenRewards}
              />
            ) : null}
            {onOpenGroupClasses ? (
              <HomeAction
                icon="people-outline"
                label={t("home.navGroups")}
                onPress={onOpenGroupClasses}
              />
            ) : null}
            {onOpenLiveClass ? (
              <HomeAction
                icon="videocam-outline"
                label={t("home.navLive")}
                onPress={onOpenLiveClass}
              />
            ) : null}
          </View>
          {guestMode ? (
            <Text style={styles.previewBadge}>{t("settings.previewBadge")}</Text>
          ) : null}
        </View>
      </ImageBackground>

      <Modal
        animationType="fade"
        transparent
        visible={showMascot}
        onRequestClose={() => setShowMascot(false)}
      >
        <AnimatedPressable style={styles.modalScrim} onPress={() => setShowMascot(false)}>
          <GlassPanel style={styles.mascotCard} padded={false}>
            <View style={{ padding: 18, alignItems: "center" }}>
              <Text style={styles.mascotTitle}>Bayon Buddy</Text>
              <Text style={styles.mascotSub}>Locale-aware study buddy with the S + Bodhi leaf mark.</Text>
              <MascotSvg width={220} height={360} showCaption />
              <PrimaryButton label="Close" onPress={() => setShowMascot(false)} variant="brand" />
            </View>
          </GlassPanel>
        </AnimatedPressable>
      </Modal>

      {error ? (
        <GlassPanel style={styles.errPanel}>
          <Text style={styles.err}>{error}</Text>
        </GlassPanel>
      ) : null}

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
              category={c.category}
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
              category={c.category}
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
            category={c.category}
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
            category={c.category}
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
            category={c.category}
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

      <AdBanner tier={account?.tier} placement="mobile-home-banner" />
    </ScrollView>
  );
}

function HomeAction({
  icon,
  label,
  onPress,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  label: string;
  onPress: () => void;
}) {
  return (
    <AnimatedPressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={styles.actionItem}
    >
      <View style={styles.actionIcon}>
        <Ionicons name={icon} size={23} color="#fff" />
      </View>
      <Text style={styles.actionLabel} numberOfLines={1}>{label}</Text>
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: "transparent" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  heroBanner: { minHeight: 340, justifyContent: "flex-end" },
  heroImage: { opacity: 0.95 },
  heroInner: { paddingHorizontal: theme.spacing.screenX, paddingTop: 56, paddingBottom: 24 },
  heroTopRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 14,
  },
  logoButton: {
    alignItems: "center", alignSelf: "flex-start", flexDirection: "row",
    gap: 10,
  },
  searchButton: {
    padding: 6,
    borderRadius: theme.radius.md,
    backgroundColor: "rgba(30,38,68,0.65)",
  },
  searchIcon: {
    fontSize: 18,
  },
  logoImg: { height: 44, width: 44, ...theme.shadow.hero },
  logoText: { color: theme.colors.text, fontSize: 15, fontWeight: "800", letterSpacing: 1 },
  kicker: { ...theme.typography.kicker, color: theme.colors.muted },
  hero: { ...theme.typography.hero, color: theme.colors.text, marginTop: 6 },
  heroSub: { color: "#c5cce0", marginTop: 8, ...theme.typography.body },
  actionDock: {
    alignItems: "flex-start",
    alignSelf: "stretch",
    backgroundColor: "rgba(8,13,28,0.82)",
    borderColor: "rgba(255,255,255,0.14)",
    borderRadius: 18,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-around",
    marginTop: 18,
    paddingHorizontal: 6,
    paddingVertical: 11,
  },
  actionItem: { alignItems: "center", flex: 1, minWidth: 0 },
  actionIcon: {
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.09)",
    borderRadius: 22,
    height: 43,
    justifyContent: "center",
    width: 43,
  },
  actionLabel: {
    color: theme.colors.text,
    fontSize: 10,
    fontWeight: "700",
    marginTop: 6,
    maxWidth: 64,
    textAlign: "center",
  },
  previewBadge: { color: theme.colors.muted, fontSize: 12, marginTop: 8 },
  errPanel: { marginHorizontal: theme.spacing.screenX, marginBottom: 12 },
  err: { color: "#ff8a8a", ...theme.typography.body },
  modalScrim: {
    alignItems: "center", backgroundColor: "rgba(3,7,18,0.82)", flex: 1,
    justifyContent: "center", padding: 20,
  },
  mascotCard: { maxWidth: 340, width: "100%" },
  mascotTitle: { color: theme.colors.text, fontSize: 22, fontWeight: "900" },
  mascotSub: { color: theme.colors.muted, marginBottom: 8, marginTop: 4, textAlign: "center" },
});
