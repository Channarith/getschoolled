import { useEffect, useRef, useState } from "react";
import { Modal, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  createStudent, getMe, listStudents, submitLearningProfile, submitOnboardingSurveyAnalytics,
} from "../api";
import { LEARNING_MODES, savedModalityRatings } from "../learningModes";
import AnimatedPressable from "./AnimatedPressable";
import GlassPanel from "./GlassPanel";
import PrimaryButton from "./PrimaryButton";
import { getToken, setSettings } from "../storage";
import { theme } from "../theme";

type Props = {
  /** Increment to open the questions from Settings. */
  manualOpenToken?: number;
  onSaved?: () => void;
};

const SCALE_ROWS = [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]];

/**
 * Settings → Update learning profile. The same six "how do you learn best"
 * ratings as the setup assistant, one per page, without the face or voice
 * check. The saved answers are prefilled so a change is a few taps.
 */
export default function LearningProfileSurvey({ manualOpenToken = 0, onSaved }: Props) {
  const [visible, setVisible] = useState(false);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [index, setIndex] = useState(0);
  const [studentId, setStudentId] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [doneCategory, setDoneCategory] = useState("");
  const opening = useRef(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  }, []);

  async function open() {
    if (!getToken() || opening.current) return;
    opening.current = true;
    try {
      const me = await getMe();
      let students = (await listStudents()).students;
      if (!students.length) {
        students = [await createStudent(me.display_name || me.email.split("@")[0])];
      }
      const primary = students.find((s) => s.onboarding_completed_at) ?? students[0];
      setAccountId(me.id);
      setStudentId(primary.id);
      void setSettings({ studentId: primary.id });
      setRatings(savedModalityRatings(primary.onboarding_answers));
      setIndex(0);
      setDoneCategory("");
      setError("");
      setVisible(true);
    } finally {
      opening.current = false;
    }
  }

  useEffect(() => {
    if (manualOpenToken > 0) void open().catch((e) => setError(String(e)));
  }, [manualOpenToken]);

  const mode = LEARNING_MODES[index];
  const current = mode ? ratings[mode.id] : undefined;
  const last = index >= LEARNING_MODES.length - 1;

  async function save() {
    if (!studentId || !accountId) return;
    if (LEARNING_MODES.some((m) => ratings[m.id] == null)) {
      setError("Please rate all six.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const answers = { modality_ratings: ratings };
      const res = await submitLearningProfile(studentId, answers);
      void submitOnboardingSurveyAnalytics({ account_id: accountId, student_id: studentId, answers })
        .catch(() => undefined);
      setDoneCategory(res.learner_category);
      onSaved?.();
      closeTimer.current = setTimeout(() => setVisible(false), 1200);
    } catch (e) {
      setError(String(e).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  }

  if (!visible) return null;

  return (
    <Modal visible animationType="slide" transparent onRequestClose={() => setVisible(false)}>
      <View style={styles.backdrop}>
        <GlassPanel style={styles.card} padded={false}>
          <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 16 }}>
            <Text style={styles.title}>How do you learn best?</Text>
            {doneCategory ? (
              <Text style={styles.body}>
                Thanks! Profile saved ({doneCategory.replace(/_/g, " ")}).
              </Text>
            ) : (
              <>
                <Text style={styles.sub}>
                  Rate from 1 (not for me) to 10 (I love it). Step {index + 1} of {LEARNING_MODES.length}.
                  Updates sync to your account.
                </Text>
                <Text style={styles.mode}>{mode.label}</Text>
                {SCALE_ROWS.map((row, rowIndex) => (
                  <View key={rowIndex} style={styles.scaleRow}>
                    {row.map((value) => {
                      const on = current === value;
                      return (
                        <AnimatedPressable
                          key={value}
                          disabled={busy}
                          accessibilityLabel={`${mode.label}: ${value} of 10`}
                          onPress={() => setRatings((r) => ({ ...r, [mode.id]: value }))}
                          style={[styles.scale, on && styles.scaleOn]}
                        >
                          <Text style={[styles.scaleText, on && styles.scaleTextOn]}>{value}</Text>
                        </AnimatedPressable>
                      );
                    })}
                  </View>
                ))}
                {error ? <Text style={styles.error}>{error}</Text> : null}
                <View style={styles.actions}>
                  <PrimaryButton
                    label={busy ? "Saving…" : last ? "Save changes" : current == null ? "Rate to continue" : "Next"}
                    onPress={() => (last ? void save() : setIndex((i) => Math.min(LEARNING_MODES.length - 1, i + 1)))}
                    disabled={busy || current == null}
                    loading={busy}
                  />
                  <PrimaryButton
                    label={index > 0 ? "Back" : "Cancel"}
                    onPress={() => (index > 0 ? setIndex((i) => i - 1) : setVisible(false))}
                    disabled={busy}
                    variant="ghost"
                  />
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
  mode: { color: theme.colors.text, fontSize: 20, fontWeight: "800", marginBottom: 12 },
  scaleRow: { flexDirection: "row", gap: 8, marginBottom: 8 },
  scale: {
    flex: 1, minHeight: 48, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.06)", borderRadius: theme.radius.md,
    borderWidth: 1, borderColor: theme.colors.border,
  },
  scaleOn: { backgroundColor: theme.colors.netflix, borderColor: theme.colors.netflix },
  scaleText: { color: theme.colors.muted, fontSize: 16, fontWeight: "700" },
  scaleTextOn: { color: "#fff" },
  error: { color: theme.colors.danger, marginTop: 8 },
  actions: { marginTop: 16, gap: 10 },
});
