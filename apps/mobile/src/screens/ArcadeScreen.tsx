import { ScrollView, StyleSheet, Text, View } from "react-native";

import { VISION_ARCADE, type VisionGame } from "../visionArcade";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { theme } from "../theme";

type Props = {
  onOpenSubject: (subject: string, gameType?: string) => void;
  onOpenVision: (game?: VisionGame) => void;
  onBack: () => void;
};

// Vision Play lists Machine Vision only. Other games and Worlds stay reachable
// from their own routes; they are not cards on this screen.
export default function ArcadeScreen({ onOpenVision, onBack }: Props) {
  const { t } = useT();
  useAndroidBackTo(onBack);

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label={t("arcade.back")} onPress={onBack} variant="ghost" />
        <Text style={styles.title}>{t("arcade.title")}</Text>
      </View>
      <Text style={styles.lead}>{t("arcade.intro")}</Text>

      <ScrollView contentContainerStyle={styles.list}>
        <GlassPanel style={styles.featured}>
          <Text style={styles.sectionTitle}>{t("arcade.visionTitle")}</Text>
          <Text style={styles.meta}>{t("arcade.visionBody")}</Text>
          <AnimatedPressable
            testID="vision-arcade-full"
            accessibilityRole="button"
            accessibilityLabel={t("arcade.visionOpen")}
            onPress={() => onOpenVision()}
            style={styles.featuredBtn}
          >
            <Text style={styles.featuredBtnText}>{t("arcade.visionOpen")}</Text>
            <Text style={styles.featuredBtnHint}>
              {t("arcade.visionHint", { n: VISION_ARCADE.reduce((n, section) => n + section.games.length, 0) })}
            </Text>
          </AnimatedPressable>
          {VISION_ARCADE.map((section) => (
            <View key={section.id} style={styles.visionGroup}>
              <Text style={styles.visionGroupTitle}>{section.title}</Text>
              <View style={styles.grid}>
                {section.games.map((game) => (
                  <AnimatedPressable
                    key={game.id}
                    testID={`vision-game-${game.id}`}
                    accessibilityRole="button"
                    accessibilityLabel={game.label}
                    onPress={() => onOpenVision(game)}
                    style={styles.tile}
                  >
                    <Text style={styles.tileEmoji}>{game.emoji}</Text>
                    <Text style={styles.tileLabel} numberOfLines={3}>{game.label}</Text>
                  </AnimatedPressable>
                ))}
              </View>
            </View>
          ))}
        </GlassPanel>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingHorizontal: 16, paddingTop: 56, gap: 8 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 20, fontWeight: "800", flex: 1, lineHeight: 26, minWidth: 0 },
  lead: { color: theme.colors.muted, fontSize: 14, lineHeight: 20 },
  error: { color: "#f87171", fontSize: 13 },
  list: { gap: 14, paddingBottom: 32 },
  featured: { gap: 8 },
  section: { gap: 8 },
  sectionTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "800", lineHeight: 21 },
  visionGroup: { gap: 6, marginTop: 8 },
  visionGroupTitle: { color: theme.colors.text, fontSize: 14, fontWeight: "700", lineHeight: 18 },
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
  featuredBtnText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "800",
    lineHeight: 21,
    includeFontPadding: false,
  },
  featuredBtnHint: {
    color: theme.colors.muted,
    fontSize: 12,
    marginTop: 4,
    lineHeight: 16,
    includeFontPadding: false,
  },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 4 },
  tile: {
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.06)",
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 14,
    width: "31%",
  },
  tileEmoji: { fontSize: 28 },
  tileLabel: {
    color: theme.colors.text,
    fontSize: 12,
    fontWeight: "700",
    includeFontPadding: false,
    lineHeight: 16,
    marginTop: 8,
    textAlign: "center",
    width: "100%",
  },
  linkGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 6 },
  linkTile: {
    backgroundColor: "rgba(255,255,255,0.08)",
    borderColor: "rgba(255,255,255,0.2)",
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 10,
    flexGrow: 1,
    flexBasis: "46%",
    maxWidth: "100%",
    minWidth: 0,
    overflow: "hidden",
  },
  linkEmoji: { fontSize: 18 },
  linkLabel: {
    color: theme.colors.text,
    fontSize: 13,
    fontWeight: "700",
    marginTop: 4,
    lineHeight: 17,
    includeFontPadding: false,
  },
});
