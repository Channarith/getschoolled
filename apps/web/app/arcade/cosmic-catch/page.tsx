"use client";

// Cosmic Catch — a real 2D canvas arcade game (math). Solve the equation up top,
// then move your catcher to grab the falling answer among decoys. Correct = burst
// of particles + combo + score; miss the right one = lose a life. Starfield,
// glow, screen shake — a genuine game loop, not DOM widgets.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  GameLoop, Particles, Starfield, Surface, clamp, rand, roundRect,
} from "../../lib/gameEngine2d";

type Age = "kids" | "tween" | "teen" | "adult";

type Token = { x: number; y: number; vy: number; value: number; correct: boolean; r: number; hit: boolean };

type Difficulty = { maxN: number; ops: ("+" | "-" | "×")[]; fall: number; decoys: number };

function difficultyFor(age: Age, level: number): Difficulty {
  const base: Record<Age, Difficulty> = {
    kids: { maxN: 9, ops: ["+"], fall: 55, decoys: 2 },
    tween: { maxN: 20, ops: ["+", "-"], fall: 75, decoys: 3 },
    teen: { maxN: 40, ops: ["+", "-", "×"], fall: 95, decoys: 3 },
    adult: { maxN: 60, ops: ["+", "-", "×"], fall: 115, decoys: 4 },
  };
  const d = { ...base[age] };
  d.fall += level * 8;   // speeds up as you level
  return d;
}

function newEquation(d: Difficulty): { text: string; answer: number } {
  const op = d.ops[Math.floor(rand(0, d.ops.length))];
  let a = Math.round(rand(1, d.maxN));
  let b = Math.round(rand(1, d.maxN));
  if (op === "×") { a = Math.round(rand(2, Math.min(12, d.maxN))); b = Math.round(rand(2, 12)); }
  if (op === "-" && b > a) [a, b] = [b, a];
  const answer = op === "+" ? a + b : op === "-" ? a - b : a * b;
  return { text: `${a} ${op} ${b} = ?`, answer };
}

