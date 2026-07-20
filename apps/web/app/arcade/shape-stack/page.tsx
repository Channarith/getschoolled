"use client";

// Shape Stack — Tetris-style geometry quiz. A shape falls in a 4-column grid;
// each column is labeled with an answer choice. Move ← → and drop (↓ / Space)
// into the column matching the geometry question. Correct = clear + score;
// wrong = penalty row. Speed ramps with level.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { GameLoop, Particles, Surface, clamp, roundRect } from "../../lib/gameEngine2d";

type Age = "kids" | "tween" | "teen" | "adult";

type Question = { prompt: string; options: string[]; answer: number; shape: string };

const QUESTIONS: Record<Age, Question[]> = {
  kids: [
    { prompt: "3 sides?", options: ["Triangle", "Square", "Circle", "Star"], answer: 0, shape: "△" },
    { prompt: "4 equal sides?", options: ["Triangle", "Square", "Circle", "Oval"], answer: 1, shape: "□" },
    { prompt: "No corners?", options: ["Square", "Triangle", "Circle", "Rectangle"], answer: 2, shape: "○" },
    { prompt: "Round shape?", options: ["Box", "Ball", "Block", "Line"], answer: 1, shape: "○" },
  ],
  tween: [
    { prompt: "Sum of triangle angles?", options: ["90°", "180°", "270°", "360°"], answer: 1, shape: "△" },
    { prompt: "Rectangle corners?", options: ["45°", "90°", "120°", "180°"], answer: 1, shape: "□" },
    { prompt: "Pentagon has how many sides?", options: ["4", "5", "6", "8"], answer: 1, shape: "⬡" },
    { prompt: "Area of 2×3 rectangle?", options: ["5", "6", "8", "9"], answer: 1, shape: "□" },
  ],
  teen: [
    { prompt: "π × r² calculates…", options: ["Perimeter", "Circle area", "Volume", "Slope"], answer: 1, shape: "○" },
    { prompt: "Hypotenuse in right △?", options: ["Shortest side", "Longest side", "Middle side", "Any side"], answer: 1, shape: "△" },
    { prompt: "Hexagon sides?", options: ["5", "6", "7", "8"], answer: 1, shape: "⬢" },
    { prompt: "Parallel lines…", options: ["Cross once", "Never meet", "Always meet", "Are perpendicular"], answer: 1, shape: "◇" },
  ],
  adult: [
    { prompt: "Volume of cube edge 3?", options: ["9", "18", "27", "36"], answer: 2, shape: "□" },
    { prompt: "Tangent touches circle at…", options: ["2 points", "1 point", "0 points", "∞ points"], answer: 1, shape: "○" },
    { prompt: "Interior angles of hexagon?", options: ["540°", "720°", "900°", "1080°"], answer: 1, shape: "⬢" },
    { prompt: "Similar triangles have…", options: ["Same size", "Same shape", "Same area", "Same perimeter"], answer: 1, shape: "△" },
  ],
};

function fallSpeed(age: Age, level: number): number {
  const base: Record<Age, number> = { kids: 0.35, tween: 0.45, teen: 0.55, adult: 0.65 };
  return base[age] + level * 0.04;
}

