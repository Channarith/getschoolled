import { ResizeMode, Video } from "expo-av";
import { useEffect, useState } from "react";
import {
  Modal, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  completeMobileAccountOnboarding,
  getMe,
  getOnboardingSurvey,
  selectMobileFreePlan,
  submitLearningProfile,
  skipLearningProfile,
  submitMobileOnboardingProfile,
  submitOnboardingSurveyAnalytics,
  type StudentProfile,
  type SurveyTemplate,
} from "../api";
import AnimatedPressable from "./AnimatedPressable";
import BiometricSetupModal from "./BiometricSetupModal";

type Props = {
  visible: boolean;
  student: StudentProfile;
  onComplete: () => void;
};

type Answers = Record<string, string | number | boolean>;

const LEARNING_STAGE = 3;

const stages = [
  { title: "Welcome to Salareen.", body: "Let’s shape a learning space around you." },
  { title: "Who’s learning?", body: "Your learner profile keeps progress and recommendations personal." },
  { title: "Start free.", body: "Learn with the free plan today. You can compare and upgrade plans any time." },
  { title: "Make it feel right.", body: "A few quick questions so lessons match how you learn." },
  { title: "Privacy comes first.", body: "Identity setup is optional for general learning and required only for accredited courses." },
];

export default function FirstSignInAssistant({ visible, student, onComplete }: Props) {
  const [stage, setStage] = useState(0);
  const [name, setName] = useState(student.display_name);
  const [ageBand, setAgeBand] = useState(student.age_band || "adult");
  const [template, setTemplate] = useState<SurveyTemplate | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [questionIndex, setQuestionIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [biometric, setBiometric] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!visible) return;
    getMe()
      .then((me) => getOnboardingSurvey(me.id, me.tier))
      .then((survey) => setTemplate(survey.enabled ? survey.template : null))
      .catch(() => setTemplate(null));
  }, [visible]);

  const questions = template?.questions ?? [];
  const question = stage === LEARNING_STAGE ? questions[questionIndex] : undefined;
  const value = question ? answers[question.id] : undefined;
  const questionAnswered = !question || !question.required || (value != null && value !== "");

  function setAnswer(next: string | number | boolean) {
    if (!question) return;
    setAnswers((current) => ({ ...current, [question.id]: next }));
  }

  async function saveLearningProfile() {
    if (!questions.length) return;
    await submitLearningProfile(student.id, answers);
    const me = await getMe();
    await submitOnboardingSurveyAnalytics({
      account_id: me.id, student_id: student.id, answers,
    }).catch(() => undefined);
  }

  async function next() {
    setBusy(true);
    setError("");
    try {
      if (stage === 1) await submitMobileOnboardingProfile(name);
      if (stage === 2) await selectMobileFreePlan();
      if (stage === LEARNING_STAGE && questionIndex < questions.length - 1) {
        setQuestionIndex((index) => index + 1);
        return;
      }
      if (stage === LEARNING_STAGE) await saveLearningProfile();
      if (stage < stages.length - 1) setStage((current) => current + 1);
      else setBiometric(true);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function skipLearning() {
    setBusy(true);
    setError("");
    try {
      await skipLearningProfile(student.id);
      setStage(LEARNING_STAGE + 1);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  function back() {
    setError("");
    if (stage === LEARNING_STAGE && questionIndex > 0) setQuestionIndex((index) => index - 1);
    else setStage((current) => Math.max(0, current - 1));
  }

  async function finish() {
    setBusy(true);
    try {
      await completeMobileAccountOnboarding(name, ageBand);
      setBiometric(false);
      onComplete();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  const title = question ? question.prompt : stages[stage].title;
  const body = question
    ? `Your learning · ${questionIndex + 1} of ${questions.length}${question.required ? "" : " · optional"}`
    : stages[stage].body;

  return (
    <>
      <Modal visible={visible && !biometric} animationType="fade" presentationStyle="fullScreen">
        <SafeAreaView style={styles.root}>
          <Video
            source={require("../../assets/setup-assistant/welcome.mp4")}
            style={styles.media}
            resizeMode={ResizeMode.COVER}
            shouldPlay={visible}
            isLooping
            isMuted
          />
          <View style={styles.scrim} />
          <View style={styles.panel}>
            <View style={styles.bars}>
              {stages.map((_, index) => <View key={index} style={[styles.bar, index <= stage && styles.active]} />)}
            </View>
            <Text style={styles.kicker}>Setup assistant · {stage + 1} of {stages.length}</Text>
            <Text style={question ? styles.questionTitle : styles.title}>{title}</Text>
            <Text style={styles.body}>{body}</Text>
            {stage === 1 ? (
              <>
                <TextInput value={name} onChangeText={setName} placeholder="Profile name" placeholderTextColor="#77819b" style={styles.input} />
                <View style={styles.row}>
                  {["child", "teen", "adult"].map((age) => (
                    <Choice key={age} title={age} active={ageBand === age} onPress={() => setAgeBand(age)} />
                  ))}
                </View>
              </>
            ) : null}
            {stage === 2 ? <Choice title="Free · $0 · Start learning" active onPress={() => undefined} /> : null}
            {question ? (
              <ScrollView style={styles.options} contentContainerStyle={styles.optionList}>
                {question.type === "choice" && question.options
                  ? question.options.map((opt) => (
                    <Choice key={opt} title={opt} wide active={value === opt} onPress={() => setAnswer(opt)} />
                  ))
                  : null}
                {question.type === "bool" ? (
                  <>
                    <Choice title="Yes" wide active={value === true} onPress={() => setAnswer(true)} />
                    <Choice title="No" wide active={value === false} onPress={() => setAnswer(false)} />
                  </>
                ) : null}
                {question.type === "rating"
                  ? [1, 2, 3, 4, 5].map((n) => (
                    <Choice key={n} title={"★".repeat(n)} wide active={value === n} onPress={() => setAnswer(n)} />
                  ))
                  : null}
                {question.type === "text" ? (
                  <TextInput
                    value={String(value ?? "")}
                    onChangeText={setAnswer}
                    multiline
                    placeholderTextColor="#77819b"
                    style={[styles.input, styles.textArea]}
                  />
                ) : null}
              </ScrollView>
            ) : null}
            {error ? <Text style={styles.error}>{error}</Text> : null}
            <AnimatedPressable
              disabled={busy || (stage === 1 && !name.trim()) || !questionAnswered}
              style={styles.button}
              onPress={() => void next()}
            >
              <Text style={styles.buttonText}>{stage === stages.length - 1 ? "Choose identity setup" : "Continue"}</Text>
            </AnimatedPressable>
            <View style={styles.secondaryRow}>
              {stage > 0 ? (
                <AnimatedPressable disabled={busy} onPress={back} style={styles.linkButton}>
                  <Text style={styles.linkText}>Back</Text>
                </AnimatedPressable>
              ) : null}
              {question ? (
                <AnimatedPressable disabled={busy} onPress={() => void skipLearning()} style={styles.linkButton}>
                  <Text style={styles.linkText}>Set up later</Text>
                </AnimatedPressable>
              ) : null}
            </View>
          </View>
        </SafeAreaView>
      </Modal>
      <BiometricSetupModal
        visible={visible && biometric}
        studentId={student.id}
        ageBand={ageBand}
        onDismiss={() => undefined}
        onComplete={() => void finish()}
      />
    </>
  );
}

function Choice({ title, active, wide, onPress }: {
  title: string; active: boolean; wide?: boolean; onPress: () => void;
}) {
  return (
    <AnimatedPressable style={[styles.choice, active && styles.choiceActive]} onPress={onPress}>
      <Text style={wide ? styles.optionText : styles.choiceText}>{title}</Text>
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#080b1d", justifyContent: "flex-end" },
  media: { ...StyleSheet.absoluteFillObject },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(4,7,20,.47)" },
  panel: { backgroundColor: "rgba(8,11,29,.94)", borderTopLeftRadius: 34, borderTopRightRadius: 34, padding: 26, paddingBottom: 44, maxHeight: "88%" },
  bars: { flexDirection: "row", gap: 6, marginBottom: 24 },
  bar: { flex: 1, height: 4, borderRadius: 3, backgroundColor: "#313956" },
  active: { backgroundColor: "#72d8ff" },
  kicker: { color: "#72d8ff", fontSize: 12, fontWeight: "900", letterSpacing: 1.5, textTransform: "uppercase" },
  title: { color: "#fff", fontSize: 43, lineHeight: 46, fontWeight: "900", letterSpacing: -1.6, marginTop: 10 },
  questionTitle: { color: "#fff", fontSize: 28, lineHeight: 33, fontWeight: "900", letterSpacing: -0.8, marginTop: 10 },
  body: { color: "#c1cbe0", fontSize: 17, lineHeight: 25, marginTop: 12, marginBottom: 18 },
  input: { color: "#fff", backgroundColor: "#121a34", borderWidth: 1, borderColor: "#3c476a", borderRadius: 14, padding: 15, fontSize: 17, marginBottom: 12 },
  textArea: { minHeight: 96, textAlignVertical: "top" },
  row: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  options: { maxHeight: 320 },
  optionList: { gap: 8 },
  choice: { flexGrow: 1, borderRadius: 14, padding: 14, backgroundColor: "#171f3a", borderWidth: 1, borderColor: "#3a4568" },
  choiceActive: { borderColor: "#72d8ff", backgroundColor: "#14364b" },
  choiceText: { color: "#eef4ff", textAlign: "center", textTransform: "capitalize", fontWeight: "700" },
  optionText: { color: "#eef4ff", fontSize: 15, fontWeight: "700" },
  button: { marginTop: 22, minHeight: 54, borderRadius: 999, backgroundColor: "#72d8ff", justifyContent: "center", alignItems: "center" },
  buttonText: { color: "#071521", fontSize: 16, fontWeight: "900" },
  secondaryRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 14 },
  linkButton: { paddingVertical: 8, paddingHorizontal: 4 },
  linkText: { color: "#a9b6d3", fontSize: 15, fontWeight: "700" },
  error: { color: "#ffb1b1", marginTop: 12 },
});
