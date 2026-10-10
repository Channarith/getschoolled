/** Pure queue for class voice. One turn is spoken once: xAI audio, or the
 * device fallback, never both. A later "speak latest" drops unheard queued
 * lines so an old slide cannot talk over the new one.
 */

export type SpeakPhase = "idle" | "checking" | "live" | "unavailable";

export type PlannedTurn = {
  id: string;
  text: string;
  gen: number;
};

export type SpeakPlan = {
  phase: SpeakPhase;
  queue: PlannedTurn[];
  inflight: PlannedTurn | null;
  sent: Set<string>;
  heardGen: number | null;
  finishedGen: number | null;
  fallbackGen: number | null;
  gen: number;
};

export type SpeakDecision =
  | { kind: "ignore" }
  | { kind: "queue" }
  | { kind: "fallback"; turn: PlannedTurn }
  | { kind: "send"; turn: PlannedTurn };

export function createSpeakPlan(): SpeakPlan {
  return {
    phase: "idle",
    queue: [],
    inflight: null,
    sent: new Set(),
    heardGen: null,
    finishedGen: null,
    fallbackGen: null,
    gen: 0,
  };
}

function dropUnsent(plan: SpeakPlan, turns: PlannedTurn[]): void {
  for (const turn of turns) {
    if (!plan.sent.has(turn.id)) plan.sent.add(turn.id);
  }
}

export function requestSpeak(
  plan: SpeakPlan,
  id: string,
  text: string,
  active: boolean,
  canSend: boolean,
): SpeakDecision {
  const spoken = text.trim();
  if (!spoken || plan.sent.has(id)) return { kind: "ignore" };
  const turn: PlannedTurn = { id, text: spoken, gen: plan.gen + 1 };
  plan.gen = turn.gen;

  if (!active || plan.phase === "unavailable") {
    plan.sent.add(id);
    plan.fallbackGen = turn.gen;
    return { kind: "fallback", turn };
  }

  if (plan.phase === "live" && canSend) {
    if (plan.inflight && plan.finishedGen !== plan.inflight.gen && plan.fallbackGen !== plan.inflight.gen) {
      plan.sent.add(plan.inflight.id);
      plan.finishedGen = plan.inflight.gen;
    }
    dropUnsent(plan, plan.queue);
    plan.queue = [];
    plan.inflight = turn;
    plan.sent.add(id);
    plan.heardGen = null;
    return { kind: "send", turn };
  }

  plan.queue = plan.queue.filter((queued) => queued.id !== id).concat(turn);
  return { kind: "queue" };
}

export function takeQueuedForSend(plan: SpeakPlan): PlannedTurn | null {
  plan.phase = "live";
  while (plan.queue.length) {
    const next = plan.queue.shift()!;
    if (plan.sent.has(next.id) || plan.fallbackGen === next.gen) continue;
    plan.inflight = next;
    plan.sent.add(next.id);
    plan.heardGen = null;
    return next;
  }
  return null;
}

function alreadySpoken(plan: SpeakPlan, turn: PlannedTurn): boolean {
  return plan.heardGen === turn.gen
    || plan.finishedGen === turn.gen
    || plan.fallbackGen === turn.gen;
}

/** Turns that never produced xAI audio. Already-heard audio is left alone. */
export function takeUnheardForFallback(plan: SpeakPlan): PlannedTurn[] {
  const pending = plan.queue.splice(0);
  const inflight = plan.inflight;
  plan.inflight = null;
  const out: PlannedTurn[] = [];
  const push = (turn: PlannedTurn) => {
    if (alreadySpoken(plan, turn)) return;
    plan.sent.add(turn.id);
    plan.fallbackGen = turn.gen;
    out.push(turn);
  };
  if (inflight) push(inflight);
  for (const turn of pending) push(turn);
  plan.phase = "unavailable";
  return out;
}

/** The agent failed this turn before any audio. One device fallback, no replay. */
export function noteAgentFailure(plan: SpeakPlan): PlannedTurn | null {
  const turn = plan.inflight;
  if (!turn || alreadySpoken(plan, turn)) return null;
  plan.sent.add(turn.id);
  plan.fallbackGen = turn.gen;
  plan.inflight = null;
  return turn;
}

export function noteAudio(plan: SpeakPlan, gen: number | null): "play" | "drop" {
  if (gen == null) return "drop";
  if (plan.fallbackGen === gen || plan.finishedGen === gen) return "drop";
  plan.heardGen = gen;
  return "play";
}

export function audioJustStarted(plan: SpeakPlan, gen: number | null, heardBefore: number | null): boolean {
  return gen != null && heardBefore !== gen && plan.heardGen === gen && plan.fallbackGen !== gen;
}

export function noteResponseEnd(plan: SpeakPlan): "finish" | "ignore" {
  const turn = plan.inflight;
  if (!turn) return "ignore";
  if (plan.finishedGen === turn.gen || plan.fallbackGen === turn.gen) return "ignore";
  if (plan.heardGen !== turn.gen) return "ignore";
  plan.finishedGen = turn.gen;
  return "finish";
}

export function finishAndTakeNext(plan: SpeakPlan, canSend: boolean): PlannedTurn | null {
  plan.inflight = null;
  if (!canSend || plan.phase !== "live") return null;
  return takeQueuedForSend(plan);
}
