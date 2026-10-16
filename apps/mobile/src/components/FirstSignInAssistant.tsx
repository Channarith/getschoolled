import { useState } from "react";
import {
  Alert, Image, Modal, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View,
} from "react-native";

import {
  completeMobileAccountOnboarding,
  getMe,
  getMobileFreePlanOffer,
  selectMobileFreePlan,
  submitLearningProfile,
  submitMobileOnboardingLearner,
  submitOnboardingSurveyAnalytics,
  type StudentProfile,
} from "../api";
import { AGE_MAX, AGE_MIN, SETUP_COLORS as C } from "../learnerCheck";
import AgeWheel from "./AgeWheel";
import AnimatedPressable from "./AnimatedPressable";
import AvatarImage from "./AvatarImage";
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

const SCALE_ROWS = [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]];

type Stage = "about" | "learn" | "identity";

function ageBandFor(age: number) {
  if (age < 13) return "child";
  if (age < 18) return "teen";
  return "adult";
}

export default function FirstSignInAssistant({ visible, student, onComplete }: Props) {
  const [stage, setStage] = useState<Stage>("about");
  const [name, setName] = useState(student.display_name ?? "");
  const [age, setAge] = useState(0);
  const [studentId, setStudentId] = useState(student.id);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [focus, setFocus] = useState<string>("video");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const { width } = useWindowDimensions();
  const wide = width >= 800;
  const columns = width >= 1100 ? 3 : width >= 700 ? 2 : 1;
  const ageBand = age ? ageBandFor(age) : "adult";
  const aboutReady = name.trim().length > 0 && age >= AGE_MIN && age <= AGE_MAX;
  const rated = LEARNING_MODES.filter((mode) => ratings[mode.id] != null).length;
  const cardWidth = columns === 1 ? "100%" : columns === 2 ? "48.5%" : "32%";

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

  async function finish() {
    setBusy(true);
    setError("");
    try {
      const offer = await getMobileFreePlanOffer();
      if (!offer.available) {
        throw new Error(offer.reason || "The free plan is no longer available.");
      }
      await selectMobileFreePlan();
      await completeMobileAccountOnboarding(name.trim(), ageBand);
      onComplete();
    } catch (reason) {
      const message = String(reason).replace(/^Error:\s*/, "");
      setError(message);
      Alert.alert("Free plan", message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Modal visible={visible && stage !== "identity"} animationType="fade" presentationStyle="fullScreen">
        <SafeAreaView style={styles.root}>
          <View style={styles.header}>
            <Text style={styles.brand}>Salareen</Text>
            <View style={styles.bars}>
              {["about", "learn", "identity"].map((item, index) => (
                <View key={item} style={[styles.bar, index <= ["about", "learn", "identity"].indexOf(stage) && styles.active]} />
              ))}
            </View>
            <Text style={styles.kicker}>{stage === "about" ? "About you" : "How you learn"}</Text>
          </View>
          <View style={[styles.split, !wide && styles.splitStack, stage === "learn" && styles.splitLearn]}>
            {stage !== "learn" ? (
              <View style={[styles.artPane, !wide && styles.artBand]}>
                <KenBurnsImage source={ART.about} style={StyleSheet.absoluteFill} />
              </View>
            ) : null}
            <View style={styles.pane}>
          {stage === "about" ? (
            <ScrollView contentContainerStyle={[styles.paneBody, wide && styles.paneCenter]} keyboardShouldPersistTaps="handled">
              <View>
                <Text style={styles.title}>What should we call you?</Text>
                <Text style={styles.body}>This name appears on your profile and in class.</Text>
                <Text style={styles.label} nativeID="profile-name-label">Profile name</Text>
                <View style={styles.nameRow}>
                  <AvatarImage avatarId={student.avatar_id} size={48} accessibilityLabel="Your avatar" />
                  <TextInput
                    value={name}
                    onChangeText={setName}
                    placeholder="e.g. Maya"
                    placeholderTextColor={C.muted}
                    accessibilityLabel="Profile name"
                    accessibilityLabelledBy="profile-name-label"
                    autoComplete="nickname"
                    textContentType="nickname"
                    style={[styles.input, styles.nameInput]}
                    maxLength={80}
                  />
                </View>
                <Text style={styles.help}>
                  The name on your profile and avatar. A nickname is fine. It doesn’t need to be your legal name.
                </Text>
                <Text style={styles.label}>How old are you?</Text>
                <View style={styles.ageRow}>
                  <AgeWheel value={age} onChange={setAge} />
                  <Text style={styles.ageHint}>
                    {age ? (ageBand === "child" ? "Kids experience" : ageBand === "teen" ? "Teen experience" : "Adult experience") : "Scroll or tap to choose"}
                  </Text>
                </View>
                {age > 0 && ageBand !== "adult" ? (
                  <Text style={styles.note}>A parent or guardian will approve the camera and voice check.</Text>
                ) : null}
                {error ? <Text style={styles.error}>{error}</Text> : null}
              </View>
            </ScrollView>
          ) : (
            <ScrollView style={styles.learn} contentContainerStyle={styles.learnInner}>
              <Text style={styles.title}>How do you learn best?</Text>
              <Text style={styles.body}>Rate each from 1 (not for me) to 10 (I love it).</Text>
              <View style={styles.grid}>
              {LEARNING_MODES.map((mode) => {
                const value = ratings[mode.id];
                return (
                  <View key={mode.id} style={[styles.card, { width: cardWidth }, focus === mode.id && styles.cardFocus]}>
                    <View style={styles.cardArt}>
                      <Image source={mode.art} style={styles.cardImage} resizeMode="cover" />
                      {value != null ? <Text style={styles.score}>{value}</Text> : null}
                    </View>
                    <Text style={styles.cardLabel}>{mode.label}</Text>
                    <View style={styles.scale} accessibilityRole="radiogroup" accessibilityLabel={`Rate ${mode.label}`}>
                      {SCALE_ROWS.map((row) => (
                        <View key={row[0]} style={styles.scaleRow}>
                          {row.map((n) => {
                            const on = value != null && n <= value;
                            return (
                              <AnimatedPressable
                                key={n}
                                testID={`rate-${mode.id}-${n}`}
                                accessibilityRole="radio"
                                accessibilityLabel={`${n}`}
                                accessibilityState={{ checked: value === n }}
                                style={[styles.dot, on && styles.dotOn]}
                                onPress={() => {
                                  setRatings((current) => ({ ...current, [mode.id]: n }));
                                  setFocus(mode.id);
                                }}
                              >
                                <Text style={[styles.dotText, on && styles.dotTextOn]}>{n}</Text>
                              </AnimatedPressable>
                            );
                          })}
                        </View>
                      ))}
                    </View>
                  </View>
                );
              })}
              </View>
              {error ? <Text style={styles.error}>{error}</Text> : null}
            </ScrollView>
          )}
              <View style={styles.foot}>
                {stage === "about" ? (
                  <AnimatedPressable
                    disabled={busy || !aboutReady}
                    style={[styles.button, (busy || !aboutReady) && styles.disabled]}
                    onPress={() => void saveAbout()}
                  >
                    <Text style={styles.buttonText}>{busy ? "Saving…" : "Continue"}</Text>
                  </AnimatedPressable>
                ) : (
                  <>
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
                  </>
                )}
              </View>
            </View>
          </View>
        </SafeAreaView>
      </Modal>
      <BiometricSetupModal
        visible={visible && stage === "identity"}
        studentId={studentId}
        ageBand={ageBand}
        stepLabel="Step 4 of 4 · Learner Check"
        onDismiss={() => undefined}
        onComplete={() => void finish()}
      />
    </>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.panel },
  header: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: C.border, backgroundColor: C.bg,
  },
  brand: { color: C.text, fontSize: 17, fontWeight: "800" },
  bars: { flex: 1, flexDirection: "row", gap: 6, maxWidth: 220 },
  bar: { flex: 1, height: 4, borderRadius: 3, backgroundColor: C.border },
  active: { backgroundColor: C.accent },
  split: { flex: 1, flexDirection: "row", minHeight: 0 },
  splitStack: { flexDirection: "column" },
  splitLearn: { flexDirection: "column" },
  artPane: { flex: 1.15, minWidth: 0, backgroundColor: C.panel2, overflow: "hidden" },
  artBand: { flex: 0, height: "28%" },
  pane: { flex: 1, minWidth: 0, minHeight: 0, backgroundColor: C.panel, borderLeftWidth: 1, borderLeftColor: C.border },
  paneBody: { flexGrow: 1, padding: 24, gap: 8 },
  paneCenter: { justifyContent: "center" },
  learn: { flex: 1 },
  learnInner: { padding: 16, paddingBottom: 16, gap: 12 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  foot: {
    flexDirection: "row", alignItems: "center", gap: 8,
    paddingHorizontal: 16, paddingTop: 12, paddingBottom: 16,
    borderTopWidth: 1, borderTopColor: C.border, backgroundColor: C.panel,
  },
  kicker: { color: C.teal, fontSize: 12, fontWeight: "800", letterSpacing: 0.6 },
  title: { color: C.text, fontSize: 32, lineHeight: 36, fontWeight: "900", letterSpacing: -0.8, marginTop: 8 },
  body: { color: C.muted, fontSize: 16, lineHeight: 23, marginTop: 8, marginBottom: 14 },
  label: { color: C.text, fontSize: 15, fontWeight: "700", marginBottom: 8 },
  nameRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  input: {
    color: C.text, backgroundColor: C.panel, borderWidth: 1, borderColor: C.border,
    borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 19,
  },
  nameInput: { flex: 1 },
  help: { color: C.muted, fontSize: 13, lineHeight: 18, marginTop: 8, marginBottom: 16 },
  ageRow: { flexDirection: "row", alignItems: "center", gap: 14 },
  ageHint: { flex: 1, color: C.teal, fontSize: 15, fontWeight: "700" },
  note: { color: C.warmText, marginTop: 12, fontSize: 14 },
  card: { borderRadius: 16, overflow: "hidden", backgroundColor: C.panel, borderWidth: 1, borderColor: C.border },
  cardFocus: { borderColor: C.accent },
  cardArt: { height: 150, backgroundColor: C.panel2 },
  cardImage: { ...StyleSheet.absoluteFillObject, width: "100%", height: "100%" },
  cardLabel: { color: C.text, fontSize: 18, fontWeight: "800", paddingHorizontal: 14, paddingTop: 12 },
  score: {
    position: "absolute", right: 10, bottom: 10, minWidth: 44, height: 44, borderRadius: 22, overflow: "hidden",
    textAlign: "center", lineHeight: 44, fontSize: 19, fontWeight: "900", color: "#ffffff",
    backgroundColor: C.accent,
  },
  scale: { gap: 6, padding: 12 },
  scaleRow: { flexDirection: "row", gap: 6 },
  dot: {
    flex: 1, minWidth: 0, height: 44, borderRadius: 10, alignItems: "center", justifyContent: "center",
    backgroundColor: C.panel2, borderWidth: 1, borderColor: C.border,
  },
  dotOn: { backgroundColor: C.accent, borderColor: C.accent },
  dotText: { color: C.text, fontSize: 15, fontWeight: "700" },
  dotTextOn: { color: "#ffffff" },
  button: { flex: 1, minHeight: 48, borderRadius: 12, backgroundColor: C.accent, justifyContent: "center", alignItems: "center" },
  buttonText: { color: "#ffffff", fontSize: 16, fontWeight: "800" },
  disabled: { opacity: 0.45 },
  linkButton: { alignSelf: "center", paddingVertical: 10 },
  linkText: { color: C.muted, fontSize: 15, fontWeight: "700" },
  error: { color: C.danger, marginTop: 12 },
});
