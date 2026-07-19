"use client";

import { useEffect, useState } from "react";
import {
  submitAssessmentCheckpoint,
  type AssessmentRun,
  type AssessmentSubmitResult,
} from "../lib/api";
import { formatLabel } from "../lib/assessmentFlow";
import { cancelSpeech, speakNaturally } from "../lib/tts";
import { useT } from "../lib/i18n";

type Props = {
  run: AssessmentRun;
  busy?: boolean;
  onBusy?: (busy: boolean) => void;
  onError?: (message: string) => void;
  onSubmitted: (result: AssessmentSubmitResult) => void;
  onDismiss?: () => void;
  dismissLabel?: string;
};

export default function AssessmentCheckpointPanel({
  run,
  busy = false,
  onBusy,
  onError,
  onSubmitted,
  onDismiss,
  dismissLabel = "Continue without submitting",
}: Props) {
  const { locale } = useT();
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
    if (first) speakNaturally(first, { locale });
    return () => { cancelSpeech(); };
  }, [run.run_id, format, run.items, locale]);

  const allAnswered = run.items.every((item) => answers[item.item_id] !== undefined);

  async function onSubmit() {
    if (!allAnswered || submitting) return;
    setSubmitting(true);
    onBusy?.(true);
    try {
      const chosen = run.items.map((item) => answers[item.item_id]);
      const result = await submitAssessmentCheckpoint(run.run_id, chosen);
      onSubmitted(result);
    } catch (e) {
      onError?.(String(e));
    } finally {
      setSubmitting(false);
      onBusy?.(false);
    }
  }

  function speakItem(itemId: string) {
    const item = run.items.find((row) => row.item_id === itemId);
    const narration = item?.audio?.narration || item?.prompt;
    if (narration) speakNaturally(narration, { locale });
  }

  return (
    <div
      className="card"
      style={{
        borderColor: format === "game" ? "#16a34a" : "#6366f1",
        background: format === "game" ? "rgba(22,163,74,0.06)" : "rgba(99,102,241,0.05)",
      }}
    >
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <h3 style={{ marginTop: 0, marginBottom: 4 }}>
          {stageLabel}
          {run.checkpoint.stage === "formative" ? ` · ${run.checkpoint.checkpoint_id}` : ""}
        </h3>
        <span className="muted" style={{ fontSize: 13 }}>
          Format: {formatLabel(format)} · Attempt {run.attempt_number}
        </span>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        {run.checkpoint.stage === "summative"
          ? "Pass this assessment to verify course completion. Answer keys stay on the server."
          : "Quick check on what you just learned. Same questions for every format."}
      </p>

      {run.items.map((item, index) => (
        <div key={item.item_id} style={{ marginBottom: 16 }}>
          {format === "video_aid" && item.video_aid && (
            <div
              style={{
                marginBottom: 8,
                padding: "10px 12px",
                borderRadius: 8,
                border: "1px solid #93c5fd",
                background: "linear-gradient(135deg, #eff6ff, #f8fafc)",
              }}
            >
              <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
                Visual aid · {item.video_aid.visual_prompt || item.topic}
              </div>
              <div style={{ fontWeight: 600 }}>{item.video_aid.presenter_cue}</div>
              {item.video_aid.captions ? (
                <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>{item.prompt}</div>
              ) : null}
            </div>
          )}
          {format === "game" && item.game && (
            <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
              Challenge · {item.game.points_per_correct} pts if correct
            </div>
          )}
          <p style={{ marginBottom: 8 }}>
            <strong>{index + 1}. {item.prompt}</strong>
          </p>
          {format === "audio" && (
            <button
              type="button"
              onClick={() => speakItem(item.item_id)}
              style={{ marginBottom: 8, fontSize: 13 }}
            >
              🔊 Hear question
            </button>
          )}
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            {item.options.map((opt, i) => (
              <button
                key={`${item.item_id}-${i}`}
                type="button"
                disabled={busy || submitting}
                onClick={() => setAnswers((prev) => ({ ...prev, [item.item_id]: i }))}
                style={{
                  background: answers[item.item_id] === i
                    ? (format === "game" ? "#16a34a" : "#6366f1")
                    : "transparent",
                  color: answers[item.item_id] === i ? "#fff" : "inherit",
                  border: "1px solid var(--border)",
                  fontSize: 13,
                }}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ))}

      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={() => void onSubmit()}
          disabled={busy || submitting || !allAnswered}
          style={{ background: "#111", color: "#fff" }}
        >
          {submitting ? "Submitting…" : "Submit assessment"}
        </button>
        {onDismiss && run.checkpoint.stage !== "summative" ? (
          <button type="button" onClick={onDismiss} disabled={busy || submitting}>
            {dismissLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}
