import { useEffect, useState } from "react";

import { getFlag } from "./api";
import {
  DEFAULT_VOICE_PAUSE_SUBMIT_MS,
  normalizeVoicePauseSubmitMs,
} from "./voiceAssistant";

export const VOICE_PAUSE_SUBMIT_FLAG = "ux.voice_pause_submit_ms";

export function useFeatureFlag(key: string, fallback = false): boolean {
  const [enabled, setEnabled] = useState(fallback);

  useEffect(() => {
    let cancelled = false;
    getFlag(key)
      .then((value) => {
        if (!cancelled) setEnabled(Boolean(value));
      })
      .catch(() => {
        if (!cancelled) setEnabled(fallback);
      });
    return () => {
      cancelled = true;
    };
  }, [fallback, key]);

  return enabled;
}

/** Resolve a numeric feature-flag value (falls back offline / on error). */
export function useFeatureFlagNumber(key: string, fallback: number): number {
  const [value, setValue] = useState(fallback);

  useEffect(() => {
    let cancelled = false;
    getFlag(key)
      .then((raw) => {
        if (cancelled) return;
        const n = typeof raw === "number" ? raw : Number(raw);
        setValue(Number.isFinite(n) ? n : fallback);
      })
      .catch(() => {
        if (!cancelled) setValue(fallback);
      });
    return () => {
      cancelled = true;
    };
  }, [fallback, key]);

  return value;
}

/** Tunable pause-to-auto-submit delay for microphone capture (ms). */
export function useVoicePauseSubmitMs(): number {
  const raw = useFeatureFlagNumber(VOICE_PAUSE_SUBMIT_FLAG, DEFAULT_VOICE_PAUSE_SUBMIT_MS);
  return normalizeVoicePauseSubmitMs(raw, DEFAULT_VOICE_PAUSE_SUBMIT_MS);
}
