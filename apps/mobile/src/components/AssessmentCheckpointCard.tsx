import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import * as Speech from "expo-speech";

import {
  submitAssessmentCheckpoint,
  type AssessmentRun,
  type AssessmentSubmitResult,
} from "../api";
import AnimatedPressable from "./AnimatedPressable";
import GlassPanel from "./GlassPanel";
import PrimaryButton from "./PrimaryButton";
import { theme } from "../theme";

type Props = {
  run: AssessmentRun;
  busy?: boolean;
  onError?: (message: string) => void;
  onSubmitted: (result: AssessmentSubmitResult) => void;
  onDismiss?: () => void;
};

function formatLabel(format: string): string {
  switch (format) {
    case "audio":
      return "Audio";
    case "video_aid":
      return "Visual aid";
    case "game":
      return "Challenge";
    default:
      return "Text";
  }
}

export default function AssessmentCheckpointCard({
  run,
  busy = false,
  onError,
  onSubmitted,
  onDismiss,
}: Props) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const format = run.presentation_format;
  const stageLabel = run.checkpoint.stage === "summative"
    ? "Course assessment"
    : "Checkpoint";

  useEffect(() => {
    setAnswers({});
  }, [run.run_id]);

  useEffect(() => {
    if (format !== "audio") return;
    const first = run.items[0]?.audio?.narration;
    if (first) Speech.speak(first);
    return () => { Speech.stop(); };
  }, [run.run_id, format, run.items]);

  const allAnswered = run.items.every((item) => answers[item.item_id] !== undefined);

  async function onSubmit() {
    if (!allAnswered || submitting) return;
    setSubmitting(true);
    try {
      const chosen = run.items.map((item) => answers[item.item_id]);
      const result = await submitAssessmentCheckpoint(run.run_id, chosen);
      onSubmitted(result);
    } catch (e) {
      onError?.((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <GlassPanel style={styles.card}>
      <Text style={styles.title}>{stageLabel}</Text>
      <Text style={styles.meta}>
        Format: {formatLabel(format)} · Attempt {run.attempt_number}
      </Text>
      <Text style={styles.hint}>
        {run.checkpoint.stage === "summative"
          ? "Pass to verify course completion. Answer keys stay on the server."
          : "Quick check on what you just learned."}
      </Text>

      {run.items.map((item, index) => (
        <View key={item.item_id} style={styles.item}>
          {format === "video_aid" && item.video_aid ? (
            <View style={styles.videoAid}>
              <Text style={styles.meta}>
                Visual aid · {item.video_aid.visual_prompt || item.topic}
              </Text>
              <Text style={styles.cue}>{item.video_aid.presenter_cue}</Text>
            </View>
          ) : null}
          {format === "game" && item.game ? (
            <Text style={styles.meta}>
              Challenge · {item.game.points_per_correct} pts if correct
            </Text>
          ) : null}
          <Text style={styles.prompt}>
            {index + 1}. {item.prompt}
          </Text>
          {format === "audio" ? (
            <PrimaryButton
              label="Hear question"
              onPress={() => Speech.speak(item.audio?.narration || item.prompt)}
              variant="ghost"
            />
          ) : null}
          {item.options.map((opt, i) => (
            <AnimatedPressable
              key={`${item.item_id}-${i}`}
              onPress={() => setAnswers((prev) => ({ ...prev, [item.item_id]: i }))}
              style={[styles.opt, answers[item.item_id] === i && styles.optOn]}
              disabled={busy || submitting}
            >
              <Text style={styles.optText}>{opt}</Text>
            </AnimatedPressable>
          ))}
        </View>
      ))}

      <PrimaryButton
        label={submitting ? "Submitting…" : "Submit assessment"}
        onPress={() => void onSubmit()}
        disabled={busy || submitting || !allAnswered}
        variant="netflix"
      />
      {onDismiss && run.checkpoint.stage !== "summative" ? (
        <PrimaryButton label="Continue without submitting" onPress={onDismiss} variant="ghost" />
      ) : null}
    </GlassPanel>
  );
}

const styles = StyleSheet.create({
  card: { gap: 10, padding: 16 },
  title: { color: theme.colors.text, fontSize: 18, fontWeight: "700" },
  meta: { color: theme.colors.muted, fontSize: 12 },
  hint: { color: theme.colors.muted, fontSize: 13, marginBottom: 4 },
  item: { gap: 8, marginBottom: 8 },
  videoAid: {
    backgroundColor: "rgba(99,102,241,0.12)",
    borderRadius: 10,
    padding: 10,
    gap: 4,
  },
  cue: { color: theme.colors.text, fontWeight: "600" },
  prompt: { color: theme.colors.text, fontWeight: "600", fontSize: 15 },
  opt: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  optOn: {
    backgroundColor: theme.colors.accent,
    borderColor: theme.colors.accent,
  },
  optText: { color: theme.colors.text },
});
