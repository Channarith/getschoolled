"use client";

// Kart Race — Mario Kart-inspired educational racing.
// HTML canvas top-down oval track. Player kart #1; 3 AI karts.
// Every 5 s a trivia question pops up: correct = 3 s speed boost (green glow),
// wrong = 2 s spin-out (kart shows ❌ and slows). Skip = no effect.
// First to complete 3 laps wins. Age-appropriate trivia built in.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { GameLoop, Surface } from "../../lib/gameEngine2d";

type Age = "kids" | "tween" | "teen" | "adult";
type QuizQ = { prompt: string; options: string[]; answerIndex: number };

// ── Trivia banks ─────────────────────────────────────────────────────────────

const TRIVIA: Record<Age, QuizQ[]> = {
  kids: [
    { prompt: "2 + 2 = ?",                                options: ["3","4","5","6"],                                  answerIndex: 1 },
    { prompt: "How many legs does a spider have?",         options: ["6","7","8","10"],                                 answerIndex: 2 },
    { prompt: "The sky on a clear day is…",                options: ["Green","Blue","Red","Yellow"],                    answerIndex: 1 },
    { prompt: "3 × 3 = ?",                                 options: ["6","8","9","12"],                                 answerIndex: 2 },
    { prompt: "Which is biggest?",                         options: ["Cat","Mouse","Elephant","Dog"],                   answerIndex: 2 },
    { prompt: "5 − 2 = ?",                                  options: ["1","2","3","4"],                                  answerIndex: 2 },
    { prompt: "What do bees make?",                        options: ["Milk","Honey","Butter","Cheese"],                 answerIndex: 1 },
    { prompt: "10 + 5 = ?",                                 options: ["12","14","15","16"],                              answerIndex: 2 },
    { prompt: "A triangle has how many sides?",            options: ["2","3","4","5"],                                  answerIndex: 1 },
    { prompt: "The color of grass.",                       options: ["Blue","Green","Red","Purple"],                    answerIndex: 1 },
  ],
  tween: [
    { prompt: "7 × 8 = ?",                                  options: ["54","56","58","64"],                              answerIndex: 1 },
    { prompt: "Capital of France?",                        options: ["London","Berlin","Paris","Rome"],                 answerIndex: 2 },
    { prompt: "H₂O is…",                                   options: ["Salt","Water","Air","Sugar"],                     answerIndex: 1 },
    { prompt: "Largest planet in our solar system?",       options: ["Earth","Saturn","Jupiter","Neptune"],             answerIndex: 2 },
    { prompt: "√64 = ?",                                    options: ["6","7","8","9"],                                  answerIndex: 2 },
    { prompt: "How many continents?",                      options: ["5","6","7","8"],                                  answerIndex: 2 },
    { prompt: "Which is NOT a primary color?",             options: ["Red","Blue","Green","Yellow"],                    answerIndex: 2 },
    { prompt: "12 × 12 = ?",                                options: ["132","140","144","148"],                          answerIndex: 2 },
    { prompt: "Powerhouse of the cell.",                   options: ["Nucleus","Ribosome","Mitochondria","Vacuole"],    answerIndex: 2 },
    { prompt: "Chemical symbol for gold.",                 options: ["Go","Gd","Au","Ag"],                             answerIndex: 2 },
  ],
  teen: [
    { prompt: "Speed of light ≈",                          options: ["3×10⁶ m/s","3×10⁸ m/s","3×10¹⁰ m/s","3×10⁴ m/s"], answerIndex: 1 },
    { prompt: "Solve 2x + 4 = 10, x = ?",                 options: ["2","3","4","5"],                                  answerIndex: 1 },
    { prompt: "DNA stands for?",                           options: ["Data Nucleic Acid","Deoxyribonucleic Acid","Dynamic Nuclear Array","Dense Nucleotide Agent"], answerIndex: 1 },
    { prompt: "Year of American Independence.",            options: ["1766","1776","1786","1796"],                      answerIndex: 1 },
    { prompt: "Area of circle r=5 (π≈3.14).",             options: ["62.8","78.5","25π","31.4"],                       answerIndex: 1 },
    { prompt: "Shakespeare wrote…",                        options: ["Don Quixote","Hamlet","The Odyssey","Faust"],     answerIndex: 1 },
    { prompt: "pH below 7 is…",                            options: ["Neutral","Basic","Acidic","Ionic"],               answerIndex: 2 },
    { prompt: "Derivative of x³ is…",                      options: ["x²","2x²","3x²","3x³"],                          answerIndex: 2 },
    { prompt: "Berlin Wall fell in…",                      options: ["1987","1989","1991","1993"],                      answerIndex: 1 },
    { prompt: "Atomic number of carbon.",                  options: ["4","6","8","12"],                                 answerIndex: 1 },
  ],
  adult: [
    { prompt: "GDP measures…",                             options: ["Population","Trade deficit","Economic output","Money supply"], answerIndex: 2 },
    { prompt: "Bayes' theorem updates…",                   options: ["Frequencies","Probabilities","Correlations","Variances"], answerIndex: 1 },
    { prompt: "Pythagorean theorem: a²+b²=",               options: ["c","c²","2c","ab"],                               answerIndex: 1 },
    { prompt: "Nietzsche: 'God is…'",                      options: ["Alive","Dead","Watching","Abstract"],             answerIndex: 1 },
    { prompt: "Inflation is measured by…",                 options: ["GDP","CPI","PMI","FDI"],                         answerIndex: 1 },
    { prompt: "Element symbol for Gold.",                  options: ["Gd","Go","Au","Ag"],                             answerIndex: 2 },
    { prompt: "Big-O of binary search?",                   options: ["O(n)","O(log n)","O(n²)","O(1)"],                answerIndex: 1 },
    { prompt: "Schrödinger's cat is about…",               options: ["Biology","Quantum superposition","Relativity","Genetics"], answerIndex: 1 },
    { prompt: "Comparative advantage means producing with lower…", options: ["Price","Opportunity cost","Labor","Tariffs"], answerIndex: 1 },
    { prompt: "Heisenberg limits knowing position and…",   options: ["Charge","Spin","Momentum","Energy"],              answerIndex: 2 },
  ],
};

