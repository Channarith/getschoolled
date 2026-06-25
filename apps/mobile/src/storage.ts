// Persistent client-side state (Continue Listening, My List, settings, streak).
// Backed by AsyncStorage so it survives app restarts and works offline.

import AsyncStorage from "@react-native-async-storage/async-storage";

import type { NarrationVoicePref } from "./voiceProfiles";

const KEYS = {
  continue: "@aic/continue.v1",     // { [courseId]: { id, title, segment, total, updatedAt } }
  myList: "@aic/mylist.v1",         // string[]
  settings: "@aic/settings.v1",     // see DEFAULT_SETTINGS
  inboxRead: "@aic/inbox-read.v1",  // string[] (notification ids marked as read)
  streak: "@aic/streak.v1",         // { days: number, lastDayISO: string }
  interests: "@aic/interests.v1",   // string[] (categories the user has opened)
  authToken: "@aic/auth-token.v1",  // identity JWT
} as const;

/** In-memory auth cache (AsyncStorage is async; API client reads sync). */
let tokenCache: string | null = null;

export type ContinueRow = {
  id: string; title: string; category?: string;
  segment: number; total: number; updatedAt: string;
};

export type Settings = {
  notificationsEnabled: boolean;
  dailyReminder: boolean;
  dailyReminderHour: number;
  newContentAlerts: boolean;
  completionAlerts: boolean;
  studentId: string;
  /** Master toggle: GPS + motion driving detection for Drive Mode. */
  driveDetectionEnabled: boolean;
  /** Use GPS speed from device location (requires permission). */
  driveUseLocation: boolean;
  /** Use accelerometer/gyro to augment motion context (requires permission on iOS). */
  driveUseMotionSensors: boolean;
  /** Open Drive tab when driving is detected. */
  driveAutoLaunch: boolean;
  /** Local alert when driving starts. */
  driveDrivingAlerts: boolean;
  /** auto = infer from learning profile (child, accessibility, pace). */
  narrationVoicePref: NarrationVoicePref;
};

export const DEFAULT_SETTINGS: Settings = {
  notificationsEnabled: true,
  dailyReminder: true,
  dailyReminderHour: 18,
  newContentAlerts: true,
  completionAlerts: true,
  studentId: "guest",
  driveDetectionEnabled: false,
  driveUseLocation: true,
  driveUseMotionSensors: true,
  driveAutoLaunch: false,
  driveDrivingAlerts: true,
  narrationVoicePref: "auto",
};

async function readJSON<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}
async function writeJSON<T>(key: string, value: T): Promise<void> {
  try { await AsyncStorage.setItem(key, JSON.stringify(value)); } catch {}
}

export async function getContinueMap(): Promise<Record<string, ContinueRow>> {
  return readJSON<Record<string, ContinueRow>>(KEYS.continue, {});
}
export async function listContinue(): Promise<ContinueRow[]> {
  const m = await getContinueMap();
  return Object.values(m).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}
export async function recordProgress(row: Omit<ContinueRow, "updatedAt">): Promise<void> {
  const m = await getContinueMap();
  m[row.id] = { ...row, updatedAt: new Date().toISOString() };
  await writeJSON(KEYS.continue, m);
}
export async function clearProgress(id: string): Promise<void> {
  const m = await getContinueMap();
  delete m[id];
  await writeJSON(KEYS.continue, m);
}

export async function getMyList(): Promise<string[]> {
  return readJSON<string[]>(KEYS.myList, []);
}
export async function isInMyList(id: string): Promise<boolean> {
  const ids = await getMyList();
  return ids.includes(id);
}
export async function toggleMyList(id: string): Promise<boolean> {
  const ids = await getMyList();
  const idx = ids.indexOf(id);
  if (idx >= 0) ids.splice(idx, 1); else ids.unshift(id);
  await writeJSON(KEYS.myList, ids);
  return idx < 0;
}

export async function getSettings(): Promise<Settings> {
  const s = await readJSON<Partial<Settings>>(KEYS.settings, {});
  return { ...DEFAULT_SETTINGS, ...s };
}
export async function setSettings(patch: Partial<Settings>): Promise<Settings> {
  const cur = await getSettings();
  const next = { ...cur, ...patch };
  await writeJSON(KEYS.settings, next);
  return next;
}

export async function getReadIds(): Promise<string[]> {
  return readJSON<string[]>(KEYS.inboxRead, []);
}
export async function markRead(id: string): Promise<void> {
  const ids = new Set(await getReadIds());
  ids.add(id);
  await writeJSON(KEYS.inboxRead, Array.from(ids));
}
export async function markAllRead(allIds: string[]): Promise<void> {
  const ids = new Set(await getReadIds());
  for (const i of allIds) ids.add(i);
  await writeJSON(KEYS.inboxRead, Array.from(ids));
}

export type Streak = { days: number; lastDayISO: string };

export async function getStreak(): Promise<Streak> {
  return readJSON<Streak>(KEYS.streak, { days: 0, lastDayISO: "" });
}

// Bump the streak when the user finishes (or makes meaningful progress in) a
// class. Increments by one if the last bump was yesterday; resets to 1 if
// it's been > 1 day; no-ops within the same day.
export async function bumpStreak(): Promise<Streak> {
  const cur = await getStreak();
  const today = new Date().toISOString().slice(0, 10);
  if (cur.lastDayISO === today) return cur;
  let days = 1;
  if (cur.lastDayISO) {
    const last = new Date(cur.lastDayISO + "T00:00:00Z");
    const now = new Date(today + "T00:00:00Z");
    const diffDays = Math.round((now.getTime() - last.getTime()) / 86400000);
    days = diffDays === 1 ? cur.days + 1 : 1;
  }
  const next = { days, lastDayISO: today };
  await writeJSON(KEYS.streak, next);
  return next;
}

export async function getInterests(): Promise<string[]> {
  return readJSON<string[]>(KEYS.interests, []);
}
export async function recordInterest(category: string): Promise<void> {
  if (!category) return;
  const set = new Set(await getInterests());
  set.add(category.toLowerCase());
  await writeJSON(KEYS.interests, Array.from(set).slice(-12));
}

export function getToken(): string | null {
  return tokenCache;
}

export async function loadAuthToken(): Promise<string | null> {
  try {
    tokenCache = await AsyncStorage.getItem(KEYS.authToken);
  } catch {
    tokenCache = null;
  }
  return tokenCache;
}

export async function setAuthToken(token: string): Promise<void> {
  tokenCache = token;
  try { await AsyncStorage.setItem(KEYS.authToken, token); } catch { /* ignore */ }
}

export async function clearAuthToken(): Promise<void> {
  tokenCache = null;
  try { await AsyncStorage.removeItem(KEYS.authToken); } catch { /* ignore */ }
}
