/**
 * Kids picture-lesson player.
 *
 * The Kids section could always LIST the early-learning adventures, but tapping
 * one dropped into Drive Mode, which has no audio course for them — so the
 * headline kids content was unreachable on mobile. This plays them, using the
 * same lesson content the web player uses (served from the curriculum service).
 */
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { getKidsLesson, type KidsLesson } from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import CornerChip from "../components/CornerChip";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { speakNatural, stopSpeech } from "../tts";
import { useT } from "../i18n";
import { theme } from "../theme";

export default function KidsLessonScreen({
  courseId,
  onBack,
}: {
  courseId: string;
  onBack: () => void;
}) {
  const { t, locale } = useT();
  const insets = useSafeAreaInsets();
  const [lesson, setLesson] = useState<KidsLesson | null>(null);
  const [error, setError] = useState("");
  const [sceneIdx, setSceneIdx] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    setError("");
    setLesson(null);
    getKidsLesson(courseId)
      .then((l) => { if (alive.current) setLesson(l); })
      .catch((e) => { if (alive.current) setError(String(e)); });
    return () => {
      alive.current = false;
      stopSpeech();
    };
  }, [courseId]);

  const scene = lesson?.scenes?.[sceneIdx] ?? null;
  const total = lesson?.scenes?.length ?? 0;
  const done = Boolean(lesson) && sceneIdx >= total;

  // Read the scene aloud: these learners are pre-readers.
  useEffect(() => {
    if (!scene) return;
    speakNatural(`${scene.title}. ${scene.instruction}`, { locale });
    return () => stopSpeech();
  }, [scene, locale]);

  function choose(choice: string) {
    if (!scene || picked) return;
    setPicked(choice);
    const right = choice === scene.answer;
    if (right) setCorrectCount((n) => n + 1);
    speakNatural(right ? t("kids.right") : t("kids.wrong", { answer: scene.answer }), { locale });
  }

  function next() {
    stopSpeech();
    setPicked(null);
    setSceneIdx((i) => i + 1);
  }

  function restart() {
    stopSpeech();
    setPicked(null);
    setCorrectCount(0);
    setSceneIdx(0);
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={[styles.content, { paddingTop: insets.top + 8 }]}>
      <CornerChip style={styles.topRow}>
        <AnimatedPressable style={styles.backBtn} onPress={() => { stopSpeech(); onBack(); }} accessibilityLabel={t("kids.back")}>
          <Ionicons name="chevron-back" size={16} color={theme.colors.goldTrim} />
        </AnimatedPressable>
        {lesson ? (
          <Text style={styles.progress} testID="kids-lesson-progress">
            {Math.min(sceneIdx + 1, total)} / {total}
          </Text>
        ) : null}
        {scene ? (
          <AnimatedPressable
            onPress={() => speakNatural(`${scene.title}. ${scene.instruction}`, { locale })}
            accessibilityLabel={t("kids.readAgain")}
          >
            <Ionicons name="volume-high" size={15} color={theme.colors.goldTrim} />
          </AnimatedPressable>
        ) : null}
      </CornerChip>

      {error ? (
        <GlassPanel style={styles.panel}>
          <Text style={styles.error}>{error}</Text>
          <PrimaryButton label={t("kids.backToList")} onPress={onBack} />
        </GlassPanel>
      ) : !lesson ? (
        <View style={styles.loading}><ActivityIndicator color={theme.colors.accent} /></View>
      ) : done ? (
        <GlassPanel style={styles.panel}>
          <View testID="kids-lesson-done" />
          <Text style={styles.celebrate}>🎉</Text>
          <Text style={styles.title}>{t("kids.greatJob")}</Text>
          <Text style={styles.body}>
            {t("kids.score", { title: lesson.title, correct: correctCount, total })}
          </Text>
          <PrimaryButton label={t("kids.playAgain")} onPress={restart} />
          <AnimatedPressable style={styles.secondary} onPress={onBack}>
            <Text style={styles.secondaryText}>{t("kids.pickAnother")}</Text>
          </AnimatedPressable>
        </GlassPanel>
      ) : scene ? (
        <GlassPanel style={[styles.panel, { borderColor: lesson.color }]}>
          <View testID="kids-lesson-scene" />
          <Text style={styles.lessonTitle}>{lesson.emoji} {lesson.title}</Text>
          <Text style={styles.title}>{scene.title}</Text>
          <Text style={styles.body}>{scene.instruction}</Text>

          <View style={styles.pictures}>
            {scene.pictures.map((p, i) => (
              <Text key={`${p}-${i}`} style={styles.picture}>{p}</Text>
            ))}
          </View>
          {scene.labels?.length ? (
            <View style={styles.labels}>
              {scene.labels.map((l, i) => (
                <Text key={`${l}-${i}`} style={styles.label}>{l}</Text>
              ))}
            </View>
          ) : null}

          <Text style={styles.question}>{scene.question}</Text>
          {scene.choices.map((choice) => {
            const isPicked = picked === choice;
            const isAnswer = choice === scene.answer;
            const state = !picked ? "idle" : isAnswer ? "right" : isPicked ? "wrong" : "idle";
            return (
              <AnimatedPressable
                key={choice}
                testID={`kids-choice-${choice}`}
                style={[
                  styles.choice,
                  state === "right" ? styles.choiceRight : undefined,
                  state === "wrong" ? styles.choiceWrong : undefined,
                ]}
                onPress={() => choose(choice)}
              >
                <Text style={styles.choiceText} numberOfLines={3}>{choice}</Text>
                {state === "right" ? <Text style={styles.choiceMark}>✓</Text> : null}
                {state === "wrong" ? <Text style={styles.choiceMark}>✕</Text> : null}
              </AnimatedPressable>
            );
          })}

          {picked ? (
            <PrimaryButton
              testID="kids-lesson-next"
              label={sceneIdx + 1 >= total ? t("kids.finish") : t("kids.next")}
              onPress={next}
            />
          ) : null}
        </GlassPanel>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  content: { flexGrow: 1, padding: 10, paddingBottom: 24, gap: 12 },
  topRow: { alignSelf: "flex-start" },
  backBtn: { flexDirection: "row", alignItems: "center", gap: 4 },
  backText: { color: theme.colors.text, fontSize: 14, fontWeight: "600" },
  progress: { color: theme.colors.muted, fontSize: 13, fontWeight: "700" },
  loading: { paddingVertical: 48, alignItems: "center" },
  panel: { flexGrow: 1, padding: 16, gap: 10, borderWidth: 1, borderColor: "rgba(232, 200, 114, 0.55)" },
  lessonTitle: { color: theme.colors.muted, fontSize: 13, fontWeight: "700", lineHeight: 18 },
  title: { color: theme.colors.text, fontSize: 22, fontWeight: "800", lineHeight: 28 },
  body: { color: theme.colors.muted, fontSize: 15, lineHeight: 21 },
  pictures: { flexDirection: "row", justifyContent: "center", flexWrap: "wrap", gap: 14, marginVertical: 8 },
  picture: { fontSize: 88 },
  labels: { flexDirection: "row", justifyContent: "center", gap: 12, flexWrap: "wrap" },
  label: { color: theme.colors.text, fontSize: 18, fontWeight: "800", letterSpacing: 2 },
  question: { color: theme.colors.text, fontSize: 17, fontWeight: "700", marginTop: 10 },
  choice: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.18)",
    backgroundColor: "rgba(255,255,255,0.06)",
  },
  choiceRight: { borderColor: "#2ecc71", backgroundColor: "rgba(46,204,113,0.18)" },
  choiceWrong: { borderColor: "#e74c3c", backgroundColor: "rgba(231,76,60,0.18)" },
  choiceText: { color: theme.colors.text, fontSize: 18, fontWeight: "700", flex: 1, lineHeight: 24, minWidth: 0 },
  choiceMark: { fontSize: 20, fontWeight: "900", color: theme.colors.text, flexShrink: 0, marginLeft: 8 },
  replay: { flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start", paddingVertical: 6 },
  replayText: { color: theme.colors.text, fontSize: 13, fontWeight: "600" },
  celebrate: { fontSize: 64, textAlign: "center" },
  secondary: { alignItems: "center", paddingVertical: 10 },
  secondaryText: { color: theme.colors.muted, fontSize: 14, fontWeight: "600" },
  error: { color: "#ff9b9b", fontSize: 14 },
});
