/** Display helpers for the learner-facing adaptation line.

The sentence key is chosen in ``aoep_shared.adaptation_line``. This module
only translates that key and tracks in-class emphasis votes.
*/

export type Emphasis = "visual" | "reading" | "listening" | "practice";

export type AdaptTick = {
  learner_line_key?: string;
  learner_line_style?: string;
  learner_line_pace?: string;
};

export function canonicalStyle(raw: string | undefined): Emphasis | "balanced" {
  const s = (raw || "").toLowerCase();
  if (s.includes("visual")) return "visual";
  if (s.includes("audit") || s.includes("listen")) return "listening";
  if (s.includes("read")) return "reading";
  if (s.includes("hand") || s.includes("kinesthetic") || s.includes("practice")) return "practice";
  return "balanced";
}

export function paceDwellFactor(pacing: string): number {
  if (pacing === "slow") return 1.45;
  if (pacing === "fast") return 0.7;
  return 1;
}

export function emptyEmphasisVotes(): Record<Emphasis, number> {
  return { visual: 0, reading: 0, listening: 0, practice: 0 };
}

/** Return the leading emphasis once one signal is clearly ahead. */
export function noteEmphasis(
  votes: Record<Emphasis, number>,
  kind: Emphasis,
): Emphasis | null {
  votes[kind] += 1;
  let best: Emphasis = kind;
  let bestN = 0;
  (Object.keys(votes) as Emphasis[]).forEach((key) => {
    if (votes[key] > bestN) {
      best = key;
      bestN = votes[key];
    }
  });
  return bestN >= 3 ? best : null;
}

export function formatAdaptLine(
  t: (key: string, vars?: Record<string, string | number>) => string,
  tick: AdaptTick | null,
): string {
  const key = tick?.learner_line_key || "";
  if (!key.startsWith("adapt.")) return "";
  const style = t(`adapt.style.${tick?.learner_line_style || "balanced"}`);
  const pace = t(`adapt.pace.${tick?.learner_line_pace || "moderate"}`);
  return t(key, { style, pace });
}

export function difficultyBadgeStyle(level: string): { background: string; color: string; border: string } {
  if (level === "hard") return { background: "#fee2e2", color: "#991b1b", border: "1px solid #dc2626" };
  if (level === "easy") return { background: "#dcfce7", color: "#166534", border: "1px solid #16a34a" };
  return { background: "#fef9c3", color: "#854d0e", border: "1px solid #ca8a04" };
}
