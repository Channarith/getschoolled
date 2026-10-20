// Scripted face engine for testing Learner Check without a real face.
//
// It stands in for YuNet + SFace: every detect() returns one centered face
// whose five landmarks walk through neutral, left, right, up, and down on a
// timer, and embedAt() returns a vector that stays close to the neutral one.
// The camera stream and the server calls are still real, so the full flow
// (scan -> face save -> voice save -> Continue) runs end to end.
//
// Enabled by NEXT_PUBLIC_LEARNER_CHECK_MOCK=1, or by ?learnerCheckMock=1 on a
// non-production build.

import type { WireFace } from "./api";
import type { ImageSource, VisionEngine } from "./vision";

const FRAME: [number, number] = [640, 480];
const STEP_MS = 650;
// Neutral first so the portrait locks, then every look with a neutral
// between them, repeated until the scan has all four.
const SCRIPT = ["center", "center", "left", "center", "right", "center", "up", "center", "down", "center"] as const;
type Phase = (typeof SCRIPT)[number];

const DIMENSIONS = 128;

function seeded(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0x100000000 - 0.5;
  };
}

function vector(seed: number): number[] {
  const next = seeded(seed);
  return Array.from({ length: DIMENSIONS }, () => next());
}

const BASE = vector(7);
const OFFSETS: Record<Phase, number[]> = {
  center: vector(11),
  left: vector(13),
  right: vector(17),
  up: vector(19),
  down: vector(23),
};

export function learnerCheckMockEnabled(): boolean {
  if (process.env.NEXT_PUBLIC_LEARNER_CHECK_MOCK === "1") return true;
  if (process.env.NODE_ENV === "production" || typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("learnerCheckMock") === "1";
}

function landmarksFor(phase: Phase): number[][] {
  const noseX = phase === "left" ? 334 : phase === "right" ? 306 : 320;
  const noseY = phase === "up" ? 243 : phase === "down" ? 257 : 250;
  return [
    [270, 200],
    [370, 200],
    [noseX, noseY],
    [285, 300],
    [355, 300],
  ];
}

function phaseOf(landmarks: number[][]): Phase {
  const [x, y] = landmarks[2] ?? [320, 250];
  if (x > 327) return "left";
  if (x < 313) return "right";
  if (y < 247) return "up";
  if (y > 253) return "down";
  return "center";
}

export function createMockVisionEngine(now: () => number = () => performance.now()): VisionEngine {
  const started = now();
  let calls = 0;

  function detect(): WireFace[] {
    const index = Math.floor((now() - started) / STEP_MS) % SCRIPT.length;
    const phase = SCRIPT[index];
    return [{
      embedding: [],
      bbox: [240, 130, 160, 220],
      landmarks: landmarksFor(phase),
      frame_size: FRAME,
    }];
  }

  function embedAt(_source: ImageSource, landmarks: number[][]): number[] {
    calls += 1;
    const offset = OFFSETS[phaseOf(landmarks)];
    const jitter = vector(97 + calls);
    return BASE.map((value, i) => value + 0.25 * offset[i] + 0.02 * jitter[i]);
  }

  return {
    detect,
    detectAndEmbed: (source) => detect().map((face) => ({ ...face, embedding: embedAt(source, face.landmarks ?? []) })),
    embedAt,
    dispose: () => undefined,
  };
}
