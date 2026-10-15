import { useState } from "react";
import {
  Image, Modal, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  completeMobileAccountOnboarding,
  getMe,
  selectMobileFreePlan,
  submitLearningProfile,
  submitMobileOnboardingLearner,
  submitOnboardingSurveyAnalytics,
  type StudentProfile,
} from "../api";
import AnimatedPressable from "./AnimatedPressable";
import BiometricSetupModal from "./BiometricSetupModal";
import KenBurnsImage from "./KenBurnsImage";

type Props = {
  visible: boolean;
  student: StudentProfile;
  onComplete: () => void;
};

export const LEARNING_MODES = [
  { id: "video", label: "Watching videos", art: require("../../assets/setup-assistant/mode-video.webp") },
  { id: "live_teacher", label: "A live teacher", art: require("../../assets/setup-assistant/mode-person.webp") },
  { id: "presentation", label: "Presentations", art: require("../../assets/setup-assistant/mode-presentation.webp") },
  { id: "reading", label: "Reading a book", art: require("../../assets/setup-assistant/mode-reading.webp") },
  { id: "tutoring", label: "1:1 tutoring", art: require("../../assets/setup-assistant/mode-tutoring.webp") },
  { id: "gaming", label: "Gaming", art: require("../../assets/setup-assistant/mode-gaming.webp") },
] as const;

const ART = {
  about: require("../../assets/setup-assistant/about.webp"),
  learn: require("../../assets/setup-assistant/learn.webp"),
};

type Stage = "about" | "learn" | "identity";

function ageBandFor(age: number) {
  if (age < 13) return "child";
  if (age < 18) return "teen";
  return "adult";
}

