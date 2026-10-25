// Sala's hands-on behaviours, shared by the course studio, On the Go and the mobile web view.
// One source: the studio serves it at /api/studio/voice-overlay/sala_interactions.js and the web app imports that URL.
//
//   giggle      tap Sala (a short wobble + a quiet two-note chirp)
//   dance       an EASTER EGG, not in the tutorial: scrub the pointer or a finger quickly side to side across Sala, or say a
//               short "dance" request. Cooldown 10 s, stops on any tap, reduced motion gets a gentle bob.
//   double-tap  touch screens: a real double-tap on the lesson fires "dblclick" even where the browser does not.
//
// Pure helpers (ScrubDetector, matchDanceIntent, DoubleTapDetector) have no DOM access so they can be unit tested in Node.

// ---- scrub gesture -------------------------------------------------------------------------------------------------
export const SCRUB_DEFAULTS = Object.freeze({
  minSwings: 4,           // 4 swings = 3 direction reversals
  windowMs: 1200,         // all swings must fall inside this window
  minAmplitudeFrac: 0.4,  // each swing must cover this share of the avatar width
  cooldownMs: 10000,
});

export class ScrubDetector {
  constructor(options = {}) {
    this.o = { ...SCRUB_DEFAULTS, ...options };
    this.cooldownUntil = 0;
    this.reset();
  }
  reset() {
    this.anchor = null;   // x where the current leg started
    this.cand = null;     // furthest x reached in the current direction
    this.dir = 0;
    this.swings = [];
  }
  /** Feed one pointer sample. Returns true once, when the scrub is recognised. */
  feed(x, t, width) {
    if (!(width > 0) || !Number.isFinite(x) || !Number.isFinite(t)) return false;
    if (t < this.cooldownUntil) return false;
    const need = this.o.minAmplitudeFrac * width;
    if (this.anchor === null) { this.anchor = x; this.cand = x; return false; }
    if (this.dir === 0) {
      if (Math.abs(x - this.anchor) >= need) {
        this.dir = Math.sign(x - this.anchor);
        this.cand = x;
        this.swings.push(t);
      }
    } else if ((x - this.cand) * this.dir >= 0) {
      this.cand = x;                                   // still travelling the same way
    } else if (Math.abs(x - this.cand) >= need) {      // came back far enough: a reversal
      this.anchor = this.cand;
      this.dir = -this.dir;
      this.cand = x;
      this.swings.push(t);
    }
    this.swings = this.swings.filter((s) => t - s <= this.o.windowMs);
    if (this.swings.length >= this.o.minSwings) {
      this.cooldownUntil = t + this.o.cooldownMs;
      this.reset();
      return true;
    }
    return false;
  }
}

// ---- touch double-tap ----------------------------------------------------------------------------------------------
export class DoubleTapDetector {
  constructor({ maxGapMs = 320, maxDistancePx = 32 } = {}) {
    this.maxGapMs = maxGapMs;
    this.maxDistancePx = maxDistancePx;
    this.last = null;
  }
  /** Register a completed tap. Returns true when it is the second tap of a double-tap. */
  tap(x, y, t) {
    const prev = this.last;
    if (prev && t - prev.t <= this.maxGapMs && Math.hypot(x - prev.x, y - prev.y) <= this.maxDistancePx) {
      this.last = null;
      return true;
    }
    this.last = { x, y, t };
    return false;
  }
}

// ---- spoken "dance" intent -----------------------------------------------------------------------------------------
// Short imperative requests only: a question about dancing must still reach Q&A. Non-English lists are machine-drafted.
const EN_FILLER = new Set(("please pls hey hi ok okay sala salareen can could would will you u for me us now just then lets let " +
  "do does a an the some your own little to go and again").split(" "));
const EN_CORE = new Set([
  "dance", "dances", "dancing", "dans", "danse", "dancin", "boogie", "boogy", "groove", "shake", "shake it", "shake shake",
  "shake it off", "show moves", "show dance", "get down", "bust move", "bust moves", "bust it", "start dancing",
  "dance dance", "dance party", "party", "twirl",
]);

