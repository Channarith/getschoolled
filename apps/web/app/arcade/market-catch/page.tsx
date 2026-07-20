"use client";

// Market Catch — catch the correct investing answer as tickers fall. Stocks &
// personal-finance quiz adapted from Cosmic Catch. Optional vs-AI race mode.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { aiProfile, aiPickAnswer, aiThinkDelay } from "../../lib/arcadeAi";
import { type ArcadeAge, financeQuestions, randomQuestion, type QuizQ } from "../../lib/arcadeQuestions";
import { clamp, GameLoop, Particles, Starfield, Surface, rand, roundRect } from "../../lib/gameEngine2d";

type Token = { x: number; y: number; vy: number; label: string; optionIndex: number; correct: boolean; r: number; hit: boolean };

type Difficulty = { fall: number; decoys: number };

function difficultyFor(age: ArcadeAge, level: number): Difficulty {
  const base: Record<ArcadeAge, Difficulty> = {
    kids: { fall: 50, decoys: 2 },
    tween: { fall: 70, decoys: 3 },
    teen: { fall: 90, decoys: 3 },
    adult: { fall: 110, decoys: 4 },
  };
  return { ...base[age], fall: base[age].fall + level * 7 };
}

export default function MarketCatch() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<ArcadeAge>("tween");
  const [vsAi, setVsAi] = useState(false);
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [score, setScore] = useState(0);
  const [aiScore, setAiScore] = useState(0);
  const [best, setBest] = useState(0);
  const [result, setResult] = useState("");

  const stateRef = useRef({
    score: 0, aiScore: 0, lives: 3, level: 0, combo: 0, catcherX: 0.5, targetX: 0.5,
    tokens: [] as Token[], question: null as QuizQ | null, used: new Set<string>(),
    shake: 0, t: 0, solved: 0, over: false, vsAi: false,
    aiCatchX: 0.5, aiPending: false,
  });

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_market_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search);
    const a = q.get("age");
    if (a === "kids" || a === "tween" || a === "teen" || a === "adult") setAge(a);
    setVsAi(q.get("ai") === "1");
  }, []);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const bank = financeQuestions(age);
    const profile = aiProfile(age);
    const s = stateRef.current;
    s.score = 0; s.aiScore = 0; s.lives = 3; s.level = 0; s.combo = 0;
    s.catcherX = 0.5; s.targetX = 0.5; s.tokens = []; s.shake = 0; s.t = 0;
    s.solved = 0; s.over = false; s.vsAi = vsAi; s.used = new Set();
    setScore(0); setAiScore(0); setOver(false); setResult(""); setRunning(true);

    const surface = new Surface(canvas);
    const particles = new Particles();
    const stars = new Starfield(80);
    const ageNow = age;

    const spawnWave = () => {
      const d = difficultyFor(ageNow, s.level);
      s.question = randomQuestion(bank, s.used);
      const q = s.question;
      const indices = [0, 1, 2, 3].slice(0, q.options.length);
      const picked = [...indices].sort(() => Math.random() - 0.5).slice(0, d.decoys + 1);
      if (!picked.includes(q.answerIndex)) picked[0] = q.answerIndex;
      const uniq = [...new Set(picked)].sort(() => Math.random() - 0.5);
      const gap = 1 / (uniq.length + 1);
      s.tokens = uniq.map((optionIndex, i) => ({
        x: gap * (i + 1), y: rand(-0.2, -0.02), vy: d.fall * rand(0.9, 1.12),
        label: q.options[optionIndex].length > 18 ? `${q.options[optionIndex].slice(0, 16)}…` : q.options[optionIndex],
        optionIndex, correct: optionIndex === q.answerIndex, r: 30, hit: false,
      }));
      if (s.vsAi && q) {
        s.aiPending = true;
        const delay = aiThinkDelay(profile);
        setTimeout(() => {
          if (s.over || !s.question) return;
          const pick = aiPickAnswer(q.answerIndex, q.options.length, profile.accuracy);
          const match = s.tokens.find((t) => t.optionIndex === pick && !t.hit);
          s.aiCatchX = match ? match.x : 0.5;
          s.aiPending = false;
        }, delay);
      }
    };
    spawnWave();

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
      const catcherW = clamp(W * 0.18, 80, 160);
      const aiPx = s.aiCatchX * W;

      for (const tk of s.tokens) tk.y += (tk.vy * dt) / H;

      let advance = false;
      for (const tk of s.tokens) {
        if (tk.hit) continue;
        const px = tk.x * W, py = tk.y * H;

        // AI catch (parallel paddle at 30% height)
        if (s.vsAi && !s.aiPending && tk.correct) {
          const aiY = H * 0.72;
          if (py + tk.r >= aiY && py - tk.r <= aiY + 14 &&
              px >= aiPx - catcherW / 2 - tk.r && px <= aiPx + catcherW / 2 + tk.r) {
            tk.hit = true;
            s.aiScore += 10 + s.level * 2;
            setAiScore(s.aiScore);
            particles.burst(px, py, "#818cf8", 16, { speed: 180 });
            advance = true;
          }
        }

        if (py + tk.r >= catcherY && py - tk.r <= catcherY + 18 &&
            px >= catcherPx - catcherW / 2 - tk.r && px <= catcherPx + catcherW / 2 + tk.r) {
          tk.hit = true;
          if (tk.correct) {
            s.combo += 1; s.solved += 1;
            const gained = 10 + s.combo * 2 + s.level * 3;
            s.score += gained; setScore(s.score);
            particles.burst(px, py, "#22c55e", 24, { speed: 220 });
            if (s.solved % 4 === 0) s.level += 1;
            advance = true;
          } else {
            s.combo = 0;
            s.score = Math.max(0, s.score - 5); setScore(s.score);
            particles.burst(px, py, "#ef4444", 12, { speed: 130 });
            s.shake = 0.6;
          }
        } else if (py - tk.r > H) {
          if (tk.correct) {
            tk.hit = true;
            s.combo = 0; s.lives -= 1; s.shake = 0.9;
            particles.burst(px, H - 10, "#f59e0b", 18, { speed: 150 });
            advance = true;
          } else {
            tk.hit = true;
          }
        }
      }

      if (advance || s.tokens.every((tk) => tk.hit)) {
        if (s.lives <= 0) {
          s.over = true;
          loop.stop();
          const key = vsAi ? "aoep_market_ai_best" : "aoep_market_best";
          try {
            const b = Math.max(s.score, Number(localStorage.getItem(key) || 0));
            localStorage.setItem(key, String(b));
            setBest(b);
          } catch { /* */ }
          if (vsAi) {
            if (s.score > s.aiScore) setResult(`You beat ${profile.name}! ${s.score} – ${s.aiScore}`);
            else if (s.aiScore > s.score) setResult(`${profile.name} wins ${s.aiScore} – ${s.score}`);
            else setResult(`Tie! ${s.score} – ${s.aiScore}`);
          }
          setOver(true); setRunning(false);
          cleanup();
          return;
        }
        spawnWave();
      }

      // Render
      ctx.save();
      const shakeX = (Math.random() - 0.5) * s.shake * 10;
      const shakeY = (Math.random() - 0.5) * s.shake * 10;
      ctx.translate(shakeX, shakeY);
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, "#052e16"); grad.addColorStop(1, "#0c1a0f");
      ctx.fillStyle = grad; ctx.fillRect(-20, -20, W + 40, H + 40);
      stars.draw(ctx, W, H, s.t * 0.5);

      // Ticker tape header
      ctx.fillStyle = "#86efac";
      ctx.font = `bold ${clamp(W * 0.042, 14, 24)}px system-ui`;
      ctx.textAlign = "center";
      const prompt = s.question?.prompt ?? "";
      ctx.fillText(prompt, W / 2, 42, W - 16);

      // Falling tickers
      for (const tk of s.tokens) {
        if (tk.hit) continue;
        const px = tk.x * W, py = tk.y * H;
        ctx.save();
        ctx.shadowColor = tk.correct ? "#22c55e" : "#64748b";
        ctx.shadowBlur = 14;
        ctx.fillStyle = tk.correct ? "#166534" : "#1e293b";
        roundRect(ctx, px - tk.r, py - tk.r * 0.55, tk.r * 2, tk.r * 1.1, 8);
        ctx.fill();
        ctx.restore();
        ctx.fillStyle = "#ecfdf5";
        ctx.font = `bold ${clamp(tk.r * 0.38, 10, 14)}px system-ui`;
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(tk.label, px, py, tk.r * 1.8);
      }

      particles.update(dt); particles.draw(ctx);

      // Player portfolio catcher
      ctx.save();
      ctx.shadowColor = "#22c55e"; ctx.shadowBlur = 16;
      ctx.fillStyle = "#16a34a";
      roundRect(ctx, catcherPx - catcherW / 2, catcherY, catcherW, 16, 8);
      ctx.fill();
      ctx.restore();

      if (s.vsAi) {
        ctx.save();
        ctx.shadowColor = "#818cf8"; ctx.shadowBlur = 12;
        ctx.fillStyle = "#6366f1";
        roundRect(ctx, aiPx - catcherW / 2, H * 0.72, catcherW, 14, 6);
        ctx.fill();
        ctx.restore();
        ctx.fillStyle = "#a5b4fc";
        ctx.font = "11px system-ui";
        ctx.textAlign = "center";
        ctx.fillText(s.aiPending ? "AI analyzing…" : profile.name, aiPx, H * 0.72 - 8);
      }

      ctx.fillStyle = "#bbf7d0";
      ctx.font = "bold 14px system-ui";
      ctx.textAlign = "left";
      ctx.fillText(`$${s.score}`, 14, H - 14);
      ctx.textAlign = "center";
      ctx.fillText(s.vsAi ? `You vs AI` : `Lv ${s.level + 1} · x${s.combo}`, W / 2, H - 14);
      ctx.textAlign = "right";
      ctx.fillText(s.vsAi ? `AI $${s.aiScore}` : "♥".repeat(Math.max(0, s.lives)), W - 14, H - 14);
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
  }, [age, vsAi]);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>📈 Market Catch</h1>
        <Link href="/arcade/challenge-ai" style={{ marginLeft: "auto" }}>🤖 Challenge AI</Link>
        <Link href="/arcade">← Arcade</Link>
      </div>
      <p className="muted">
        Read the investing question, then catch the correct answer ticker before it hits the bottom.
        {vsAi ? " Outscore the AI opponent!" : ""}
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <span className="muted">Age:</span>
        {(["kids", "tween", "teen", "adult"] as ArcadeAge[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={running}
            style={{ opacity: age === a ? 1 : 0.55, fontWeight: age === a ? 700 : 400 }}>{a}</button>
        ))}
        <label style={{ marginLeft: 8, display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={vsAi} onChange={(e) => setVsAi(e.target.checked)} disabled={running} />
          vs AI
        </label>
        <span className="muted" style={{ marginLeft: "auto" }}>Best: {best}</span>
      </div>

      <div style={{ position: "relative", width: "100%", aspectRatio: "4 / 3", borderRadius: 14, overflow: "hidden", border: "1px solid #14532d" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }} />
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "rgba(5,46,22,0.75)", color: "#fff",
          }}>
            {over && <div style={{ fontSize: 22, fontWeight: 700, textAlign: "center" }}>{result || `Game over · $${score}`}</div>}
            <button onClick={start} style={{ background: "#16a34a", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Trade again" : "▶ Start trading"}
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
