/**
 * Signed-out demos, matching the web demo picker
 * (apps/web/app/lib/salesDemo.ts DEMO_ONLY_FEATURE_IDS).
 * The app opens the lab and the lesson themselves, with embed=mobile, so a
 * phone is not stuck inside the website's headings and a second iframe.
 */

import { englishSpokenCode } from "./i18n/englishVariety";

export type PublicDemo = {
  id: string;
  path: string;
  emoji: string;
  title: string;
  subtitle: string;
  description: string;
};

export const PUBLIC_DEMOS: PublicDemo[] = [
  {
    id: "drivers-ed",
    path: "/studio?access=sample&course=drivers-ed&embed=mobile",
    emoji: "🤖",
    title: "Serenity · Solo AI",
    subtitle: "Driver's Ed · 10-min demo",
    description: "Serenity, your holographic AI teacher, walks you through the free 10-minute driver's ed demo with xAI voice.",
  },
  {
    id: "on-the-go",
    path: "/studio?access=sample&course=drivers-ed&presentation=audio&embed=mobile",
    emoji: "🎧",
    title: "Serenity · On-the-Go",
    subtitle: "Audio only · 10-min demo",
    description: "Serenity teaches the same driver's ed demo by ear (xAI when configured). The free trial stops at 10 minutes.",
  },
  {
    id: "arcade",
    path: "/children-lab?embed=mobile",
    emoji: "🎮",
    title: "Vision arcade",
    subtitle: "Machine vision for kids",
    description: "Children play webcam games: faces, hands, movement, and listening. The camera stays on this device.",
  },
];

export function publicDemoUrl(webAppUrl: string, path: string): string {
  const base = webAppUrl.replace(/\/$/, "");
  const route = path.startsWith("/") ? path : `/${path}`;
  return `${base}${route}`;
}

export function spokenDemoCode(locale: string): string {
  const raw = (locale || "en").trim().toLowerCase().replace(/_/g, "-");
  if (
    raw === "yue" || raw.startsWith("yue-") ||
    raw === "zh-hk" || raw.startsWith("zh-hk") ||
    raw === "zh-mo" || raw.startsWith("zh-mo") ||
    raw === "cantonese"
  ) return "yue";
  if (raw === "km" || raw.startsWith("km-")) return "km";
  const english = englishSpokenCode(raw);
  if (english) return english;
  return raw.split("-")[0] || "en";
}

/** Studio and the vision lab accept a lang query. The lab page itself still
 * asks for English unless the WebView rewrites its TTS and speech calls.
 */
export function demoPathWithLocale(path: string, locale: string): string {
  const code = spokenDemoCode(locale);
  if (!path.includes("/children-lab") && !path.includes("/studio")) return path;
  if (/[?&]lang=/.test(path)) return path;
  const join = path.includes("?") ? "&" : "?";
  return `${path}${join}lang=${encodeURIComponent(code)}`;
}

const SPEECH_BCP: Record<string, string> = {
  en: "en-US", es: "es-ES", fr: "fr-FR", de: "de-DE", it: "it-IT", pt: "pt-BR",
  nl: "nl-NL", pl: "pl-PL", ru: "ru-RU", uk: "uk-UA", tr: "tr-TR", ar: "ar-SA",
  he: "he-IL", hi: "hi-IN", bn: "bn-IN", ur: "ur-PK", fa: "fa-IR", zh: "zh-CN",
  yue: "zh-HK",
  ja: "ja-JP", ko: "ko-KR", vi: "vi-VN", th: "th-TH", id: "id-ID", sw: "sw-KE",
  el: "el-GR", cs: "cs-CZ", km: "km-KH",
};

/** Runs before the vision lab script so its hardcoded English TTS and mic follow the app locale. */
export function childrenLabLocaleScript(locale: string): string {
  const code = spokenDemoCode(locale);
  const bcp = SPEECH_BCP[code] || code;
  return `(function(){
    var lang=${JSON.stringify(code)};
    var bcp=${JSON.stringify(bcp)};
    try { document.documentElement.lang = lang; } catch (e) {}
    var orig=window.fetch;
    if (typeof orig==="function") {
      window.fetch=function(input, init){
        if (typeof input==="string" && input.indexOf("/api/tts?")>=0) {
          input=input.replace(/([?&]language=)[^&]*/,"$1"+encodeURIComponent(lang));
        }
        return orig.call(this, input, init);
      };
    }
    ["SpeechRecognition","webkitSpeechRecognition"].forEach(function(name){
      var Ctor=window[name];
      if (typeof Ctor!=="function") return;
      function Wrapped(){
        var rec=new Ctor();
        try { rec.lang=bcp; } catch (e) {}
        try {
          Object.defineProperty(rec,"lang",{configurable:true,get:function(){return bcp;},set:function(){}});
        } catch (e) {}
        return rec;
      }
      Wrapped.prototype=Ctor.prototype;
      window[name]=Wrapped;
    });
  })();`;
}

/** Keeps the air/screen switch on the game. The lab top bar clips it on a phone. */
export function childrenLabTouchScript(): string {
  return `(function(){
    if (window.__SALAREEN_TOUCH_TOGGLE__) return;
    window.__SALAREEN_TOUCH_TOGGLE__ = true;
    var css = "#touch-mode{position:fixed !important;left:12px !important;"
      + "bottom:calc(72px + env(safe-area-inset-bottom)) !important;z-index:30 !important;"
      + "display:inline-flex !important;align-items:center;justify-content:center;"
      + "min-height:44px !important;padding:.45rem .8rem !important;white-space:nowrap;"
      + "background:#111827 !important;border:2px solid #5eead4 !important;color:#fff !important}"
      + "body.phone-play .vision-readout,#vision-readout{display:grid !important;left:8px !important;"
      + "right:8px !important;top:8px !important;bottom:auto !important;min-width:0 !important;z-index:8 !important;"
      + "grid-template-columns:1fr 1fr !important;pointer-events:none !important;right:100px !important}"
      + "#home{position:relative !important;z-index:40 !important;min-width:44px !important;min-height:44px !important}"
      + "#countdown:not(.hidden){display:grid !important;position:absolute !important;top:8px !important;"
      + "right:8px !important;width:84px !important;height:84px !important;z-index:20 !important;"
      + "font-size:1.7rem !important}";
    function show() {
      var btn = document.getElementById("touch-mode");
      if (!btn) return;
      btn.hidden = false;
      btn.removeAttribute("hidden");
      if (document.getElementById("salareen-touch-style")) return;
      var style = document.createElement("style");
      style.id = "salareen-touch-style";
      style.textContent = css;
      (document.head || document.documentElement).appendChild(style);
    }
    if (document.documentElement) {
      new MutationObserver(show).observe(document.documentElement, {childList:true, subtree:true, attributes:true, attributeFilter:["hidden","class"]});
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", show);
    else show();
  })(); true;`;
}
