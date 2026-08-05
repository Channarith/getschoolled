// Push / local notifications wrapper.
//
// expo-notifications gives us real iOS / Android notifications. We use:
//   * presentNotificationAsync   - fire an immediate banner (e.g. completion).
//   * scheduleNotificationAsync  - schedule the daily reminder + new-content
//                                  alerts for items that should pop later.
//
// All scheduling is LOCAL - no remote push server is required for the demo.
// EAS Build with the right entitlements is enough for production push later.

import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import type { NotificationItem } from "./api";
import {
  DEFAULT_SETTINGS,
  getContentAlertDay,
  getLastOpenAt,
  getNotifiedCourses,
  getSettings,
  rememberNotifiedCourses,
  setContentAlertDay,
  type Settings,
} from "./storage";

const CHANNEL_ID = "aiclassroom-default";
const DAILY_REMINDER_TAG = "daily-reminder";
const NEW_CONTENT_TAG_PREFIX = "new-content:";
/** One slot for everything new, so content never arrives at a random hour. */
const CONTENT_DIGEST_TAG = "new-content-digest";
/**
 * A learner who opened the app inside this window is "current": they have
 * already seen what is on the shelf, so only genuinely new classes are worth a
 * notification. Lapsed users can still get a recommendation nudge.
 */
const RECENTLY_ACTIVE_HOURS = 36;

let _handlerInstalled = false;

export function installNotificationHandler() {
  if (_handlerInstalled) return;
  _handlerInstalled = true;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: true,
    }),
  });
}

async function ensureChannel() {
  if (Platform.OS !== "android") return;
  await Notifications.setNotificationChannelAsync(CHANNEL_ID, {
    name: "Salareen",
    importance: Notifications.AndroidImportance.DEFAULT,
    sound: "default",
    enableVibrate: true,
  });
}

export async function ensurePermissions(): Promise<boolean> {
  installNotificationHandler();
  await ensureChannel();
  const { status: existing } = await Notifications.getPermissionsAsync();
  if (existing === "granted") return true;
  const { status } = await Notifications.requestPermissionsAsync({
    ios: { allowAlert: true, allowBadge: true, allowSound: true },
  });
  return status === "granted";
}

export async function fireImmediate(title: string, body: string,
                                    data: Record<string, unknown> = {}) {
  installNotificationHandler();
  await ensureChannel();
  await Notifications.scheduleNotificationAsync({
    content: { title, body, data },
    trigger: null,
  });
}

export async function fireCompletionAlert(courseTitle: string, courseId: string) {
  await fireImmediate(
    "Class complete",
    `Nice work finishing "${courseTitle}". Want to start another?`,
    { courseId, kind: "completion" },
  );
}

export async function fireDrivingDetectedAlert(courseId?: string) {
  const s = await getSettings();
  if (!s.notificationsEnabled || !s.driveDrivingAlerts) return;
  await fireImmediate(
    "Driving detected",
    "Hands-free On the Go is ready. Tap to continue your class.",
    { courseId, kind: "driving", deepLink: "aiclassroom://drive" },
  );
}

// Cancel any previously scheduled instance with the same identifier prefix so
// re-scheduling is idempotent.
async function cancelByIdentifier(identifier: string) {
  try {
    await Notifications.cancelScheduledNotificationAsync(identifier);
  } catch {}
}

export async function rescheduleDailyReminder(settings?: Settings) {
  const s = settings || (await getSettings());
  await cancelByIdentifier(DAILY_REMINDER_TAG);
  if (!s.notificationsEnabled || !s.dailyReminder) return;
  await ensureChannel();
  await Notifications.scheduleNotificationAsync({
    identifier: DAILY_REMINDER_TAG,
    content: {
      title: "Your daily class is ready",
      body: "Five minutes of audio, hands-free. Tap to open On the Go.",
      data: { kind: "daily", deepLink: "aiclassroom://drive" },
    },
    trigger: {
      hour: Math.max(0, Math.min(23, s.dailyReminderHour | 0)),
      minute: 0,
      repeats: true,
    } as Notifications.DailyTriggerInput,
  });
}

/**
 * Drain alerts queued by the previous scheme.
 *
 * Older builds queued one "new-content:<item id>" notification per item on a
 * 31/61/91-minute offset. Those are already sitting in the OS queue on an
 * upgraded install and would keep arriving at odd hours after this change, so
 * clear them out before scheduling the routine digest.
 */
async function cancelLegacyContentAlerts(): Promise<void> {
  try {
    const pending = await Notifications.getAllScheduledNotificationsAsync();
    await Promise.all(
      pending
        .filter((n) => String(n.identifier || "").startsWith(NEW_CONTENT_TAG_PREFIX))
        .map((n) => cancelByIdentifier(n.identifier)),
    );
  } catch {
    /* best effort: never block scheduling on cleanup */
  }
}

