import { useRef, useState } from "react";
import {
  Keyboard, KeyboardAvoidingView, Modal, Platform, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  getMe,
  submitLearningProfile,
  submitMobileOnboardingLearner,
  submitOnboardingSurveyAnalytics,
  type StudentProfile,
} from "../api";
import MobileOnboardingPlanStep from "./MobileOnboardingPlanStep";
import { AGE_MAX, AGE_MIN, SETUP_COLORS as C } from "../learnerCheck";
import AgeWheel from "./AgeWheel";
import AnimatedPressable from "./AnimatedPressable";
import AvatarImage from "./AvatarImage";
import BiometricSetupModal from "./BiometricSetupModal";
import KenBurnsImage from "./KenBurnsImage";
import MobileMascotMeshy from "./MobileMascotMeshy";
import { type MascotScene } from "./MascotActor";
import { useLayoutMetrics } from "../layout";
import { withTimeout } from "../learnerCheck";
import { SAVE_WAIT_MS, isRetryableIdentityWrite, queueLearningProfileSync } from "../onboardingSync";

type Props = {
  visible: boolean;
  student: StudentProfile;
  onComplete: () => void;
};

/**
 * The six learning modalities the setup assistant asks about. Each one now
 * owns a themed mascot scene (`sceneKind`) so the survey page can act out the
 * modality: Sala puts on a baton for "a live teacher", picks up a book for
 * "reading", holds a joystick for "gaming", etc. Keep this list ordered —
 * the one-page-per-choice walker iterates it in order.
 */
export const LEARNING_MODES = [
  { id: "video",        label: "Watching videos", sceneKind: "video" },
  { id: "live_teacher", label: "A live teacher",  sceneKind: "teacher" },
  { id: "presentation", label: "Presentations",   sceneKind: "presentation" },
  { id: "reading",      label: "Reading a book",  sceneKind: "reading" },
  { id: "tutoring",     label: "1:1 tutoring",    sceneKind: "tutoring" },
  { id: "gaming",       label: "Gaming",          sceneKind: "gaming" },
] as const satisfies ReadonlyArray<{
  readonly id: string;
  readonly label: string;
  readonly sceneKind: Extract<MascotScene, { kind: string }>["kind"];
}>;

const ART = {
  about: require("../../assets/setup-assistant/about.webp"),
  learn: require("../../assets/setup-assistant/learn.webp"),
};

const SCALE_ROWS = [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]];

