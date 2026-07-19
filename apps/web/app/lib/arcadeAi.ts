// Lightweight AI opponent for "Challenge the AI" arcade modes.

import type { ArcadeAge } from "./arcadeQuestions";

export type AiProfile = {
  name: string;
  accuracy: number;   // 0–1 chance to pick correct answer
  thinkMs: number;    // base delay before answering
  jitterMs: number;   // random extra delay
};

const PROFILES: Record<ArcadeAge, AiProfile> = {
  kids: { name: "Chip the Robot", accuracy: 0.62, thinkMs: 2200, jitterMs: 800 },
  tween: { name: "Nova AI", accuracy: 0.74, thinkMs: 1800, jitterMs: 600 },
  teen: { name: "Professor Byte", accuracy: 0.84, thinkMs: 1400, jitterMs: 500 },
  adult: { name: "Grandmaster Sigma", accuracy: 0.92, thinkMs: 1000, jitterMs: 400 },
};

export function aiProfile(age: ArcadeAge): AiProfile {
  return PROFILES[age];
}

/** Pick an answer index; returns correct index with probability `accuracy`. */
export function aiPickAnswer(correctIndex: number, optionCount: number, accuracy: number): number {
  if (Math.random() < accuracy) return correctIndex;
  const wrong = Array.from({ length: optionCount }, (_, i) => i).filter((i) => i !== correctIndex);
  return wrong[Math.floor(Math.random() * wrong.length)];
}

export function aiThinkDelay(profile: AiProfile): number {
  return profile.thinkMs + Math.random() * profile.jitterMs;
}

export type DuelState = {
  playerScore: number;
  aiScore: number;
  round: number;
  maxRounds: number;
  aiThinking: boolean;
};

export function initDuel(maxRounds = 8): DuelState {
  return { playerScore: 0, aiScore: 0, round: 0, maxRounds, aiThinking: false };
}

export function scoreDuelRound(
  state: DuelState,
  playerCorrect: boolean,
  aiCorrect: boolean,
  playerFast: boolean,
): DuelState {
  let playerScore = state.playerScore;
  let aiScore = state.aiScore;
  if (playerCorrect) playerScore += playerFast ? 15 : 10;
  if (aiCorrect) aiScore += 10;
  if (playerCorrect && !aiCorrect) playerScore += 5;   // beat AI bonus
  if (!playerCorrect && aiCorrect) aiScore += 3;
  return { ...state, playerScore, aiScore, round: state.round + 1, aiThinking: false };
}

export function duelWinner(state: DuelState): "player" | "ai" | "tie" | null {
  if (state.round < state.maxRounds) return null;
  if (state.playerScore > state.aiScore) return "player";
  if (state.aiScore > state.playerScore) return "ai";
  return "tie";
}