// ── Track geometry ────────────────────────────────────────────────────────────
// Kart position parameterized as t ∈ [0, 1). Start/finish at t=0 (rightmost point).
// Uses ellipse: x = cx + rx·cos(2πt), y = cy + ry·sin(2πt)

function trackXY(t: number, cx: number, cy: number, rx: number, ry: number) {
  const a = 2 * Math.PI * t;
  return { x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a) };
}

// ── Kart definition ───────────────────────────────────────────────────────────

const KART_DEFS = [
  { color: "#ef4444", border: "#fca5a5", emoji: "🔴", name: "You",   baseSpeed: 0.062 },
  { color: "#facc15", border: "#fef08a", emoji: "🟡", name: "Sunny", baseSpeed: 0.058 },
  { color: "#3b82f6", border: "#93c5fd", emoji: "🔵", name: "Wave",  baseSpeed: 0.064 },
  { color: "#22c55e", border: "#86efac", emoji: "🟢", name: "Zoom",  baseSpeed: 0.056 },
] as const;

type KartState = {
  t: number;           // track position [0,1)
  prevT: number;       // previous frame t (for lap detection)
  speed: number;       // laps/second
  baseSpeed: number;
  laps: number;
  boost: number;       // seconds remaining
  spin: number;        // seconds remaining
  boostText: number;   // "BOOST!" display timer
  color: string;
  border: string;
  emoji: string;
  name: string;
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function KartRace() {
  const [age,  setAge]    = useState<Age>("tween");
  const [phase, setPhase] = useState<"idle" | "playing" | "done">("idle");
  const [winner, setWinner] = useState<string | null>(null);
  const [trivia, setTrivia] = useState<QuizQ | null>(null);
  const [hud, setHud] = useState({ lap: 1, pos: 1 });

  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const kartsRef    = useRef<KartState[]>([]);
  const loopRef     = useRef<GameLoop | null>(null);
  const triviaTimer = useRef(0);          // seconds until next question (counts down)
  const triviaActive = useRef(false);     // true while question panel is visible
  const usedQs      = useRef(new Set<number>());
  const winnerRef   = useRef<string | null>(null);
  const ageRef      = useRef<Age>("tween");

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") {
      setAge(q as Age);
      ageRef.current = q as Age;
    }
  }, []);

  useEffect(() => { ageRef.current = age; }, [age]);

  // ── pick next trivia question ──
  const pickTrivia = useCallback(() => {
    const bank = TRIVIA[ageRef.current];
    const avail = bank.map((_, i) => i).filter((i) => !usedQs.current.has(i));
    if (!avail.length) usedQs.current.clear(); // recycle
    const pool = avail.length ? avail : bank.map((_, i) => i);
    const idx  = pool[Math.floor(Math.random() * pool.length)];
    usedQs.current.add(idx);
    return bank[idx];
  }, []);

  // ── start / restart ──
  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Stop any previous loop
    loopRef.current?.stop();
    loopRef.current = null;

    // Init karts — spread around the track so they don't collide at start
    kartsRef.current = KART_DEFS.map((d, i) => ({
      ...d,
      t:         i * 0.25,   // quarter-lap apart
      prevT:     i * 0.25,
      speed:     d.baseSpeed + (i === 0 ? 0 : (Math.random() - 0.5) * 0.006),
      laps:      0,
      boost:     0,
      spin:      0,
      boostText: 0,
    }));

    winnerRef.current = null;
    usedQs.current.clear();
    triviaTimer.current  = 5;
    triviaActive.current = false;

    setPhase("playing");
    setWinner(null);
    setTrivia(null);
    setHud({ lap: 1, pos: 1 });

    const surface = new Surface(canvas);

    const loop = new GameLoop((dt) => {
      const { ctx } = surface;
      const W = surface.width;
      const H = surface.height;
      const cx = W / 2;
      const cy = H / 2;
      const rx = W * 0.38;
      const ry = H * 0.34;

      // ── trivia countdown (pauses while question is showing) ──
      if (!triviaActive.current && !winnerRef.current) {
        triviaTimer.current -= dt;
        if (triviaTimer.current <= 0) {
          triviaTimer.current  = 5;
          triviaActive.current = true;
          setTrivia(pickTrivia());
        }
      }

      // ── update karts ──
      let newWinner: string | null = null;
      for (const k of kartsRef.current) {
        k.boost     = Math.max(0, k.boost - dt);
        k.spin      = Math.max(0, k.spin  - dt);
        k.boostText = Math.max(0, k.boostText - dt);

        let spd = k.baseSpeed;
        if (k.spin  > 0) spd = k.baseSpeed * 0.12;
        else if (k.boost > 0) spd = k.baseSpeed * 1.95;

        k.prevT = k.t;
        k.t += spd * dt;

        // Lap detection: crossed t=0 boundary
        if (k.t >= 1) {
          k.t -= 1;
          k.laps += 1;
          if (k.laps >= 3 && !winnerRef.current) {
            newWinner = k.name;
          }
        }
      }

      if (newWinner) {
        winnerRef.current = newWinner;
        loop.stop();
        setWinner(newWinner);
        setPhase("done");
        setTrivia(null);
      }

      // ── HUD: player lap + position ──
      const you = kartsRef.current[0];
      const sorted = [...kartsRef.current].sort((a, b) =>
        b.laps !== a.laps ? b.laps - a.laps : b.t - a.t
      );
      const pos = sorted.findIndex((k) => k === you) + 1;
      setHud({ lap: you.laps + 1, pos });

      // ── draw ──
      // Background: grass
      ctx.fillStyle = "#14502d";
      ctx.fillRect(0, 0, W, H);

      // Track outer fill (dark gray)
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx + 22, ry + 22, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#1f2937";
      ctx.fill();

      // Track surface
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
      ctx.strokeStyle = "#4b5563";
      ctx.lineWidth   = 42;
      ctx.stroke();

      // Track edge lines (white)
      ctx.strokeStyle = "#e5e7eb";
      ctx.lineWidth   = 2;
      for (const r of [rx - 20, rx + 20]) {
        ctx.beginPath();
        ctx.ellipse(cx, cy, r, r / (rx / ry), 0, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Track center dashes
      ctx.setLineDash([12, 18]);
      ctx.strokeStyle = "#fbbf24";
      ctx.lineWidth   = 1.5;
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // Inner grass
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx - 22, ry - 22, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#166534";
      ctx.fill();

      // Start / finish line (at t=0, rightmost point)
      const sfX = cx + rx;
      ctx.save();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth   = 4;
      ctx.beginPath();
      ctx.moveTo(sfX - 22, cy);
      ctx.lineTo(sfX + 22, cy);
      ctx.stroke();
      // Checkerboard pattern
      const sqW = 5, sqH = 4;
      for (let row = 0; row < 2; row++) {
        for (let col = 0; col < 8; col++) {
          const dark = (row + col) % 2 === 0;
          ctx.fillStyle = dark ? "#000" : "#fff";
          ctx.fillRect(sfX - 20 + col * sqW, cy - sqH + row * sqH, sqW, sqH);
        }
      }
      ctx.restore();

      // ── draw karts ──
      ctx.textAlign    = "center";
      ctx.textBaseline = "middle";

      for (let i = kartsRef.current.length - 1; i >= 0; i--) {
        const k  = kartsRef.current[i];
        const { x, y } = trackXY(k.t, cx, cy, rx, ry);

        if (k.spin > 0) {
          // Spinning: flicker ❌
          ctx.globalAlpha = 0.5 + 0.5 * Math.sin(Date.now() / 55);
          ctx.font = "20px serif";
          ctx.fillText("❌", x, y);
          ctx.globalAlpha = 1;
        } else {
          // Boost glow
          if (k.boost > 0) {
            ctx.shadowColor = "#4ade80";
            ctx.shadowBlur  = 18;
          }

          // Kart body: colored circle
          ctx.beginPath();
          ctx.arc(x, y, 14, 0, Math.PI * 2);
          ctx.fillStyle = k.color;
          ctx.fill();
          ctx.lineWidth   = 2.5;
          ctx.strokeStyle = k.border;
          ctx.stroke();

          // Emoji / number
          ctx.shadowBlur = 0;
          ctx.font       = "13px serif";
          ctx.fillText(k.emoji, x, y);

          // "BOOST!" label
          if (k.boostText > 0) {
            const alpha = Math.min(1, k.boostText / 0.6);
            ctx.globalAlpha = alpha;
            ctx.font        = "bold 11px sans-serif";
            ctx.fillStyle   = "#4ade80";
            ctx.fillText("BOOST!", x, y - 24 - (0.8 - k.boostText) * 12);
            ctx.globalAlpha = 1;
          }

          ctx.shadowBlur = 0;
        }

        // Kart name + lap (player only, or first in sorted)
        if (i === 0) {
          ctx.font      = "bold 11px sans-serif";
          ctx.fillStyle = "#fff";
          ctx.fillText(`Lap ${Math.min(k.laps + 1, 3)}/3`, x, y - 26);
        }
      }

      // HUD overlay at top-left
      ctx.fillStyle   = "rgba(0,0,0,0.55)";
      ctx.beginPath();
      (ctx as CanvasRenderingContext2D & { roundRect?: (x: number, y: number, w: number, h: number, r: number) => void }).roundRect?.(8, 8, 200, 40, 8);
      ctx.fill();
      ctx.font        = "bold 13px sans-serif";
      ctx.fillStyle   = "#fbbf24";
      ctx.textAlign   = "left";
      ctx.textBaseline = "top";
      const posLabel  = ["1st","2nd","3rd","4th"][pos - 1] ?? `${pos}th`;
      ctx.fillText(`🔴 Lap ${Math.min(you.laps + 1, 3)}/3 · ${posLabel}`, 16, 18);
    });

    loopRef.current = loop;
    loop.start();
  }, [pickTrivia]);

  // Cleanup on unmount
  useEffect(() => () => { loopRef.current?.stop(); }, []);

  // ── trivia answer handler ──
  const answerTrivia = (optIdx: number | null) => {
    if (!trivia) return;
    triviaActive.current = false;
    setTrivia(null);
    triviaTimer.current = 5;

    if (optIdx === null) return; // skip

    const correct = optIdx === trivia.answerIndex;
    const player  = kartsRef.current[0];
    if (!player) return;

    if (correct) {
      player.boost     = 3;
      player.boostText = 0.8;
    } else {
      player.spin = 2;
    }
  };

  const posLabel = ["1st","2nd","3rd","4th"][hud.pos - 1] ?? `${hud.pos}th`;

  return (
    <main className="container" style={{ maxWidth: 700, paddingBottom: 48 }}>
      <style>{`
        @keyframes boostPulse {
          0%,100% { box-shadow: 0 0 0 0 rgba(74,222,128,0); }
          50%      { box-shadow: 0 0 20px 8px rgba(74,222,128,0.7); }
        }
        @keyframes triviaIn {
          from { opacity:0; transform: translateY(12px); }
          to   { opacity:1; transform: translateY(0); }
        }
        .trivia-panel { animation: triviaIn 0.2s ease-out; }
        .opt-kart:hover { background: #1e40af !important; transform: scale(1.03); transition: transform 0.1s; }
      `}</style>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 4 }}>
        <h1 style={{ margin: 0 }}>🏎️ Kart Race</h1>
        <Link href="/arcade" style={{ marginLeft: "auto", color: "#94a3b8" }}>← Arcade</Link>
      </div>
      <p className="muted" style={{ marginBottom: 12 }}>
        Answer trivia to boost your 🔴 kart! Wrong = spin-out. First to 3 laps wins.
      </p>

      {/* Age selector */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        {(["kids","tween","teen","adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={phase === "playing"}
            style={{ opacity: age === a ? 1 : 0.5, fontWeight: age === a ? 700 : 400 }}>{a}</button>
        ))}
        <button onClick={start}
          style={{ marginLeft: "auto", background: "#dc2626", color: "#fff", padding: "10px 22px", fontWeight: 700, borderRadius: 8, border: 0, cursor: "pointer" }}>
          {phase === "idle" ? "▶ Start race" : "↺ Restart"}
        </button>
      </div>

      {/* Live HUD strip */}
      {phase === "playing" && (
        <div style={{ display: "flex", gap: 16, marginBottom: 8, fontSize: 13, color: "#94a3b8", flexWrap: "wrap" }}>
          <span>You 🔴 — Lap {Math.min(hud.lap, 3)}/3 · <strong style={{ color: "#fbbf24" }}>{posLabel}</strong></span>
          <span>🟡 Sunny &nbsp;🔵 Wave &nbsp;🟢 Zoom</span>
        </div>
      )}

      {/* Canvas */}
      <div style={{ position: "relative", width: "100%", borderRadius: 14, overflow: "hidden", background: "#14502d" }}>
        <canvas
          ref={canvasRef}
          style={{ display: "block", width: "100%", height: 340 }}
        />
      </div>

      {/* Trivia panel */}
      {trivia && phase === "playing" && (
        <div className="trivia-panel" style={{
          marginTop: 12,
          padding: "16px 20px",
          background: "#0f172a",
          borderRadius: 14,
          border: "2px solid #fbbf24",
        }}>
          <div style={{ fontWeight: 700, color: "#fbbf24", marginBottom: 10, fontSize: 15 }}>
            ❓ {trivia.prompt}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 10 }}>
            {trivia.options.map((opt, i) => (
              <button key={i} className="opt-kart" onClick={() => answerTrivia(i)}
                style={{ padding: "10px 8px", borderRadius: 8, background: "#1e3a8a", color: "#fff", fontWeight: 600, border: 0, cursor: "pointer", fontSize: 14 }}>
                {opt}
              </button>
            ))}
          </div>
          <button onClick={() => answerTrivia(null)}
            style={{ background: "transparent", color: "#64748b", border: "1px solid #334155", borderRadius: 6, padding: "6px 14px", cursor: "pointer", fontSize: 12 }}>
            Skip
          </button>
        </div>
      )}

      {/* Winner screen */}
      {phase === "done" && winner && (
        <div style={{ textAlign: "center", padding: 32, marginTop: 14, background: "#0f172a", borderRadius: 16 }}>
          <div style={{ fontSize: 52, marginBottom: 8 }}>{winner === "You" ? "🏆" : "🥈"}</div>
          <h2 style={{ color: "#fbbf24", marginBottom: 6 }}>
            {winner === "You" ? "You won the race!" : `${winner} wins the race!`}
          </h2>
          <p className="muted" style={{ marginBottom: 20 }}>
            {winner === "You" ? "Amazing driving and great trivia answers!" : "Better luck next time — answer more trivia questions correctly!"}
          </p>
          <button onClick={start}
            style={{ background: "#dc2626", color: "#fff", padding: "12px 30px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer", fontWeight: 700 }}>
            ▶ Race again
          </button>
        </div>
      )}

      {/* Idle state */}
      {phase === "idle" && (
        <div style={{ textAlign: "center", padding: 40, color: "#64748b", marginTop: 8 }}>
          Press <strong style={{ color: "#f87171" }}>Start race</strong> to begin!
          <br /><br />
          <span style={{ fontSize: 13 }}>
            🔴 You &emsp; 🟡 Sunny &emsp; 🔵 Wave &emsp; 🟢 Zoom<br />
            Trivia questions appear every 5 s. Correct = 🚀 boost, Wrong = 💥 spin-out.
          </span>
        </div>
      )}
    </main>
  );
}
