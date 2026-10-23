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
  };

  if (!document.body) {
    document.addEventListener("DOMContentLoaded", () => initCourseVoiceOverlay(opts), { once: true });
    return null;
  }

  // Hide the chrome by default. The classic CSS .chrome-hidden rule in
  // STUDIO_CSS already does the heavy lifting; .aoep-voice-first just
  // re-applies it alongside tagging the mode for CSS/JS checks.
  document.body.classList.add("aoep-voice-first", "chrome-hidden");
  if (options.demo) document.body.classList.add("demo-clean");

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
    if (consented) return;
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
    for (const node of document.querySelectorAll(".sala-help, .sala-rotate, .sala-tutorial")) mountOnTop(node);
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

  const TUTORIAL_KEY = "sala_demo_tutorial_seen_v1";
  const DEMO_TUTORIAL = [
    {
      icon: "✨", title: "Meet Sala",
      lines: [
        "Tap the Sala picture to start the lesson. Tap it again to turn listening on or off.",
        "Sala teaches out loud. Allow the microphone when your device asks.",
      ],
    },
    {
      icon: "🎙️", title: "Just say it",
      lines: ["Talk to Sala like a teacher. Try:"],
      chips: ["pause", "next", "back", "repeat", "captions on", "full screen", "speak Spanish", "louder", "mute"],
      after: ["Or ask any question about the course."],
    },
    {
      icon: "👆", title: "Tap and double-tap",
      lines: [
        "Tap the lesson to move to the next part.",
        "Double-tap the lesson to go full screen. Double-tap again to leave full screen.",
      ],
    },
    {
      icon: "💡", title: "Good to know",
      lines: [
        "Find a quiet spot so Sala can hear you.",
        "If you step out of the camera's view, the lesson pauses and picks up when you are back.",
        "The free demo runs for 10 minutes.",
      ],
    },
  ];

  function showDemoTutorial(startLesson) {
    document.querySelector(".sala-tutorial")?.remove();
    let step = 0;
    const overlay = document.createElement("div");
    overlay.className = "sala-tutorial";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "How to use this lesson");
    const render = () => {
      const t = DEMO_TUTORIAL[step];
      const last = step === DEMO_TUTORIAL.length - 1;
      const chips = t.chips ? `<ul>${t.chips.map((c) => `<li>${c}</li>`).join("")}</ul>` : "";
      overlay.innerHTML = `
        <div class="card">
          <div class="dots">${DEMO_TUTORIAL.map((_, i) => `<i class="${i === step ? "on" : ""}"></i>`).join("")}</div>
          <div class="icon" aria-hidden="true">${t.icon}</div>
          <h2>${t.title}</h2>
          ${t.lines.map((l) => `<p>${l}</p>`).join("")}${chips}${(t.after || []).map((l) => `<p>${l}</p>`).join("")}
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
    const close = () => {
      try { window.localStorage.setItem(TUTORIAL_KEY, "1"); } catch { /* not kept: shows again next time */ }
      overlay.remove();
      if (startLesson) {
        goFullScreenOnPhone();
        const welcome = document.getElementById("page-welcome");
        if (welcome && !welcome.hidden) clickById("btn-start-voice");
        if (!consented) setConsented(true);
      }
    };
    render();
    mountOnTop(overlay);
  }

  function wireDemoHelp() {
    if (document.querySelector(".sala-help")) return;
    const help = el("button", { type: "button", class: "sala-help", "aria-label": "How to use this lesson", title: "How to use this lesson" }, ["?"]);
    help.addEventListener("click", () => showDemoTutorial(false));
    mountOnTop(help);
    let seen = false;
    try { seen = window.localStorage.getItem(TUTORIAL_KEY) === "1"; } catch { seen = false; }
    if (!seen) showDemoTutorial(true);
  }

  function wireAvatarGesture() {
    wireDemoHelp();
    document.addEventListener("click", (event) => {
      const wrap = event.target.closest && event.target.closest("#theodore-avatar-wrap");
      if (!wrap) return;
      event.stopPropagation();
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

  renderOverlay();
  renderTypeToAsk();
  if (options.demo) wireAvatarGesture();
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
    });
  } catch { /* defensive — never block the player on overlay boot */ }
})();
