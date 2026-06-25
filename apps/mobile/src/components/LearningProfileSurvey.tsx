import { useEffect, useRef, useState } from "react";
import {
  Modal, ScrollView, StyleSheet, Switch, Text,
  TextInput, View,
} from "react-native";

import {
  createStudent, getMe, getOnboardingSurvey, listStudents,
  skipLearningProfile, submitLearningProfile, submitOnboardingSurveyAnalytics,
  type StudentProfile, type SurveyTemplate,
} from "../api";
import AnimatedPressable from "./AnimatedPressable";
import GlassPanel from "./GlassPanel";
import PrimaryButton from "./PrimaryButton";
import { getToken } from "../storage";
import { theme } from "../theme";

type Props = {
  /** Bumps when the user signs in or out — gates one auto-prompt per login. */
  authEpoch?: number;
  /** Increment to open the survey from Settings (manual edit). */
  manualOpenToken?: number;
  onSaved?: () => void;
};

function requiredMissing(template: SurveyTemplate, answers: Record<string, unknown>): string[] {
  return template.questions
    .filter((q) => q.required && (answers[q.id] == null || answers[q.id] === ""))
    .map((q) => q.id);
}

function answersFromProfile(student: StudentProfile): Record<string, string | number | boolean> {
  const stored = student.onboarding_answers;
  if (stored && Object.keys(stored).length) {
    return stored as Record<string, string | number | boolean>;
  }
  const styleLabels: Record<string, string> = {
    visual: "Visual — diagrams, video, demonstrations",
    auditory: "Auditory — listening, discussion, narration",
    reading_writing: "Reading & writing — notes, text, written steps",
    hands_on: "Hands-on — practice, labs, doing it yourself",
    mixed: "Mixed — no single style stands out",
  };
  const paceLabels: Record<string, string> = {
    slow: "Slower with more review", moderate: "Moderate and steady", fast: "Faster with less repetition",
  };
  const structureLabels: Record<string, string> = {
    step_by_step: "Step-by-step in order", examples_first: "Examples first, then rules",
    big_picture: "Big picture first, then details", practice_heavy: "Short bursts with frequent practice",
  };
  const sessionLabels: Record<string, string> = {
    short: "About 10 minutes", medium: "About 20–30 minutes", long: "45 minutes or longer",
  };
  const groupLabels: Record<string, string> = {
    solo: "Mostly on my own", group: "Small group or class", either: "Either works for me",
  };
  const readingLabels: Record<string, string> = {
    beginner: "Beginner — keep language simple", intermediate: "Intermediate",
    advanced: "Advanced — dense text is fine",
  };
  const motivationLabels: Record<string, string> = {
    career: "Career / job skills", school: "School or certification",
    personal: "Personal curiosity", other: "Other",
  };
  const acc = student.accessibility || {};
  return {
    primary_style: styleLabels[student.primary_style || ""] || "",
    pace: paceLabels[student.learning_pace || ""] || "",
    structure: structureLabels[student.learning_structure || ""] || "",
    session_length: sessionLabels[student.session_length || ""] || "",
    group_preference: groupLabels[student.group_preference || ""] || "",
    reading_level: readingLabels[student.reading_level || ""] || "",
    motivation: motivationLabels[student.motivation || ""] || "",
    needs_captions: Boolean(acc.needs_captions),
    needs_large_text: Boolean(acc.needs_large_text),
    needs_extra_time: Boolean(acc.needs_extra_time),
    uses_assistive_tech: Boolean(acc.uses_assistive_tech),
    accommodations_notes: student.accommodations_notes || "",
  };
}

