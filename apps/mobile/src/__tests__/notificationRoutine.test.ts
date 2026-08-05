/**
 * Notifications must arrive on a routine, once a day.
 *
 * Reported symptoms: alerts did not come at the same time each day, and several
 * arrived per day. Both came from scheduleAlertsFor queueing one notification
 * per item on a *time-interval* trigger (31/61/91… minutes after whenever the
 * app last ran scheduling), re-running on every tab change, and deduping only
 * against the OS pending list — so once an alert fired it could be queued again.
 *
 * These pin the replacement contract:
 *   - one content notification per calendar day, in the learner's chosen slot;
 *   - never re-alert a course we already alerted about;
 *   - a learner who was here recently only hears about genuinely NEW classes.
 */

import type { NotificationItem } from "../api";

const mockScheduleNotificationAsync = jest.fn().mockResolvedValue("id");
const mockCancelScheduledNotificationAsync = jest.fn().mockResolvedValue(undefined);

jest.mock("expo-notifications", () => ({
  scheduleNotificationAsync: (...a: unknown[]) => mockScheduleNotificationAsync(...a),
  cancelScheduledNotificationAsync: (...a: unknown[]) =>
    mockCancelScheduledNotificationAsync(...a),
  cancelAllScheduledNotificationsAsync: jest.fn().mockResolvedValue(undefined),
  getAllScheduledNotificationsAsync: jest.fn().mockResolvedValue([]),
  setNotificationHandler: jest.fn(),
  setNotificationChannelAsync: jest.fn().mockResolvedValue(undefined),
  getPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
  requestPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
  AndroidImportance: { DEFAULT: 3, HIGH: 4 },
}));

jest.mock("react-native", () => ({ Platform: { OS: "ios" } }));

// In-memory stand-in for the AsyncStorage-backed notification state.
const store: {
  notified: string[];
  lastOpenAt: string;
  alertDay: string;
} = { notified: [], lastOpenAt: "", alertDay: "" };

jest.mock("../storage", () => ({
  DEFAULT_SETTINGS: {},
  getSettings: jest.fn().mockResolvedValue({
    notificationsEnabled: true,
    dailyReminder: true,
    dailyReminderHour: 8,
    newContentAlerts: true,
    completionAlerts: true,
  }),
  getNotifiedCourses: jest.fn(async () => store.notified),
  rememberNotifiedCourses: jest.fn(async (keys: string[]) => {
    store.notified = Array.from(new Set([...store.notified, ...keys]));
  }),
  getLastOpenAt: jest.fn(async () => store.lastOpenAt),
  getContentAlertDay: jest.fn(async () => store.alertDay),
  setContentAlertDay: jest.fn(async (day: string) => { store.alertDay = day; }),
}));

import {
  digestContent,
  isRecentlyActive,
  nextOccurrence,
  scheduleAlertsFor,
  selectAlertableItems,
} from "../notifications";

function item(over: Partial<NotificationItem> & { id: string }): NotificationItem {
  return {
    kind: "new_class",
    title: `Class ${over.id}`,
    body: "body",
    course_id: over.id,
    deep_link: null,
    created_at: "2026-08-05T00:00:00Z",
    icon: "bell",
    ...over,
  } as NotificationItem;
}

const settings = {
  notificationsEnabled: true,
  dailyReminder: true,
  dailyReminderHour: 8,
  newContentAlerts: true,
  completionAlerts: true,
} as never;

describe("routine time", () => {
  it("schedules for the learner's hour today when it has not passed", () => {
    const at = nextOccurrence(8, 5, new Date("2026-08-05T06:00:00"));
    expect(at.getHours()).toBe(8);
    expect(at.getMinutes()).toBe(5);
    expect(at.getDate()).toBe(5);
  });

  it("rolls to tomorrow once the hour has passed, never a random offset", () => {
    const at = nextOccurrence(8, 5, new Date("2026-08-05T09:30:00"));
    expect(at.getHours()).toBe(8);
    expect(at.getDate()).toBe(6);
  });
});

describe("recently-active gating", () => {
  const now = new Date("2026-08-05T10:00:00Z");

  it("treats a visit within the window as recent", () => {
    expect(isRecentlyActive("2026-08-04T22:00:00Z", now)).toBe(true);
  });

  it("treats a long absence, or no record at all, as not recent", () => {
    expect(isRecentlyActive("2026-08-01T10:00:00Z", now)).toBe(false);
    expect(isRecentlyActive("", now)).toBe(false);
  });

  it("tells a returning learner about new classes only", () => {
    const picked = selectAlertableItems(
      [item({ id: "c1" }), item({ id: "c2", kind: "recommended" })],
      { alreadyNotified: new Set(), recentlyActive: true },
    );
    expect(picked.map((p) => p.course_id)).toEqual(["c1"]);
  });

  it("also nudges a lapsed learner with recommendations", () => {
    const picked = selectAlertableItems(
      [item({ id: "c1" }), item({ id: "c2", kind: "recommended" })],
      { alreadyNotified: new Set(), recentlyActive: false },
    );
    expect(picked.map((p) => p.course_id)).toEqual(["c1", "c2"]);
  });

  it("never alerts twice about the same course, even with a fresh item id", () => {
    const picked = selectAlertableItems(
      // Same course, new server id — this is what re-alerted people daily.
      [item({ id: "new-2026-08-05", course_id: "course-1" })],
      { alreadyNotified: new Set(["course-1"]), recentlyActive: false },
    );
    expect(picked).toEqual([]);
  });

  it("ignores inbox-only kinds", () => {
    const picked = selectAlertableItems(
      [item({ id: "s", kind: "streak" }), item({ id: "r", kind: "reminder" })],
      { alreadyNotified: new Set(), recentlyActive: false },
    );
    expect(picked).toEqual([]);
  });
});

