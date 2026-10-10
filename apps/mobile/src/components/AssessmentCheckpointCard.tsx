import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import {
  submitAssessmentCheckpoint,
  type AssessmentRun,
  type AssessmentSubmitResult,
} from "../api";
import AnimatedPressable from "./AnimatedPressable";
import GlassPanel from "./GlassPanel";
import PrimaryButton from "./PrimaryButton";
import { speakNatural, stopSpeech } from "../tts";
import { useT, type StringKey } from "../i18n";
import { theme } from "../theme";

type Props = {
  run: AssessmentRun;
  busy?: boolean;
  onError?: (message: string) => void;
  onSubmitted: (result: AssessmentSubmitResult) => void;
  onDismiss?: () => void;
};

function formatKey(format: string): StringKey {
  switch (format) {
    case "audio":
      return "assessment.audio";
    case "video_aid":
      return "assessment.visual";
    case "game":
      return "assessment.challenge";
    default:
      return "assessment.text";
  }
}

export default function AssessmentCheckpointCard({
  run,
  busy = false,
  onError,
  onSubmitted,
  onDismiss,
}: Props) {
  const { t, locale } = useT();
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const format = run.presentation_format;
  const stageLabel = run.checkpoint.stage === "summative"
    ? t("assessment.summative")
    : t("assessment.checkpoint");

  useEffect(() => {
    setAnswers({});
  }, [run.run_id]);

  useEffect(() => {
    if (format !== "audio") return;
    const first = run.items[0]?.audio?.narration;
    if (first) speakNatural(first, { locale });
    return () => { stopSpeech(); };
  }, [run.run_id, format, run.items, locale]);

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
        {t("assessment.meta", { format: t(formatKey(format)), n: run.attempt_number })}
      </Text>
      <Text style={styles.hint}>
        {run.checkpoint.stage === "summative"
          ? t("assessment.summativeHint")
          : t("assessment.checkHint")}
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
              label={t("assessment.hear")}
              onPress={() => speakNatural(item.audio?.narration || item.prompt, { locale })}
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
        label={submitting ? t("assessment.submitting") : t("assessment.submit")}
        onPress={() => void onSubmit()}
        disabled={busy || submitting || !allAnswered}
        variant="netflix"
      />
      {onDismiss && run.checkpoint.stage !== "summative" ? (
        <PrimaryButton label={t("assessment.skip")} onPress={onDismiss} variant="ghost" />
      ) : null}
    </GlassPanel>
  );
}

const styles = StyleSheet.create({
  card: { gap: 10, padding: 16 },
  title: { color: theme.colors.text, fontSize: 18, fontWeight: "700", lineHeight: 24, includeFontPadding: false },
  meta: { color: theme.colors.muted, fontSize: 12, lineHeight: 16, includeFontPadding: false },
  hint: { color: theme.colors.muted, fontSize: 13, lineHeight: 18, marginBottom: 4 },
  item: { gap: 8, marginBottom: 8 },
  videoAid: {
    backgroundColor: "rgba(99,102,241,0.12)",
    borderRadius: 10,
    padding: 10,
    gap: 4,
  },
  cue: { color: theme.colors.text, fontWeight: "600" },
  prompt: { color: theme.colors.text, fontWeight: "600", fontSize: 15, lineHeight: 21, includeFontPadding: false },
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
  optText: { color: theme.colors.text, flex: 1, minWidth: 0, lineHeight: 20, includeFontPadding: false },
});
