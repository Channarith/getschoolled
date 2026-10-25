// Course Studio: Sala-only voice-first player.
//
// A single, framework-free ES module served from /api/studio/voice/ and included
// at the end of studio_page.py. Owns:
//   • the ALWAYS-listening Web Speech recognizer (opt-in; one consent card),
//   • a local-only intent parser (transcripts never leave the browser; only the
//     matched intent is handed to the player),
//   • an on-screen "Sala listening" pill that doubles as the mute toggle,
//   • an optional semi-transparent "Type to Sala" pill (gated by the
//     accessibility.typetoask_mode feature flag passed in via ?typemode=1),
//   • double-click-to-fullscreen on the lesson stage,
//   • a safety net: long-press 750 ms OR three missed commands in 15 s
//     reveals the full classic chrome (removes body.aoep-voice-first).
//
// The parser body MUST stay in lockstep with
// apps/web/app/lib/courseVoiceIntent.ts and apps/mobile/src/courseVoiceIntent.ts
// A parity test imports courseVoiceIntentCatalog() and compares the three.

const CONSENT_KEY = "aoep_course_voice_consent_v1";
const MISS_WINDOW_MS = 15000;
const MISS_LIMIT = 3;
const LONG_PRESS_MS = 750;

// ---- Pure intent parser -----------------------------------------------------
// NOTE: port of apps/web/app/lib/courseVoiceIntent.ts. Keep in sync.

const WAKE_RE = /\b(hey\s+sala(?:reen)?|salareen|sala)\b[\s,.:!?-]*/gi;

const LANGUAGES = {
  english: "en", spanish: "es", french: "fr", german: "de", italian: "it",
  portuguese: "pt", dutch: "nl", polish: "pl", russian: "ru", ukrainian: "uk",
  turkish: "tr", arabic: "ar", hebrew: "he", hindi: "hi", bengali: "bn",
  urdu: "ur", persian: "fa", farsi: "fa", chinese: "zh", mandarin: "zh",
  cantonese: "yue", japanese: "ja", korean: "ko", vietnamese: "vi",
  thai: "th", indonesian: "id", swahili: "sw", greek: "el", czech: "cs",
  khmer: "km", cambodian: "km",
};

export function courseVoiceIntentCatalog() {
  return [
    "pause", "resume", "restart", "start", "next", "previous", "repeat",
    "captions_on", "captions_off", "captions_toggle",
    "fullscreen_on", "fullscreen_off",
    "set_language", "set_speed",
    "mute_mic",
    "show_controls", "hide_controls",
    "help", "ask",
  ];
}

export function languageCodeFromSpoken(name) {
  const n = String(name || "").toLowerCase().trim();
  if (!n) return null;
  if (LANGUAGES[n]) return LANGUAGES[n];
  if (/^[a-z]{2,3}$/.test(n) && Object.values(LANGUAGES).includes(n)) return n;
  return null;
}

function normalize(text) {
  return String(text || "").toLowerCase().replace(WAKE_RE, " ").replace(/\s+/g, " ").trim();
}

function looksLikeAsk(text) {
  const t = text.trim();
  if (!t) return false;
  if (t.endsWith("?")) return true;
  if (/^(ask|question)\b/.test(t)) return true;
  return /^(what|why|how|when|where|who|whose|which|can|could|would|will|do|does|did|is|are|should|explain|define|describe|tell me|help me)\b/.test(t);
}

export function parseCourseVoiceIntent(utterance) {
  const text = normalize(utterance);
  if (!text) return null;

  if (/^(stop\s+listening|mute\s+(?:the\s+)?(?:mic|microphone|yourself)|be\s+quiet(?:\s+mic)?|silence\s+(?:yourself|mic|microphone))\b/.test(text)) {
    return { kind: "mute_mic" };
  }

  if (/\b(?:(?:turn\s+)?(?:on|enable|show|display)\s+(?:closed\s+)?(?:captions?|subtitles?|cc)|(?:closed\s+)?(?:captions?|subtitles?|cc)\s+on)\b/.test(text)) {
    return { kind: "captions_on" };
  }
  if (/\b(?:(?:turn\s+)?(?:off|disable|hide|remove)\s+(?:closed\s+)?(?:captions?|subtitles?|cc)|(?:closed\s+)?(?:captions?|subtitles?|cc)\s+off)\b/.test(text)) {
    return { kind: "captions_off" };
  }
  if (/^(?:(?:closed\s+)?captions|subtitles|cc)$/.test(text)) {
    return { kind: "captions_toggle" };
  }

  if (/\b(exit|leave|close|quit)\s+(?:full\s*screen|fullscreen)\b|^(?:exit|normal\s+size|smaller|minimize)$/.test(text)) {
    return { kind: "fullscreen_off" };
  }
  if (/\b(?:go\s+)?(?:full\s*screen|fullscreen)|\bmake\s+it\s+(?:bigger|full)\b|\bbigger\s+screen\b/.test(text)) {
    return { kind: "fullscreen_on" };
  }

  if (/\b(?:show|display|bring\s+(?:up|back))\s+(?:the\s+)?(?:controls?|buttons?|options?|menu)\b/.test(text)) {
    return { kind: "show_controls" };
  }
  if (/\b(?:hide|close)\s+(?:the\s+)?(?:controls?|buttons?|options?|menu)\b/.test(text)) {
    return { kind: "hide_controls" };
  }

  if (/\b(slow(?:\s+down)?|slower|less\s+speed)\b/.test(text)) return { kind: "set_speed", speed: "slower" };
  if (/\b(speed\s+up|faster|more\s+speed)\b/.test(text)) return { kind: "set_speed", speed: "faster" };
  if (/\b(normal\s+speed|regular\s+speed|default\s+speed)\b/.test(text)) return { kind: "set_speed", speed: "normal" };

  const langMatch = text.match(/\b(?:speak(?:\s+in)?|say(?:\s+it)?\s+in|change\s+language\s+to|switch\s+(?:language\s+)?to|language\s+to|in)\s+([a-z\-]{2,20})\b/);
  if (langMatch) {
    const code = languageCodeFromSpoken(langMatch[1]);
    if (code) return { kind: "set_language", language: code };
  }

  if (/\b(restart|start\s+over|from\s+the\s+beginning|back\s+to\s+(?:the\s+)?beginning)\b/.test(text)) {
    return { kind: "restart" };
  }

  if (/^(pause|stop|hold\s+on|wait|freeze)$|\b(pause|stop\s+(?:the\s+)?(?:course|lesson|class|video))\b/.test(text)) {
    return { kind: "pause" };
  }
  if (/^(resume|continue|unpause|play|keep\s+going|carry\s+on)$|\b(resume|unpause|keep\s+going|carry\s+on)\b/.test(text)) {
    return { kind: "resume" };
  }
  if (/^(start|begin)$|\b(start|begin)\s+(?:the\s+)?(?:course|lesson|class)\b/.test(text)) {
    return { kind: "start" };
  }

  if (/^(next|forward|skip|move\s+on)$|\bnext\s+(?:slide|chapter|section|step)\b|\bskip\s+ahead\b/.test(text)) {
    return { kind: "next" };
  }
  if (/^(back|previous|rewind)$|\b(previous|go\s+back|back\s+up|last\s+(?:slide|one))\b/.test(text)) {
    return { kind: "previous" };
  }
  if (/^(repeat|again)$|\b(repeat|say\s+that\s+again|come\s+again|one\s+more\s+time|do\s+it\s+again)\b/.test(text)) {
    return { kind: "repeat" };
  }

  if (/^(help|commands?)$|\b(what\s+can\s+i\s+say|what\s+commands|how\s+do\s+i\s+use\s+this)\b/.test(text)) {
    return { kind: "help" };
  }

  const askMatch = text.match(/^(?:ask\s+(?:sala\s+)?|question[:,-]?\s*)(.+)$/);
  if (askMatch && askMatch[1]) {
    return { kind: "ask", question: askMatch[1].trim() };
  }

  if (looksLikeAsk(text)) {
    return { kind: "ask", question: text };
  }

  return null;
}

