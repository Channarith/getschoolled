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
    path: "/studio?access=sample&course=drivers-ed&demo=1&embed=mobile",
    emoji: "🤖",
    title: "Serenity · Solo AI",
    subtitle: "Driver's Ed · 4-min demo",
    description: "Serenity, your holographic AI teacher, walks you through the free 4-minute driver's ed demo with Salane Voice.",
  },
  {
    id: "arcade",
    path: "/children-lab?embed=mobile",
    emoji: "🎮",
    title: "Vision Play",
    subtitle: "Machine vision for kids",
    description: "Machine vision: faces, hands, movement, and listening. The camera stays on this device.",
  },
];

/** Not listed in the picker: reached by four quick taps on the Salareen logo (see secretTaps.ts). */
export const HIDDEN_ON_THE_GO_DEMO: PublicDemo = {
  id: "on-the-go",
  path: "/demo/on-the-go",
  emoji: "🎧",
  title: "Serenity · On-the-Go",
  subtitle: "Audio only · 4-min demo",
  description: "Serenity teaches the same driver's ed demo by ear with Salane Voice. The free trial stops at 4 minutes.",
};

export function publicDemoUrl(webAppUrl: string, path: string): string {
  const base = webAppUrl.replace(/\/$/, "");
  const route = path.startsWith("/") ? path : `/${path}`;
  return `${base}${route}`;
}

/**
 * True when an HTTP error from the WebView belongs to the page itself. A missing image,
 * model or font (a 404 for a file the page does not need) must not replace the whole lab
 * with the error screen; only the page failing to load should.
 */
export function isPageHttpError(eventUrl: string | undefined, pageUrl: string): boolean {
  if (!eventUrl) return true;
  const norm = (value: string) => {
    try {
      const u = new URL(value);
      return `${u.origin}${u.pathname.replace(/\/+$/, "")}`;
    } catch {
      return value.split(/[?#]/)[0].replace(/\/+$/, "");
    }
  };
  return norm(eventUrl) === norm(pageUrl);
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
/**
 * Copies the voice the learner picked in the app into the hosted demo page's own storage before the page runs.
 * The demos are web pages inside a WebView with a separate localStorage, so without this they would ignore the app's choice.
 * Keys match the site: aoep_demo_voice (custom voice id or "default"), aoep_drive_voice (catalog voice id), aoep_voice_explicit ("1" an edge
 * voice picked on purpose, "0" the Salane Voice picked on purpose, absent when never chosen), aoep_live_voice_engine. A learner who never
 * chose gets the published default (Sage) in the page, exactly as on the site.
 */
export function demoVoiceHandoffScript(p: { cloneVoice?: string; voiceId?: string; agent?: string; explicit?: "1" | "0" | "" }): string {
  const put = (key: string, value: string) => `try{localStorage.setItem(${JSON.stringify(key)},${JSON.stringify(value)});}catch(e){}`;
  const drop = (key: string) => `try{localStorage.removeItem(${JSON.stringify(key)});}catch(e){}`;
  return [
    put("aoep_demo_voice", p.cloneVoice || "default"),
    p.voiceId ? put("aoep_drive_voice", p.voiceId) : drop("aoep_drive_voice"),
    p.explicit ? put("aoep_voice_explicit", p.explicit) : drop("aoep_voice_explicit"),
    put("aoep_live_voice_engine", p.agent === "xai" ? "xai" : "salane"),
    "true;",
  ].join("\n");
}

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

/** Tells the page the app went to the background or came back, so a lesson can pause and resume. */
export function appStateScript(state: string): string {
  const value = state === "active" || state === "background" || state === "inactive" ? state : "active";
  return `(function(){try{window.dispatchEvent(new CustomEvent("salareen-app-state",{detail:{state:"${value}"}}));}catch(e){}
    var frames=document.querySelectorAll("iframe");
    for(var i=0;i<frames.length;i++){try{frames[i].contentWindow.postMessage({type:"salareen-app-state",state:"${value}"},"*");}catch(e){}}
  })(); true;`;
}
