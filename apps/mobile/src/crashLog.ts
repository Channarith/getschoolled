/**
 * Durable crash log — survives the app crashing and relaunching.
 *
 * The native crash (iOS .ips / Android tombstone) is only accessible to Apple
 * / Google / us-via-a-cable, and shipping without a hosted crash reporter
 * means a user hitting a JS fatal has no way to tell us WHY. This module
 * writes a last-crash summary to `${documentDirectory}/salareen-last-crash.txt`
 * from the global error handler (set up by `clientLog.installClientLog()`),
 * and reads it back on the NEXT launch so the Bug Reporter can show the user
 * exactly what crashed last time — and ship it to the backend with the next
 * bug report.
 *
 * No network, no 3rd party. If `expo-file-system` is unavailable the module
 * degrades to in-memory only (so hot-reload / Expo Go / tests still work).
 */

import { Platform } from "react-native";

const CRASH_FILE = "salareen-last-crash.txt";
const MAX_PERSISTED_BYTES = 32 * 1024; // 32 KB — enough for a long stack

type FS = {
  documentDirectory?: string | null;
  readAsStringAsync(uri: string): Promise<string>;
  writeAsStringAsync(uri: string, contents: string): Promise<void>;
  deleteAsync(uri: string, opts?: { idempotent?: boolean }): Promise<void>;
  getInfoAsync(uri: string): Promise<{ exists: boolean }>;
};

// Dynamic require so this module can be imported in environments without
// expo-file-system (jest, SSR of unrelated code, pre-prebuild type checks).
function tryLoadFs(): FS | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require("expo-file-system") as FS;
    if (!mod || typeof mod.writeAsStringAsync !== "function") return null;
    return mod;
  } catch {
    return null;
  }
}

const fs = tryLoadFs();

function crashFileUri(): string | null {
  if (!fs?.documentDirectory) return null;
  // documentDirectory already ends with "/"
  return `${fs.documentDirectory}${CRASH_FILE}`;
}

export type CrashRecord = {
  timestamp: string;     // ISO
  platform: string;      // ios | android
  isFatal: boolean;
  message: string;
  stack: string;
  source: "errorUtils" | "unhandledRejection" | "errorBoundary";
};

function serialize(rec: CrashRecord): string {
  const banner = `=== Salareen crash record ===`;
  return [
    banner,
    `timestamp:  ${rec.timestamp}`,
    `platform:   ${rec.platform}`,
    `source:     ${rec.source}`,
    `isFatal:    ${rec.isFatal}`,
    `message:    ${rec.message}`,
    `--- stack ---`,
    rec.stack,
  ].join("\n").slice(0, MAX_PERSISTED_BYTES);
}

// In-memory copy of the record we wrote this session, so the Bug Reporter
// can show a crash that happened this session too (ErrorBoundary case).
let lastWrittenThisSession: CrashRecord | null = null;

/**
 * Write a crash record durably. Returns false on any failure (no throw).
 * SAFE to call from a global error handler on the brink of abort().
 */
export function writeCrashRecord(input: {
  error: unknown;
  isFatal: boolean;
  source: CrashRecord["source"];
}): boolean {
  try {
    const err = input.error as Error | undefined;
    const rec: CrashRecord = {
      timestamp: new Date().toISOString(),
      platform: Platform.OS,
      isFatal: Boolean(input.isFatal),
      source: input.source,
      message: (err && (err.message || String(err))) || "unknown",
      stack: (err && err.stack) || "",
    };
    lastWrittenThisSession = rec;
    const uri = crashFileUri();
    if (!uri || !fs) return false;
    // Fire and forget — do NOT await; we may be seconds from abort().
    void fs
      .writeAsStringAsync(uri, serialize(rec))
      .catch(() => { /* best-effort */ });
    return true;
  } catch {
    return false;
  }
}

/**
 * Read the previous session's crash record, if any.
 * The record is left in place so repeated reads work; call clearCrashRecord()
 * once the user has acknowledged it (e.g. tapped "Dismiss" in the Bug Reporter).
 */
export async function readPreviousCrash(): Promise<CrashRecord | null> {
  // Prefer the on-disk record (previous session). Fall back to session copy.
  const uri = crashFileUri();
  if (uri && fs) {
    try {
      const info = await fs.getInfoAsync(uri);
      if (info.exists) {
        const raw = await fs.readAsStringAsync(uri);
        return parse(raw);
      }
    } catch { /* ignore */ }
  }
  return lastWrittenThisSession;
}

export async function clearCrashRecord(): Promise<void> {
  lastWrittenThisSession = null;
  const uri = crashFileUri();
  if (!uri || !fs) return;
  try {
    await fs.deleteAsync(uri, { idempotent: true });
  } catch { /* ignore */ }
}

function parse(text: string): CrashRecord {
  const get = (key: string): string => {
    const m = text.match(new RegExp(`^${key}:\\s*(.*)$`, "m"));
    return m?.[1]?.trim() || "";
  };
  const stackIdx = text.indexOf("--- stack ---");
  const stack = stackIdx >= 0 ? text.slice(stackIdx + "--- stack ---".length).trim() : "";
  return {
    timestamp: get("timestamp") || new Date().toISOString(),
    platform: get("platform") || Platform.OS,
    source: (get("source") as CrashRecord["source"]) || "errorUtils",
    isFatal: get("isFatal") === "true",
    message: get("message") || "unknown",
    stack,
  };
}