export default function ShapeStack() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("tween");
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [score, setScore] = useState(0);
  const [best, setBest] = useState(0);
  const stateRef = useRef({
    score: 0, lives: 3, level: 0, col: 1, y: 0, qIdx: 0,
    questions: [] as Question[], shake: 0, t: 0, solved: 0, over: false,
  });

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_shapestack_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const s = stateRef.current;
    s.score = 0; s.lives = 3; s.level = 0; s.col = 1; s.y = 0; s.qIdx = 0;
    s.questions = [...QUESTIONS[age]].sort(() => Math.random() - 0.5);
    s.shake = 0; s.t = 0; s.solved = 0; s.over = false;
    setScore(0); setOver(false); setRunning(true);

    const surface = new Surface(canvas);
    const particles = new Particles();
    const ageNow = age;
    const COLS = 4;

    const currentQ = () => s.questions[s.qIdx % s.questions.length];

    const nextQ = () => {
      s.qIdx += 1;
      s.col = 1; s.y = 0;
    };

    const kd = (e: KeyboardEvent) => {
      if (s.over) return;
      if (e.key === "ArrowLeft") s.col = clamp(s.col - 1, 0, COLS - 1);
      if (e.key === "ArrowRight") s.col = clamp(s.col + 1, 0, COLS - 1);
      if (e.key === "ArrowDown" || e.key === " ") {
        e.preventDefault();
        lockPiece();
      }
    };
    window.addEventListener("keydown", kd);

    const lockPiece = () => {
      const q = currentQ();
      const px = (s.col + 0.5) * (surface.width / COLS);
      const py = surface.height * 0.72;
      if (s.col === q.answer) {
        s.solved += 1;
        const gained = 15 + s.level * 4;
        s.score += gained; setScore(s.score);
        particles.burst(px, py, "#34d399", 22, { speed: 200 });
        if (s.solved % 3 === 0) s.level += 1;
        nextQ();
      } else {
        s.lives -= 1;
        s.shake = 0.8;
        particles.burst(px, py, "#f87171", 16, { speed: 160 });
        if (s.lives <= 0) endGame();
        else nextQ();
      }
    };

    const endGame = () => {
      s.over = true;
      loop.stop();
      try {
        const b = Math.max(s.score, Number(localStorage.getItem("aoep_shapestack_best") || 0));
        localStorage.setItem("aoep_shapestack_best", String(b));
        setBest(b);
      } catch { /* */ }
      setOver(true); setRunning(false);
      cleanup();
    };

    const loop = new GameLoop((dt) => {
      const { ctx } = surface;
      const W = surface.width, H = surface.height;
      s.t += dt;
      s.shake = Math.max(0, s.shake - dt * 3);

      const speed = fallSpeed(ageNow, s.level);
      s.y += speed * dt;
      if (s.y >= 0.68) lockPiece();

      const q = currentQ();
      const colW = W / COLS;
      const pieceX = s.col * colW + colW / 2;
      const pieceY = H * (0.12 + s.y);

      // Render
      ctx.save();
      const sx = (Math.random() - 0.5) * s.shake * 8;
      const sy = (Math.random() - 0.5) * s.shake * 8;
      ctx.translate(sx, sy);

      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, "#0a1628"); grad.addColorStop(1, "#1e1b4b");
      ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);

      // Question banner
      ctx.fillStyle = "#e0e7ff";
      ctx.font = `bold ${clamp(W * 0.045, 16, 28)}px system-ui, sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(q.prompt, W / 2, 36);

      // Column labels (answer bins)
      for (let c = 0; c < COLS; c++) {
        const x = c * colW;
        const selected = c === s.col;
        ctx.fillStyle = selected ? "rgba(124,58,237,0.35)" : "rgba(30,41,59,0.6)";
        roundRect(ctx, x + 4, H * 0.68, colW - 8, H * 0.28, 8);
        ctx.fill();
        ctx.strokeStyle = selected ? "#a78bfa" : "#334155";
        ctx.lineWidth = selected ? 2 : 1;
        ctx.stroke();
        ctx.fillStyle = "#cbd5e1";
        ctx.font = `${clamp(colW * 0.12, 11, 16)}px system-ui, sans-serif`;
        const label = q.options[c] ?? "";
        ctx.fillText(label.length > 12 ? label.slice(0, 11) + "…" : label, x + colW / 2, H * 0.84);
      }

      // Falling shape piece
      ctx.save();
      ctx.shadowColor = "#818cf8"; ctx.shadowBlur = 20;
      ctx.fillStyle = "#6366f1";
      ctx.beginPath(); ctx.arc(pieceX, pieceY, clamp(colW * 0.18, 22, 38), 0, Math.PI * 2); ctx.fill();
      ctx.restore();
      ctx.fillStyle = "#fff";
      ctx.font = `bold ${clamp(colW * 0.2, 24, 40)}px system-ui, sans-serif`;
      ctx.fillText(q.shape, pieceX, pieceY);

      particles.update(dt); particles.draw(ctx);

      // HUD
      ctx.fillStyle = "#94a3b8"; ctx.font = "bold 14px system-ui, sans-serif";
      ctx.textAlign = "left"; ctx.fillText(`Score ${s.score}`, 12, H - 12);
      ctx.textAlign = "center"; ctx.fillText(`Lv ${s.level + 1}`, W / 2, H - 12);
      ctx.textAlign = "right"; ctx.fillText("♥".repeat(Math.max(0, s.lives)), W - 12, H - 12);

      ctx.fillStyle = "#64748b"; ctx.font = "12px system-ui, sans-serif";
      ctx.textAlign = "center"; ctx.fillText("← → move  ·  ↓ or Space drop", W / 2, H * 0.64);
      ctx.restore();
    });

    const cleanup = () => {
      loop.stop();
      surface.dispose();
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
        <h1 style={{ margin: 0 }}>📐 Shape Stack</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/arcade/challenge-ai">🤖 Challenge AI</Link>
      </div>
      <p className="muted">Tetris-style geometry quiz — drop the falling shape into the column with the correct answer.</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <span className="muted">Age:</span>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={running}
            style={{ opacity: age === a ? 1 : 0.55, fontWeight: age === a ? 700 : 400 }}>{a}</button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>Best: {best}</span>
      </div>

      <div style={{ position: "relative", width: "100%", aspectRatio: "3 / 4", borderRadius: 14, overflow: "hidden", border: "1px solid #312e81" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }}
          onClick={(e) => {
            if (!running) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const col = clamp(Math.floor(((e.clientX - rect.left) / rect.width) * 4), 0, 3);
            stateRef.current.col = col;
          }}
        />
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "rgba(10,22,40,0.75)", color: "#fff",
          }}>
            {over && <div style={{ fontSize: 22, fontWeight: 700 }}>Game over · Score {score}</div>}
            <button onClick={start} style={{ background: "#6366f1", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Play again" : "▶ Play"}
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
