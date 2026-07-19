"use client";

// Geometry Blocks — Tetris-style geometry quiz. A question appears at the top;
// steer the falling block into the column of the correct answer before it locks.
// Wrong answers stack and clutter the board. Challenge the AI mode races a bot.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { aiProfile, aiPickAnswer, aiThinkDelay } from "../../lib/arcadeAi";
import { type ArcadeAge, geometryQuestions, randomQuestion, type QuizQ } from "../../lib/arcadeQuestions";
import { clamp, GameLoop, Particles, roundRect, Surface } from "../../lib/gameEngine2d";

const COLS = 4;
const ROWS = 11;
const COLORS = ["#f472b6", "#38bdf8", "#a3e635", "#fbbf24"];

type Cell = { optionIndex: number; correct: boolean } | null;

export default function GeometryBlocks() {
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
    score: 0, aiScore: 0, lives: 3, level: 0, combo: 0,
    board: Array.from({ length: ROWS }, () => Array<Cell>(COLS).fill(null)),
    pieceCol: 1, pieceRow: 0, falling: true, shake: 0, t: 0,
    question: null as QuizQ | null, used: new Set<string>(),
    over: false, vsAi: false, aiPending: false, aiCol: 0,
    fallSpeed: 0.35, lockTimer: 0,
  });

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_geoblocks_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search);
    const a = q.get("age");
    if (a === "kids" || a === "tween" || a === "teen" || a === "adult") setAge(a);
    setVsAi(q.get("ai") === "1");
  }, []);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const bank = geometryQuestions(age);
    const s = stateRef.current;
    s.score = 0; s.aiScore = 0; s.lives = 3; s.level = 0; s.combo = 0;
    s.board = Array.from({ length: ROWS }, () => Array<Cell>(COLS).fill(null));
    s.pieceCol = 1; s.pieceRow = 0; s.falling = true; s.shake = 0; s.t = 0;
    s.used = new Set(); s.over = false; s.vsAi = vsAi; s.aiPending = false;
    s.fallSpeed = 0.35; s.lockTimer = 0;
    s.question = randomQuestion(bank, s.used);
    setScore(0); setAiScore(0); setOver(false); setResult(""); setRunning(true);

    const surface = new Surface(canvas);
    const particles = new Particles();
    const profile = aiProfile(age);

    const nextQuestion = () => {
      s.question = randomQuestion(bank, s.used);
      s.pieceCol = 1; s.pieceRow = 0; s.falling = true; s.lockTimer = 0;
      if (s.vsAi && s.question) {
        s.aiPending = true;
        const correct = s.question.answerIndex;
        const delay = aiThinkDelay(profile);
        setTimeout(() => {
          if (s.over || !s.question) return;
          s.aiCol = aiPickAnswer(correct, COLS, profile.accuracy);
          s.aiPending = false;
          const aiOk = s.aiCol === correct;
          if (aiOk) { s.aiScore += 10 + s.level * 2; setAiScore(s.aiScore); }
        }, delay);
      }
    };

    const lockPiece = () => {
      if (!s.question) return;
      const correct = s.question.answerIndex;
      const ok = s.pieceCol === correct;
      const row = Math.floor(s.pieceRow);
      if (row >= 0 && row < ROWS) {
        s.board[row][s.pieceCol] = { optionIndex: s.pieceCol, correct: ok };
      }
      if (ok) {
        s.combo += 1;
        const gained = 12 + s.combo * 3 + s.level * 4;
        s.score += gained; setScore(s.score);
        // Clear the row
        for (let c = 0; c < COLS; c++) s.board[row][c] = null;
        s.level += 1;
        s.fallSpeed = Math.min(0.9, s.fallSpeed + 0.04);
        particles.burst((s.pieceCol + 0.5) * surface.width / COLS, (row + 0.5) * (surface.height * 0.65) / ROWS + surface.height * 0.22, "#34d399", 22);
        if (s.vsAi && s.aiCol === correct) { /* both correct — player still wins row */ }
      } else {
        s.combo = 0;
        s.lives -= 1;
        s.shake = 0.7;
        particles.burst((s.pieceCol + 0.5) * surface.width / COLS, (row + 0.5) * (surface.height * 0.65) / ROWS + surface.height * 0.22, "#f87171", 14);
        if (s.vsAi && s.aiCol === correct) {
          s.aiScore += 8; setAiScore(s.aiScore);
        }
      }
      if (s.lives <= 0 || s.board[0].some((c) => c !== null)) {
        s.over = true;
        loop.stop();
        const key = vsAi ? "aoep_geoblocks_ai_best" : "aoep_geoblocks_best";
        try {
          const b = Math.max(s.score, Number(localStorage.getItem(key) || 0));
          localStorage.setItem(key, String(b));
          setBest(b);
        } catch { /* */ }
        if (vsAi) {
          if (s.score > s.aiScore) setResult(`You beat ${profile.name}! ${s.score} – ${s.aiScore}`);
          else if (s.aiScore > s.score) setResult(`${profile.name} wins ${s.aiScore} – ${s.score}`);
          else setResult(`Tie game! ${s.score} – ${s.aiScore}`);
        }
        setOver(true); setRunning(false);
        cleanup();
        return;
      }
      nextQuestion();
    };

    const kd = (e: KeyboardEvent) => {
      if (!s.falling || s.over) return;
      if (e.key === "ArrowLeft") s.pieceCol = clamp(s.pieceCol - 1, 0, COLS - 1);
      if (e.key === "ArrowRight") s.pieceCol = clamp(s.pieceCol + 1, 0, COLS - 1);
      if (e.key === "ArrowDown") { s.pieceRow = ROWS - 1; lockPiece(); }
    };
    window.addEventListener("keydown", kd);

    const onTap = (clientX: number) => {
      const rect = canvas.getBoundingClientRect();
      const col = clamp(Math.floor(((clientX - rect.left) / rect.width) * COLS), 0, COLS - 1);
      s.pieceCol = col;
    };
    const mm = (e: MouseEvent) => onTap(e.clientX);
    const tm = (e: TouchEvent) => { if (e.touches[0]) onTap(e.touches[0].clientX); };
    canvas.addEventListener("click", mm);
    canvas.addEventListener("touchstart", tm, { passive: true });

    const loop = new GameLoop((dt) => {
      const { ctx } = surface;
      const W = surface.width, H = surface.height;
      s.t += dt;
      s.shake = Math.max(0, s.shake - dt * 3);

      const boardTop = H * 0.22;
      const boardH = H * 0.65;
      const cellW = W / COLS;
      const cellH = boardH / ROWS;

      if (s.falling && !s.over) {
        s.pieceRow += s.fallSpeed * dt * 8;
        const bottom = ROWS - 1;
        const blocked = s.pieceRow >= bottom ||
          (Math.floor(s.pieceRow) + 1 < ROWS && s.board[Math.floor(s.pieceRow) + 1]?.[s.pieceCol]);
        if (blocked || s.pieceRow >= bottom) {
          s.lockTimer += dt;
          if (s.lockTimer > 0.08) lockPiece();
        }
      }

      // -------- render --------
      ctx.save();
      const sx = (Math.random() - 0.5) * s.shake * 8;
      const sy = (Math.random() - 0.5) * s.shake * 8;
      ctx.translate(sx, sy);
      ctx.fillStyle = "#0f172a";
      ctx.fillRect(0, 0, W, H);

      // Question banner
      if (s.question) {
        ctx.fillStyle = "#e2e8f0";
        ctx.font = `bold ${clamp(W * 0.038, 14, 22)}px system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.fillText(s.question.prompt, W / 2, 28, W - 20);
      }

      // Column labels (answer options)
      if (s.question) {
        ctx.font = `${clamp(W * 0.028, 10, 14)}px system-ui, sans-serif`;
        for (let c = 0; c < COLS; c++) {
          const opt = s.question.options[c] ?? "";
          const short = opt.length > 14 ? `${opt.slice(0, 12)}…` : opt;
          ctx.fillStyle = c === s.question.answerIndex && s.over ? "#34d399" : "#94a3b8";
          ctx.fillText(short, (c + 0.5) * cellW, boardTop - 6, cellW - 4);
        }
      }

      // Grid + locked cells
      for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
          const x = c * cellW, y = boardTop + r * cellH;
          ctx.strokeStyle = "rgba(148,163,184,0.15)";
          ctx.strokeRect(x + 1, y + 1, cellW - 2, cellH - 2);
          const cell = s.board[r][c];
          if (cell) {
            ctx.fillStyle = cell.correct ? "rgba(52,211,153,0.5)" : "rgba(248,113,113,0.55)";
            roundRect(ctx, x + 3, y + 3, cellW - 6, cellH - 6, 6);
            ctx.fill();
          }
        }
      }

      // Falling piece (geometric shape)
      if (s.falling && !s.over) {
        const px = s.pieceCol * cellW + cellW / 2;
        const py = boardTop + s.pieceRow * cellH + cellH / 2;
        ctx.save();
        ctx.shadowColor = COLORS[s.pieceCol]; ctx.shadowBlur = 16;
        ctx.fillStyle = COLORS[s.pieceCol];
        ctx.beginPath();
        ctx.arc(px, py, Math.min(cellW, cellH) * 0.32, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        // Shape icon inside
        ctx.fillStyle = "#0f172a";
        ctx.font = `bold ${cellH * 0.35}px system-ui`;
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        const shapes = ["△", "□", "⬠", "○"];
        ctx.fillText(shapes[s.pieceCol % 4], px, py);
      }

      // AI indicator
      if (s.vsAi && s.question) {
        const aiX = (s.aiCol + 0.5) * cellW;
        ctx.strokeStyle = s.aiPending ? "#fbbf24" : "#818cf8";
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(aiX, boardTop - 18);
        ctx.lineTo(aiX, boardTop + boardH);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "#a5b4fc";
        ctx.font = "11px system-ui";
        ctx.textAlign = "center";
        ctx.fillText(s.aiPending ? "AI thinking…" : profile.name, aiX, boardTop - 22);
      }

      particles.update(dt); particles.draw(ctx);

      // HUD
      ctx.fillStyle = "#cbd5e1";
      ctx.font = "bold 14px system-ui";
      ctx.textAlign = "left";
      ctx.fillText(`Score ${s.score}`, 10, H - 12);
      if (s.vsAi) {
        ctx.textAlign = "center";
        ctx.fillText(`vs ${profile.name}: ${s.aiScore}`, W / 2, H - 12);
      } else {
        ctx.textAlign = "center";
        ctx.fillText(`Lv ${s.level + 1} · x${s.combo}`, W / 2, H - 12);
      }
      ctx.textAlign = "right";
      ctx.fillText("♥".repeat(Math.max(0, s.lives)), W - 10, H - 12);
      ctx.restore();
    });

    const cleanup = () => {
      loop.stop();
      surface.dispose();
      window.removeEventListener("keydown", kd);
      canvas.removeEventListener("click", mm);
      canvas.removeEventListener("touchstart", tm);
    };
    (canvas as unknown as { __cleanup?: () => void }).__cleanup = cleanup;
    loop.start();
  }, [age, vsAi]);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>📐 Geometry Blocks</h1>
        <Link href="/arcade/challenge-ai" style={{ marginLeft: "auto" }}>🤖 Challenge AI</Link>
        <Link href="/arcade">← Arcade</Link>
      </div>
      <p className="muted">
        Tetris-style geometry quiz — steer the falling block into the column with the correct answer.
        {vsAi ? " Race the AI to clear rows!" : " Use ← → or tap a column. ↓ to drop fast."}
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

      <div style={{ position: "relative", width: "100%", aspectRatio: "3 / 4", borderRadius: 14, overflow: "hidden", border: "1px solid #334155" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }} />
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "rgba(15,23,42,0.82)", color: "#fff",
          }}>
            {over && (
              <div style={{ fontSize: 20, fontWeight: 700, textAlign: "center" }}>
                {result || `Game over · Score ${score}`}
              </div>
            )}
            <button onClick={start} style={{ background: "#6366f1", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Play again" : "▶ Play"}
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
