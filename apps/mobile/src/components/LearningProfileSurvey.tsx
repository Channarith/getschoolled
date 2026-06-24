import { useEffect, useState } from "react";
import {
  Modal, Pressable, ScrollView, StyleSheet, Switch, Text,
  TextInput, View,
} from "react-native";

import {
  createStudent, getMe, getOnboardingSurvey, listStudents,
  skipLearningProfile, submitLearningProfile, submitOnboardingSurveyAnalytics,
  type StudentProfile, type SurveyTemplate,
} from "../api";
import { getToken } from "../storage";

type Props = {
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
export default function LearningProfileSurvey({ manualOpenToken = 0, onSaved }: Props) {
  const [visible, setVisible] = useState(false);
  const [manual, setManual] = useState(false);
  const [template, setTemplate] = useState<SurveyTemplate | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | number | boolean>>({});
  const [studentId, setStudentId] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [doneCategory, setDoneCategory] = useState("");

  async function prepare(force: boolean) {
    if (!getToken()) return;
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
    void prepare(false).catch(() => undefined);
  }, []);

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
        <View style={styles.card}>
          <ScrollView contentContainerStyle={{ paddingBottom: 16 }}>
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
                            <Pressable key={opt} disabled={busy}
                              onPress={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                              style={[styles.chip, on && styles.chipOn]}>
                              <Text style={[styles.chipText, on && styles.chipTextOn]}>{opt}</Text>
                            </Pressable>
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
                          thumbColor={answers[q.id] ? "#0ea5e9" : "#666"} />
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
                        placeholderTextColor="#6b7280"
                      />
                    ) : null}
                  </View>
                ))}
                {error ? <Text style={styles.error}>{error}</Text> : null}
                <View style={styles.actions}>
                  <Pressable disabled={busy} onPress={() => void onSubmit()} style={styles.primaryBtn}>
                    <Text style={styles.primaryText}>{busy ? "Saving…" : manual ? "Save changes" : "Save profile"}</Text>
                  </Pressable>
                  {!manual ? (
                    <Pressable disabled={busy} onPress={() => void onSkip()} style={styles.secondaryBtn}>
                      <Text style={styles.secondaryText}>Skip for now</Text>
                    </Pressable>
                  ) : (
                    <Pressable disabled={busy} onPress={() => setVisible(false)} style={styles.secondaryBtn}>
                      <Text style={styles.secondaryText}>Cancel</Text>
                    </Pressable>
                  )}
                </View>
              </>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.65)", justifyContent: "center", padding: 16 },
  card: { backgroundColor: "#151c34", borderRadius: 16, maxHeight: "90%", padding: 16 },
  title: { color: "#e8ecf6", fontSize: 22, fontWeight: "800", marginBottom: 8 },
  sub: { color: "#9aa6c2", marginBottom: 12, lineHeight: 18 },
  body: { color: "#e8ecf6", lineHeight: 20 },
  q: { marginBottom: 14 },
  qPrompt: { color: "#e8ecf6", fontWeight: "700", marginBottom: 8 },
  chips: { gap: 8 },
  chip: { backgroundColor: "#1d2746", borderRadius: 10, padding: 10, marginBottom: 6 },
  chipOn: { backgroundColor: "#0ea5e9" },
  chipText: { color: "#9aa6c2", fontSize: 13 },
  chipTextOn: { color: "#001022", fontWeight: "700" },
  boolRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  input: {
    backgroundColor: "#1d2746", color: "#e8ecf6", borderRadius: 10,
    padding: 10, minHeight: 72, textAlignVertical: "top",
  },
  error: { color: "#ff6b6b", marginTop: 8 },
  actions: { marginTop: 16, gap: 10 },
  primaryBtn: { backgroundColor: "#0ea5e9", borderRadius: 999, paddingVertical: 12, alignItems: "center" },
  primaryText: { color: "#001022", fontWeight: "800" },
  secondaryBtn: { borderWidth: 1, borderColor: "#334155", borderRadius: 999, paddingVertical: 12, alignItems: "center" },
  secondaryText: { color: "#9aa6c2", fontWeight: "700" },
});
