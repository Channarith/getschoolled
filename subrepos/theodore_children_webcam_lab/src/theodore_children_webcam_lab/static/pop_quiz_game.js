// Pop Quiz Toss: the playable game (DOM, effects, voice). Logic lives in pop_quiz.js.
//
// A short question appears with two targets. The player can SAY the answer and
// THROW the ball at it. Both right = 5 points, one right = 2, first to 100 wins.
// Camera and microphone stay on the device; nothing here uploads anything.

import {advanceThrowGesture, newThrowTracker} from "./vision_math.js";
import * as Q from "./pop_quiz.js";

const TUTORIAL = [
  {
    icon: "🎯",
    title: "Say it and throw it!",
    lines: [
      "A question pops up with two targets. Say the answer out loud and throw the ball at the right one.",
      "Both right = 5 points. Just one = 2 points. Reach 100 points to win!",
    ],
  },
  {
    icon: "📷",
    title: "Get set up",
    lines: [
      "Stand about two big steps back so your hand and shoulder are in the picture.",
      "Keep your hand inside the picture. If it drifts out, the ball drops. Green tips will tell you to step closer or back.",
      "Face a light and use a plain background. On a phone or without a camera, press and drag on the ball instead.",
    ],
  },
  {
    icon: "✊",
    title: "Grab, pull, throw",
    lines: [
      "✊ Close your fist to grab the ball. Keep it closed.",
      "↩️ Pull your fist back toward you, like a slingshot.",
      "🖐️ Open your hand to throw, toward the answer. Do not open early!",
    ],
    motion: true,
  },
  {
    icon: "🌀",
    title: "Curve balls",
    lines: [
      "Swirl your fist in a circle before you throw, or swing your arm in an arc, to bend the ball.",
      "Curve balls look amazing and can sneak around to the answer you were aiming at.",
    ],
  },
  {
    icon: "💡",
    title: "Pro tips",
    lines: [
      "Close is good enough. Aim toward the side of the right answer and let go.",
      "Big, smooth arm moves work best, especially on a slower camera.",
      "Say the answer clearly while the ball is in your hand. No microphone? You can still throw for 2 points.",
      "Never throw a real object. This is a pretend ball!",
    ],
  },
];

const FIRE = ["🔥", "✨", "💥"];
const TRAILS = [
  ["✨", "⭐", "💫"],
  ["🔥", "🔥", "✨"],
  ["🌈", "✨", "⭐", "💖"],
  ["☄️", "💫", "⭐", "🌟"],
];

function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}

function svg(inner) {
  return `<svg viewBox="0 0 100 100" aria-hidden="true">${inner}</svg>`;
}

function flower(cx, cy, r, petal) {
  const dots = [0, 72, 144, 216, 288].map((a) => {
    const x = cx + Math.cos((a * Math.PI) / 180) * r;
    const y = cy + Math.sin((a * Math.PI) / 180) * r;
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(r * 0.8).toFixed(1)}" fill="${petal}"/>`;
  }).join("");
  return `${dots}<circle cx="${cx}" cy="${cy}" r="${(r * 0.7).toFixed(1)}" fill="#fde047"/>`;
}

const ART = {
  dartboard: svg(
    '<circle cx="50" cy="50" r="48" fill="#1e293b"/><circle cx="50" cy="50" r="42" fill="#ef4444"/>'
    + '<circle cx="50" cy="50" r="33" fill="#fef3c7"/><circle cx="50" cy="50" r="24" fill="#22c55e"/>'
    + '<circle cx="50" cy="50" r="14" fill="#fef3c7"/><circle cx="50" cy="50" r="7" fill="#ef4444"/>',
  ),
  pins: svg(
    '<path d="M50 6C41 6 39 17 42 27C46 38 33 48 33 67C33 85 40 95 50 95C60 95 67 85 67 67C67 48 54 38 58 27C61 17 59 6 50 6Z" fill="#fff" stroke="#94a3b8" stroke-width="2"/>'
    + '<path d="M42 25Q50 31 58 25" stroke="#ef4444" stroke-width="5" fill="none"/>'
    + '<path d="M38 36Q50 43 62 36" stroke="#ef4444" stroke-width="4" fill="none"/>'
    + '<circle cx="44" cy="62" r="3" fill="#1f2937"/><circle cx="56" cy="62" r="3" fill="#1f2937"/>'
    + '<path d="M44 72Q50 78 56 72" stroke="#1f2937" stroke-width="2.5" fill="none" stroke-linecap="round"/>',
  ),
  teddy: svg(
    '<circle cx="24" cy="24" r="15" fill="#b45309"/><circle cx="76" cy="24" r="15" fill="#b45309"/>'
    + '<circle cx="24" cy="24" r="8" fill="#fcd34d"/><circle cx="76" cy="24" r="8" fill="#fcd34d"/>'
    + '<circle cx="50" cy="54" r="36" fill="#d97706"/><ellipse cx="50" cy="66" rx="15" ry="12" fill="#fde68a"/>'
    + '<ellipse cx="50" cy="60" rx="5.5" ry="4" fill="#1f2937"/>'
    + '<circle cx="37" cy="47" r="4.5" fill="#1f2937"/><circle cx="63" cy="47" r="4.5" fill="#1f2937"/>'
    + '<circle cx="38.5" cy="45.5" r="1.4" fill="#fff"/><circle cx="64.5" cy="45.5" r="1.4" fill="#fff"/>'
    + '<path d="M44 70Q50 76 56 70" stroke="#1f2937" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
    + '<circle cx="30" cy="62" r="5" fill="#fb7185" opacity=".55"/><circle cx="70" cy="62" r="5" fill="#fb7185" opacity=".55"/>',
  ),
  bouquet: svg(
    '<path d="M50 56V80" stroke="#16a34a" stroke-width="4"/>'
    + '<ellipse cx="30" cy="52" rx="12" ry="5" fill="#22c55e" transform="rotate(-25 30 52)"/>'
    + '<ellipse cx="70" cy="52" rx="12" ry="5" fill="#22c55e" transform="rotate(25 70 52)"/>'
    + flower(33, 36, 8, "#f472b6") + flower(67, 36, 8, "#a78bfa") + flower(50, 22, 8, "#fb923c")
    + '<path d="M26 58L74 58L58 96L42 96Z" fill="#f9a8d4" stroke="#ec4899" stroke-width="2"/>'
    + '<path d="M34 66L66 66" stroke="#ec4899" stroke-width="2"/>',
  ),
};

