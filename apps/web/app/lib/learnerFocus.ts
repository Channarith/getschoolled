/**
 * Attention and away/back windows for class cameras.
 *
 * Keep the numeric constants aligned with aoep_shared.learner_focus and
 * the children-lab vision_math.js module. Tests grep all three.
 *
 * YuNet (this web app's on-device detector) exposes five landmarks: eyes, nose,
 * mouth corners. That is enough for yaw / looking away. It is not enough for
 * "looking at a phone" — do not pass allowPoseOnly for those samples.
 * Face-mesh pitch + eye-look blendshapes are the phone signal, and only after
 * SIGNAL_HOLD_MS so a glance does not count.
 */

export const AWAY_HOLD_MS = 2500;
export const RETURN_HOLD_MS = 1200;
export const SIGNAL_HOLD_MS = 1500;
export const BLIND_ARM_MS = 8000;
export const PHONE_PITCH_WITH_GAZE_DEG = 18;
export const PHONE_PITCH_POSE_ONLY_DEG = 28;
export const GAZE_DOWN_MIN = 0.38;
export const YAW_AWAY_DEG = 25;

export const PAUSE_LINE = "I'll pause here. Come back when you're ready.";
export const RESUME_LINE = "Welcome back. We'll continue from the same place.";
export const PHONE_LINE = "Looks like you might be looking down at a phone. The lesson is still here when you look up.";
export const LOOK_AWAY_LINE = "Look back at the screen when you can. I'll keep going from here.";
export const LEFT_LINE = "I can't see you in the camera. I'll wait here.";

export type PresenceSample = {
  atMs: number;
  facePresent: boolean;
  pitchDeg?: number | null;
  yawDeg?: number | null;
  gazeDown?: number | null;
  gazeFrontal?: number | null;
  /** True only for a face-mesh pitch. False for YuNet. */
  allowPoseOnly?: boolean;
  explicitAway?: boolean;
  source?: string;
};

export type PresenceCue = {
  type: "pause" | "resume" | "notice";
  kind: string;
  line: string;
  notice?: string;
  awayMs?: number;
  atMs: number;
  signal?: string;
};

type WatchState = {
  phase: "unknown" | "here" | "away";
  awaySince: number | null;
  backSince: number | null;
  awayStarted: number;
  phoneSince: number | null;
  lookSince: number | null;
  phoneOpen: boolean;
  lookOpen: boolean;
  seenFace: boolean;
  /** Null until the first sample. Zero is a real clock value. */
  started: number | null;
};

function phoneSignal(sample: PresenceSample): string | null {
  const pitch = sample.pitchDeg;
  if (pitch == null || !Number.isFinite(pitch)) return null;
  if (sample.gazeDown != null && Number.isFinite(sample.gazeDown)) {
    return pitch >= PHONE_PITCH_WITH_GAZE_DEG && sample.gazeDown >= GAZE_DOWN_MIN
      ? "pitch_and_gaze"
      : null;
  }
  if (sample.allowPoseOnly && pitch >= PHONE_PITCH_POSE_ONLY_DEG) return "head_pose_only";
  return null;
}

function attentionEvents(watch: WatchState, sample: PresenceSample, now: number): PresenceCue[] {
  const events: PresenceCue[] = [];
  const phone = phoneSignal(sample);
  if (phone) {
    if (watch.phoneSince == null) watch.phoneSince = now;
    if (!watch.phoneOpen && now - (watch.phoneSince ?? now) >= SIGNAL_HOLD_MS) {
      watch.phoneOpen = true;
      events.push({
        type: "notice",
        kind: "looking_at_phone",
        line: PHONE_LINE,
        signal: phone,
        atMs: now,
      });
    }
  } else {
    watch.phoneSince = null;
    watch.phoneOpen = false;
  }
  const yaw = sample.yawDeg;
  const frontal = sample.gazeFrontal;
  const away = phone
    ? null
    : (yaw != null && Math.abs(yaw) >= YAW_AWAY_DEG
      ? "yaw"
      : (frontal != null && frontal < 0.4 ? "gaze_frontal" : null));
  if (away) {
    if (watch.lookSince == null) watch.lookSince = now;
    if (!watch.lookOpen && now - (watch.lookSince ?? now) >= SIGNAL_HOLD_MS) {
      watch.lookOpen = true;
      events.push({
        type: "notice",
        kind: "looking_away",
        line: LOOK_AWAY_LINE,
        signal: away,
        atMs: now,
      });
    }
  } else {
    watch.lookSince = null;
    watch.lookOpen = false;
  }
  return events;
}