export default function CosmicCatch() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("tween");
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [score, setScore] = useState(0);
  const [best, setBest] = useState(0);
  const stateRef = useRef({
    score: 0, lives: 3, level: 0, combo: 0, catcherX: 0.5, targetX: 0.5,
    tokens: [] as Token[], eq: { text: "", answer: 0 }, shake: 0, t: 0, solved: 0,
    over: false,
  });

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_cosmic_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const s = stateRef.current;
    s.score = 0; s.lives = 3; s.level = 0; s.combo = 0; s.catcherX = 0.5; s.targetX = 0.5;
    s.tokens = []; s.shake = 0; s.t = 0; s.solved = 0; s.over = false;
    setScore(0); setOver(false); setRunning(true);

    const surface = new Surface(canvas);
    const particles = new Particles();
    const stars = new Starfield(110);
    const ageNow = age;

    const spawnWave = () => {
      const d = difficultyFor(ageNow, s.level);
      s.eq = newEquation(d);
      const values = new Set<number>([s.eq.answer]);
      while (values.size < d.decoys + 1) {
        const delta = Math.round(rand(-6, 6)) || 1;
        const v = Math.max(0, s.eq.answer + delta);
        if (v !== s.eq.answer) values.add(v);
      }
      const arr = [...values].sort(() => Math.random() - 0.5);
      const gap = 1 / (arr.length + 1);
      s.tokens = arr.map((value, i) => ({
        x: gap * (i + 1), y: rand(-0.2, -0.02), vy: d.fall * rand(0.9, 1.15),
        value, correct: value === s.eq.answer, r: 26, hit: false,
      }));
    };
    spawnWave();

    // Input: pointer + keyboard.
    const onMove = (clientX: number) => {
      const rect = canvas.getBoundingClientRect();
      s.targetX = clamp((clientX - rect.left) / rect.width, 0, 1);
    };
    const mm = (e: MouseEvent) => onMove(e.clientX);
    const tm = (e: TouchEvent) => { if (e.touches[0]) onMove(e.touches[0].clientX); };
    const kd = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") s.targetX = clamp(s.targetX - 0.08, 0, 1);
      if (e.key === "ArrowRight") s.targetX = clamp(s.targetX + 0.08, 0, 1);
    };
    canvas.addEventListener("mousemove", mm);
    canvas.addEventListener("touchmove", tm, { passive: true });
    window.addEventListener("keydown", kd);

    const loop = new GameLoop((dt) => {
      const { ctx } = surface;
      const W = surface.width, H = surface.height;
      s.t += dt;
      s.catcherX = clamp(s.catcherX + (s.targetX - s.catcherX) * Math.min(1, dt * 14), 0, 1);
      s.shake = Math.max(0, s.shake - dt * 3);

      const catcherPx = s.catcherX * W;
      const catcherY = H - 46;
      const catcherW = clamp(W * 0.16, 70, 150);

      // Update tokens (vy is px/sec; y is normalized 0..1).
      for (const tk of s.tokens) tk.y += (tk.vy * dt) / H;

      // Collision + off-screen.
      let advance = false;
      for (const tk of s.tokens) {
        if (tk.hit) continue;
        const px = tk.x * W, py = tk.y * H;
        if (py + tk.r >= catcherY && py - tk.r <= catcherY + 18 &&
            px >= catcherPx - catcherW / 2 - tk.r && px <= catcherPx + catcherW / 2 + tk.r) {
          tk.hit = true;
          if (tk.correct) {
            s.combo += 1; s.solved += 1;
            const gained = 10 + s.combo * 2 + s.level * 3;
            s.score += gained; setScore(s.score);
            particles.burst(px, py, "#34d399", 26, { speed: 240 });
            if (s.solved % 4 === 0) s.level += 1;
            advance = true;
          } else {
            s.combo = 0;
            s.score = Math.max(0, s.score - 5); setScore(s.score);
            particles.burst(px, py, "#f87171", 14, { speed: 140 });
            s.shake = 0.6;
          }
        } else if (py - tk.r > H) {
          if (tk.correct) {
            tk.hit = true;
            s.combo = 0; s.lives -= 1; s.shake = 0.9;
            particles.burst(px, H - 10, "#fbbf24", 20, { speed: 160 });
            advance = true;
          } else {
            tk.hit = true;   // decoy fell off — harmless
          }
        }
      }
      if (advance || s.tokens.every((tk) => tk.hit)) {
        if (s.lives <= 0) {
          s.over = true;
          loop.stop();
          try {
            const b = Math.max(s.score, Number(localStorage.getItem("aoep_cosmic_best") || 0));
            localStorage.setItem("aoep_cosmic_best", String(b));
            setBest(b);
          } catch { /* */ }
          setOver(true); setRunning(false);
          cleanup();
          return;
        }
        spawnWave();
      }

      // -------- render --------
      ctx.save();
      const sx = (Math.random() - 0.5) * s.shake * 10;
      const sy = (Math.random() - 0.5) * s.shake * 10;
      ctx.translate(sx, sy);
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, "#0b0720"); grad.addColorStop(1, "#1a0a2e");
      ctx.fillStyle = grad; ctx.fillRect(-20, -20, W + 40, H + 40);
      stars.draw(ctx, W, H, s.t);

      // Equation banner.
      ctx.fillStyle = "#e9d5ff";
      ctx.font = `bold ${clamp(W * 0.06, 22, 44)}px system-ui, sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(s.eq.text, W / 2, 44);

      // Tokens (glowing bubbles).
      for (const tk of s.tokens) {
        if (tk.hit) continue;
        const px = tk.x * W, py = tk.y * H;
        ctx.save();
        ctx.shadowColor = "#7c3aed"; ctx.shadowBlur = 22;
        const g = ctx.createRadialGradient(px, py, 4, px, py, tk.r);
        g.addColorStop(0, "#c4b5fd"); g.addColorStop(1, "#6d28d9");
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(px, py, tk.r, 0, Math.PI * 2); ctx.fill();
        ctx.restore();
        ctx.fillStyle = "#fff"; ctx.font = "bold 20px system-ui, sans-serif";
        ctx.fillText(String(tk.value), px, py);
      }

      particles.update(dt); particles.draw(ctx);

      // Catcher (glowing paddle).
      ctx.save();
      ctx.shadowColor = "#22d3ee"; ctx.shadowBlur = 18;
      ctx.fillStyle = "#22d3ee";
      roundRect(ctx, catcherPx - catcherW / 2, catcherY, catcherW, 16, 8);
      ctx.fill();
      ctx.restore();

      // HUD.
      ctx.fillStyle = "#a5b4fc"; ctx.font = "bold 16px system-ui, sans-serif";
      ctx.textAlign = "left"; ctx.fillText(`Score ${s.score}`, 14, H - 16);
      ctx.textAlign = "center"; ctx.fillText(`Lv ${s.level + 1}  ·  x${s.combo} combo`, W / 2, H - 16);
      ctx.textAlign = "right"; ctx.fillText("♥".repeat(Math.max(0, s.lives)), W - 14, H - 16);
      ctx.restore();
    });

    const cleanup = () => {
      loop.stop();
      surface.dispose();
      canvas.removeEventListener("mousemove", mm);
      canvas.removeEventListener("touchmove", tm);
      window.removeEventListener("keydown", kd);
    };
    (canvas as unknown as { __cleanup?: () => void }).__cleanup = cleanup;
    loop.start();
  }, [age]);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🪐 Cosmic Catch</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>
      <p className="muted">Solve the equation, then catch the correct answer. Move with your mouse, finger, or ← → keys.</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <span className="muted">Age:</span>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={running}
            style={{ opacity: age === a ? 1 : 0.55, fontWeight: age === a ? 700 : 400 }}>
            {a}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>Best: {best}</span>
      </div>

      <div style={{ position: "relative", width: "100%", aspectRatio: "4 / 3", borderRadius: 14, overflow: "hidden", border: "1px solid #2d1b4e" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }} />
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "rgba(11,7,32,0.7)", color: "#fff",
          }}>
            {over && <div style={{ fontSize: 22, fontWeight: 700 }}>Game over · Score {score}</div>}
            <button onClick={start} style={{ background: "#7c3aed", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Play again" : "▶ Play"}
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