// ---- Dispatcher: intent -> existing Course Studio handler --------------------

function clickById(id) {
  const el = document.getElementById(id);
  if (el && typeof el.click === "function") el.click();
  return Boolean(el);
}

function setLanguageSelect(code) {
  const ids = ["teach-lang-stage", "teach-lang"];
  let changed = false;
  for (const id of ids) {
    const sel = document.getElementById(id);
    if (!sel) continue;
    const option = Array.from(sel.options || []).find((o) => o.value === code);
    if (!option) continue;
    if (sel.value !== code) {
      sel.value = code;
      sel.dispatchEvent(new Event("change", { bubbles: true }));
      changed = true;
    }
  }
  return changed;
}

function requestFs() {
  const target = document.getElementById("teach-stage") || document.documentElement;
  if (document.fullscreenElement) return true;
  if (typeof target.requestFullscreen === "function") {
    target.requestFullscreen().catch(() => {});
    return true;
  }
  return false;
}

function exitFs() {
  if (!document.fullscreenElement) return true;
  if (typeof document.exitFullscreen === "function") {
    document.exitFullscreen().catch(() => {});
    return true;
  }
  return false;
}

function announce(message) {
  // Reuse Studio's existing toast when available; fall back to a short
  // live-region update so screen readers hear what Sala did.
  const toast = window.__salaToast;
  if (typeof toast === "function") { toast(message); return; }
  const el = document.getElementById("sala-voice-announce");
  if (el) el.textContent = message;
}

function dispatchIntent(intent, { reveal }) {
  switch (intent.kind) {
    case "pause":
      // Course Studio exposes toggleLecturePause via the pause button.
      if (!clickById("btn-pause")) announce("Pause isn't available on this slide.");
      return true;
    case "resume":
      // Resume button exists for post-pause restarts; otherwise re-click pause.
      if (!clickById("btn-resume") && !clickById("btn-pause")) announce("Resume isn't available.");
      return true;
    case "restart":
      if (!clickById("btn-start-over")) announce("Restart isn't available right now.");
      return true;
    case "start":
      if (!clickById("btn-teach") && !clickById("btn-resume")) announce("Start isn't ready yet.");
      return true;
    case "next":
      if (!clickById("btn-next")) announce("No next slide available.");
      return true;
    case "previous":
      // Course Studio has no explicit "previous" button; use the course-map
      // scrubber if present, else say so.
      {
        const scrub = document.getElementById("course-map-scrub");
        if (scrub && typeof scrub.value !== "undefined") {
          const value = Math.max(0, Number(scrub.value || 0) - 1);
          scrub.value = String(value);
          scrub.dispatchEvent(new Event("change", { bubbles: true }));
          return true;
        }
        announce("Going back isn't available here.");
      }
      return true;
    case "repeat":
      // The hidden chrome includes a repeat button for the last narration.
      if (!clickById("btn-repeat")) announce("Nothing to repeat yet.");
      return true;
    case "captions_on":
    case "captions_off":
    case "captions_toggle":
      // The captions button is a toggle; drive it with current state when
      // we need a specific side.
      {
        const btn = document.getElementById("btn-captions");
        if (!btn) { announce("Captions aren't available."); return true; }
        const isOff = btn.classList.contains("is-off");
        if (intent.kind === "captions_toggle" ||
            (intent.kind === "captions_on" && isOff) ||
            (intent.kind === "captions_off" && !isOff)) {
          btn.click();
        }
      }
      return true;
    case "fullscreen_on":
      requestFs();
      return true;
    case "fullscreen_off":
      exitFs();
      return true;
    case "set_language":
      if (!setLanguageSelect(intent.language)) {
        announce(`Language ${intent.language} isn't offered for this course.`);
      }
      return true;
    case "set_speed":
      // No native rate control in Studio today; narrate so the learner knows
      // Sala heard them.
      announce(`Speed ${intent.speed} isn't adjustable here yet.`);
      return true;
    case "mute_mic":
      // Handled by the overlay; falls through here only when a typed command
      // triggers mute. Signal the overlay to flip the mute state.
      window.dispatchEvent(new CustomEvent("sala:mute-mic"));
      return true;
    case "show_controls":
      reveal("voice-command");
      return true;
    case "hide_controls":
      document.body.classList.add("aoep-voice-first");
      return true;
    case "help":
      announce("Say: pause, resume, next, back, captions on, speak Spanish, fullscreen, exit, or ask a question.");
      return true;
    case "ask":
      // Fire a message any Sala listener in the parent page can catch.
      window.dispatchEvent(new CustomEvent("sala:ask", { detail: { question: intent.question } }));
      try {
        window.parent?.postMessage({ type: "sala-ask", question: intent.question }, "*");
      } catch { /* cross-origin; non-fatal */ }
      return true;
    default:
      return false;
  }
}

// ---- Demo-only commands -----------------------------------------------------
// Kept out of courseVoiceIntentCatalog() so the web/mobile parity test is unaffected.
// Everything here stays inside this course page.

let audioGain = 1;
let audioGainInstalled = false;

function installAudioGain() {
  if (audioGainInstalled) return;
  audioGainInstalled = true;
  try {
    const desc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, "volume");
    if (desc && desc.set && desc.get) {
      Object.defineProperty(HTMLMediaElement.prototype, "volume", {
        configurable: true,
        get() { return desc.get.call(this); },
        set(v) { desc.set.call(this, Math.max(0, Math.min(1, Number(v) * audioGain))); },
      });
    }
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function patchedPlay(...args) {
      try { desc.set.call(this, Math.max(0, Math.min(1, audioGain))); } catch { /* non-fatal */ }
      return play.apply(this, args);
    };
    const synth = window.speechSynthesis;
    if (synth && typeof synth.speak === "function") {
      const speak = synth.speak.bind(synth);
      synth.speak = (u) => { try { u.volume = Math.min(1, audioGain); } catch { /* non-fatal */ } return speak(u); };
    }
  } catch { /* non-fatal */ }
}

