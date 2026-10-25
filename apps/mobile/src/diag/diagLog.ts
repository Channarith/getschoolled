/** Triage log for camera games and the in-app WebView (Android first, iOS the same).
 *
 * One ring buffer (about 2,000 entries) holds what the app saw natively (permission results, WebView load errors,
 * render-process crashes) and what the hosted camera pages report (see static/vision_diag.js in the children lab).
 * It is mirrored to AsyncStorage so a crash or a restart keeps the last session. Nothing leaves the phone
 * automatically: the person taps Share or attaches it to a bug report, and sees the text first.
 * No images, audio or video frames are ever recorded; only numbers, error names and timings.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Dimensions, I18nManager, PixelRatio, Platform, Share } from "react-native";
import Constants from "expo-constants";

import { APP_VERSION } from "../version";

export type DiagSource = "app" | "web";
export type DiagEntry = { t: number; k: string; m: string; src: DiagSource; d?: unknown };

export const DIAG_MAX_ENTRIES = 2000;
const STORE_KEY = "@salareen/diag-buffer-v1";
const PREV_KEY = "@salareen/diag-buffer-prev-v1";
const DEBUG_KEY = "@salareen/diag-debug-v1";
const PERSIST_DEBOUNCE_MS = 2500;

let entries: DiagEntry[] = [];
let previous: DiagEntry[] = [];
let lastWebReport = "";
let debugMode = false;
let started = false;
let armedForBugReport = false;
let persistTimer: ReturnType<typeof setTimeout> | null = null;

export function redact(text: unknown): string {
  return String(text ?? "")
    .replace(/eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}/g, "[jwt]")
    .replace(/Bearer\s+[\w.~+/=-]+/gi, "Bearer [redacted]")
    .replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, "[email]")
    .replace(/([?&#](?:token|access_token|id_token|key|api_key|secret|password|auth|code)=)[^&\s#]+/gi, "$1[redacted]");
}

function schedulePersist(): void {
  if (persistTimer) return;
  persistTimer = setTimeout(() => {
    persistTimer = null;
    void AsyncStorage.setItem(STORE_KEY, JSON.stringify(entries.slice(-DIAG_MAX_ENTRIES))).catch(() => { /* storage full: the memory copy still works */ });
  }, PERSIST_DEBOUNCE_MS);
}

function push(entry: DiagEntry): void {
  entries.push(entry);
  if (entries.length > DIAG_MAX_ENTRIES + 100) entries = entries.slice(-DIAG_MAX_ENTRIES);
  schedulePersist();
}

export function diagLog(kind: string, message: unknown, data?: unknown): void {
  const entry: DiagEntry = { t: Date.now(), k: kind, m: redact(message).slice(0, 400), src: "app" };
  if (data !== undefined) entry.d = data;
  push(entry);
}

/** Entries posted by the hosted page (type "salareen-diag"). Bounded per message so a chatty page cannot flood the app. */
export function addWebEntries(list: unknown): number {
  if (!Array.isArray(list)) return 0;
  let added = 0;
  for (const item of list.slice(0, 200)) {
    if (!item || typeof item !== "object") continue;
    const e = item as { t?: unknown; k?: unknown; m?: unknown; d?: unknown };
    push({ t: Number(e.t) || Date.now(), k: `web.${String(e.k ?? "log").slice(0, 24)}`, m: redact(e.m).slice(0, 400), src: "web", d: e.d });
    added += 1;
  }
  return added;
}

export function setWebReport(text: unknown): void {
  lastWebReport = redact(text).slice(0, 60000);
}

export function getWebReport(): string {
  return lastWebReport;
}

export function isDebugMode(): boolean {
  return debugMode;
}

export async function setDebugMode(on: boolean): Promise<void> {
  debugMode = on;
  diagLog("debug", `debug mode ${on ? "on (WebView remote debugging, verbose logs)" : "off"}`);
  try { await AsyncStorage.setItem(DEBUG_KEY, on ? "1" : "0"); } catch { /* not persisted this time */ }
}

/** "Send to Salareen" on the camera check: the next bug report starts with the camera diagnostics switched on. */
export function armDiagForBugReport(): void {
  armedForBugReport = true;
}

export function consumeDiagArmed(): boolean {
  const was = armedForBugReport;
  armedForBugReport = false;
  return was;
}

export function diagEntryCount(): number {
  return entries.length;
}

export function peekDiagEntries(): DiagEntry[] {
  return entries.slice();
}

export function clearDiag(): void {
  entries = [];
  previous = [];
  lastWebReport = "";
  schedulePersist();
}

type PlatformConstantsLike = Record<string, unknown> | undefined;

