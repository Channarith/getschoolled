"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  applyAdmin,
  AUTH_EVENT,
  evaluateFlags,
  getFlag,
  getMe,
  getToken,
  isAdminUnlocked,
} from "./api";
import { SALES_DEMO_FLAGS } from "./salesDemo";
import {
  DEFAULT_VOICE_PAUSE_SUBMIT_MS,
  normalizeVoicePauseSubmitMs,
} from "./voiceCommands";

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

/** null until the saved sign-in token has been read. */
export function useSignedIn(): boolean | null {
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  useEffect(() => {
    const sync = () => setSignedIn(Boolean(getToken()));
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return signedIn;
}

/**
 * True when demo-only mode (sales_demo.exclusive) is on AND the visitor is
 * signed out. Signed-in users always see the regular site; demo-only mode is
 * an anonymous-visitor-only experience.
 */
export function useDemoOnlyAnonymous(): boolean {
  const demoOnly = useFlag<boolean>(SALES_DEMO_FLAGS.exclusive, false);
  const [signedOut, setSignedOut] = useState(true);
  useEffect(() => {
    const sync = () => setSignedOut(!getToken());
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return demoOnly && signedOut;
}

/**
 * Whether the current user is an admin (server-authoritative via /auth/me,
 * cached via localStorage.aoep_admin). Re-resolves on sign-in/out.
 *
 * Used as the lock-out guard for the `sales_demo.restrict_signed_in` and
 * `sales_demo.login_enabled` flags — admins must always keep full access
 * so a mis-toggled flag can't orphan the operator.
 */
export function useIsAdmin(): boolean {
  const [admin, setAdmin] = useState<boolean>(() => isAdminUnlocked());
  useEffect(() => {
    let cancelled = false;
    const resolveFromServer = async () => {
      if (!getToken()) {
        if (!cancelled) setAdmin(false);
        return;
      }
      try {
        const me = await getMe();
        if (cancelled) return;
        if (me.is_admin) applyAdmin(true); // persist for sync reads elsewhere
        setAdmin(Boolean(me.is_admin) || isAdminUnlocked());
      } catch {
        if (!cancelled) setAdmin(isAdminUnlocked());
      }
    };
    const sync = () => {
      setAdmin(isAdminUnlocked());
      void resolveFromServer();
    };
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      cancelled = true;
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return admin;
}

/**
 * True when login should be hidden for the general public (flag
 * `sales_demo.login_enabled=false`). ALWAYS false for admins and when the
 * `?override=1` escape hatch is present on the URL — so flipping the flag
 * off can never lock an admin out.
 */
export function useLoginGateHidden(): boolean {
  const loginEnabled = useFlag<boolean>(SALES_DEMO_FLAGS.loginEnabled, true);
  const isAdmin = useIsAdmin();
  const [override, setOverride] = useState(false);
  useEffect(() => {
    try {
      const p = new URLSearchParams(window.location.search);
      setOverride(p.get("override") === "1");
    } catch {
      setOverride(false);
    }
  }, []);
  if (isAdmin || override) return false;
  return !loginEnabled;
}

/**
 * True when a signed-in NON-admin user should be kept inside the demo-only
 * showcase (flag `sales_demo.restrict_signed_in=true`). Admins always see
 * the full site, no matter what this flag says — that's the lock-out guard.
 */
export function useRestrictSignedIn(): boolean {
  const restrict = useFlag<boolean>(SALES_DEMO_FLAGS.restrictSignedIn, false);
  const isAdmin = useIsAdmin();
  const signedIn = useSignedIn();
  return Boolean(restrict && signedIn && !isAdmin);
}

/**
 * True when the admin has opted into the FULL navigation (Home, Browse, For
 * You, Kids, Corporate, Languages, Drive, Group Classes, Watch, Homework)
 * via flag `nav.full_tabs_enabled`. When OFF (default), every signed-in
 * account sees the simplified 5-tab launch header. Lives in LocalizedNav.tsx.
 */
export function useFullNavTabs(): boolean {
  return useFlag<boolean>("nav.full_tabs_enabled", false);
}

/**
 * True (default) when the simplified Vision Play Lab mode is on: /arcade
 * shows ONLY the Vision Arcade iframe and hides the rest of the games hub
 * (banner, categories, picker, leaderboard, etc.). Admin can toggle via
 * `arcade.vision_only` in /admin to restore the full arcade hub.
 */
export function useArcadeVisionOnly(): boolean {
  return useFlag<boolean>("arcade.vision_only", true);
}

/** Resolved ``ux.voice_pause_submit_ms`` (default 4.5s). */
export function useVoicePauseSubmitMs(): number {
  const raw = useFlag<number>("ux.voice_pause_submit_ms", DEFAULT_VOICE_PAUSE_SUBMIT_MS);
  return normalizeVoicePauseSubmitMs(raw);
}
