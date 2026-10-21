import type { StringKey } from "./i18n/strings";

export type AdaptTick = {
  learner_line_key?: string;
  learner_line_style?: string;
  learner_line_pace?: string;
};

const LINE_KEYS: Record<string, StringKey> = {
  "adapt.starting": "adapt.starting",
  "adapt.lookedAway": "adapt.lookedAway",
  "adapt.easier": "adapt.easier",
  "adapt.movingAhead": "adapt.movingAhead",
  "adapt.reteach": "adapt.reteach",
  "adapt.slowing": "adapt.slowing",
  "adapt.staysVisual": "adapt.staysVisual",
  "adapt.staysReading": "adapt.staysReading",
  "adapt.staysListening": "adapt.staysListening",
  "adapt.staysPractice": "adapt.staysPractice",
};

const STYLE_KEYS: Record<string, StringKey> = {
  visual: "adapt.style.visual",
  listening: "adapt.style.listening",
  reading: "adapt.style.reading",
  practice: "adapt.style.practice",
  balanced: "adapt.style.balanced",
};

const PACE_KEYS: Record<string, StringKey> = {
  slow: "adapt.pace.slow",
  moderate: "adapt.pace.moderate",
  fast: "adapt.pace.fast",
};

export function formatAdaptLine(
  t: (key: StringKey, vars?: Record<string, string | number>) => string,
  tick: AdaptTick | null,
): string {
  const key = LINE_KEYS[tick?.learner_line_key || ""];
  if (!key) return "";
  const style = t(STYLE_KEYS[tick?.learner_line_style || "balanced"] || "adapt.style.balanced");
  const pace = t(PACE_KEYS[tick?.learner_line_pace || "moderate"] || "adapt.pace.moderate");
  return t(key, { style, pace });
}