export default function FirstSignInAssistant({ visible, student, onComplete }: Props) {
  const [stage, setStage] = useState<Stage>("about");
  const [name, setName] = useState("");
  const [age, setAge] = useState(0);
  const [studentId, setStudentId] = useState(student.id);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [focus, setFocus] = useState<string>("video");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const ageBand = age ? ageBandFor(age) : "adult";
  const rated = LEARNING_MODES.filter((mode) => ratings[mode.id] != null).length;
  const focusArt = LEARNING_MODES.find((mode) => mode.id === focus)?.art ?? ART.learn;

  async function withBusy(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (reason) {
      setError(String(reason).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  }

  function saveAbout() {
    return withBusy(async () => {
      const result = await submitMobileOnboardingLearner(name.trim(), age);
      setStudentId(result.studentId);
      setStage("learn");
    });
  }

  function saveLearning() {
    return withBusy(async () => {
      const answers = { modality_ratings: ratings };
      await submitLearningProfile(studentId, answers);
      const me = await getMe().catch(() => null);
      if (me) {
        void submitOnboardingSurveyAnalytics({ account_id: me.id, student_id: studentId, answers })
          .catch(() => undefined);
      }
      setStage("identity");
    });
  }

  function finish() {
    return withBusy(async () => {
      await selectMobileFreePlan().catch(() => undefined);
      await completeMobileAccountOnboarding(name.trim(), ageBand);
      onComplete();
    });
  }

  return (
    <>
      <Modal visible={visible && stage !== "identity"} animationType="fade" presentationStyle="fullScreen">
        <SafeAreaView style={styles.root}>
          <KenBurnsImage key={stage === "learn" ? focus : "about"} source={stage === "learn" ? focusArt : ART.about} opacity={stage === "learn" ? 0.45 : 0.9} />
          <View style={styles.scrim} />
          <View style={styles.bars}>
            {["about", "learn", "identity"].map((item, index) => (
              <View key={item} style={[styles.bar, index <= ["about", "learn", "identity"].indexOf(stage) && styles.active]} />
            ))}
          </View>

          {stage === "about" ? (
            <View style={styles.panel}>
              <Text style={styles.kicker}>Step 2 of 4 · About you</Text>
              <Text style={styles.title}>Hi! What should we call you?</Text>
              <Text style={styles.body}>Your personal assistant will set things up just for you.</Text>
              <TextInput
                value={name}
                onChangeText={setName}
                placeholder="Your first name"
                placeholderTextColor="#77819b"
                style={styles.input}
                maxLength={80}
              />
              <Text style={styles.label}>How old are you?</Text>
              <View style={styles.ageRow}>
                <AnimatedPressable style={styles.stepper} onPress={() => setAge((value) => Math.max(3, (value || 13) - 1))}>
                  <Text style={styles.stepperText}>−</Text>
                </AnimatedPressable>
                <TextInput
                  value={age ? String(age) : ""}
                  onChangeText={(text) => setAge(Math.min(120, Number(text.replace(/\D/g, "")) || 0))}
                  keyboardType="number-pad"
                  placeholder="—"
                  placeholderTextColor="#77819b"
                  accessibilityLabel="Age"
                  style={[styles.input, styles.ageInput]}
                />
                <AnimatedPressable style={styles.stepper} onPress={() => setAge((value) => Math.min(120, (value || 12) + 1))}>
                  <Text style={styles.stepperText}>+</Text>
                </AnimatedPressable>
              </View>
              {age > 0 && ageBand !== "adult" ? (
                <Text style={styles.note}>A parent or guardian will approve camera and voice setup.</Text>
              ) : null}
              {error ? <Text style={styles.error}>{error}</Text> : null}
              <AnimatedPressable
                disabled={busy || !name.trim() || age < 3}
                style={[styles.button, (busy || !name.trim() || age < 3) && styles.disabled]}
                onPress={() => void saveAbout()}
              >
                <Text style={styles.buttonText}>{busy ? "Saving…" : "Continue"}</Text>
              </AnimatedPressable>
            </View>
          ) : (
            <ScrollView style={styles.learn} contentContainerStyle={styles.learnInner}>
              <Text style={styles.kicker}>Step 3 of 4 · How you learn</Text>
              <Text style={styles.title}>How do you learn best?</Text>
              <Text style={styles.body}>Rate each one from 1 (not for me) to 10 (I love it).</Text>
              {LEARNING_MODES.map((mode) => {
                const value = ratings[mode.id];
                return (
                  <View key={mode.id} style={[styles.card, focus === mode.id && styles.cardFocus]}>
                    <View style={styles.cardArt}>
                      <Image source={mode.art} style={styles.cardImage} resizeMode="cover" />
                      {value != null ? <Text style={styles.score}>{value}</Text> : null}
                      <Text style={styles.cardLabel}>{mode.label}</Text>
                    </View>
                    <View style={styles.scale} accessibilityRole="radiogroup" accessibilityLabel={`Rate ${mode.label}`}>
                      {Array.from({ length: 10 }, (_, index) => index + 1).map((n) => (
                        <AnimatedPressable
                          key={n}
                          accessibilityRole="radio"
                          accessibilityState={{ checked: value === n }}
                          style={[styles.dot, value != null && n <= value && styles.dotOn]}
                          onPress={() => {
                            setRatings((current) => ({ ...current, [mode.id]: n }));
                            setFocus(mode.id);
                          }}
                        >
                          <Text style={[styles.dotText, value != null && n <= value && styles.dotTextOn]}>{n}</Text>
                        </AnimatedPressable>
                      ))}
                    </View>
                  </View>
                );
              })}
              {error ? <Text style={styles.error}>{error}</Text> : null}
              <AnimatedPressable
                disabled={busy || rated < LEARNING_MODES.length}
                style={[styles.button, (busy || rated < LEARNING_MODES.length) && styles.disabled]}
                onPress={() => void saveLearning()}
              >
                <Text style={styles.buttonText}>
                  {busy ? "Saving…" : rated < LEARNING_MODES.length ? `Rate ${LEARNING_MODES.length - rated} more` : "Continue"}
                </Text>
              </AnimatedPressable>
              <AnimatedPressable disabled={busy} onPress={() => setStage("about")} style={styles.linkButton}>
                <Text style={styles.linkText}>Back</Text>
              </AnimatedPressable>
            </ScrollView>
          )}
        </SafeAreaView>
      </Modal>
      <BiometricSetupModal
        visible={visible && stage === "identity"}
        studentId={studentId}
        ageBand={ageBand}
        stepLabel="Step 4 of 4 · Face & Voice ID"
        onDismiss={() => undefined}
        onComplete={() => void finish()}
      />
    </>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#04060f" },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(4,6,15,.55)" },
  bars: { flexDirection: "row", gap: 6, paddingHorizontal: 24, paddingTop: 16 },
  bar: { flex: 1, height: 4, borderRadius: 3, backgroundColor: "rgba(255,255,255,.2)" },
  active: { backgroundColor: "#8be9ff" },
  panel: { flex: 1, justifyContent: "flex-end", padding: 24, paddingBottom: 40 },
  learn: { flex: 1 },
  learnInner: { padding: 20, paddingBottom: 48, gap: 14 },
  kicker: { color: "#8be9ff", fontSize: 12, fontWeight: "900", letterSpacing: 1.5, textTransform: "uppercase", marginTop: 12 },
  title: { color: "#fff", fontSize: 38, lineHeight: 41, fontWeight: "900", letterSpacing: -1.4, marginTop: 8 },
  body: { color: "#d3dbee", fontSize: 17, lineHeight: 24, marginTop: 10, marginBottom: 16 },
  label: { color: "#e6ecfa", fontSize: 15, fontWeight: "700", marginBottom: 8 },
  input: {
    color: "#fff", backgroundColor: "rgba(10,14,30,.75)", borderWidth: 1, borderColor: "rgba(255,255,255,.18)",
    borderRadius: 16, padding: 16, fontSize: 20, marginBottom: 16,
  },
  ageRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  ageInput: { width: 96, textAlign: "center", marginBottom: 0 },
  stepper: {
    width: 52, height: 52, borderRadius: 26, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(255,255,255,.1)", borderWidth: 1, borderColor: "rgba(255,255,255,.18)",
  },
  stepperText: { color: "#fff", fontSize: 26, fontWeight: "600" },
  note: { color: "#ffd60a", marginTop: 12, fontSize: 14 },
  card: {
    borderRadius: 22, overflow: "hidden", backgroundColor: "rgba(12,16,34,.82)",
    borderWidth: 1, borderColor: "rgba(255,255,255,.1)",
  },
  cardFocus: { borderColor: "rgba(139,233,255,.6)" },
  cardArt: { height: 150, justifyContent: "flex-end" },
  cardImage: { ...StyleSheet.absoluteFillObject, width: "100%", height: "100%" },
  cardLabel: {
    color: "#fff", fontSize: 20, fontWeight: "900", padding: 14,
    textShadowColor: "rgba(0,0,0,.8)", textShadowRadius: 10,
  },
  score: {
    position: "absolute", right: 12, top: 12, minWidth: 42, height: 42, borderRadius: 21, overflow: "hidden",
    textAlign: "center", lineHeight: 42, fontSize: 19, fontWeight: "900", color: "#8be9ff",
    backgroundColor: "rgba(4,6,15,.75)",
  },
  scale: { flexDirection: "row", gap: 4, padding: 12 },
  dot: { flex: 1, height: 34, borderRadius: 9, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,255,255,.08)" },
  dotOn: { backgroundColor: "#8be9ff" },
  dotText: { color: "#b7c2dc", fontSize: 12, fontWeight: "800" },
  dotTextOn: { color: "#04060f" },
  button: { marginTop: 22, minHeight: 54, borderRadius: 999, backgroundColor: "#f4f7ff", justifyContent: "center", alignItems: "center" },
  buttonText: { color: "#04060f", fontSize: 16, fontWeight: "900" },
  disabled: { opacity: 0.45 },
  linkButton: { alignSelf: "center", paddingVertical: 10 },
  linkText: { color: "#a9b6d3", fontSize: 15, fontWeight: "700" },
  error: { color: "#ffb1b1", marginTop: 12 },
});
