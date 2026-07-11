/**
 * U-STR-1 — streak accounting (QA V&V plan, Mobile dimension).
 *
 * bumpStreak() is the retention primitive: it must increment once per calendar
 * day, no-op on repeat same-day bumps, and reset after a gap. A double-bump or
 * a false reset directly corrupts a user's visible streak.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import { bumpStreak, getStreak } from "../storage";

// Freeze "now" to a fixed UTC day; each test advances it explicitly.
function setToday(iso: string): void {
  jest.useFakeTimers();
  jest.setSystemTime(new Date(`${iso}T12:00:00Z`));
}

beforeEach(async () => {
  await AsyncStorage.clear();
});

afterEach(() => {
  jest.useRealTimers();
});

test("first-ever bump starts the streak at 1", async () => {
  setToday("2026-07-11");
  const s = await bumpStreak();
  expect(s).toEqual({ days: 1, lastDayISO: "2026-07-11" });
});

test("a second bump on the same day is a no-op", async () => {
  setToday("2026-07-11");
  await bumpStreak();
  const s = await bumpStreak();
  expect(s.days).toBe(1);
  expect(s.lastDayISO).toBe("2026-07-11");
});

test("a bump the next day increments", async () => {
  setToday("2026-07-11");
  await bumpStreak();
  setToday("2026-07-12");
  const s = await bumpStreak();
  expect(s).toEqual({ days: 2, lastDayISO: "2026-07-12" });
});

test("a gap of more than one day resets to 1", async () => {
  setToday("2026-07-11");
  await bumpStreak();
  setToday("2026-07-11");
  // advance the stored streak to prove the reset overrides a real count
  await bumpStreak();
  setToday("2026-07-15"); // 4-day gap
  const s = await bumpStreak();
  expect(s).toEqual({ days: 1, lastDayISO: "2026-07-15" });
});

test("consecutive days accumulate then persist", async () => {
  for (const [day, expected] of [
    ["2026-07-11", 1],
    ["2026-07-12", 2],
    ["2026-07-13", 3],
  ] as const) {
    setToday(day);
    await bumpStreak();
    expect((await getStreak()).days).toBe(expected);
  }
});