/** One-time learning survey (auto after login) + manual relaunch from Settings. */
export default function LearningProfileSurvey({
  authEpoch = 0,
  manualOpenToken = 0,
  onSaved,
}: Props) {
  const autoPromptedEpochRef = useRef(-1);
  const visibleRef = useRef(false);
  const [visible, setVisible] = useState(false);
  const [manual, setManual] = useState(false);
  const [template, setTemplate] = useState<SurveyTemplate | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | number | boolean>>({});
  const [studentId, setStudentId] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [doneCategory, setDoneCategory] = useState("");

  useEffect(() => {
    visibleRef.current = visible;
  }, [visible]);

  async function prepare(force: boolean) {
    if (!getToken()) return;
    if (!force && visibleRef.current) return;

    const me = await getMe();
    const survey = await getOnboardingSurvey(me.id, me.tier);
    if (!survey.enabled || !survey.template) return;

    let students = (await listStudents()).students;
    if (!students.length) {
      students = [await createStudent(me.display_name || me.email.split("@")[0])];
    }
    const primary = students.find((s) => !s.onboarding_completed_at) ?? students[0];
    if (!force && primary.onboarding_completed_at) return;

    setAccountId(me.id);
    setStudentId(primary.id);
    setTemplate(survey.template);
    setAnswers(primary.onboarding_completed_at ? answersFromProfile(primary) : {});
    setDoneCategory("");
    setError("");
    setManual(force);
    setVisible(true);
  }

  useEffect(() => {
    if (!getToken()) {
      autoPromptedEpochRef.current = -1;
      return;
    }
    if (autoPromptedEpochRef.current === authEpoch) return;
    autoPromptedEpochRef.current = authEpoch;
    void prepare(false).catch(() => undefined);
  }, [authEpoch]);

  useEffect(() => {
    if (manualOpenToken > 0) {
      void prepare(true).catch((e) => setError(String(e)));
    }
  }, [manualOpenToken]);

  async function onSubmit() {
    if (!template || !studentId || !accountId) return;
    if (requiredMissing(template, answers).length) {
      setError("Please answer all required questions.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await submitLearningProfile(studentId, answers);
      await submitOnboardingSurveyAnalytics({
        account_id: accountId, student_id: studentId, answers,
      }).catch(() => undefined);
      setDoneCategory(res.learner_category);
      onSaved?.();
      setTimeout(() => setVisible(false), manual ? 1200 : 1800);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSkip() {
    if (!studentId) { setVisible(false); return; }
    setBusy(true);
    try {
      await skipLearningProfile(studentId);
      onSaved?.();
      setVisible(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!visible || !template) return null;

  return (
    <Modal visible animationType="slide" transparent onRequestClose={() => setVisible(false)}>
      <View style={styles.backdrop}>
        <GlassPanel style={styles.card} padded={false}>
          <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 16 }}>
            <Text style={styles.title}>{template.title}</Text>
            {doneCategory ? (
              <Text style={styles.body}>
                Thanks! Profile saved ({doneCategory.replace(/_/g, " ")}).
              </Text>
            ) : (
              <>
                {manual && (
                  <Text style={styles.sub}>
                    Updates sync to your account in the cloud — clearing app data will not reset this.
                  </Text>
                )}
                {template.subtitle ? <Text style={styles.sub}>{template.subtitle}</Text> : null}
                {template.questions.map((q) => (
                  <View key={q.id} style={styles.q}>
                    <Text style={styles.qPrompt}>{q.prompt}{q.required ? " *" : ""}</Text>
                    {q.type === "choice" && q.options ? (
                      <View style={styles.chips}>
                        {q.options.map((opt) => {
                          const on = answers[q.id] === opt;
                          return (
                            <AnimatedPressable key={opt} disabled={busy}
                              onPress={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                              style={[styles.chip, on && styles.chipOn]}>
                              <Text style={[styles.chipText, on && styles.chipTextOn]}>{opt}</Text>
                            </AnimatedPressable>
                          );
                        })}
                      </View>
                    ) : null}
                    {q.type === "bool" ? (
                      <View style={styles.boolRow}>
                        <Switch
                          value={Boolean(answers[q.id])}
                          disabled={busy}
                          onValueChange={(v) => setAnswers((a) => ({ ...a, [q.id]: v }))}
                          trackColor={{ false: "#334155", true: theme.colors.netflix }}
                          thumbColor="#fff"
                        />
                        <Text style={styles.body}>Yes</Text>
                      </View>
                    ) : null}
                    {q.type === "text" ? (
                      <TextInput
                        style={styles.input}
                        multiline
                        editable={!busy}
                        value={String(answers[q.id] ?? "")}
                        onChangeText={(t) => setAnswers((a) => ({ ...a, [q.id]: t }))}
                        placeholderTextColor={theme.colors.muted}
                      />
                    ) : null}
                  </View>
                ))}
                {error ? <Text style={styles.error}>{error}</Text> : null}
                <View style={styles.actions}>
                  <PrimaryButton
                    label={busy ? "Saving…" : manual ? "Save changes" : "Save profile"}
                    onPress={() => void onSubmit()}
                    disabled={busy}
                    loading={busy}
                  />
                  {!manual ? (
                    <PrimaryButton
                      label="Skip for now"
                      onPress={() => void onSkip()}
                      disabled={busy}
                      variant="ghost"
                    />
                  ) : (
                    <PrimaryButton
                      label="Cancel"
                      onPress={() => setVisible(false)}
                      disabled={busy}
                      variant="ghost"
                    />
                  )}
                </View>
              </>
            )}
          </ScrollView>
        </GlassPanel>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: theme.colors.scrimHeavy, justifyContent: "center", padding: 16 },
  card: { maxHeight: "90%" },
  title: { color: theme.colors.text, fontSize: 22, fontWeight: "800", marginBottom: 8 },
  sub: { color: theme.colors.muted, marginBottom: 12, lineHeight: 18 },
  body: { color: theme.colors.text, lineHeight: 20 },
  q: { marginBottom: 14 },
  qPrompt: { color: theme.colors.text, fontWeight: "700", marginBottom: 8 },
  chips: { gap: 8 },
  chip: {
    backgroundColor: "rgba(255,255,255,0.06)", borderRadius: theme.radius.md,
    padding: 10, marginBottom: 6, borderWidth: 1, borderColor: theme.colors.border,
  },
  chipOn: { backgroundColor: theme.colors.netflix, borderColor: theme.colors.netflix },
  chipText: { color: theme.colors.muted, fontSize: 13 },
  chipTextOn: { color: "#fff", fontWeight: "700" },
  boolRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  input: {
    backgroundColor: "rgba(255,255,255,0.06)", color: theme.colors.text,
    borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.colors.border,
    padding: 10, minHeight: 72, textAlignVertical: "top",
  },
  error: { color: theme.colors.danger, marginTop: 8 },
  actions: { marginTop: 16, gap: 10 },
});
