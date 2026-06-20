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
import { DEFAULT_SETTINGS, getSettings, type Settings } from "./storage";

const CHANNEL_ID = "aiclassroom-default";
const DAILY_REMINDER_TAG = "daily-reminder";
const NEW_CONTENT_TAG_PREFIX = "new-content:";

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
    name: "Salarean",
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
      body: "Five minutes of audio, hands-free. Tap to open Drive Mode.",
      data: { kind: "daily", deepLink: "aiclassroom://drive" },
    },
    trigger: {
      hour: Math.max(0, Math.min(23, s.dailyReminderHour | 0)),
      minute: 0,
      repeats: true,
    } as Notifications.DailyTriggerInput,
  });
}

// Schedule local "new content" notifications for items the server returned
// in the inbox. We stagger them over the next few hours and dedupe so an
// item is only scheduled once even across app restarts.
export async function scheduleAlertsFor(items: NotificationItem[],
                                        settings?: Settings) {
  const s = settings || (await getSettings());
  if (!s.notificationsEnabled || !s.newContentAlerts) return;
  await ensureChannel();
  const existing = await Notifications.getAllScheduledNotificationsAsync();
  const seen = new Set(existing.map((n) => n.identifier));
  let i = 0;
  for (const item of items) {
    if (item.kind !== "new_class" && item.kind !== "recommended") continue;
    const identifier = `${NEW_CONTENT_TAG_PREFIX}${item.id}`;
    if (seen.has(identifier)) continue;
    const seconds = 60 * 30 * (i + 1) + 60; // 31 min, 61 min, ...
    i += 1;
    if (i > 5) break;
    await Notifications.scheduleNotificationAsync({
      identifier,
      content: {
        title: item.title,
        body: item.body,
        data: { id: item.id, deepLink: item.deep_link, kind: item.kind },
      },
      trigger: { seconds, repeats: false } as Notifications.TimeIntervalTriggerInput,
    });
  }
}

export async function cancelAll() {
  await Notifications.cancelAllScheduledNotificationsAsync();
}

export async function listScheduled() {
  return Notifications.getAllScheduledNotificationsAsync();
}

export { DEFAULT_SETTINGS };