function applyAudioGain(next) {
  audioGain = Math.max(0, Math.min(1, next));
  installAudioGain();
  document.querySelectorAll("audio, video").forEach((m) => { try { m.volume = audioGain; } catch { /* non-fatal */ } });
  try {
    if (audioGain === 0) window.speechSynthesis?.cancel();
  } catch { /* non-fatal */ }
}

export function parseDemoCommand(utterance) {
  const text = normalize(utterance);
  if (!text) return null;
  if (/^(?:un\s*mute|sound\s+on|turn\s+(?:the\s+)?(?:sound|audio|volume)\s+on)$/.test(text)) return { kind: "audio_on" };
  if (/^(?:mute|sound\s+off|turn\s+(?:the\s+)?(?:sound|audio|volume)\s+off|mute\s+(?:the\s+)?(?:sound|audio|volume|course|lesson))$/.test(text)) return { kind: "audio_off" };
  if (/\b(?:volume\s+up|louder|turn\s+(?:it|the\s+volume)\s+up)\b/.test(text)) return { kind: "volume", delta: 0.25 };
  if (/\b(?:volume\s+down|quieter|softer|turn\s+(?:it|the\s+volume)\s+down)\b/.test(text)) return { kind: "volume", delta: -0.25 };
  if (/\b(?:hide|remove)\s+(?:the\s+)?(?:camera|webcam|my\s+(?:camera|face|video))\b/.test(text)) return { kind: "camera_hide" };
  if (/\b(?:show|turn\s+on)\s+(?:the\s+)?(?:camera|webcam)\b/.test(text)) return { kind: "camera_show" };
  return null;
}

function dispatchDemoCommand(cmd) {
  switch (cmd.kind) {
    case "audio_off": applyAudioGain(0); announce("Sound off."); return true;
    case "audio_on": applyAudioGain(audioGain > 0 ? audioGain : 1); announce("Sound on."); return true;
    case "volume": applyAudioGain((audioGain || 0) + cmd.delta); return true;
    case "camera_hide":
    case "camera_show": {
      const cam = document.getElementById("student-cam");
      if (cam) cam.style.display = cmd.kind === "camera_hide" ? "none" : "";
      return true;
    }
    default: return false;
  }
}

function askTheCourse(question) {
  const box = document.getElementById("voice-ask");
  if (!box) return false;
  box.value = question;
  return clickById("btn-talk-send");
}

