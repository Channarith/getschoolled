import { useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";

import { listLessons, type LessonRow } from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
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

export default function LiveClassScreen({ onStart, onOpenLiveRooms, onBack }: Props) {
  const { t } = useT();
  useAndroidBackTo(onBack);
  const [lessons, setLessons] = useState<LessonRow[]>([]);
  const [lessonId, setLessonId] = useState("");
  // Live Class is solo-only; the group option was removed from the UI.
  const classType: LiveClassMode = "solo";
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    const load = async () => {
      setError("");
      try {
        const rows = await listLessons();
        if (!alive) return;
        setLessons(rows);
        if (rows.length && !lessonId) setLessonId(rows[0].lesson_id);
      } catch (e) {
        if (!alive) return;
        setError((e as Error).message);
      } finally {
        if (alive) { setLoading(false); setRefreshing(false); }
      }
    };
    void load();
    return () => { alive = false; };
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
          onRefresh={async () => {
            setRefreshing(true);
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
          }}
          tintColor={theme.colors.netflix}
        />
      }
    >
      <View style={styles.header}>
        <PrimaryButton label={t("liveClass.back")} onPress={onBack} variant="ghost" />
        <Text style={styles.kicker}>{t("liveClass.kicker")}</Text>
        <Text style={styles.title}>{t("liveClass.title")}</Text>
        <Text style={styles.sub}>{t("liveClass.sub")}</Text>
        <View style={styles.liveRoomsAction}>
          <PrimaryButton
            label={t("live.browseCta")}
            onPress={onOpenLiveRooms}
            variant="ghost"
          />
        </View>
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
              label={t("liveClass.startSolo")}
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
  liveRoomsAction: { marginTop: 14 },
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