export function deviceSummary(): Record<string, unknown> {
  const pc = (Platform as unknown as { constants?: PlatformConstantsLike }).constants;
  const win = Dimensions.get("window");
  const scr = Dimensions.get("screen");
  const out: Record<string, unknown> = {
    app: `Salareen ${APP_VERSION}`,
    os: Platform.OS === "android" ? `Android ${String(pc?.Release ?? "?")} (API ${String(Platform.Version)})` : `${Platform.OS} ${String(Platform.Version)}`,
    model: Platform.OS === "android" ? `${String(pc?.Brand ?? "")} ${String(pc?.Model ?? "")}`.trim() : String(pc?.interfaceIdiom ?? ""),
    runtime: String(Constants.executionEnvironment ?? "unknown"),
    expo: String(Constants.expoVersion ?? ""),
    window: `${Math.round(win.width)}x${Math.round(win.height)}`,
    screen: `${Math.round(scr.width)}x${Math.round(scr.height)}`,
    pixelRatio: PixelRatio.get(),
    fontScale: PixelRatio.getFontScale(),
    rtl: I18nManager.isRTL,
    hermes: Boolean((globalThis as { HermesInternal?: unknown }).HermesInternal),
  };
  try {
    // expo-device is optional at runtime (not in every jest or web build).
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Device = require("expo-device") as { modelName?: string | null; brand?: string | null; totalMemory?: number | null; deviceYearClass?: number | null; isDevice?: boolean };
    if (Device.modelName) out.deviceModel = `${Device.brand ?? ""} ${Device.modelName}`.trim();
    if (Device.totalMemory) out.totalMemoryGB = Math.round((Device.totalMemory / 1073741824) * 10) / 10;
    if (Device.deviceYearClass) out.deviceYearClass = Device.deviceYearClass;
    if (typeof Device.isDevice === "boolean") out.realDevice = Device.isDevice;
  } catch { /* module not available */ }
  return out;
}

function line(e: DiagEntry): string {
  const time = new Date(e.t).toISOString().slice(11, 23);
  return `${time} ${e.src === "web" ? "W" : "A"} ${e.k.padEnd(18)} ${e.m}`;
}

/** The text a person shares or attaches. Everything in it is redacted and bounded. */
export function buildDiagReport(options: { tail?: number; maxChars?: number; includeWebReport?: boolean } = {}): string {
  const tail = options.tail ?? 400;
  const maxChars = options.maxChars ?? 120000;
  const lines: string[] = [];
  lines.push("Salareen camera and WebView diagnostics", `generated ${new Date().toISOString()}  debug=${debugMode}`, "");
  lines.push("== App and device");
  for (const [k, v] of Object.entries(deviceSummary())) lines.push(`${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`);
  lines.push("");
  if (options.includeWebReport !== false && lastWebReport) lines.push("== Last camera check report (from the page)", lastWebReport, "");
  const errors = entries.filter((e) => /error|crash|gone|terminat|denied|fail/i.test(`${e.k} ${e.m}`)).slice(-40);
  if (errors.length) lines.push(`== Problems seen (${errors.length} most recent)`, ...errors.map(line), "");
  const shown = entries.slice(-tail);
  lines.push(`== Event log (${entries.length} entries, last ${shown.length}; A = app, W = web page)`, ...shown.map(line));
  if (previous.length) {
    lines.push("", `== Previous session (${previous.length} entries, last 60)`, ...previous.slice(-60).map(line));
  }
  const text = redact(lines.join("\n"));
  return text.length > maxChars ? `${text.slice(0, maxChars)}\n[truncated]` : text;
}

/** Shorter text for the bug report, which has a size limit. */
export function buildBugDiagText(): string {
  return buildDiagReport({ tail: 120, maxChars: 9000 });
}

export async function shareDiagReport(text?: string): Promise<boolean> {
  const message = text ?? buildDiagReport();
  try {
    const result = await Share.share({ title: "Salareen camera diagnostics", message });
    return result.action !== Share.dismissedAction;
  } catch (error) {
    diagLog("error", `share failed: ${String((error as Error)?.message || error)}`);
    return false;
  }
}

/** Load the last session and the debug switch, and note this launch. Safe to call more than once. */
export async function initDiag(): Promise<void> {
  if (started) return;
  started = true;
  try {
    const stored = await AsyncStorage.getItem(STORE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as DiagEntry[];
      if (Array.isArray(parsed)) {
        previous = parsed.slice(-DIAG_MAX_ENTRIES);
        void AsyncStorage.setItem(PREV_KEY, JSON.stringify(previous.slice(-400))).catch(() => { /* ok */ });
      }
    }
    debugMode = (await AsyncStorage.getItem(DEBUG_KEY)) === "1";
  } catch { /* first run or storage unavailable */ }
  const d = deviceSummary();
  diagLog("launch", `${String(d.app)} · ${String(d.os)} · ${String(d.deviceModel || d.model)} · ${String(d.runtime)} · hermes ${String(d.hermes)}`);
}

/** For tests. */
export function resetDiagForTests(): void {
  entries = [];
  previous = [];
  lastWebReport = "";
  debugMode = false;
  armedForBugReport = false;
  started = false;
  if (persistTimer) { clearTimeout(persistTimer); persistTimer = null; }
}