function stripMarks(s) {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "d");
}
function normalize(text) {
  return stripMarks(String(text || "").toLowerCase())
    .replace(/[’']/g, "")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}
function lev1(a, b) {          // true when the edit distance is at most 1
  if (a === b) return true;
  if (Math.abs(a.length - b.length) > 1) return false;
  let i = 0; let j = 0; let edits = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { i += 1; j += 1; continue; }
    edits += 1;
    if (edits > 1) return false;
    if (a.length > b.length) i += 1;
    else if (a.length < b.length) j += 1;
    else { i += 1; j += 1; }
  }
  return edits + (a.length - i) + (b.length - j) <= 1;
}
function englishDance(text) {
  const n = normalize(text);
  if (!n) return false;
  const raw = n.split(" ");
  if (raw.length > 8) return false;
  const core = raw.filter((w) => !EN_FILLER.has(w));
  if (!core.length || core.length > 3) return false;
  const phrase = core.join(" ");
  if (EN_CORE.has(phrase)) return true;
  if (core.length === 1 && core[0].length >= 4 && ["dance", "boogie", "shake", "groove"].some((w) => lev1(core[0], w))) return true;
  if (core.length === 2 && core[0] === "shake" && lev1(core[1], "shake")) return true;
  return false;
}

const OTHER = {
  es: ["baila", "bailar", "bailemos", "ponte a bailar", "a bailar", "haz un baile", "baila para mi", "mueve el esqueleto"],
  fr: ["danse", "danser", "dansons", "fais une danse", "danse pour moi", "on danse"],
  de: ["tanz", "tanze", "tanzen", "tanz fur mich", "tanze fur mich", "lass uns tanzen"],
  it: ["balla", "ballare", "balliamo", "fai un ballo", "balla per me"],
  pt: ["danca", "dancar", "vamos dancar", "danca pra mim", "faz uma danca", "dance"],
  vi: ["nhay di", "nhay mua", "nhay mot dieu", "nhay cho toi xem", "nhay nao"],
};
const CJK = {
  zh: ["跳舞", "跳个舞", "跳支舞", "跳一个舞", "来跳舞", "跳一下", "跳舞吧", "跳個舞"],
  yue: ["跳舞", "跳隻舞", "跳只舞", "跳吓舞", "跳下舞", "跳啖舞"],
  ja: ["踊って", "踊れ", "ダンス", "踊ろう", "踊ってみて", "ダンスして", "おどって"],
  ko: ["춤춰", "춤춰줘", "춤춰봐", "춤 춰", "춤을 춰", "춤춰 봐"],
  th: ["เต้น", "เต้นหน่อย", "เต้นให้ดู", "เต้นสิ"],
  km: ["រាំ", "រាំមួយ", "រាំទៅ", "រាំបន្តិច"],
};
const QUESTIONISH = /[吗嗎呢什么什麼為什麼为什么か？?]|\b(why|what|how|when|who|history|hobby)\b/;

function baseLang(lang) {
  const l = String(lang || "en").toLowerCase().replace("_", "-");
  if (l === "zh-hk" || l === "zh-yue" || l.startsWith("yue")) return "yue";
  return l.split("-")[0];
}

/** True for a short "dance" request in English (always) or the given UI language. */
export function matchDanceIntent(text, lang = "en") {
  if (englishDance(text)) return true;
  const base = baseLang(lang);
  if (CJK[base]) {
    const t = String(text || "").trim();
    if (!t || t.length > 14 || QUESTIONISH.test(t)) return false;
    const compact = t.replace(/[\s。！!，,、]/g, "");
    return CJK[base].some((k) => compact.includes(k.replace(/\s/g, "")));
  }
  if (OTHER[base]) {
    const n = normalize(text);
    if (!n || n.split(" ").length > 7 || QUESTIONISH.test(n)) return false;
    const stripped = n.replace(/\b(por favor|s il te plait|bitte|per favore|por favor|lam on)\b/g, "").replace(/\s+/g, " ").trim();
    return OTHER[base].some((k) => stripped === k || stripped.startsWith(k + " ") || stripped.endsWith(" " + k));
  }
  return false;
}

// ---- browser behaviour ---------------------------------------------------------------------------------------------
const STYLE_ID = "sala-interactions-style";
const CSS = `
@keyframes salaDanceMoves {
  0% { transform: none; } 10% { transform: translateX(-7%) rotate(-8deg) scale(1.04,.96); }
  22% { transform: translateX(7%) rotate(8deg) scale(.97,1.05); } 34% { transform: translateY(-9%) rotate(-5deg) scale(1.05); }
  46% { transform: translateX(-6%) rotate(7deg) scale(1.03,.97); } 58% { transform: translateX(6%) translateY(-4%) rotate(-7deg); }
  70% { transform: translateY(-6%) rotate(0) scale(1.06,.95); } 84% { transform: rotateY(360deg) scale(1.04); } 100% { transform: none; } }
@keyframes salaDanceGlow { 0%,100% { filter: drop-shadow(0 6px 12px rgba(201,167,122,.35)); }
  50% { filter: drop-shadow(0 0 18px rgba(240,214,150,.95)) brightness(1.08); } }
@keyframes salaDanceCalm { 0%,100% { transform: none; } 50% { transform: translateY(-3%); } }
@keyframes salaGiggleWobble { 30% { transform: scale(1.06,.92) rotate(-2deg); } 62% { transform: scale(.98,1.05) rotate(2deg); } }
@keyframes salaSpark { 0% { opacity: 0; transform: translateY(0) scale(.4); } 25% { opacity: 1; }
  100% { opacity: 0; transform: translateY(-46px) scale(1.1) rotate(40deg); } }
.sala-dancing { animation: salaDanceMoves 1.2s ease-in-out 4, salaDanceGlow 1.2s ease-in-out 4; transform-origin: 50% 90%; perspective: 600px; }
.sala-dancing-calm { animation: salaDanceCalm 1.6s ease-in-out 3; }
.sala-giggling { animation: salaGiggleWobble .72s ease; transform-origin: 50% 90%; }
.sala-spark { position: absolute; pointer-events: none; color: #e8c97a; font-size: 14px; animation: salaSpark 1.4s ease-out forwards; }
@media (prefers-reduced-motion: reduce) { .sala-dancing, .sala-giggling { animation: salaDanceCalm 1.6s ease-in-out 3; } .sala-spark { display: none; } }
`;
function ensureStyle(doc) {
  if (doc.getElementById(STYLE_ID)) return;
  const s = doc.createElement("style");
  s.id = STYLE_ID;
  s.textContent = CSS;
  doc.head.appendChild(s);
}

function chirp(notes, { volume = 0.03, step = 0.09 } = {}) {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    if (ctx.state === "suspended") ctx.resume?.().catch(() => {});
    const now = ctx.currentTime;
    notes.forEach((hz, i) => {
      const o = ctx.createOscillator(); const g = ctx.createGain();
      o.type = "triangle"; o.frequency.value = hz;
      g.gain.setValueAtTime(0, now + i * step);
      g.gain.linearRampToValueAtTime(volume, now + i * step + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + i * step + step * 1.6);
      o.connect(g); g.connect(ctx.destination);
      o.start(now + i * step); o.stop(now + i * step + step * 1.7);
    });
    window.setTimeout(() => ctx.close?.().catch(() => {}), (notes.length * step + 0.5) * 1000);
  } catch { /* audio is optional */ }
}

export const DANCE_MENU_FLAG_KEY = "aoep.flag.sala_dance_menu";
export function salaDanceMenuEnabled() {
  try { return window.localStorage.getItem(DANCE_MENU_FLAG_KEY) === "1" || window.__AOEP_FLAGS__?.sala_dance_menu === true; }
  catch { return false; }
}

/**
 * Attach giggle / dance / scrub handling to one avatar element.
 * Policy: the dance never talks over narration. Sound is skipped while narration plays, the mic is listening (it would hear
 * the music), or Sala is muted; the visual dance still runs. Voice and scrub triggers share a 10 s cooldown.
 */
export function attachSalaInteractions(el, opts = {}) {
  const doc = el.ownerDocument;
  const o = {
    isNarrating: () => false, isMicListening: () => false, isMuted: () => false, onDance: null, onGiggle: null,
    ignoreSelector: "button, a, input, select, textarea, [role='button'], .avatar-handle, .avatar-grip",
    cooldownMs: SCRUB_DEFAULTS.cooldownMs, durationMs: 4800, ...opts,
  };
  ensureStyle(doc);
  const detector = new ScrubDetector({ cooldownMs: 0 });
  let danceTimer = null; let lastEnd = 0; let suppressClickUntil = 0; let dancing = false; const sparks = [];
  const reduced = () => Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const quiet = () => o.isNarrating() || o.isMicListening() || o.isMuted();

  function clearSparks() { while (sparks.length) sparks.pop().remove(); }
  function stopDance() {
    if (!dancing) return;
    dancing = false;
    window.clearTimeout(danceTimer);
    el.classList.remove("sala-dancing", "sala-dancing-calm");
    clearSparks();
    lastEnd = Date.now();
  }
  function dance(reason = "api") {
    const now = Date.now();
    if (dancing || now - lastEnd < o.cooldownMs) return false;
    dancing = true;
    const calm = reduced();
    el.classList.remove("sala-dancing", "sala-dancing-calm");
    void el.offsetWidth;
    el.classList.add(calm ? "sala-dancing-calm" : "sala-dancing");
    if (!calm) {
      const host = el.style.position ? el : el.parentElement || el;
      for (let i = 0; i < 7; i += 1) {
        const sp = doc.createElement("span");
        sp.className = "sala-spark"; sp.textContent = "✦"; sp.setAttribute("aria-hidden", "true");
        sp.style.left = `${10 + ((i * 37) % 80)}%`; sp.style.top = `${18 + ((i * 23) % 50)}%`; sp.style.animationDelay = `${(i % 4) * 0.35}s`;
        host.appendChild(sp); sparks.push(sp);
      }
    }
    if (!quiet()) chirp([523, 659, 784, 659, 784, 1047, 784, 659], { volume: 0.025, step: 0.28 });
    if (typeof o.onDance === "function") { try { o.onDance(reason); } catch { /* integrator hook */ } }
    danceTimer = window.setTimeout(stopDance, o.durationMs);
    return true;
  }
  function giggle() {
    el.classList.remove("sala-giggling");
    void el.offsetWidth;
    el.classList.add("sala-giggling");
    window.setTimeout(() => el.classList.remove("sala-giggling"), 760);
    if (!o.isNarrating() && !o.isMuted()) chirp([700, 980], { volume: 0.03, step: 0.09 });
    if (typeof o.onGiggle === "function") { try { o.onGiggle(); } catch { /* integrator hook */ } }
  }

  const ignored = (event) => Boolean(event.target?.closest?.(o.ignoreSelector));
  const down = (event) => { if (!ignored(event)) detector.reset(); };
  const move = (event) => {
    if (ignored(event)) return;
    const touchLike = event.pointerType === "touch" || event.pointerType === "pen";
    if (touchLike ? event.buttons !== 1 : event.buttons !== 0) return;   // mouse: hover scrub; touch: finger down on Sala
    const rect = el.getBoundingClientRect();
    if (detector.feed(event.clientX, event.timeStamp || Date.now(), rect.width)) {
      if (touchLike) suppressClickUntil = Date.now() + 700;
      dance("scrub");
    }
  };
  const reset = () => detector.reset();
  // Registered on window in the capture phase so it runs before the studio's own document-level click handler.
  const swallowClick = (event) => {
    if (!el.contains(event.target)) return;
    if (dancing || Date.now() < suppressClickUntil) {
      if (dancing) stopDance();
      event.stopImmediatePropagation(); event.preventDefault();
    }
  };
  el.style.touchAction = "none";    // the avatar only: a finger scrub must not scroll the page
  el.addEventListener("pointerdown", down);
  el.addEventListener("pointermove", move);
  el.addEventListener("pointerup", reset);
  el.addEventListener("pointercancel", reset);
  el.addEventListener("pointerleave", reset);
  window.addEventListener("click", swallowClick, true);
  const onAttention = () => stopDance();
  window.addEventListener("sala:attention", onAttention);
  doc.addEventListener("visibilitychange", () => { if (doc.hidden) stopDance(); });

  return {
    dance, stopDance, giggle, isDancing: () => dancing,
    /** Call from the voice path: true means the utterance was a dance request and must NOT reach Q&A. */
    handleUtterance(text, lang) {
      if (!matchDanceIntent(text, lang)) return false;
      dance("voice");
      return true;
    },
    dispose() {
      stopDance();
      el.removeEventListener("pointerdown", down); el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", reset); el.removeEventListener("pointercancel", reset); el.removeEventListener("pointerleave", reset);
      window.removeEventListener("click", swallowClick, true); window.removeEventListener("sala:attention", onAttention);
    },
  };
}

/** Make a touch double-tap on `stage` fire "dblclick" where the browser does not (iOS Safari, some WebViews). */
export function attachTouchDoubleTap(stage, { ignoreSelector = "button, select, input, textarea, a, [role='button']" } = {}) {
  const detector = new DoubleTapDetector();
  let nativeAt = 0; let downAt = null;
  stage.style.touchAction = stage.style.touchAction || "manipulation";
  stage.addEventListener("dblclick", () => { nativeAt = Date.now(); }, true);
  stage.addEventListener("pointerdown", (e) => { if (e.pointerType === "touch") downAt = { x: e.clientX, y: e.clientY, t: Date.now() }; });
  stage.addEventListener("pointerup", (e) => {
    if (e.pointerType !== "touch" || !downAt) return;
    const moved = Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y);
    const held = Date.now() - downAt.t;
    downAt = null;
    if (moved > 12 || held > 400 || e.target?.closest?.(ignoreSelector)) return;
    if (detector.tap(e.clientX, e.clientY, Date.now())) {
      const target = e.target; const stamp = Date.now();
      // After the click that follows this pointerup, so the studio's click handler has already queued (and now cancels) its timer.
      window.setTimeout(() => {
        if (nativeAt >= stamp) return;       // the browser already fired its own dblclick
        target.dispatchEvent(new MouseEvent("dblclick", { bubbles: true, cancelable: true, clientX: e.clientX, clientY: e.clientY }));
      }, 70);
    }
  });
}

/** Attach `attach(el)` to every avatar element now and whenever one appears later (per-page avatars are created late). */
export const AVATAR_SELECTOR = "[data-sala-avatar], #theodore-avatar-wrap, [data-testid='on-the-go-mascot']";
export function observeAvatars(attach, doc = document) {
  const seen = new WeakSet();
  const scan = () => doc.querySelectorAll(AVATAR_SELECTOR).forEach((node) => { if (!seen.has(node)) { seen.add(node); attach(node); } });
  scan();
  let queued = false;       // the studio mutates its DOM constantly: look at most every 250 ms
  const mo = new MutationObserver(() => {
    if (queued) return;
    queued = true;
    window.setTimeout(() => { queued = false; scan(); }, 250);
  });
  mo.observe(doc.documentElement, { childList: true, subtree: true });
  return () => mo.disconnect();
}
