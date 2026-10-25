/** Glue between the hosted pages and the app's diagnostic log. */
import type { PublicDemo } from "../publicDemos";
import { addWebEntries, diagLog, setWebReport } from "./diagLog";

/** The hosted camera check (public, no sign-in; the page uploads nothing). */
export const CAMERA_CHECK_PATH = "/diag/vision";

export const CAMERA_CHECK_DEMO: PublicDemo = {
  id: "camera-check",
  path: CAMERA_CHECK_PATH,
  emoji: "📷",
  title: "Camera check",
  subtitle: "Test camera, face and hand tracking",
  description: "Runs the same camera and tracking steps the games use and prints what happened. Nothing is uploaded.",
};

export function isCameraCheckPath(path: string): boolean {
  return path.startsWith(CAMERA_CHECK_PATH);
}

/**
 * Runs before the page's own scripts. The camera pages load their own richer logger (vision_diag.js) which posts
 * "salareen-diag" batches. Every other page only gets this light forwarder for warnings, errors and crashes, so a
 * course or demo page that breaks still leaves a trace. It stays silent once the richer logger is active.
 */
export function diagBridgeScript(): string {
  return `(function(){
  if (window.__gsBridgeOn) return; window.__gsBridgeOn = true;
  var sent = 0, MAX = 200;
  function post(kind, msg){
    if (window.__gsDiagBooted || sent >= MAX) return;
    sent += 1;
    try { window.ReactNativeWebView.postMessage(JSON.stringify({type:'salareen-diag', session:'bridge', entries:[{t:Date.now(), k:kind, m:String(msg).slice(0,300)}]})); } catch (e) {}
  }
  ['warn','error'].forEach(function(level){
    var original = console[level];
    if (typeof original !== 'function') return;
    console[level] = function(){
      try { post('console.'+level, Array.prototype.map.call(arguments, function(a){ try { return typeof a === 'string' ? a : (a && a.message) ? a.name+': '+a.message : JSON.stringify(a); } catch (e) { return String(a); } }).join(' ')); } catch (e) {}
      return original.apply(console, arguments);
    };
  });
  window.addEventListener('error', function(ev){ post('error', 'window.onerror: '+(ev.message||'error')+' @ '+String(ev.filename||'').split('/').pop()+':'+(ev.lineno||0)); });
  window.addEventListener('unhandledrejection', function(ev){ post('error', 'unhandledrejection: '+(ev.reason && (ev.reason.name+': '+ev.reason.message) || String(ev.reason))); });
  true;
})();`;
}

export type WebMessageResult = { handled: boolean; shareText?: string };

/** Routes a WebView message. Returns handled=false for anything that is not a diagnostic message. */
export function routeDiagMessage(raw: string): WebMessageResult {
  let message: { type?: string; entries?: unknown; text?: unknown; level?: unknown };
  try { message = JSON.parse(raw); } catch { return { handled: false }; }
  switch (message?.type) {
    case "salareen-diag":
      addWebEntries(message.entries);
      return { handled: true };
    case "salareen-diag-report":
      setWebReport(message.text);
      diagLog("camera-check", `report received (${String(message.level || "unknown")})`);
      return { handled: true };
    case "salareen-diag-share":
      setWebReport(message.text);
      return { handled: true, shareText: typeof message.text === "string" ? message.text : undefined };
    default:
      return { handled: false };
  }
}
