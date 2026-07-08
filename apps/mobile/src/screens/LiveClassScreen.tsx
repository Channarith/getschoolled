import { useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";

import { listLessons, type LessonRow } from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useT } from "../i18n";
import { theme } from "../theme";

export type LiveClassMode = "solo" | "group";

type Props = {
  onStart: (lessonId: string, title: string, classType: LiveClassMode) => void;
  onBack: () => void;
};

export default function LiveClassScreen({ onStart, onBack }: Props) {
  const { t } = useT();
  const [lessons, setLessons] = useState<LessonRow[]>([]);
  const [lessonId, setLessonId] = useState("");
  const [classType, setClassType] = useState<LiveClassMode>("solo");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try {
      const rows = await listLessons();
      setLessons(rows);
      if (rows.length && !lessonId) setLessonId(rows[0].lesson_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selected = lessons.find((l) => l.lesson_id === lessonId);

  function start() {
    if (!lessonId || !selected) return;
    onStart(lessonId, selected.title, classType);
  }

  return (
    <ScrollView
      style={styles.bg}
      contentContainerStyle={styles.scroll}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => { setRefreshing(true); void load(); }}
          tintColor={theme.colors.netflix}
        />
      }
    >
      <View style={styles.header}>
        <PrimaryButton label={t("liveClass.back")} onPress={onBack} variant="ghost" />
        <Text style={styles.kicker}>{t("liveClass.kicker")}</Text>
        <Text style={styles.title}>{t("liveClass.title")}</Text>
        <Text style={styles.sub}>{t("liveClass.sub")}</Text>
      </View>

      {loading ? (
        <ActivityIndicator color={theme.colors.netflix} style={{ marginTop: 24 }} />
      ) : error ? (
        <GlassPanel>
          <Text style={styles.err}>{error}</Text>
        </GlassPanel>
      ) : lessons.length === 0 ? (
        <GlassPanel>
          <Text style={styles.sub}>{t("liveClass.empty")}</Text>
        </GlassPanel>
      ) : (
        <>
          <Text style={styles.section}>{t("liveClass.mode")}</Text>
          <View style={styles.modeRow}>
            <AnimatedPressable
              onPress={() => setClassType("solo")}
              style={[styles.modeChip, classType === "solo" && styles.modeChipOn]}
            >
              <Text style={[styles.modeText, classType === "solo" && styles.modeTextOn]}>
                {t("liveClass.solo")}
              </Text>
              <Text style={[styles.modeHint, classType === "solo" && styles.modeHintOn]}>
                {t("liveClass.soloHint")}
              </Text>
            </AnimatedPressable>
            <AnimatedPressable
              onPress={() => setClassType("group")}
              style={[styles.modeChip, classType === "group" && styles.modeChipOn]}
            >
              <Text style={[styles.modeText, classType === "group" && styles.modeTextOn]}>
                {t("liveClass.group")}
              </Text>
              <Text style={[styles.modeHint, classType === "group" && styles.modeHintOn]}>
                {t("liveClass.groupHint")}
              </Text>
            </AnimatedPressable>
          </View>

          <Text style={styles.section}>{t("liveClass.pickLesson")}</Text>
          {lessons.map((l) => {
            const on = l.lesson_id === lessonId;
            return (
              <AnimatedPressable
                key={l.lesson_id}
                onPress={() => setLessonId(l.lesson_id)}
                style={[styles.lessonRow, on && styles.lessonRowOn]}
              >
                <Text style={[styles.lessonTitle, on && styles.lessonTitleOn]}>{l.title}</Text>
                {l.language ? (
                  <Text style={styles.lessonMeta}>{l.language}{l.audience ? ` · ${l.audience}` : ""}</Text>
                ) : null}
              </AnimatedPressable>
            );
          })}

          <View style={{ marginTop: 20 }}>
            <PrimaryButton
              label={classType === "solo" ? t("liveClass.startSolo") : t("liveClass.startGroup")}
              onPress={start}
              disabled={!lessonId}
              variant="netflix"
            />
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  scroll: { paddingHorizontal: theme.spacing.screenX, paddingTop: 56, paddingBottom: 32 },
  header: { marginBottom: 20 },
  kicker: {
    color: theme.colors.muted,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.2,
    marginTop: 8,
  },
  title: { color: theme.colors.text, fontSize: 26, fontWeight: "800", marginTop: 4 },
  sub: { color: theme.colors.muted, fontSize: 14, lineHeight: 20, marginTop: 8 },
  section: {
    color: theme.colors.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.8,
    marginTop: 16,
    marginBottom: 10,
  },
  modeRow: { flexDirection: "row", gap: 10 },
  modeChip: {
    flex: 1,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: "rgba(255,255,255,0.04)",
    padding: 14,
  },
  modeChipOn: {
    borderColor: theme.colors.netflix,
    backgroundColor: "rgba(229,9,20,0.12)",
  },
  modeText: { color: theme.colors.text, fontSize: 15, fontWeight: "800" },
  modeTextOn: { color: "#fff" },
  modeHint: { color: theme.colors.muted, fontSize: 11, marginTop: 4, lineHeight: 15 },
  modeHintOn: { color: "rgba(255,255,255,0.75)" },
  lessonRow: {
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: "rgba(255,255,255,0.04)",
    padding: 14,
    marginBottom: 8,
  },
  lessonRowOn: {
    borderColor: theme.colors.accent,
    backgroundColor: "rgba(110,168,254,0.1)",
  },
  lessonTitle: { color: theme.colors.text, fontSize: 15, fontWeight: "700" },
  lessonTitleOn: { color: "#fff" },
  lessonMeta: { color: theme.colors.muted, fontSize: 12, marginTop: 4 },
  err: { color: theme.colors.netflix, fontSize: 13 },
});
