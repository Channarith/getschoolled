"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { AUTH_EVENT, evaluateFlags, getFlag, getMe } from "./api";

// Admin-only flags are excluded from the public /flags/evaluate bulk list, but the
// client still needs a few of them (the ops kill-switches) to render banners /
// gate writes. The single-key /flags/{key} endpoint resolves any key, so we fetch
// those explicitly and merge them into the map.
const EXTRA_KEYS = ["ops.maintenance_mode", "ops.read_only_mode"] as const;

type FlagsMap = Record<string, unknown>;

type FlagsContextValue = {
  flags: FlagsMap;
  ready: boolean;
  refresh: () => void;
};

const FlagsContext = createContext<FlagsContextValue>({
  flags: {},
  ready: false,
  refresh: () => {},
});

export function FlagsProvider({ children }: { children: React.ReactNode }) {
  const [flags, setFlags] = useState<FlagsMap>({});
  const [ready, setReady] = useState(false);

  const load = useCallback(async () => {
    // Bucket rollouts/tier targeting on the signed-in account when available.
    let subject: string | undefined;
    let tier: string | undefined;
    try {
      const me = await getMe();
      subject = me.id;
      tier = me.tier;
    } catch {
      /* anonymous visitor — resolve with defaults */
    }
    try {
      const base = await evaluateFlags(subject, tier);
      const extras = await Promise.all(
        EXTRA_KEYS.map((k) => getFlag(k, subject).catch(() => undefined)),
      );
      const merged: FlagsMap = { ...base };
      EXTRA_KEYS.forEach((k, i) => {
        if (extras[i] !== undefined) merged[k] = extras[i];
      });
      setFlags(merged);
    } catch {
      /* memory unavailable — keep last-known/empty so callers use fallbacks */
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    void load();
    const onChange = () => void load();
    window.addEventListener(AUTH_EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(AUTH_EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  }, [load]);

  return (
    <FlagsContext.Provider value={{ flags, ready, refresh: () => void load() }}>
      {children}
    </FlagsContext.Provider>
  );
}

/** Read a single flag's resolved value with a typed fallback. */
export function useFlag<T = boolean>(key: string, fallback: T): T {
  const { flags, ready } = useContext(FlagsContext);
  if (!ready || !(key in flags)) return fallback;
  return flags[key] as T;
}

export function useFlags() {
  return useContext(FlagsContext);
}