/** Local YYYY-MM-DD, used to hold the digest to one per calendar day. */
function localDayKey(at: Date): string {
  const y = at.getFullYear();
  const m = String(at.getMonth() + 1).padStart(2, "0");
  const d = String(at.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** The next time the clock reads `hour`:`minute`, today or tomorrow. */
export function nextOccurrence(hour: number, minute: number, now: Date): Date {
  const at = new Date(now);
  at.setHours(Math.max(0, Math.min(23, hour | 0)), Math.max(0, Math.min(59, minute | 0)), 0, 0);
  if (at.getTime() <= now.getTime()) at.setDate(at.getDate() + 1);
  return at;
}

export function isRecentlyActive(lastOpenAt: string, now: Date): boolean {
  const last = Date.parse(lastOpenAt || "");
  if (!Number.isFinite(last)) return false;
  return now.getTime() - last <= RECENTLY_ACTIVE_HOURS * 3600 * 1000;
}

/** Stable per-course key: server item ids rotate daily and would re-alert forever. */
function contentKey(item: NotificationItem): string {
  return (item.course_id || "").trim() || item.id;
}

/**
 * Pick what is worth telling the learner about.
 *
 * A learner who has been in the app recently already saw the shelf, so they get
 * new classes only. Someone who has been away also gets recommendations.
 */
export function selectAlertableItems(
  items: NotificationItem[],
  opts: { alreadyNotified: Set<string>; recentlyActive: boolean },
): NotificationItem[] {
  const kinds = opts.recentlyActive
    ? new Set(["new_class"])
    : new Set(["new_class", "recommended"]);
  const picked: NotificationItem[] = [];
  const seenKeys = new Set<string>();
  for (const item of items) {
    if (!kinds.has(item.kind)) continue;
    const key = contentKey(item);
    if (opts.alreadyNotified.has(key) || seenKeys.has(key)) continue;
    seenKeys.add(key);
    picked.push(item);
  }
  return picked;
}

export function digestContent(items: NotificationItem[]): { title: string; body: string } {
  if (items.length === 1) {
    return { title: items[0].title, body: items[0].body };
  }
  const names = items.slice(0, 3).map((i) => i.title).join(", ");
  const more = items.length > 3 ? ` +${items.length - 3} more` : "";
  return {
    title: `${items.length} new classes for you`,
    body: `${names}${more}. Tap to browse.`,
  };
}

/**
 * Queue ONE notification for new content, at the learner's routine hour.
 *
 * This replaces per-item alerts fired 31/61/91… minutes after whenever the app
 * happened to run, which is what made notifications arrive at unpredictable
 * times and several times a day. Now: at most one content notification per
 * calendar day, always in the same slot as the daily reminder.
 */
export async function scheduleAlertsFor(items: NotificationItem[],
                                        settings?: Settings,
                                        now: Date = new Date()) {
  const s = settings || (await getSettings());
  await cancelLegacyContentAlerts();
  if (!s.notificationsEnabled || !s.newContentAlerts) {
    await cancelByIdentifier(CONTENT_DIGEST_TAG);
    return;
  }

  // One per calendar day: later app opens must not re-queue or re-time it.
  const today = localDayKey(now);
  if ((await getContentAlertDay()) === today) return;

  const [alreadyNotified, lastOpenAt] = await Promise.all([
    getNotifiedCourses(),
    getLastOpenAt(),
  ]);
  const picked = selectAlertableItems(items, {
    alreadyNotified: new Set(alreadyNotified),
    recentlyActive: isRecentlyActive(lastOpenAt, now),
  });
  if (picked.length === 0) return;

  await ensureChannel();
  await cancelByIdentifier(CONTENT_DIGEST_TAG);

  // Sit just after the daily reminder so the two never collide.
  const at = nextOccurrence(s.dailyReminderHour | 0, 5, now);
  const { title, body } = digestContent(picked);
  await Notifications.scheduleNotificationAsync({
    identifier: CONTENT_DIGEST_TAG,
    content: {
      title,
      body,
      data: {
        kind: "new_content_digest",
        count: picked.length,
        deepLink: picked.length === 1 ? picked[0].deep_link : "aiclassroom://browse",
      },
    },
    // expo-notifications 0.28 takes a plain { date } object here; the typed
    // SchedulableTriggerInputTypes discriminator only exists in later SDKs.
    trigger: { date: at } as Notifications.DateTriggerInput,
  });

  await Promise.all([
    rememberNotifiedCourses(picked.map(contentKey)),
    setContentAlertDay(today),
  ]);
}

export async function cancelAll() {
  await Notifications.cancelAllScheduledNotificationsAsync();
}

export async function listScheduled() {
  return Notifications.getAllScheduledNotificationsAsync();
}

export { DEFAULT_SETTINGS };