type Stage = "about" | "learn" | "identity" | "plan";

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
  // Learn step is now a walker — one modality per page. ``learnIndex`` is the
  // page cursor into LEARNING_MODES. ``focus`` still tracks the most recently
  // interacted mode for visual card accent (back-compat with the test suite).
  const [learnIndex, setLearnIndex] = useState(0);
  const [focus, setFocus] = useState<string>("video");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const learnerSave = useRef<Promise<{ studentId: string }> | null>(null);

  const { isCompact, isMedium, isExpanded, height, insets } = useLayoutMetrics();
  const wide = isMedium || isExpanded;
  const artHeight = isCompact ? Math.min(112, Math.round(height * 0.15)) : undefined;
  const ageBand = age ? ageBandFor(age) : "adult";
  const aboutReady = name.trim().length > 0 && age >= AGE_MIN && age <= AGE_MAX;
  const rated = LEARNING_MODES.filter((mode) => ratings[mode.id] != null).length;
  const currentMode = LEARNING_MODES[learnIndex];
  const currentRating = currentMode ? ratings[currentMode.id] : undefined;
  const isLastMode = learnIndex >= LEARNING_MODES.length - 1;

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
    Keyboard.dismiss();
    setError("");
    setStage("learn");
    const pending = submitMobileOnboardingLearner(name.trim(), age);
    learnerSave.current = pending;
    pending
      .then((result) => {
        if (learnerSave.current !== pending) return;
        setStudentId(result.studentId);
      })
      .catch((reason) => {
        if (learnerSave.current !== pending) return;
        learnerSave.current = null;
        setError(String(reason).replace(/^Error:\s*/, ""));
        setStage("about");
      });
  }

  function saveLearning() {
    return withBusy(async () => {
      const learner = learnerSave.current ? await learnerSave.current : null;
      const id = learner?.studentId || studentId;
      const answers = { modality_ratings: ratings };
      let saved = true;
      const sending = submitLearningProfile(id, answers);
      sending.catch(() => undefined);
      try {
        await withTimeout(sending, SAVE_WAIT_MS, "Saving your answers timed out.");
      } catch (reason) {
        // A busy identity service must not hold the learner on the ratings.
        // The request keeps running; the outbox sends the same ratings again.
        if (!id || !isRetryableIdentityWrite(reason)) throw reason;
        await queueLearningProfileSync(id, answers);
        saved = false;
      }
      if (saved) {
        // Analytics only. Nothing on the next screen needs it.
        void getMe()
          .then((me) => submitOnboardingSurveyAnalytics({ account_id: me.id, student_id: id, answers }))
          .catch(() => undefined);
      }
      setStage("identity");
    });
  }

  return (
    <>
      <Modal visible={visible && stage !== "identity" && stage !== "plan"} animationType="fade" presentationStyle="fullScreen">
        <SafeAreaView style={styles.root} edges={["top", "left", "right"]}>
          <KeyboardAvoidingView
            style={styles.fill}
            behavior={Platform.OS === "ios" ? "padding" : undefined}
          >
          <View style={styles.header}>
            <Text style={styles.brand}>Salareen</Text>
            <View style={styles.bars}>
              {["about", "learn", "identity", "plan"].map((item, index) => (
                <View key={item} style={[styles.bar, index <= ["about", "learn", "identity", "plan"].indexOf(stage) && styles.active]} />
              ))}
            </View>
            <Text style={styles.kicker}>{stage === "about" ? "About you" : "How you learn"}</Text>
          </View>
          <View style={[styles.split, !wide && styles.splitStack, stage === "learn" && styles.splitLearn]}>
            {/*
              Art pane. The Meshy GLB plays in front of the photo: a calm
              idle while the age wheel is in use, and a matching clip for
              the learning-mode card that is open.
            */}
            <View style={[
              styles.artPane,
              stage === "learn" && styles.artPaneLearn,
              isCompact && stage !== "learn" && { flex: 0, height: artHeight },
            ]}>
              <View style={styles.mascotStage} pointerEvents="none">
                <KenBurnsImage source={stage === "about" ? ART.about : ART.learn} style={StyleSheet.absoluteFill} />
                <MobileMascotMeshy
                  scene={
                    stage === "about"
                      ? (age > 0 ? { kind: "age-morph", age } : { kind: "idle" })
                      : ({ kind: currentMode?.sceneKind ?? "idle" } as MascotScene)
                  }
                  style={StyleSheet.absoluteFill}
                />
              </View>
            </View>
            <View style={styles.pane}>
          {stage === "about" ? (
            <ScrollView style={styles.scroller} contentContainerStyle={[styles.paneBody, wide && styles.paneCenter]} keyboardShouldPersistTaps="handled">
              <View>
                <Text style={[styles.title, isCompact && styles.titleCompact]}>What should we call you?</Text>
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
            /*
              One-page-per-choice survey. Previously six cards sat on the same
              screen; now each modality owns its own page so Sala can act out
              that modality on the art pane and the learner only sees one
              clean rating row at a time. The current page is driven by
              ``learnIndex``; Next / Back traverse the LEARNING_MODES list.
            */
            <ScrollView style={styles.learn} contentContainerStyle={styles.learnInner}>
              <Text style={[styles.title, isCompact && styles.titleCompact]}>How do you learn best?</Text>
              <Text style={styles.body}>
                Rate from 1 (not for me) to 10 (I love it). Step {learnIndex + 1} of {LEARNING_MODES.length}.
              </Text>
              {currentMode ? (
                <View
                  key={currentMode.id}
                  testID={`learn-page-${currentMode.id}`}
                  style={[styles.card, styles.cardFull, focus === currentMode.id && styles.cardFocus]}
                >
                  <Text style={styles.cardLabel}>{currentMode.label}</Text>
                  <View
                    style={styles.scale}
                    accessibilityRole="radiogroup"
                    accessibilityLabel={`Rate ${currentMode.label}`}
                  >
                    {SCALE_ROWS.map((row) => (
                      <View key={row[0]} style={styles.scaleRow}>
                        {row.map((n) => {
                          const on = currentRating != null && n <= currentRating;
                          return (
                            <AnimatedPressable
                              key={n}
                              testID={`rate-${currentMode.id}-${n}`}
                              accessibilityRole="radio"
                              accessibilityLabel={`${n} out of 10`}
                              accessibilityState={{ checked: currentRating === n }}
                              hitSlop={{ top: 6, bottom: 6, left: 4, right: 4 }}
                              style={[styles.dot, on && styles.dotOn]}
                              onPress={() => {
                                setRatings((current) => ({ ...current, [currentMode.id]: n }));
                                setFocus(currentMode.id);
                              }}
                            >
                              <Text style={[styles.dotText, on && styles.dotTextOn]}>{n}</Text>
                            </AnimatedPressable>
                          );
                        })}
                      </View>
                    ))}
                  </View>
                  {currentRating != null ? (
                    <Text style={styles.ratedHint}>Picked {currentRating}/10. Tap Next to continue.</Text>
                  ) : (
                    <Text style={styles.ratedHint}>Tap a number to rate this one, then Next.</Text>
                  )}
                </View>
              ) : null}
              {error ? <Text style={styles.error}>{error}</Text> : null}
            </ScrollView>
          )}
              <View style={[styles.foot, { paddingBottom: Math.max(insets.bottom, 12) }]}>
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
                    {/*
                      Walker controls. Next advances to the following modality
                      and only unlocks once the current one is rated. On the
                      last page, Next becomes Finish and submits.
                    */}
                    <AnimatedPressable
                      disabled={busy || currentRating == null}
                      style={[styles.button, (busy || currentRating == null) && styles.disabled]}
                      onPress={() => {
                        if (isLastMode) {
                          void saveLearning();
                        } else {
                          setLearnIndex((i) => Math.min(LEARNING_MODES.length - 1, i + 1));
                        }
                      }}
                    >
                      <Text style={styles.buttonText}>
                        {busy
                          ? "Saving…"
                          : isLastMode
                            ? (rated < LEARNING_MODES.length ? "Rate this one" : "Finish")
                            : (currentRating == null ? "Rate to continue" : "Next")}
                      </Text>
                    </AnimatedPressable>
                    <AnimatedPressable
                      disabled={busy}
                      onPress={() => {
                        if (learnIndex === 0) setStage("about");
                        else setLearnIndex((i) => Math.max(0, i - 1));
                      }}
                      style={styles.linkButton}
                    >
                      <Text style={styles.linkText}>Back</Text>
                    </AnimatedPressable>
                  </>
                )}
              </View>
            </View>
          </View>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>
      <BiometricSetupModal
        visible={visible && stage === "identity"}
        studentId={studentId}
        ageBand={ageBand}
        stepLabel="Step 4 of 4 · Learner Check"
        onDismiss={() => undefined}
        onComplete={() => setStage("plan")}
      />
      <MobileOnboardingPlanStep
        visible={visible && stage === "plan"}
        displayName={name.trim()}
        ageBand={ageBand}
        onComplete={onComplete}
      />
    </>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.panel },
  fill: { flex: 1 },
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
  artPaneLearn: { flex: 0, height: 148 },
  pane: { flex: 1, minWidth: 0, minHeight: 0, backgroundColor: C.panel, borderLeftWidth: 1, borderLeftColor: C.border },
  scroller: { flex: 1 },
  paneBody: { flexGrow: 1, padding: 20, gap: 8 },
  paneCenter: { justifyContent: "center" },
  learn: { flex: 1 },
  learnInner: { padding: 16, paddingBottom: 16, gap: 12 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  foot: {
    flexShrink: 0, flexDirection: "row", alignItems: "center", gap: 8,
    paddingHorizontal: 16, paddingTop: 10,
    borderTopWidth: 1, borderTopColor: C.border, backgroundColor: C.panel,
  },
  kicker: { color: C.teal, fontSize: 12, fontWeight: "800", letterSpacing: 0.6 },
  title: { color: C.text, fontSize: 32, lineHeight: 36, fontWeight: "900", letterSpacing: -0.8, marginTop: 8 },
  titleCompact: { fontSize: 26, lineHeight: 30, marginTop: 0 },
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
  cardFull: { alignSelf: "stretch" },
  cardFocus: { borderColor: C.accent },
  cardArt: { height: 150, backgroundColor: C.panel2 },
  cardImage: { ...StyleSheet.absoluteFillObject, width: "100%", height: "100%" },
  cardLabel: { color: C.text, fontSize: 22, fontWeight: "800", paddingHorizontal: 16, paddingTop: 16 },
  ratedHint: { color: C.muted, fontSize: 13, paddingHorizontal: 16, paddingBottom: 14, paddingTop: 2 },
  mascotStage: { flex: 1, alignItems: "center", justifyContent: "flex-end", paddingBottom: 16 },
  score: {
    position: "absolute", right: 10, bottom: 10, minWidth: 44, height: 44, borderRadius: 22, overflow: "hidden",
    textAlign: "center", lineHeight: 44, fontSize: 19, fontWeight: "900", color: "#ffffff",
    backgroundColor: C.accent,
  },
  scale: { gap: 12, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 12 },
  scaleRow: { flexDirection: "row", alignItems: "stretch", gap: 12 },
  dot: {
    flex: 1, flexBasis: 0, minWidth: 0, height: 64, borderRadius: 16, alignItems: "center", justifyContent: "center",
    backgroundColor: C.panel2, borderWidth: 1, borderColor: C.border,
  },
  dotOn: { backgroundColor: C.accent, borderColor: C.accent },
  dotText: { color: C.text, fontSize: 22, fontWeight: "800" },
  dotTextOn: { color: "#ffffff" },
  button: { flex: 1, minHeight: 52, borderRadius: 12, backgroundColor: C.accent, justifyContent: "center", alignItems: "center" },
  buttonText: { color: "#ffffff", fontSize: 16, fontWeight: "800" },
  disabled: { opacity: 0.45 },
  linkButton: { alignSelf: "center", paddingVertical: 10 },
  linkText: { color: C.muted, fontSize: 15, fontWeight: "700" },
  error: { color: C.danger, marginTop: 12 },
});
