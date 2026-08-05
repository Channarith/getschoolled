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

import { getKidsLesson, type KidsLesson } from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { speakNatural, stopSpeech } from "../tts";
import { theme } from "../theme";

export default function KidsLessonScreen({
  courseId,
  onBack,
}: {
  courseId: string;
  onBack: () => void;
}) {
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
    speakNatural(`${scene.title}. ${scene.instruction}`, { locale: "en" });
    return () => stopSpeech();
  }, [scene]);

  function choose(choice: string) {
    if (!scene || picked) return;
    setPicked(choice);
    const right = choice === scene.answer;
    if (right) setCorrectCount((n) => n + 1);
    speakNatural(right ? "Yes! That's right." : `Not quite. The answer is ${scene.answer}.`, { locale: "en" });
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
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <View style={styles.topRow}>
        <AnimatedPressable style={styles.backBtn} onPress={() => { stopSpeech(); onBack(); }}>
          <Ionicons name="chevron-back" size={18} color={theme.colors.text} />
          <Text style={styles.backText}>Back</Text>
        </AnimatedPressable>
        {lesson ? (
          <Text style={styles.progress} testID="kids-lesson-progress">
            {Math.min(sceneIdx + 1, total)} / {total}
          </Text>
        ) : null}
      </View>

      {error ? (
        <GlassPanel style={styles.panel}>
          <Text style={styles.error}>{error}</Text>
          <PrimaryButton label="Back to Kids" onPress={onBack} />
        </GlassPanel>
      ) : !lesson ? (
        <View style={styles.loading}><ActivityIndicator color={theme.colors.accent} /></View>
      ) : done ? (
        <GlassPanel style={styles.panel}>
          <View testID="kids-lesson-done" />
          <Text style={styles.celebrate}>🎉</Text>
          <Text style={styles.title}>Great job!</Text>
          <Text style={styles.body}>
            You finished {lesson.title} and got {correctCount} of {total} right.
          </Text>
          <PrimaryButton label="Play again" onPress={restart} />
          <AnimatedPressable style={styles.secondary} onPress={onBack}>
            <Text style={styles.secondaryText}>Pick another adventure</Text>
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
                <Text style={styles.choiceText}>{choice}</Text>
                {state === "right" ? <Text style={styles.choiceMark}>✓</Text> : null}
                {state === "wrong" ? <Text style={styles.choiceMark}>✕</Text> : null}
              </AnimatedPressable>
            );
          })}

          <AnimatedPressable
            style={styles.replay}
            onPress={() => speakNatural(`${scene.title}. ${scene.instruction}`, { locale: "en" })}
          >
            <Ionicons name="volume-high" size={16} color={theme.colors.text} />
            <Text style={styles.replayText}>Read it again</Text>
          </AnimatedPressable>

          {picked ? (
            <PrimaryButton
              testID="kids-lesson-next"
              label={sceneIdx + 1 >= total ? "Finish" : "Next"}
              onPress={next}
            />
          ) : null}
        </GlassPanel>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.bg },
  content: { padding: 16, paddingBottom: 40, gap: 12 },
  topRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  backBtn: { flexDirection: "row", alignItems: "center", gap: 4 },
  backText: { color: theme.colors.text, fontSize: 14, fontWeight: "600" },
  progress: { color: theme.colors.muted, fontSize: 13, fontWeight: "700" },
  loading: { paddingVertical: 48, alignItems: "center" },
  panel: { padding: 16, gap: 10, borderWidth: 2 },
  lessonTitle: { color: theme.colors.muted, fontSize: 13, fontWeight: "700" },
  title: { color: theme.colors.text, fontSize: 22, fontWeight: "800" },
  body: { color: theme.colors.muted, fontSize: 15, lineHeight: 21 },
  pictures: { flexDirection: "row", justifyContent: "center", gap: 14, marginVertical: 8 },
  picture: { fontSize: 64 },
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
  choiceText: { color: theme.colors.text, fontSize: 18, fontWeight: "700" },
  choiceMark: { fontSize: 20, fontWeight: "900", color: theme.colors.text },
  replay: { flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start", paddingVertical: 6 },
  replayText: { color: theme.colors.text, fontSize: 13, fontWeight: "600" },
  celebrate: { fontSize: 64, textAlign: "center" },
  secondary: { alignItems: "center", paddingVertical: 10 },
  secondaryText: { color: theme.colors.muted, fontSize: 14, fontWeight: "600" },
  error: { color: "#ff9b9b", fontSize: 14 },
});