describe("digest copy", () => {
  it("uses the class itself when there is only one", () => {
    expect(digestContent([item({ id: "c1", title: "Algebra" })])).toEqual({
      title: "Algebra",
      body: "body",
    });
  });

  it("summarises several into one message", () => {
    const d = digestContent([
      item({ id: "a", title: "A" }), item({ id: "b", title: "B" }),
      item({ id: "c", title: "C" }), item({ id: "d", title: "D" }),
    ]);
    expect(d.title).toBe("4 new classes for you");
    expect(d.body).toContain("+1 more");
  });
});

describe("scheduleAlertsFor", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    store.notified = [];
    store.lastOpenAt = "";
    store.alertDay = "";
  });

  it("queues exactly one notification, at the routine hour", async () => {
    const now = new Date("2026-08-05T06:00:00");
    await scheduleAlertsFor([item({ id: "c1" }), item({ id: "c2" })], settings, now);

    expect(mockScheduleNotificationAsync).toHaveBeenCalledTimes(1);
    const req = mockScheduleNotificationAsync.mock.calls[0][0];
    expect(req.identifier).toBe("new-content-digest");
    // A date in the learner's slot — not a "31 minutes from now" offset.
    expect(req.trigger.seconds).toBeUndefined();
    expect(req.trigger.date).toBeInstanceOf(Date);
    expect(req.trigger.date.getHours()).toBe(8);
    expect(req.trigger.date.getMinutes()).toBe(5);
  });

  it("does not queue a second time the same day, however often the app opens", async () => {
    const now = new Date("2026-08-05T06:00:00");
    await scheduleAlertsFor([item({ id: "c1" })], settings, now);
    expect(mockScheduleNotificationAsync).toHaveBeenCalledTimes(1);

    // Tab switches / refreshes later that day used to re-queue alerts.
    await scheduleAlertsFor([item({ id: "c2" })], settings, new Date("2026-08-05T07:00:00"));
    await scheduleAlertsFor([item({ id: "c3" })], settings, new Date("2026-08-05T18:00:00"));
    expect(mockScheduleNotificationAsync).toHaveBeenCalledTimes(1);
  });

  it("stays silent when everything has already been alerted", async () => {
    store.notified = ["c1"];
    await scheduleAlertsFor([item({ id: "c1" })], settings, new Date("2026-08-05T06:00:00"));
    expect(mockScheduleNotificationAsync).not.toHaveBeenCalled();
  });

  it("remembers what it alerted so tomorrow does not repeat it", async () => {
    await scheduleAlertsFor([item({ id: "c1" })], settings, new Date("2026-08-05T06:00:00"));
    expect(store.notified).toContain("c1");

    store.alertDay = "";  // next day
    await scheduleAlertsFor([item({ id: "c1" })], settings, new Date("2026-08-06T06:00:00"));
    expect(mockScheduleNotificationAsync).toHaveBeenCalledTimes(1);
  });

  it("drains alerts left over from the old per-item scheme on upgrade", async () => {
    const notifications = jest.requireMock("expo-notifications");
    notifications.getAllScheduledNotificationsAsync.mockResolvedValueOnce([
      { identifier: "new-content:item-a" },
      { identifier: "new-content:item-b" },
      { identifier: "daily-reminder" },
    ]);

    await scheduleAlertsFor([item({ id: "c1" })], settings, new Date("2026-08-05T06:00:00"));

    expect(mockCancelScheduledNotificationAsync).toHaveBeenCalledWith("new-content:item-a");
    expect(mockCancelScheduledNotificationAsync).toHaveBeenCalledWith("new-content:item-b");
    // The routine daily reminder must survive the cleanup.
    expect(mockCancelScheduledNotificationAsync).not.toHaveBeenCalledWith("daily-reminder");
  });

  it("clears any pending digest when content alerts are switched off", async () => {
    await scheduleAlertsFor(
      [item({ id: "c1" })],
      { ...(settings as object), newContentAlerts: false } as never,
      new Date("2026-08-05T06:00:00"),
    );
    expect(mockScheduleNotificationAsync).not.toHaveBeenCalled();
    expect(mockCancelScheduledNotificationAsync).toHaveBeenCalledWith("new-content-digest");
  });
});
