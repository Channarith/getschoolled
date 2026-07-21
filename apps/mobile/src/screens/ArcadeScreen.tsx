import { useEffect, useState } from "react";
import {
  ActivityIndicator, Alert, Linking, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";

import { ARCADE_SECTIONS, arcadeWebUrl } from "../arcadeCatalog";
import { getGamesCatalog, type GamesCatalog } from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { WEB_APP_URL } from "../config";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { theme } from "../theme";

const SUBJECT_EMOJI: Record<string, string> = {
  biology: "🧬", chemistry: "⚗️", physics: "🪐", math: "➗", science: "🔬",
  history: "🏛️", art: "🎨", technology: "💻", programming: "👾",
  life_growth: "🌱", etiquette: "🤝", wordplay: "🔤", geometry: "📐",
  creation: "🛠️", farming: "🌾", finance: "📈",
};

const FALLBACK_SUBJECTS = [
  "biology", "chemistry", "physics", "math", "science",
  "history", "art", "technology", "programming", "finance",
];

type Props = {
  onOpenSubject: (subject: string, gameType?: string) => void;
  onBack: () => void;
};

export default function ArcadeScreen({ onOpenSubject, onBack }: Props) {
  const { t, locale } = useT();
  useAndroidBackTo(onBack);
  const [cat, setCat] = useState<GamesCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = async (alive?: { current: boolean }) => {
    setError("");
    try {
      const result = await getGamesCatalog(locale);
      if (!alive || alive.current) setCat(result);
    } catch (e) {
      if (!alive || alive.current) setError(t("arcade.error", { error: String(e) }));
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

  const subjects = cat?.subjects?.length ? cat.subjects : FALLBACK_SUBJECTS;

  function labelFor(id: string): string {
    const loc = cat?.subjects_localized?.find((s) => s.id === id);
    if (loc?.name) return loc.name;
    return id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  async function openWebGame(path: string, label: string) {
    const url = arcadeWebUrl(WEB_APP_URL, path);
    try {
      const ok = await Linking.canOpenURL(url);
      if (!ok) {
        Alert.alert(t("arcade.webOpenFailed"), url);
        return;
      }
      await Linking.openURL(url);
    } catch {
      Alert.alert(t("arcade.webOpenFailed"), label);
    }
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label={t("arcade.back")} onPress={onBack} variant="ghost" />
        <Text style={styles.title}>{t("arcade.title")}</Text>
      </View>
      <Text style={styles.lead}>{t("arcade.intro")}</Text>

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {loading && !refreshing ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginTop: 24 }} />
      ) : null}

      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); void load(); }}
            tintColor={theme.colors.netflix}
          />
        }
      >
        <GlassPanel style={styles.featured}>
          <Text style={styles.sectionTitle}>{t("arcade.featured")}</Text>
          <Text style={styles.meta}>{t("arcade.featuredSub")}</Text>
          <AnimatedPressable
            accessibilityRole="button"
            accessibilityLabel={t("game.potionLab")}
            onPress={() => onOpenSubject("chemistry", "potion")}
            style={styles.featuredBtn}
          >
            <Text style={styles.featuredBtnText}>{t("game.potionLab")}</Text>
            <Text style={styles.featuredBtnHint}>{t("game.potionTip")}</Text>
          </AnimatedPressable>
        </GlassPanel>

        <GlassPanel style={styles.section}>
          <Text style={styles.sectionTitle}>{t("arcade.inApp")}</Text>
          <Text style={styles.meta}>{t("arcade.inAppSub")}</Text>
          <View style={styles.grid}>
            {subjects.map((id) => (
              <AnimatedPressable
                key={id}
                accessibilityRole="button"
                accessibilityLabel={labelFor(id)}
                onPress={() => onOpenSubject(id)}
                style={styles.tile}
              >
                <Text style={styles.tileEmoji}>{SUBJECT_EMOJI[id] ?? "🎮"}</Text>
                <Text style={styles.tileLabel} numberOfLines={2}>{labelFor(id)}</Text>
              </AnimatedPressable>
            ))}
          </View>
        </GlassPanel>

        {ARCADE_SECTIONS.filter((s) => s.id !== "native").map((section) => (
          <GlassPanel key={section.id} style={styles.section}>
            <Text style={styles.sectionTitle}>{section.title}</Text>
            <Text style={styles.meta}>{section.subtitle}</Text>
            <Text style={styles.webHint}>{t("arcade.webHint")}</Text>
            <View style={styles.linkGrid}>
              {section.games.map((game) => (
                <AnimatedPressable
                  key={game.id}
                  accessibilityRole="button"
                  accessibilityLabel={game.label}
                  onPress={() => void openWebGame(game.path, game.label)}
                  style={styles.linkTile}
                >
                  <Text style={styles.linkEmoji}>{game.emoji}</Text>
                  <Text style={styles.linkLabel} numberOfLines={2}>{game.label}</Text>
                </AnimatedPressable>
              ))}
            </View>
          </GlassPanel>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingHorizontal: 16, paddingTop: 56, gap: 8 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 20, fontWeight: "800", flex: 1 },
  lead: { color: theme.colors.muted, fontSize: 14, lineHeight: 20 },
  error: { color: "#f87171", fontSize: 13 },
  list: { gap: 14, paddingBottom: 32 },
  featured: { gap: 8 },
  section: { gap: 8 },
  sectionTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "800" },
  meta: { color: theme.colors.muted, fontSize: 13, lineHeight: 18 },
  webHint: { color: theme.colors.accent, fontSize: 11, fontWeight: "600", marginTop: 2 },
  featuredBtn: {
    backgroundColor: "rgba(124,58,237,0.25)",
    borderColor: "rgba(167,139,250,0.45)",
    borderRadius: theme.radius.md,
    borderWidth: 1,
    marginTop: 4,
    padding: 14,
  },
  featuredBtnText: { color: "#fff", fontSize: 16, fontWeight: "800" },
  featuredBtnHint: { color: theme.colors.muted, fontSize: 12, marginTop: 4, lineHeight: 16 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 4 },
  tile: {
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.06)",
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 14,
    width: "31%",
    minWidth: 96,
    flexGrow: 1,
  },
  tileEmoji: { fontSize: 28 },
  tileLabel: {
    color: theme.colors.text,
    fontSize: 12,
    fontWeight: "700",
    marginTop: 8,
    textAlign: "center",
  },
  linkGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 6 },
  linkTile: {
    backgroundColor: "rgba(255,255,255,0.08)",
    borderColor: "rgba(255,255,255,0.2)",
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 10,
    minWidth: "47%",
    flexGrow: 1,
    flexBasis: "45%",
  },
  linkEmoji: { fontSize: 18 },
  linkLabel: { color: theme.colors.text, fontSize: 13, fontWeight: "700", marginTop: 4 },
});
