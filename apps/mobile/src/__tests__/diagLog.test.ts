import AsyncStorage from "@react-native-async-storage/async-storage";

import {
  DIAG_MAX_ENTRIES, addWebEntries, armDiagForBugReport, buildBugDiagText, buildDiagReport, clearDiag,
  consumeDiagArmed, deviceSummary, diagEntryCount, diagLog, initDiag, isDebugMode, peekDiagEntries,
  redact, resetDiagForTests, setDebugMode, setWebReport,
} from "../diag/diagLog";
import { CAMERA_CHECK_DEMO, CAMERA_CHECK_PATH, diagBridgeScript, isCameraCheckPath, routeDiagMessage } from "../diag/webDiag";
import { createTapCounter } from "../secretTaps";

beforeEach(async () => {
  resetDiagForTests();
  await AsyncStorage.clear();
});

describe("redaction", () => {
  it("removes tokens, bearer headers, emails and secret query values", () => {
    const text = redact(
      "Bearer abc.def-123 user a.b@example.com https://x.test/p?token=SECRET123&k=1 eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk",
    );
    expect(text).not.toMatch(/SECRET123|example\.com|eyJhbGci|abc\.def-123/);
    expect(text).toContain("[email]");
    expect(text).toContain("token=[redacted]");
    expect(text).toContain("[jwt]");
  });
});

describe("ring buffer", () => {
  it("stays bounded and keeps the newest entries", () => {
    for (let i = 0; i < 5000; i += 1) diagLog("test", `entry ${i}`);
    expect(diagEntryCount()).toBeLessThanOrEqual(DIAG_MAX_ENTRIES + 100);
    expect(diagEntryCount()).toBeGreaterThanOrEqual(DIAG_MAX_ENTRIES);
    const entries = peekDiagEntries();
    expect(entries[entries.length - 1].m).toBe("entry 4999");
  });

  it("bounds what one page message can add and marks it as coming from the page", () => {
    const flood = Array.from({ length: 500 }, (_, i) => ({ t: i, k: "console.warn", m: `w ${i}` }));
    expect(addWebEntries(flood)).toBe(200);
    const first = peekDiagEntries()[0];
    expect(first.src).toBe("web");
    expect(first.k).toBe("web.console.warn");
    expect(addWebEntries("not an array")).toBe(0);
    expect(addWebEntries([null, 5, "x"])).toBe(0);
  });

  it("clears everything including the page report", () => {
    diagLog("a", "b");
    setWebReport("report");
    clearDiag();
    expect(diagEntryCount()).toBe(0);
    expect(buildDiagReport()).not.toContain("== Last camera check report");
  });
});

describe("report", () => {
  it("has the device, problems and event sections, redacted", () => {
    diagLog("perm", "CAMERA granted");
    diagLog("error", "WebView render process gone didCrash=false for user me@example.com");
    addWebEntries([{ t: Date.now(), k: "mp", m: "face model GPU 115 ms" }]);
    setWebReport("== Device\nplatform: Android 14");
    const text = buildDiagReport();
    expect(text).toContain("== App and device");
    expect(text).toContain("== Last camera check report (from the page)");
    expect(text).toContain("== Problems seen");
    expect(text).toContain("== Event log");
    expect(text).toContain("face model GPU 115 ms");
    expect(text).not.toContain("me@example.com");
  });

  it("truncates the short bug-report form and names the app version", () => {
    for (let i = 0; i < 400; i += 1) diagLog("noise", "x".repeat(300));
    const text = buildBugDiagText();
    expect(text.length).toBeLessThanOrEqual(9100);
    expect(deviceSummary().app).toMatch(/^Salareen /);
  });
});

describe("debug mode and persistence", () => {
  it("persists the debug switch", async () => {
    expect(isDebugMode()).toBe(false);
    await setDebugMode(true);
    expect(isDebugMode()).toBe(true);
    resetDiagForTests();
    await initDiag();
    expect(isDebugMode()).toBe(true);
    await setDebugMode(false);
    resetDiagForTests();
    await initDiag();
    expect(isDebugMode()).toBe(false);
  });

  it("restores the previous session after a restart", async () => {
    jest.useFakeTimers();
    diagLog("session", "first run entry");
    jest.advanceTimersByTime(3000);
    jest.useRealTimers();
    await Promise.resolve();
    resetDiagForTests();
    await initDiag();
    expect(buildDiagReport()).toContain("== Previous session");
    expect(buildDiagReport()).toContain("first run entry");
  });

  it("arms the next bug report once", () => {
    expect(consumeDiagArmed()).toBe(false);
    armDiagForBugReport();
    expect(consumeDiagArmed()).toBe(true);
    expect(consumeDiagArmed()).toBe(false);
  });
});

describe("page messages", () => {
  it("routes diagnostic batches, reports and share requests, and ignores everything else", () => {
    expect(routeDiagMessage(JSON.stringify({ type: "salareen-diag", entries: [{ t: 1, k: "gum", m: "ok" }] })).handled).toBe(true);
    expect(peekDiagEntries().some((e) => e.k === "web.gum")).toBe(true);
    const report = routeDiagMessage(JSON.stringify({ type: "salareen-diag-report", text: "REPORT TEXT", level: "warn" }));
    expect(report.handled).toBe(true);
    expect(buildDiagReport()).toContain("REPORT TEXT");
    const share = routeDiagMessage(JSON.stringify({ type: "salareen-diag-share", text: "SHARE ME" }));
    expect(share).toEqual({ handled: true, shareText: "SHARE ME" });
    expect(routeDiagMessage(JSON.stringify({ type: "salareen-telemetry" })).handled).toBe(false);
    expect(routeDiagMessage("not json").handled).toBe(false);
  });

  it("injects a forwarder that stays quiet once the page's own logger is active", () => {
    const script = diagBridgeScript();
    expect(script).toContain("salareen-diag");
    expect(script).toContain("__gsDiagBooted");
    expect(() => new Function(script)).not.toThrow();
  });

  it("opens the hosted camera check at its public path", () => {
    expect(CAMERA_CHECK_PATH).toBe("/diag/vision");
    expect(CAMERA_CHECK_DEMO.path).toBe(CAMERA_CHECK_PATH);
    expect(isCameraCheckPath("/diag/vision?seconds=8")).toBe(true);
    expect(isCameraCheckPath("/children-lab?embed=mobile")).toBe(false);
  });
});

describe("hidden debug switch", () => {
  it("needs seven quick taps", () => {
    let now = 0;
    const counter = createTapCounter({ count: 7, windowMs: 3000, now: () => now });
    for (let i = 0; i < 6; i += 1) { now += 400; expect(counter.tap()).toBe(false); }
    now += 400;
    expect(counter.tap()).toBe(true);
  });

  it("starts over when the taps are too slow", () => {
    let now = 0;
    const counter = createTapCounter({ count: 7, windowMs: 3000, now: () => now });
    for (let i = 0; i < 6; i += 1) { now += 400; counter.tap(); }
    now += 5000;
    expect(counter.tap()).toBe(false);
  });
});