export function createPresenceWatch() {
  const watch: WatchState = {
    phase: "unknown",
    awaySince: null,
    backSince: null,
    awayStarted: 0,
    phoneSince: null,
    lookSince: null,
    phoneOpen: false,
    lookOpen: false,
    seenFace: false,
    started: null,
  };
  return {
    update(sample: PresenceSample): PresenceCue[] {
      const rawNow = Number(sample.atMs);
      const now = Number.isFinite(rawNow) ? rawNow : 0;
      if (watch.started == null) watch.started = now;
      const events: PresenceCue[] = [];
      if (sample.facePresent) {
        watch.seenFace = true;
        watch.awaySince = null;
        if (watch.phase === "away") {
          if (watch.backSince == null) watch.backSince = now;
          if (now - (watch.backSince ?? now) >= RETURN_HOLD_MS) {
            const awayMs = Math.max(0, now - watch.awayStarted);
            watch.phase = "here";
            watch.backSince = null;
            events.push({
              type: "resume",
              kind: "returned",
              line: RESUME_LINE,
              awayMs,
              atMs: now,
              signal: sample.source || "",
            });
          }
        } else if (watch.phase === "unknown") {
          watch.phase = "here";
        }
        if (watch.phase === "here") events.push(...attentionEvents(watch, sample, now));
        return events;
      }
      watch.backSince = null;
      watch.phoneSince = null;
      watch.lookSince = null;
      watch.phoneOpen = false;
      watch.lookOpen = false;
      if (sample.explicitAway) {
        if (watch.phase !== "away") {
          watch.phase = "away";
          watch.awayStarted = now;
          watch.awaySince = now;
          events.push({
            type: "pause",
            kind: "left_frame",
            line: PAUSE_LINE,
            atMs: now,
            signal: sample.source || "explicit",
          });
        }
        return events;
      }
      const armed = watch.seenFace || now - (watch.started ?? now) >= BLIND_ARM_MS;
      if (!armed) return events;
      if (watch.awaySince == null) watch.awaySince = now;
      const held = watch.seenFace ? AWAY_HOLD_MS : 0;
      if (watch.phase !== "away" && now - (watch.awaySince ?? now) >= held) {
        watch.phase = "away";
        watch.awayStarted = watch.awaySince;
        events.push({
          type: "pause",
          kind: "left_frame",
          line: PAUSE_LINE,
          notice: LEFT_LINE,
          atMs: now,
          signal: sample.source || "no_face",
        });
      }
      return events;
    },
  };
}

/** YuNet order: right eye, left eye, nose, mouth corners. Yaw only. */
export function yawFromFivePoint(landmarks: number[][] | undefined): { yawDeg: number; gazeFrontal: number } | null {
  if (!landmarks || landmarks.length < 3) return null;
  const right = landmarks[0];
  const left = landmarks[1];
  const nose = landmarks[2];
  if (!right || !left || !nose) return null;
  const iod = Math.hypot(left[0] - right[0], left[1] - right[1]) || 1;
  const mid = (right[0] + left[0]) / 2;
  const offset = (nose[0] - mid) / iod;
  return {
    yawDeg: Math.max(-60, Math.min(60, offset * 50)),
    gazeFrontal: Math.max(0, Math.min(1, 1 - Math.abs(offset) * 1.6)),
  };
}