// ---- Overlay UI --------------------------------------------------------------

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (k === "style" && typeof v === "object") Object.assign(node.style, v);
    else if (k === "className") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else node.setAttribute(k, v);
  }
  if (children) for (const child of children) {
    if (child == null) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function readConsent() {
  try { return window.localStorage.getItem(CONSENT_KEY) === "1"; }
  catch { return false; }
}

function writeConsent(value) {
  try {
    if (value) window.localStorage.setItem(CONSENT_KEY, "1");
    else window.localStorage.removeItem(CONSENT_KEY);
  } catch { /* non-fatal */ }
}

export function initCourseVoiceOverlay(opts = {}) {
  const options = {
    typeToAsk: Boolean(opts.typeToAsk),
    locale: String(opts.locale || "en-US"),
    stageSelector: opts.stageSelector || "#teach-stage",
    demo: Boolean(opts.demo),
    clean: Boolean(opts.clean),
  };
  // The one movable widget (camera + Sala's voice + timer): the full course and the public demo.
  options.widget = Boolean(opts.widget || options.clean || options.demo);

  if (!document.body) {
    document.addEventListener("DOMContentLoaded", () => initCourseVoiceOverlay(opts), { once: true });
    return null;
  }

  // Hide the chrome by default. The classic CSS .chrome-hidden rule in
  // STUDIO_CSS already does the heavy lifting; .aoep-voice-first just
  // re-applies it alongside tagging the mode for CSS/JS checks.
  document.body.classList.add("aoep-voice-first", "chrome-hidden");
  if (options.demo || options.clean) document.body.classList.add("demo-clean");
  if (options.clean) document.body.classList.add("course-clean");
  if (options.demo) document.body.classList.add("demo-widget");

  const root = el("div", {
    "aria-live": "polite",
    "class": "sala-voice-root",
    style: { position: "fixed", inset: "0", pointerEvents: "none", zIndex: "60" },
  });
  const announceLive = el("div", {
    id: "sala-voice-announce",
    "aria-live": "polite",
    "aria-atomic": "true",
    style: { position: "absolute", width: "1px", height: "1px", overflow: "hidden", clip: "rect(0 0 0 0)" },
  });
  root.appendChild(announceLive);
  document.body.appendChild(root);

  let consented = options.demo ? false : readConsent();
  let muted = false;
  let listening = false;
  let recognizer = null;
  let missTimestamps = [];
  let typedOpen = false;

  const supported = (() => {
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    return Boolean(Ctor);
  })();

  function reveal(reason) {
    if (options.demo) return;
    if (options.clean) {
      // Only an explicit request (or no voice support) brings the classic controls back.
      if (reason !== "voice-command" && reason !== "not-supported") return;
      document.body.classList.remove("course-clean", "demo-clean");
      document.getElementById("course-widget")?.remove();
    }
    document.body.classList.remove("aoep-voice-first", "chrome-hidden");
    document.body.classList.add("aoep-voice-revealed");
    announce(reason === "voice-command"
      ? "Classic controls back on. Say 'hide controls' to return to voice mode."
      : "Classic controls back on so you can finish.");
  }

  function recordMiss(_transcript) {
    const now = Date.now();
    missTimestamps = missTimestamps.filter((t) => now - t <= MISS_WINDOW_MS);
    missTimestamps.push(now);
    if (missTimestamps.length >= MISS_LIMIT) {
      missTimestamps = [];
      reveal("misses");
    }
  }

  function handleUtterance(transcript) {
    if (options.demo) {
      const demoCmd = parseDemoCommand(transcript);
      if (demoCmd) { dispatchDemoCommand(demoCmd); return; }
    }
    const intent = parseCourseVoiceIntent(transcript);
    if (!intent) { if (!options.demo) recordMiss(transcript); return; }
    if (intent.kind === "mute_mic") { setMuted(true); return; }
    if (options.demo && intent.kind === "ask") { askTheCourse(intent.question); return; }
    if (options.demo && intent.kind === "start") { clickById("btn-start-voice"); return; }
    dispatchIntent(intent, { reveal });
  }

  function startRecognizer() {
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Ctor || muted || !consented) return;
    const rec = new Ctor();
    rec.lang = options.locale || "en-US";
    rec.interimResults = false;
    rec.continuous = true;
    rec.onresult = (event) => {
      const start = event.resultIndex || 0;
      for (let i = start; i < event.results.length; i += 1) {
        const first = event.results[i]?.[0];
        const transcript = (first?.transcript || "").trim();
        if (!transcript) continue;
        handleUtterance(transcript);
      }
    };
    rec.onerror = (event) => {
      if (!event?.error || event.error === "no-speech" || event.error === "aborted") return;
      if (event.error === "not-allowed") {
        setConsented(false);
        writeConsent(false);
      }
    };
    rec.onend = () => {
      if (muted || !consented) { listening = false; renderPill(); return; }
      try { rec.start(); } catch { listening = false; renderPill(); }
    };
    recognizer = rec;
    try { rec.start(); listening = true; }
    catch { listening = false; }
    renderPill();
  }

  function stopRecognizer() {
    if (!recognizer) return;
    try { recognizer.onresult = null; recognizer.onerror = null; recognizer.onend = null; } catch { /* non-fatal */ }
    try { recognizer.stop(); } catch { /* non-fatal */ }
    recognizer = null;
    listening = false;
  }

  function setMuted(value) {
    muted = Boolean(value);
    if (muted) stopRecognizer();
    else startRecognizer();
    renderPill();
  }

  function setConsented(value) {
    consented = Boolean(value);
    if (!options.demo) writeConsent(consented);
    if (consented) startRecognizer();
    else stopRecognizer();
    renderOverlay();
  }

  let pillNode = null;
  function renderPill() {
    if (pillNode) pillNode.remove();
    syncWidgetStatus();
    if (!consented) return;
    const label = !supported ? "Voice unavailable"
      : muted ? "Mic muted — tap to resume"
        : listening ? "Sala listening"
          : "Starting Sala…";
    const dotColor = muted ? "#f87171" : listening ? "#22c55e" : "#eab308";
    pillNode = el("button", {
      type: "button",
      "aria-label": muted ? "Unmute Sala's microphone" : "Mute Sala's microphone",
      "aria-pressed": muted ? "true" : "false",
      class: "sala-pill",
      style: {
        position: "absolute", left: "50%", bottom: "20px",
        transform: "translateX(-50%)", display: "inline-flex", alignItems: "center",
        gap: "8px", padding: "8px 14px", borderRadius: "999px",
        border: "1px solid rgba(255,255,255,0.25)", background: "rgba(15,23,42,0.6)",
        color: "#fff", fontSize: "13px", cursor: "pointer",
        backdropFilter: "blur(6px)", pointerEvents: "auto",
      },
    }, [
      el("span", {
        "aria-hidden": "true",
        style: {
          display: "inline-block", width: "10px", height: "10px",
          borderRadius: "50%", background: dotColor,
          boxShadow: muted ? "none" : `0 0 0 4px ${dotColor}22`,
        },
      }),
      el("span", null, [label]),
    ]);
    pillNode.addEventListener("click", () => setMuted(!muted));
    root.appendChild(pillNode);
  }

  let overlayNode = null;
  function renderOverlay() {
    if (overlayNode) { overlayNode.remove(); overlayNode = null; }
    renderPill();
    if (consented || options.clean) return;
    const canSpeak = supported;
    const text = canSpeak
      ? "Sala can run this course by voice. Tap once to let her listen; she'll only act on commands like \"pause\", \"next\", \"captions on\"."
      : "Voice commands aren't supported in this browser. Open the classic controls to continue.";
    overlayNode = el("div", {
      class: "sala-consent",
      style: {
        position: "absolute", left: "50%", bottom: "24px",
        transform: "translateX(-50%)", maxWidth: "420px",
        padding: "12px 16px", borderRadius: "14px",
        background: "rgba(15,23,42,0.88)", color: "#fff",
        fontSize: "14px", lineHeight: "1.35",
        boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
        display: "flex", flexDirection: "column", gap: "8px",
        pointerEvents: "auto",
      },
    }, [el("div", null, [text])]);
    if (canSpeak) {
      const accept = el("button", {
        type: "button",
        class: "sala-consent-accept",
        style: {
          alignSelf: "flex-start", padding: "8px 14px",
          borderRadius: "999px", border: "0", background: "#4f46e5",
          color: "#fff", fontWeight: "600", cursor: "pointer",
        },
      }, ["Let Sala listen"]);
      accept.addEventListener("click", () => setConsented(true));
      overlayNode.appendChild(accept);
    } else {
      const reveal = el("button", {
        type: "button", class: "sala-consent-reveal",
        style: {
          alignSelf: "flex-start", padding: "8px 14px",
          borderRadius: "999px", border: "0", background: "#4f46e5",
          color: "#fff", fontWeight: "600", cursor: "pointer",
        },
      }, ["Show classic controls"]);
      reveal.addEventListener("click", () => reveal("not-supported"));
      overlayNode.appendChild(reveal);
    }
    root.appendChild(overlayNode);
  }

  // Type-to-ask pill when the accessibility flag is on. Added once; stays
  // visible so a learner who cannot speak can issue the same intents.
  let typedPill = null;
  let typedForm = null;
  function renderTypeToAsk() {
    if (!options.typeToAsk) return;
    if (typedPill) return;
    typedPill = el("button", {
      type: "button",
      "aria-label": "Type a command for Sala",
      class: "sala-type-pill",
      style: {
        position: "absolute", right: "16px", bottom: "16px",
        padding: "10px 14px", borderRadius: "999px",
        border: "1px solid rgba(255,255,255,0.4)",
        background: "rgba(15,23,42,0.45)",
        color: "rgba(255,255,255,0.9)", fontSize: "13px",
        cursor: "pointer", backdropFilter: "blur(6px)",
        pointerEvents: "auto",
      },
    }, ["\u2328 Type to Sala"]);
    typedPill.addEventListener("click", () => {
      if (typedForm) { typedForm.remove(); typedForm = null; return; }
      typedForm = el("form", {
        class: "sala-type-form",
        style: {
          position: "absolute", right: "16px", bottom: "60px",
          display: "flex", gap: "6px", padding: "8px",
          borderRadius: "10px", background: "rgba(15,23,42,0.9)",
          boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
          pointerEvents: "auto",
        },
      });
      const input = el("input", {
        placeholder: "pause, next, captions on, …",
        "aria-label": "Type a command",
        style: {
          minWidth: "220px", padding: "8px 10px", borderRadius: "6px",
          border: "1px solid rgba(255,255,255,0.3)",
          background: "rgba(0,0,0,0.4)", color: "#fff", fontSize: "14px",
        },
      });
      const submit = el("button", {
        type: "submit",
        style: {
          padding: "8px 12px", borderRadius: "6px", border: "0",
          background: "#4f46e5", color: "#fff", fontWeight: "600",
          cursor: "pointer",
        },
      }, ["Send"]);
      typedForm.appendChild(input);
      typedForm.appendChild(submit);
      typedForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = String(input.value || "").trim();
        if (typedForm) { typedForm.remove(); typedForm = null; }
        if (!text) return;
        const intent = parseCourseVoiceIntent(text);
        if (!intent) { recordMiss(text); announce(`Sala did not understand "${text}".`); return; }
        if (intent.kind === "mute_mic") { setMuted(true); return; }
        dispatchIntent(intent, { reveal });
      });
      root.appendChild(typedForm);
      input.focus();
    });
    root.appendChild(typedPill);
  }

  // Double-click / long-press on the stage area.
  function wireStageGestures() {
    const stage = document.querySelector(options.stageSelector);
    if (!stage) return;
    stage.addEventListener("dblclick", (event) => {
      // Demo: the studio's own double-click already toggles full screen.
      if (options.demo) return;
      // Ignore double-clicks on actual controls; only trigger when the user
      // double-clicked the lesson content itself.
      if (event.target.closest("button, select, input, a, [role='button']")) return;
      if (document.fullscreenElement) exitFs(); else requestFs();
    });
    let pressTimer = null;
    const cancel = () => { if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; } };
    stage.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button, select, input, a, [role='button']")) return;
      cancel();
      pressTimer = setTimeout(() => {
        pressTimer = null;
        reveal("long-press");
      }, LONG_PRESS_MS);
    });
    stage.addEventListener("pointerup", cancel);
    stage.addEventListener("pointermove", cancel);
    stage.addEventListener("pointercancel", cancel);
    stage.addEventListener("pointerleave", cancel);
  }

  // Allow the dispatcher to request mute via a custom event (type-to-ask path).
  window.addEventListener("sala:mute-mic", () => setMuted(true));

  // Demo: the avatar is the only control. One click starts the course (the
  // avatar talks) and opens the mic; clicking again mutes or unmutes it.
  // On a phone every pixel counts: the first tap goes straight to full screen.
  const phoneQuery = window.matchMedia ? window.matchMedia("(max-width: 760px), (max-height: 520px) and (pointer: coarse)") : null;
  // Only the full-screen element is drawn while in full screen, so our buttons
  // and the tutorial have to live inside it, and move back when it ends.
  function mountOnTop(node) {
    const host = document.fullscreenElement || document.body;
    if (node.parentNode !== host) host.appendChild(node);
  }
  document.addEventListener("fullscreenchange", () => {
    for (const node of document.querySelectorAll(".sala-help, .sala-rotate, .sala-tutorial, #course-widget")) mountOnTop(node);
    showRotateHint();
  });

  function showRotateHint() {
    if (!phoneQuery || !phoneQuery.matches) return;
    const portrait = window.matchMedia("(orientation: portrait)").matches;
    let hint = document.querySelector(".sala-rotate");
    if (!portrait || !(document.body.classList.contains("presenting") || document.fullscreenElement)) { hint?.remove(); return; }
    if (!hint) {
      hint = el("div", { class: "sala-rotate", role: "status" }, ["\u{1F504} Turn your phone sideways for the biggest picture"]);
      mountOnTop(hint);
      setTimeout(() => hint?.remove(), 8000);
    }
  }
  if (window.matchMedia) {
    const orient = window.matchMedia("(orientation: portrait)");
    if (orient.addEventListener) orient.addEventListener("change", showRotateHint);
  }

  function goFullScreenOnPhone() {
    if (!phoneQuery || !phoneQuery.matches) return;
    if (document.body.classList.contains("presenting") || document.fullscreenElement) return;
    clickById("btn-fullscreen");
    // Where the phone allows it (Android Chrome in full screen), use the wide picture.
    setTimeout(() => {
      try { window.screen?.orientation?.lock?.("landscape")?.catch(() => {}); } catch { /* not supported */ }
      showRotateHint();
    }, 400);
  }

  const TUTORIAL_KEY = options.demo ? "sala_demo_tutorial_seen_v4" : "sala_course_tutorial_seen_v2";
  // The demo tutorial shows first in every new browser session (the opening video is per session too); the full course
  // keeps it once per device.
  const tutorialStore = () => (options.demo ? window.sessionStorage : window.localStorage);

  // Driver's Ed demo opening: the page around us shows a video. Order: this tutorial first
  // (video waiting, paused, behind it), then the video, then the lesson. Until the video is
  // done the page carries .sala-intro-hold, so the first slide stays hidden, and starting the
  // lesson waits too. The parent hears about the tutorial through postMessage.
  const INTRO_SEEN_KEY = "salareen.driversEdIntro.seen.v1";
  let tutorialState = "pending";
  let pendingLessonStart = false;
  const introHolding = () => document.documentElement.classList.contains("sala-intro-hold");
  function reportTutorial(state) {
    tutorialState = state;
    try {
      if (window.parent !== window) window.parent.postMessage({ type: "sala-tutorial", state }, window.location.origin);
    } catch { /* cross-origin parent: it just will not hear us */ }
  }
  function startLessonNow() {
    goFullScreenOnPhone();
    const welcome = document.getElementById("page-welcome");
    if (welcome && !welcome.hidden) clickById("btn-start-voice");
    if (!consented) setConsented(true);
  }
  function releaseIntroHold() {
    if (!introHolding()) return;
    document.documentElement.classList.remove("sala-intro-hold");
    if (pendingLessonStart) {
      pendingLessonStart = false;
      startLessonNow();
    }
  }
  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin || event.source !== window.parent) return;
    const kind = event.data && event.data.type;
    if (kind === "sala-intro-done") releaseIntroHold();
    else if (kind === "sala-intro-query") reportTutorial(tutorialState);
  });
  // Safety net if the message is missed: let go once the page has marked the video as seen.
  if (introHolding()) {
    const holdStarted = Date.now();
    const holdTimer = window.setInterval(() => {
      let seen = false;
      try { seen = window.sessionStorage.getItem(INTRO_SEEN_KEY) === "1"; } catch { /* private mode */ }
      if (seen || !introHolding() || Date.now() - holdStarted > 600000) {
        window.clearInterval(holdTimer);
        releaseIntroHold();
      }
    }, 500);
  }
  const PICTURE_STEPS = [
    {
      image: "/api/studio/voice-overlay/tutorial-tap.webp",
      title: "Tap the lesson",
      alt: "Tap the lesson. It moves ahead.",
    },
    {
      image: "/api/studio/voice-overlay/tutorial-double.webp",
      title: "Full screen",
      alt: "Double-tap the lesson. Full screen.",
    },
    {
      image: "/api/studio/voice-overlay/sala-giggle.png",
      title: "Tap Sala",
      alt: "Tap Sala. Sala giggles.",
      portrait: true,
      lines: ["Tap Sala to start. Sala giggles. Tap again to turn listening on or off."],
    },
    {
      image: "/api/studio/voice-overlay/tutorial-dance.webp",
      title: "Sala can dance",
      alt: "Sala can dance.",
    },
  ];
  const SAY_IT = {
    icon: "🎙️", title: "Just say it",
    lines: ["Talk to Sala like a teacher. Captions stay off until you ask. Try:"],
    chips: ["pause", "next", "back", "repeat", "captions on", "full screen", "speak Spanish", "louder", "mute"],
  };
  const DEMO_TUTORIAL = [
    ...PICTURE_STEPS,
    { ...SAY_IT, after: ["Or ask any question about the course. The free demo runs for 10 minutes."] },
  ];
  const FULL_TUTORIAL = [
    ...PICTURE_STEPS,
    { ...SAY_IT, after: ["Or ask any question about the lesson. Tap the yellow ? button any time to see this again."] },
  ];
  // Clean full course: no Sala figure to tap and no floating ? button. One small panel holds the camera and Sala's voice.
  const CLEAN_TUTORIAL = [
    PICTURE_STEPS[0],
    PICTURE_STEPS[1],
    {
      icon: "🎛️", title: "Your little panel",
      lines: ["One small panel has your camera and Sala's voice. Drag it anywhere. Tap the dash to tuck it away."],
      after: ["Tap the three dots for Help, Progress, language, captions and Exit lesson."],
    },
    { ...SAY_IT, after: ["Or ask any question about the lesson. Open the three dots and tap Help to see this again."] },
  ];
  const tutorialSteps = () => (options.demo ? DEMO_TUTORIAL : options.clean ? CLEAN_TUTORIAL : FULL_TUTORIAL);

  function showDemoTutorial(startLesson) {
    document.querySelector(".sala-tutorial")?.remove();
    reportTutorial("open");
    let step = 0;
    const overlay = document.createElement("div");
    overlay.className = "sala-tutorial";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "How to use this lesson");
    const render = () => {
      const steps = tutorialSteps();
      const t = steps[step];
      const last = step === steps.length - 1;
      const chips = t.chips ? `<ul>${t.chips.map((c) => `<li>${c}</li>`).join("")}</ul>` : "";
      const frame = t.image
        ? `<img class="frame${t.portrait ? " portrait" : ""}" src="${t.image}" alt="${t.alt || t.title}">`
        : `<div class="icon" aria-hidden="true">${t.icon}</div><h2>${t.title}</h2>`;
      overlay.innerHTML = `
        <div class="card${t.image ? " has-frame" : ""}">
          <div class="dots">${tutorialSteps().map((_, i) => `<i class="${i === step ? "on" : ""}"></i>`).join("")}</div>
          ${frame}
          ${(t.lines || []).map((l) => `<p>${l}</p>`).join("")}${chips}${(t.after || []).map((l) => `<p>${l}</p>`).join("")}
          <div class="actions">
            ${step > 0 ? '<button type="button" class="back">Back</button>' : '<button type="button" class="skip">Skip</button>'}
            <button type="button" class="go">${last ? (startLesson ? "Start the lesson" : "Done") : "Next"}</button>
          </div>
        </div>`;
      overlay.querySelector(".go").onclick = () => (last ? close() : (step += 1, render()));
      const back = overlay.querySelector(".back");
      if (back) back.onclick = () => { step -= 1; render(); };
      const skip = overlay.querySelector(".skip");
      if (skip) skip.onclick = () => close();
    };
    const onKey = (event) => { if (event.key === "Escape") close(); };
    const close = () => {
      try { tutorialStore().setItem(TUTORIAL_KEY, "1"); } catch { /* not kept: shows again next time */ }
      document.removeEventListener("keydown", onKey);
      overlay.remove();
      (document.querySelector(".sala-help") || document.querySelector("#course-widget .cw-menu-btn"))?.focus?.({ preventScroll: true });
      reportTutorial("closed");
      if (startLesson) {
        if (introHolding()) pendingLessonStart = true;
        else startLessonNow();
      }
    };
    render();
    mountOnTop(overlay);
    document.addEventListener("keydown", onKey);
    overlay.querySelector(".go")?.focus?.({ preventScroll: true });
  }

  function wireDemoHelp() {
    if (document.querySelector(".sala-help")) return;
    if (!options.widget) {
      const help = el("button", { type: "button", class: "sala-help", "aria-label": "How to use this lesson", title: "How to use this lesson" }, ["?"]);
      help.addEventListener("click", () => showDemoTutorial(false));
      mountOnTop(help);
    }
    let seen = false;
    try { seen = tutorialStore().getItem(TUTORIAL_KEY) === "1"; } catch { seen = false; }
    if (!seen) showDemoTutorial(Boolean(options.demo));
    else reportTutorial("closed");
  }

  function wireAvatarGesture() {
    buildCourseWidget();
    wireDemoHelp();
    document.addEventListener("click", (event) => {
      const wrap = event.target.closest && event.target.closest("#theodore-avatar-wrap");
      if (!wrap) return;
      event.stopPropagation();
      wrap.classList.remove("sala-giggle");
      void wrap.offsetWidth;
      wrap.classList.add("sala-giggle");
      window.setTimeout(() => wrap.classList.remove("sala-giggle"), 720);
      goFullScreenOnPhone();
      const welcome = document.getElementById("page-welcome");
      if (welcome && !welcome.hidden) clickById("btn-start-voice");
      if (!consented) setConsented(true);
      else setMuted(!muted);
    }, true);
    const sync = () => {
      const wrap = document.getElementById("theodore-avatar-wrap");
      if (wrap) wrap.classList.toggle("sala-listening", Boolean(listening && !muted));
    };
    setInterval(sync, 400);
  }

  // ---- Full course (course-clean): ONE movable widget ------------------------------------
  // The lesson fills the screen. A single small panel holds the webcam preview, Sala's voice (the shared
  // Salane Voice widget, mounted in embedded mode) and a one-line status plus a menu with Help, Progress,
  // Captions, Language, Mute and Exit. Dragging works from the grip or the bar; the spot is remembered.
  const CW_POS_KEY = options.demo ? "aoep.courseWidget.pos.demo.v1" : "aoep.courseWidget.pos.v1";
  const CW_COLLAPSE_KEY = "aoep.courseWidget.collapsed.v1";
  const CW_HINT_KEY = "aoep.courseWidget.hint.v1";
  let cw = null;
  let presenceLine = "";

  function readJson(key) {
    try { return JSON.parse(window.localStorage.getItem(key) || "null"); } catch { return null; }
  }
  function writeJson(key, value) {
    try { window.localStorage.setItem(key, JSON.stringify(value)); } catch { /* not kept */ }
  }
  function safeInsets() {
    const probe = el("div", { "aria-hidden": "true", style: {
      position: "fixed", top: "env(safe-area-inset-top, 0px)", left: "env(safe-area-inset-left, 0px)",
      right: "env(safe-area-inset-right, 0px)", bottom: "env(safe-area-inset-bottom, 0px)", visibility: "hidden", pointerEvents: "none",
    } });
    document.body.appendChild(probe);
    const r = probe.getBoundingClientRect();
    probe.remove();
    return { top: Math.max(0, r.top), left: Math.max(0, r.left), right: Math.max(0, window.innerWidth - r.right), bottom: Math.max(0, window.innerHeight - r.bottom) };
  }
  function hintSeen() {
    try { return window.localStorage.getItem(CW_HINT_KEY) === "1"; } catch { return false; }
  }
  function noteHintSeen() {
    try { window.localStorage.setItem(CW_HINT_KEY, "1"); } catch { /* shows again next visit */ }
    syncWidgetStatus();
  }

  function syncWidgetStatus() {
    if (!cw) return;
    let text;
    let kind = "";
    if (presenceLine) { text = presenceLine; kind = "paused"; }
    else if (!supported) text = "Voice commands aren't supported in this browser.";
    else if (!consented) text = hintSeen() ? "Tap the lesson to start." : "Tap to start. Say “pause” or “next”.";
    else if (muted) text = "Mic muted.";
    else if (listening) text = "Sala is listening.";
    else text = "Starting Sala…";
    // A small dot; the words go in the tooltip and a screen-reader-only span, not on screen.
    cw.status.dataset.kind = kind;
    cw.status.dataset.state = kind === "paused" ? "paused" : muted ? "muted" : listening ? "on" : "wait";
    cw.status.title = text;
    cw.status.textContent = "";
    cw.status.append(el("span", { class: "cw-sr" }, [text]));
  }

  function placeCourseWidget(left, top, persist) {
    if (!cw) return;
    const box = cw.root;
    const safe = safeInsets();
    const w = box.offsetWidth || 236;
    const h = box.offsetHeight || 120;
    const x = Math.max(safe.left + 8, Math.min(window.innerWidth - safe.right - w - 8, left));
    const y = Math.max(safe.top + 8, Math.min(window.innerHeight - safe.bottom - h - 8, top));
    box.style.left = `${Math.round(x)}px`;
    box.style.top = `${Math.round(y)}px`;
    if (persist) writeJson(CW_POS_KEY, { left: Math.round(x), top: Math.round(y) });
  }

  function exitLesson() {
    try {
      if (window.ReactNativeWebView) { window.ReactNativeWebView.postMessage(JSON.stringify({ type: "salareen-exit" })); return; }
    } catch { /* fall through */ }
    try {
      if (window.parent !== window) { window.parent.postMessage({ type: "sala-course-exit" }, window.location.origin); return; }
    } catch { /* fall through */ }
    if (window.history.length > 1) window.history.back();
    else window.location.href = "/";
  }

  function buildCourseWidget() {
    if (!options.widget || cw) return;
    const root = el("aside", { id: "course-widget", role: "region", "aria-label": "Lesson panel: camera, Sala's voice and menu" });
    const bar = el("div", { class: "cw-bar" });
    const grip = el("button", { type: "button", class: "cw-grip", "aria-label": "Move this panel. Drag, or use the arrow keys.", title: "Drag to move" }, ["⋮⋮"]);
    const status = el("p", { class: "cw-status", "aria-live": "polite" });
    const collapse = el("button", { type: "button", class: "cw-btn cw-collapse", "aria-expanded": "true", "aria-label": "Tuck away camera and voice", title: "Tuck away" }, ["–"]);
    const menuBtn = el("button", { type: "button", class: "cw-btn cw-menu-btn", "aria-haspopup": "menu", "aria-expanded": "false", "aria-label": "Lesson menu", title: "Menu" }, ["⋯"]);
    bar.append(grip, status, collapse, menuBtn);
    const body = el("div", { class: "cw-body" });
    const clockMount = el("div", { class: "cw-clock" });
    const camMount = el("div", { class: "cw-cam" });
    const voiceMount = el("div", { class: "cw-voice" });
    body.append(clockMount, camMount, voiceMount);
    const menu = el("div", { class: "cw-menu", role: "menu", hidden: "" });
    root.append(bar, body, menu);
    document.body.prepend(root);
    cw = { root, status, menu, menuBtn, collapse, camMount, voiceMount };

    // Position: remembered, else a corner clear of the lesson text (which sits along the bottom): top-right in the demo, top-left in the full course.
    const saved = readJson(CW_POS_KEY);
    const hasSaved = Boolean(saved && Number.isFinite(saved.left) && Number.isFinite(saved.top));
    const cornerLeft = () => (options.demo ? window.innerWidth - (root.offsetWidth || 236) - 8 : 8);
    placeCourseWidget(hasSaved ? saved.left : cornerLeft(), hasSaved ? saved.top : 8, false);
    cw.pinnedCorner = !hasSaved;
    window.addEventListener("resize", () => {
      if (cw.pinnedCorner) placeCourseWidget(cornerLeft(), 8, false);
      else placeCourseWidget(parseFloat(root.style.left) || 8, parseFloat(root.style.top) || 8, true);
    });

    // Tuck away / bring back the camera and voice (they keep running; only the view is folded).
    const setCollapsed = (value) => {
      root.dataset.collapsed = value ? "1" : "0";
      collapse.setAttribute("aria-expanded", value ? "false" : "true");
      collapse.textContent = value ? "+" : "–";
      collapse.setAttribute("aria-label", value ? "Show camera and voice" : "Tuck away camera and voice");
      try { window.localStorage.setItem(CW_COLLAPSE_KEY, value ? "1" : "0"); } catch { /* not kept */ }
      requestAnimationFrame(() => placeCourseWidget(parseFloat(root.style.left) || 8, parseFloat(root.style.top) || 8, true));
    };
    let startCollapsed = false;
    try { startCollapsed = window.localStorage.getItem(CW_COLLAPSE_KEY) === "1"; } catch { startCollapsed = false; }
    setCollapsed(startCollapsed);
    collapse.addEventListener("click", () => setCollapsed(root.dataset.collapsed !== "1"));

    // Drag from the grip or any empty part of the bar; arrow keys move the grip when focused.
    let drag = null;
    bar.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target.closest(".cw-btn")) return;
      const rect = root.getBoundingClientRect();
      drag = { id: event.pointerId, dx: event.clientX - rect.left, dy: event.clientY - rect.top };
      try { bar.setPointerCapture(event.pointerId); } catch { /* not supported */ }
      event.preventDefault();
    });
    bar.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      placeCourseWidget(event.clientX - drag.dx, event.clientY - drag.dy, false);
    });
    const endDrag = (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      drag = null;
      cw.pinnedCorner = false;
      placeCourseWidget(parseFloat(root.style.left) || 8, parseFloat(root.style.top) || 8, true);
    };
    bar.addEventListener("pointerup", endDrag);
    bar.addEventListener("pointercancel", endDrag);
    grip.addEventListener("keydown", (event) => {
      const step = event.shiftKey ? 40 : 12;
      const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
      const move = moves[event.key];
      if (!move) return;
      event.preventDefault();
      placeCourseWidget((parseFloat(root.style.left) || 8) + move[0], (parseFloat(root.style.top) || 8) + move[1], true);
    });

    // Menu.
    const closeMenu = (focusButton) => {
      menu.hidden = true;
      menuBtn.setAttribute("aria-expanded", "false");
      if (focusButton) menuBtn.focus({ preventScroll: true });
    };
    const item = (label, onClick) => {
      const node = el("button", { type: "button", role: "menuitem" }, [label]);
      node.addEventListener("click", () => { closeMenu(false); onClick(); });
      return node;
    };
    const buildMenu = () => {
      menu.textContent = "";
      menu.appendChild(item("Help", () => showDemoTutorial(false)));
      const percent = document.getElementById("course-map-percent")?.textContent?.trim();
      menu.appendChild(el("div", { class: "cw-info", role: "presentation" }, [`Progress: ${percent || "0%"}`]));
      const plan = document.getElementById("course-price")?.textContent?.trim();
      if (plan) menu.appendChild(el("div", { class: "cw-info", role: "presentation" }, [`Plan: ${plan}`]));
      const captions = document.getElementById("btn-captions");
      if (captions) {
        const off = captions.classList.contains("is-off");
        menu.appendChild(item(off ? "Captions on" : "Captions off", () => captions.click()));
      }
      const langSource = document.getElementById("teach-lang-stage") || document.getElementById("teach-lang");
      if (langSource && langSource.options && langSource.options.length > 1) {
        const select = el("select", { "aria-label": "Lesson language" });
        for (const option of Array.from(langSource.options)) {
          const o = el("option", { value: option.value }, [option.textContent || option.value]);
          if (option.value === langSource.value) o.selected = true;
          select.appendChild(o);
        }
        select.addEventListener("change", () => { setLanguageSelect(select.value); closeMenu(true); });
        menu.appendChild(select);
      }
      if (supported && consented) menu.appendChild(item(muted ? "Unmute mic" : "Mute mic", () => setMuted(!muted)));
      if (!supported) menu.appendChild(item("Show classic controls", () => reveal("not-supported")));
      menu.appendChild(item("Exit lesson", exitLesson));
    };
    menuBtn.addEventListener("click", () => {
      if (menu.hidden) {
        buildMenu();
        menu.hidden = false;
        menuBtn.setAttribute("aria-expanded", "true");
        menu.querySelector("[role=menuitem], select")?.focus?.({ preventScroll: true });
      } else closeMenu(true);
    });
    root.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !menu.hidden) { event.stopPropagation(); closeMenu(true); }
    });
    document.addEventListener("pointerdown", (event) => {
      if (!menu.hidden && !root.contains(event.target)) closeMenu(false);
    }, true);

    // The camera preview and Sala's voice move into the panel as soon as they exist.
    const adopt = () => {
      const cam = document.getElementById("student-cam");
      if (cam && cam.parentElement !== camMount) camMount.appendChild(cam);
      const live = document.getElementById("theodore-live-audio");
      if (live) {
        live.setAttribute("data-embedded", "");
        if (live.parentElement !== voiceMount) voiceMount.appendChild(live);
      }
      const clock = document.getElementById("sample-clock");
      if (clock && clock.parentElement !== clockMount) clockMount.appendChild(clock);   // the demo's 10-minute timer lives in the widget too
      return Boolean(cam && live);
    };
    adopt();
    let tries = 0;
    const adoptTimer = window.setInterval(() => {
      tries += 1;
      if (adopt() || tries > 60) window.clearInterval(adoptTimer);
    }, 500);
    // Keep adopting if the page re-creates either element later (a language change reloads the voice widget).
    new MutationObserver(() => adopt()).observe(document.body, { childList: true });

    // "You left the camera" and similar notes land in the status line, not in a big banner.
    const aside = document.getElementById("attention-aside");
    if (aside) {
      const mirror = () => { presenceLine = aside.hidden ? "" : (aside.textContent || "").trim(); syncWidgetStatus(); };
      new MutationObserver(mirror).observe(aside, { attributes: true, childList: true, characterData: true, subtree: true });
      mirror();
    }
    syncWidgetStatus();
  }

  function wireCleanCourse() {
    buildCourseWidget();
    wireDemoHelp();
    // One gesture: the first tap on the lesson (not on the panel) starts the lesson and lets Sala listen.
    const first = (event) => {
      if (event.target.closest && event.target.closest("#course-widget, .sala-tutorial")) return;
      if (document.querySelector(".sala-tutorial")) return;
      document.removeEventListener("pointerup", first, true);
      goFullScreenOnPhone();
      if (!(event.target.closest && event.target.closest("#teach-stage"))) clickById("btn-start-voice");
      if (!consented) setConsented(true);
      noteHintSeen();
    };
    document.addEventListener("pointerup", first, true);
  }

  renderOverlay();
  renderTypeToAsk();
  if (options.demo) wireAvatarGesture();
  else if (options.clean) wireCleanCourse();
  else wireDemoHelp();
  wireStageGestures();
  if (consented) startRecognizer();

  return {
    reveal,
    setMuted,
    isListening: () => listening,
    isMuted: () => muted,
    dispose: () => {
      stopRecognizer();
      root.remove();
      document.body.classList.remove("aoep-voice-first", "aoep-voice-revealed", "chrome-hidden");
    },
  };
}

// Auto-boot when the page is Course Studio. Reads URL flags:
//   voicefirst=0  => disable Sala-only mode entirely (debug / A/B)
//   typemode=1    => show the "Type to Sala" accessibility pill
//   lang=xx-XX    => recognizer locale (BCP-47)
(function boot() {
  try {
    const params = new URLSearchParams(window.location.search || "");
    if (params.get("voicefirst") === "0") return;
    const stage = document.getElementById("teach-stage");
    if (!stage) return;
    initCourseVoiceOverlay({
      typeToAsk: params.get("typemode") === "1",
      locale: params.get("lang") || "en-US",
      demo: params.get("demo") === "1",
      // The full course (not the demo) gets the clean layout: the lesson and ONE movable widget.
      clean: params.get("demo") !== "1" && params.get("access") === "full" && params.get("clean") !== "0",
    });
  } catch { /* defensive — never block the player on overlay boot */ }
})();