export function createPopQuizGame(d) {
  const {state, $, stage, spriteLayer} = d;
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  const pq = {
    active: false,
    phase: "idle", // idle | tutorial | play | won
    points: 0,
    rounds: 0,
    streak: 0,
    bestStreak: 0,
    index: 0,
    round: null,
    targets: [],
    ball: null,
    tracker: newThrowTracker(),
    voice: false,
    heard: "",
    thrown: null,
    flying: false,
    resolving: false,
    bank: null,
    progress: Q.loadProgress(localStorage),
    level: 1,
    rec: null,
    micOk: true,
    listening: false,
    hud: null,
    coachAt: 0,
    lastSeen: 0,
    timers: new Set(),
    startedRoundAt: 0,
    audio: null,
    sessionTotalStart: 0,
  };
  pq.level = Q.levelFor(pq.progress.total);
  window.addEventListener("resize", () => { if (pq.active) placeTargets(); });

  // ---- small helpers -------------------------------------------------------------

  function later(fn, ms) {
    const id = setTimeout(() => {
      pq.timers.delete(id);
      fn();
    }, ms);
    pq.timers.add(id);
    return id;
  }

  function clearTimers() {
    for (const id of pq.timers) clearTimeout(id);
    pq.timers.clear();
  }

  function box() {
    return d.stageBox();
  }

  function sfx(kind) {
    if (state.muted) return;
    try {
      pq.audio = pq.audio || new (window.AudioContext || window.webkitAudioContext)();
      const ctx = pq.audio;
      const notes = {
        whoosh: [[300, 0.12, "sawtooth"], [180, 0.12, "sawtooth"]],
        ding: [[660, 0.1, "triangle"], [880, 0.18, "triangle"]],
        perfect: [[660, 0.09, "triangle"], [880, 0.09, "triangle"], [1320, 0.22, "triangle"]],
        nope: [[220, 0.14, "sine"], [165, 0.2, "sine"]],
        win: [[523, 0.1, "triangle"], [659, 0.1, "triangle"], [784, 0.1, "triangle"], [1047, 0.3, "triangle"]],
        unlock: [[784, 0.1, "square"], [988, 0.1, "square"], [1319, 0.25, "square"]],
      }[kind] || [];
      let t = ctx.currentTime;
      for (const [freq, len, type] of notes) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type;
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.08, t + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + len);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + len + 0.02);
        t += len * 0.8;
      }
    } catch (_) {
      // Sound is a bonus; never let it break play.
    }
  }

  // ---- effects --------------------------------------------------------------------

  function fx(className, html, x, y, ms, vars = {}) {
    const el = document.createElement("span");
    el.className = `pq-fx ${className}`;
    el.innerHTML = html;
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    for (const [k, v] of Object.entries(vars)) el.style.setProperty(k, v);
    spriteLayer.append(el);
    setTimeout(() => el.remove(), ms);
    return el;
  }

  function burst(x, y, emojis, count, spread = 170) {
    const n = reduced ? Math.ceil(count / 3) : count;
    for (let i = 0; i < n; i += 1) {
      const a = Math.random() * Math.PI * 2;
      const dist = spread * (0.4 + Math.random() * 0.8);
      fx("pq-burst", pick(emojis), x, y, 950, {
        "--dx": `${Math.cos(a) * dist}px`,
        "--dy": `${Math.sin(a) * dist - 30}px`,
        "--rot": `${Math.round(Math.random() * 540 - 270)}deg`,
        "--s": `${(0.8 + Math.random() * 1.1).toFixed(2)}`,
      });
    }
  }

  function shockwave(x, y, color = "#fde047") {
    if (reduced) return;
    fx("pq-wave", "", x, y, 700, {"--c": color});
  }

  function floatText(x, y, text, kind = "") {
    const {w} = box();
    fx(`pq-float ${kind}`, text, Math.max(110, Math.min(w - 110, x)), y, 1300);
  }

  function confetti(n = 46) {
    const {w} = box();
    const colors = ["#fde047", "#fb7185", "#34d399", "#60a5fa", "#c084fc", "#f97316"];
    for (let i = 0; i < (reduced ? 12 : n); i += 1) {
      const el = fx("pq-confetti", "", Math.random() * w, -12, 2300, {
        "--c": pick(colors),
        "--dx": `${Math.round(Math.random() * 180 - 90)}px`,
        "--delay": `${Math.round(Math.random() * 500)}ms`,
        "--rot": `${Math.round(Math.random() * 720)}deg`,
      });
      el.style.background = pick(colors);
    }
  }

  function shake() {
    if (reduced) return;
    stage.classList.remove("pq-shake");
    void stage.offsetWidth;
    stage.classList.add("pq-shake");
    later(() => stage.classList.remove("pq-shake"), 450);
  }

  function flash(color) {
    if (reduced) return;
    fx("pq-flash", "", 0, 0, 500, {"--c": color});
  }

  function banner(text, kind = "") {
    if (!pq.hud) return;
    const el = pq.hud.querySelector(".pq-banner");
    if (!el) return;
    el.textContent = text;
    el.className = `pq-banner show ${kind}`;
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove("show"), 1700);
  }

  // ---- HUD -------------------------------------------------------------------------

  function ensureHud() {
    if (pq.hud?.isConnected) return pq.hud;
    const el = document.createElement("div");
    el.className = "pq-hud";
    el.innerHTML = `
      <div class="pq-top">
        <div class="pq-score" aria-live="polite"><b class="pq-pts">0</b><small>/ ${Q.GOAL_POINTS}</small></div>
        <div class="pq-bar" role="progressbar" aria-valuemin="0" aria-valuemax="${Q.GOAL_POINTS}"><i></i></div>
        <div class="pq-streak" title="Points in a row">🔥<b>0</b></div>
        <div class="pq-level" title="Your level">Lv <b>1</b></div>
        <button type="button" class="pq-help" aria-label="How to play">?</button>
      </div>
      <div class="pq-question" role="status" aria-live="polite">
        <div class="pq-q">Getting your question…</div>
        <div class="pq-chips" aria-hidden="true"><span class="pq-chip pq-voice">🎤 Say it</span><span class="pq-chip pq-throw">🎯 Throw it</span></div>
      </div>
      <div class="pq-banner" role="status"></div>
      <div class="pq-coach" role="status" aria-live="polite"></div>
      <div class="pq-heard" aria-live="polite"></div>`;
    stage.append(el);
    document.body.classList.add("pq-playing");
    el.querySelector(".pq-help").addEventListener("click", () => showTutorial(true));
    pq.hud = el;
    renderHud();
    return el;
  }

  function renderHud() {
    const el = pq.hud;
    if (!el) return;
    el.querySelector(".pq-pts").textContent = String(pq.points);
    el.querySelector(".pq-bar i").style.width = `${Math.min(100, (pq.points / Q.GOAL_POINTS) * 100)}%`;
    el.querySelector(".pq-bar").setAttribute("aria-valuenow", String(pq.points));
    const streak = el.querySelector(".pq-streak");
    streak.querySelector("b").textContent = String(pq.streak);
    streak.dataset.tier = String(Q.streakTier(pq.streak).tier);
    el.querySelector(".pq-level b").textContent = String(pq.level);
    const voice = el.querySelector(".pq-voice");
    voice.classList.toggle("ok", pq.voice);
    voice.classList.toggle("off", !pq.micOk);
    voice.textContent = !pq.micOk ? "🎤 Mic off" : pq.voice ? "🎤 Got it ✓" : "🎤 Say it";
    const thrown = el.querySelector(".pq-throw");
    thrown.classList.toggle("ok", pq.thrown?.correct === true);
    thrown.classList.toggle("bad", pq.thrown?.correct === false);
    thrown.textContent = pq.thrown ? (pq.thrown.correct ? "🎯 Hit ✓" : "🎯 Other one") : "🎯 Throw it";
  }

  function coach(key) {
    const el = pq.hud?.querySelector(".pq-coach");
    if (!el) return;
    const now = performance.now();
    if (!key) {
      if (now - pq.coachAt > 1400) el.classList.remove("show");
      return;
    }
    el.textContent = Q.COACH_TEXT[key] || "";
    el.classList.add("show");
    pq.coachAt = now;
  }

  // ---- tutorial --------------------------------------------------------------------

  function showTutorial(force = false) {
    ensureHud();
    let seen = false;
    try {
      seen = localStorage.getItem(Q.TUTORIAL_KEY) === "1";
    } catch (_) {
      seen = false;
    }
    if (seen && !force) return false;
    stage.querySelector(".pq-tutorial")?.remove();
    stopVoice();
    pq.phase = "tutorial";
    let step = 0;
    const overlay = document.createElement("div");
    overlay.className = "pq-tutorial";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "How to play Pop Quiz Toss");
    const render = () => {
      const s = TUTORIAL[step];
      const last = step === TUTORIAL.length - 1;
      overlay.innerHTML = `
        <div class="pq-card">
          <div class="pq-dots">${TUTORIAL.map((_, i) => `<i class="${i === step ? "on" : ""}"></i>`).join("")}</div>
          <div class="pq-icon${s.motion ? " motion" : ""}" aria-hidden="true">${s.motion ? '<span class="a">✊</span><span class="b">↩️</span><span class="c">🖐️</span>' : s.icon}</div>
          <h2>${s.title}</h2>
          ${s.lines.map((l) => `<p>${l}</p>`).join("")}
          <div class="pq-actions">
            <button type="button" class="pq-skip">${last ? "Back" : "Skip"}</button>
            ${step > 0 ? '<button type="button" class="pq-prev">◀</button>' : ""}
            <button type="button" class="pq-next">${last ? "Let's play!" : "Next ▶"}</button>
          </div>
        </div>`;
      overlay.querySelector(".pq-next").onclick = () => (last ? close() : (step += 1, render()));
      overlay.querySelector(".pq-prev")?.addEventListener("click", () => { step -= 1; render(); });
      overlay.querySelector(".pq-skip").onclick = () => (last ? (step = 0, render()) : close());
      overlay.querySelector(".pq-next").focus?.();
    };
    const close = () => {
      try {
        localStorage.setItem(Q.TUTORIAL_KEY, "1");
      } catch (_) {
        // Not kept: the tutorial simply shows again next time.
      }
      overlay.remove();
      pq.phase = "play";
      startVoice();
      d.chooseGame();
    };
    render();
    stage.append(overlay);
    return true;
  }

  // ---- voice ---------------------------------------------------------------------------

  function startVoice() {
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Ctor) {
      pq.micOk = false;
      renderHud();
      return;
    }
    if (pq.rec || pq.phase !== "play") return;
    const rec = new Ctor();
    rec.lang = "en-US";
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 3;
    rec.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        for (let a = 0; a < result.length; a += 1) onHeard(result[a].transcript, result.isFinal);
      }
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        pq.micOk = false;
        pq.listening = false;
        renderHud();
      }
    };
    rec.onend = () => {
      pq.rec = null;
      pq.listening = false;
      if (pq.active && pq.phase === "play" && pq.micOk) later(startVoice, 250);
    };
    try {
      rec.start();
      pq.rec = rec;
      pq.listening = true;
      pq.micOk = true;
    } catch (_) {
      pq.rec = null;
    }
    renderHud();
  }

  function stopVoice() {
    const rec = pq.rec;
    pq.rec = null;
    pq.listening = false;
    if (rec) {
      rec.onend = null;
      try { rec.stop(); } catch (_) { /* already stopped */ }
    }
  }

  function onHeard(text, isFinal) {
    if (!pq.round || pq.resolving || pq.phase !== "play") return;
    // Ignore the question being read out loud, and the first beat of a round.
    if (window.speechSynthesis?.speaking || performance.now() - pq.startedRoundAt < 900) return;
    const said = String(text || "").trim();
    if (!said) return;
    if (!pq.voice && Q.answerMatches(said, pq.round.answer)) {
      pq.voice = true;
      const {w, h} = box();
      floatText(w / 2, h * 0.2, "🎤 Nice answer!", "voice");
      burst(w / 2, h * 0.22, ["🎵", "✨", "💬"], 8, 120);
      sfx("ding");
      renderHud();
      if (pq.thrown) settle();
      else {
        banner("Now throw it for more points!", "tip");
        // Voice only: give the throw a fair window before scoring.
        later(() => { if (!pq.thrown && !pq.resolving) finish(); }, 9000);
      }
    } else if (isFinal) {
      const el = pq.hud?.querySelector(".pq-heard");
      if (el) {
        el.textContent = `I heard "${said.slice(0, 40)}"`;
        el.classList.add("show");
        clearTimeout(el._t);
        el._t = setTimeout(() => el.classList.remove("show"), 2200);
      }
    }
  }

  // The typed answer box and Check button feed the same matcher.
  function typedAnswer(text) {
    onHeard(text, true);
  }

  // ---- rounds -------------------------------------------------------------------------------

  async function loadBank() {
    if (pq.bank) return pq.bank;
    try {
      const response = await fetch("/static/quiz_bank.json");
      if (response.ok) pq.bank = await response.json();
    } catch (_) {
      pq.bank = null;
    }
    return pq.bank || Q.EMERGENCY_BANK;
  }

  async function fetchRound(index) {
    try {
      const response = await fetch(`/api/child/quiz-round?age=${encodeURIComponent(state.age)}&index=${index}`);
      if (!response.ok) throw new Error(String(response.status));
      return await response.json();
    } catch (_) {
      return Q.quizRound(await loadBank(), state.age, index);
    }
  }

  function validRound(round) {
    return round && typeof round.question === "string" && typeof round.answer === "string"
      && Array.isArray(round.choices) && round.choices.length === 2
      && round.choices.every((c) => typeof c === "string") && round.choices.includes(round.answer);
  }

  function labelClass(text) {
    const len = String(text).length;
    return len <= 5 ? "len-s" : len <= 9 ? "len-m" : "len-l";
  }

  function renderTargets(round, theme) {
    for (const node of [...spriteLayer.querySelectorAll(".pq-target")]) node.remove();
    pq.targets = round.choices.map((answer, i) => {
      const el = document.createElement("div");
      el.className = `pq-target theme-${theme}`;
      el.dataset.answer = answer;
      el.setAttribute("role", "img");
      el.setAttribute("aria-label", `Answer ${answer}`);
      el.style.left = `${(i === 0 ? 0.2 : 0.8) * 100}%`;
      el.innerHTML = `<span class="pq-art">${ART[theme]}</span><span class="pq-label ${labelClass(answer)}">${answer}</span>`;
      spriteLayer.append(el);
      return {answer, el};
    });
    placeTargets();
  }

  // Fit the targets into the free band between the question card and the score
  // bar, whatever the screen: smaller art on a short phone, bigger on a tablet.
  function placeTargets() {
    if (!pq.targets.length || !pq.hud) return;
    const st = stage.getBoundingClientRect();
    const q = pq.hud.querySelector(".pq-question")?.getBoundingClientRect();
    const bar = pq.hud.querySelector(".pq-top")?.getBoundingClientRect();
    const top = (q ? q.bottom - st.top : 0) + 10;
    const bottom = (bar ? bar.top - st.top : st.height) - 10;
    const labelH = 46;
    const wanted = Math.max(120, Math.min(210, Math.min(st.width, st.height) * 0.24));
    const art = Math.max(70, Math.min(wanted, bottom - top - labelH));
    const center = top + (art + labelH) / 2;
    for (const item of pq.targets) {
      item.el.style.setProperty("--pq-art", `${Math.round(art)}px`);
      item.el.style.top = `${Math.round(center)}px`;
    }
  }

  function targetCenters() {
    const root = stage.getBoundingClientRect();
    const minSide = Math.min(box().w || 0, box().h || 0);
    return pq.targets.map((item) => {
      const art = item.el.querySelector(".pq-art").getBoundingClientRect();
      return {
        ...item,
        x: art.left - root.left + art.width / 2,
        y: art.top - root.top + art.height / 2,
        // Generous: the whole art plus a margin, and never smaller than the lab's catch radius.
        radius: Math.max(d.catchRadius(), art.width * 0.75, minSide * 0.14),
      };
    });
  }

  function ensureBall(emoji) {
    if (pq.ball?.isConnected) return pq.ball;
    const el = document.createElement("div");
    el.className = "pq-ball";
    el.setAttribute("aria-hidden", "true");
    el.textContent = emoji;
    spriteLayer.append(el);
    pq.ball = el;
    return el;
  }

  function ballAt(point, animate = false) {
    if (!point) return;
    const el = ensureBall(pq.ballEmoji || "⚽");
    el.style.transition = animate ? "left .12s linear,top .12s linear" : "none";
    el.style.left = `${point.x}px`;
    el.style.top = `${point.y}px`;
  }

  function dropBall() {
    pq.ball?.remove();
    pq.ball = null;
  }

  async function arm(roundId) {
    pq.active = true;
    ensureHud();
    if (pq.phase === "tutorial") return;
    if (pq.phase === "idle" && showTutorial(false)) return;
    if (pq.phase === "idle") {
      pq.phase = "play";
      startVoice();
    }
    if (pq.phase === "won") return;
    const data = await fetchRound(pq.index);
    if (state.roundId !== roundId || state.game !== "pop-quiz-toss") return;
    if (!validRound(data)) {
      d.setPrompt("Pop Quiz Toss", "I could not load a question. Try again in a moment.");
      return;
    }
    pq.round = data;
    pq.voice = false;
    pq.thrown = null;
    pq.flying = false;
    pq.resolving = false;
    pq.heard = "";
    pq.tracker = newThrowTracker();
    pq.startedRoundAt = performance.now();
    pq.level = Q.levelFor(pq.progress.total);
    pq.ballEmoji = Q.ballFor(pq.index, pq.level);
    const qEl = pq.hud?.querySelector(".pq-q");
    if (qEl) qEl.textContent = data.question;
    renderTargets(data, Q.themeFor(pq.index, pq.level));
    dropBall();
    renderHud();
    d.setPrompt(
      data.question,
      "Say the answer, then grab the ball with a fist, pull back, and open your hand to throw it at the right target.",
      data.speak,
    );
    d.tellActivity(data.speak, {force: true});
    d.speak(data.speak);
    // A question that nobody touches should not trap the game.
    later(() => { if (pq.round === data && !pq.resolving && !pq.thrown && !pq.voice) skipRound(); }, 45000);
  }

  function skipRound() {
    banner("Let's try another one!", "tip");
    pq.index += 1;
    pq.resolving = true;
    state.roundDone = true;
    later(() => { state.roundDone = false; d.chooseGame(); }, 900);
  }

  // ---- throwing -----------------------------------------------------------------------------

  function handOf() {
    return [...state.handData]
      .filter((hand) => hand?.wrist && (hand.screen || hand.points?.length))
      .sort((a, b) => (Number(b.scale) || 0) - (Number(a.scale) || 0))[0] || null;
  }

  function update(now = performance.now(), handOverride = null) {
    if (state.game !== "pop-quiz-toss" || pq.phase !== "play" || !pq.round || pq.resolving || pq.flying || state.roundDone) return;
    const hand = handOverride || handOf();
    const b = box();
    const minSide = Math.min(b.w, b.h) || 1;
    const palm = hand?.screen ? Math.max(36, minSide * 0.08) : (Number(hand?.scale) || 0) * minSide;
    if (hand) pq.lastSeen = now;
    coach(Q.coachHint({
      seen: Boolean(hand),
      msSinceSeen: pq.lastSeen ? now - pq.lastSeen : 0,
      wrist: hand?.wrist && !hand.screen ? {x: hand.wrist.x / (b.w || 1), y: hand.wrist.y / (b.h || 1)} : null,
      palmFraction: hand && !hand.screen ? Number(hand.scale) || 0 : 0,
    }));
    const wasActive = pq.tracker.phase === "grabbed" || pq.tracker.phase === "cocked";
    const step = advanceThrowGesture(
      pq.tracker,
      hand ? {at: now, palm: Math.max(1, palm), fist: Boolean(hand.fist), point: hand.wrist} : {at: now},
      state.age,
    );
    pq.tracker = step.tracker;
    const phase = step.tracker.phase;
    if (window.__pqTrace) window.__pqTrace.push({at: Math.round(now), hand: Boolean(hand), fist: Boolean(hand?.fist), phase, event: step.event});
    if (hand?.wrist && (phase === "grabbed" || phase === "cocked")) {
      ballAt(hand.wrist);
      const turn = Math.abs(Q.orbitTurn(step.tracker.orbit || []));
      pq.ball?.classList.toggle("spin", turn > Math.PI);
      pq.ball?.classList.toggle("curve-ready", turn >= 1.5 * Math.PI);
      if (turn >= 1.5 * Math.PI && !pq.curveTold) {
        pq.curveTold = true;
        banner("🌀 Curve ball ready!", "curve");
      }
    }
    if (step.event === "grabbed") d.setPrompt(pq.round.question, "Great grab! Keep your fist closed and pull it back.");
    else if (step.event === "cocked") d.setPrompt(pq.round.question, "Now open your hand and throw it at the answer!");
    else if (step.event === "released-early") banner("Keep your fist closed until you throw", "tip");
    else if (step.event === "lost" && wasActive) { dropBall(); pq.curveTold = false; banner("Hand lost. Show your fist again", "tip"); }
    else if (step.event === "released" && step.release) launch(step.release);
  }

  function launch(release) {
    pq.curveTold = false;
    const targets = targetCenters();
    const result = Q.resolveThrow(release, targets);
    const b = box();
    if (result.miss || !result.target) {
      dropBall();
      banner("Throw toward one of the answers", "tip");
      pq.tracker = newThrowTracker();
      return;
    }
    pq.flying = true;
    sfx("whoosh");
    const start = {x: release.origin.x, y: release.origin.y};
    const end = result.end;
    const tier = Q.streakTier(pq.streak).tier;
    const curved = Math.abs(result.curve) >= 0.3;
    const ball = ensureBall(pq.ballEmoji || "⚽");
    ball.classList.remove("spin", "curve-ready");
    ball.dataset.tier = String(tier);
    ball.classList.add("flying");
    if (curved) banner(result.kind === "spin" ? "🌀 CURVE BALL!" : "↪️ Nice curve!", "curve");
    const duration = reduced ? 160 : curved ? 640 : 480;
    const startedAt = performance.now();
    let lastTrail = 0;
    const step = () => {
      const t = Math.min(1, (performance.now() - startedAt) / duration);
      const eased = 1 - (1 - t) ** 2.2;
      const p = Q.curvePoint(start, result.control, end, eased);
      ball.style.left = `${p.x}px`;
      ball.style.top = `${p.y}px`;
      ball.style.setProperty("--shrink", String(1 - 0.35 * eased));
      ball.style.setProperty("--spin", `${Math.round(eased * (curved ? 900 : 360))}deg`);
      const nowMs = performance.now();
      if (!reduced && nowMs - lastTrail > 28) {
        lastTrail = nowMs;
        fx("pq-trail", pick(TRAILS[Math.min(3, tier)]), p.x, p.y, 650, {
          "--dx": `${Math.round(Math.random() * 30 - 15)}px`,
          "--dy": `${Math.round(Math.random() * 30 - 15)}px`,
          "--s": `${(0.6 + Math.random() * 0.9).toFixed(2)}`,
        });
      }
      if (t < 1) requestAnimationFrame(step);
      else landed(result, end, curved);
    };
    requestAnimationFrame(step);
  }

  function landed(result, end, curved) {
    pq.flying = false;
    dropBall();
    const target = result.target;
    const correct = target.answer === pq.round.answer;
    pq.thrown = {correct, curved, perfect: Boolean(result.perfect), accuracy: result.accuracy};
    target.el.classList.add(correct ? "hit" : "miss");
    shockwave(end.x, end.y, correct ? "#fde047" : "#94a3b8");
    burst(end.x, end.y, correct ? pick([FIRE, ["⭐", "✨", "🎉"], ["💖", "✨", "🌟"], ["🌸", "✨", "💫"]]) : ["💨", "😅"], correct ? 14 : 5);
    if (correct) {
      shake();
      sfx(result.perfect ? "perfect" : "ding");
      if (result.perfect) floatText(end.x, end.y - 40, "PERFECT!", "perfect");
    } else {
      sfx("nope");
    }
    renderHud();
    settle();
  }

  // After a throw: wait a moment for the spoken answer, unless it is already in or no mic.
  function settle() {
    if (pq.resolving) return;
    if (pq.voice || !pq.micOk || !pq.listening) {
      finish();
      return;
    }
    banner("Say the answer too for bonus points!", "tip");
    later(() => { if (!pq.resolving) finish(); }, 3800);
  }

  function finish() {
    if (pq.resolving || !pq.round) return;
    pq.resolving = true;
    const voice = pq.voice;
    const throwHit = pq.thrown?.correct === true;
    const points = Q.roundPoints({voice, throwHit});
    const before = pq.level;
    pq.points += points;
    pq.rounds += 1;
    pq.streak = Q.nextStreak(pq.streak, points);
    pq.bestStreak = Math.max(pq.bestStreak, pq.streak);
    pq.progress.total += points;
    pq.progress.best = Math.max(pq.progress.best, pq.points);
    pq.progress.bestStreak = Math.max(pq.progress.bestStreak, pq.streak);
    pq.level = Q.levelFor(pq.progress.total);
    Q.saveProgress(localStorage, pq.progress);
    pq.index += 1;
    const {w, h} = box();
    const tier = Q.streakTier(pq.streak);
    const correctTarget = pq.targets.find((t) => t.answer === pq.round.answer);
    if (!throwHit) correctTarget?.el.classList.add("reveal");
    if (points === Q.POINTS_BOTH) {
      floatText(w / 2, h * 0.34, `+${points} PERFECT!`, "perfect");
      confetti(30);
      flash("#fde04755");
    } else if (points > 0) {
      floatText(w / 2, h * 0.34, `+${points}`, "good");
    } else {
      floatText(w / 2, h * 0.34, `It was ${pq.round.answer}`, "learn");
    }
    if (tier.tier > 0 && points > 0 && pq.streak % 1 === 0 && Q.streakTier(pq.streak - 1).tier !== tier.tier) {
      banner(tier.label, `tier${tier.tier}`);
      burst(w / 2, h * 0.3, tier.tier >= 2 ? ["🌈", "⭐", "💫", "🔥"] : FIRE, 18, 220);
    } else if (pq.streak >= 2 && points > 0) {
      banner(`${pq.streak} in a row!`, "streak");
    }
    if (pq.level > before) {
      const reward = Q.UNLOCKS[pq.level - 1];
      later(() => {
        banner(`🎉 Level ${pq.level}! New ${reward.theme ? "ball and target" : "ball"} ${reward.ball}`, "unlock");
        sfx("unlock");
        confetti(40);
      }, 1100);
    }
    renderHud();
    state.roundDone = true;
    state.combo = pq.streak;
    const result = d.calculateFun(points > 0);
    state.fun = result.score;
    d.renderScore();
    d.recordEvent(points > 0 ? "success" : "retry", result);
    d.tellActivity(
      points > 0
        ? `The player scored ${points} points. Celebrate in one short sentence. Do not ask another question.`
        : `The player missed. Encourage them in one short sentence. The answer was ${pq.round.answer}.`,
      {force: true},
    );
    const hold = points === Q.POINTS_BOTH ? 1700 : points > 0 ? 1500 : 2200;
    later(() => {
      if (Q.hasWon(pq.points)) { win(); return; }
      state.roundDone = false;
      d.chooseGame();
    }, hold);
  }

  // ---- winning ----------------------------------------------------------------------------------

  function win() {
    pq.phase = "won";
    pq.progress.wins += 1;
    Q.saveProgress(localStorage, pq.progress);
    stopVoice();
    sfx("win");
    confetti(90);
    const stars = Q.starsFor(pq.rounds, pq.points);
    const next = Q.nextUnlock(pq.progress.total);
    const el = document.createElement("div");
    el.className = "pq-win";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-label", "You won");
    el.innerHTML = `
      <div class="pq-card">
        <div class="pq-icon" aria-hidden="true">🏆</div>
        <h2>${pq.points} points! You win!</h2>
        <div class="pq-stars" aria-label="${stars} stars">${"★".repeat(stars)}${"☆".repeat(3 - stars)}</div>
        <p>${pq.rounds} ${pq.rounds === 1 ? "question" : "questions"} · best streak ${pq.bestStreak} · level ${pq.level}</p>
        ${next ? `<p class="pq-next-unlock">${next.remaining} more points to unlock ${next.reward.ball}${next.reward.theme ? " and a new target" : ""}</p>` : '<p class="pq-next-unlock">Every ball and target unlocked!</p>'}
        <div class="pq-actions"><button type="button" class="pq-again">Play again</button></div>
      </div>`;
    stage.append(el);
    el.querySelector(".pq-again").onclick = () => {
      el.remove();
      pq.points = 0;
      pq.rounds = 0;
      pq.streak = 0;
      pq.bestStreak = 0;
      pq.phase = "play";
      startVoice();
      renderHud();
      state.roundDone = false;
      d.chooseGame();
    };
    el.querySelector(".pq-again").focus?.();
  }

  // ---- lifecycle ----------------------------------------------------------------------------------

  // While the fist is pulled back, show the line the ball will fly along.
  function drawGuide(ctx) {
    const t = pq.tracker;
    if (!ctx || pq.phase !== "play" || t?.phase !== "cocked" || !t.grabPoint || !t.cockPoint) return;
    const dx = t.grabPoint.x - t.cockPoint.x;
    const dy = t.grabPoint.y - t.cockPoint.y;
    const length = Math.max(1, Math.hypot(dx, dy));
    const b = box();
    const reach = Math.max(b.w, b.h);
    ctx.save();
    ctx.strokeStyle = "#fde047";
    ctx.lineWidth = 5;
    ctx.setLineDash([12, 9]);
    ctx.beginPath();
    ctx.moveTo(t.cockPoint.x, t.cockPoint.y);
    ctx.lineTo(t.cockPoint.x + (dx / length) * reach, t.cockPoint.y + (dy / length) * reach);
    ctx.stroke();
    ctx.restore();
  }

  function cancelThrow() {
    pq.tracker = newThrowTracker();
    pq.curveTold = false;
    if (!pq.flying) dropBall();
  }

  function clearRoundVisuals() {
    for (const node of [...spriteLayer.querySelectorAll(".pq-target,.pq-ball,.pq-fx")]) node.remove();
    pq.targets = [];
    pq.ball = null;
    pq.round = pq.resolving ? pq.round : null;
  }

  function teardown() {
    pq.active = false;
    clearTimers();
    stopVoice();
    clearRoundVisuals();
    stage.querySelector(".pq-tutorial")?.remove();
    stage.querySelector(".pq-win")?.remove();
    pq.hud?.remove();
    pq.hud = null;
    document.body.classList.remove("pq-playing");
    pq.phase = "idle";
    pq.round = null;
    pq.resolving = false;
    pq.flying = false;
  }

  return {
    arm,
    update,
    cancelThrow,
    drawGuide,
    teardown,
    typedAnswer,
    startVoice,
    showTutorial,
    clearRoundVisuals,
    onHeard,
    isActive: () => pq.active,
    // Only when a test has turned on tracing: lets a test jump near the goal.
    setPointsForTest: (points) => { if (window.__pqTrace) { pq.points = Number(points) || 0; renderHud(); } },
    snapshot: () => ({points: pq.points, streak: pq.streak, phase: pq.phase, rounds: pq.rounds, index: pq.index, question: pq.round?.question || ""}),
  };
}
