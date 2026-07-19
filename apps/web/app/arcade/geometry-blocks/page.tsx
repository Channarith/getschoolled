"use client";

// Geometry Blocks — a real Tetris game with a geometry-quiz twist. Falling
// tetrominoes, rotation, hard drop, line clears, levels and speed-up — a genuine
// game loop (canvas + fixed-ish timestep), not DOM widgets. The learning layer:
// a live geometry question sits beside the board; answering correctly grants a
// "line bomb" (clears the bottom row) plus bonus points, so knowing your shapes,
// angles and areas is a real in-game power.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { GameLoop, Particles, Surface, roundRect } from "../../lib/gameEngine2d";

type Age = "kids" | "tween" | "teen" | "adult";

const COLS = 10;
const ROWS = 20;

// Colors indexed 1..7 (0 = empty).
const COLORS = ["", "#22d3ee", "#f59e0b", "#a78bfa", "#34d399", "#f472b6", "#60a5fa", "#f87171"];

type Cell = number; // 0 empty, else color index
type Matrix = number[][];

type Piece = { m: Matrix; x: number; y: number; color: number };

const SHAPES: Matrix[] = [
  [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]], // I
  [[2, 2], [2, 2]],                                          // O
  [[0, 3, 0], [3, 3, 3], [0, 0, 0]],                         // T
  [[0, 4, 4], [4, 4, 0], [0, 0, 0]],                         // S
  [[5, 5, 0], [0, 5, 5], [0, 0, 0]],                         // Z
  [[6, 0, 0], [6, 6, 6], [0, 0, 0]],                         // J
  [[0, 0, 7], [7, 7, 7], [0, 0, 0]],                         // L
];

function rotateCW(m: Matrix): Matrix {
  const n = m.length;
  const out: Matrix = m.map((row) => row.map(() => 0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) out[j][n - 1 - i] = m[i][j];
  }
  return out;
}

function emptyGrid(): Cell[][] {
  return Array.from({ length: ROWS }, () => Array<Cell>(COLS).fill(0));
}

function randomPiece(): Piece {
  const idx = Math.floor(Math.random() * SHAPES.length);
  const m = SHAPES[idx].map((row) => [...row]);
  const color = idx + 1;
  const x = Math.floor((COLS - m[0].length) / 2);
  return { m, x, y: 0, color };
}

// ---- geometry question bank -------------------------------------------------
type Q = { q: string; options: string[]; answer: number };

const QUESTIONS: Record<Age, Q[]> = {
  kids: [
    { q: "How many sides does a triangle have?", options: ["3", "4", "5"], answer: 0 },
    { q: "How many sides does a square have?", options: ["3", "4", "6"], answer: 1 },
    { q: "How many corners does a rectangle have?", options: ["4", "3", "5"], answer: 0 },
    { q: "A shape with 5 sides is a…", options: ["Pentagon", "Hexagon", "Octagon"], answer: 0 },
    { q: "How many sides does a circle have?", options: ["0", "1", "3"], answer: 0 },
    { q: "How many sides does a hexagon have?", options: ["6", "5", "8"], answer: 0 },
  ],
  tween: [
    { q: "Angles in a triangle add up to…", options: ["180°", "90°", "360°"], answer: 0 },
    { q: "A right angle measures…", options: ["90°", "45°", "180°"], answer: 0 },
    { q: "How many sides does an octagon have?", options: ["8", "6", "10"], answer: 0 },
    { q: "Perimeter of a 4×3 rectangle?", options: ["14", "12", "7"], answer: 0 },
    { q: "Area of a 4×3 rectangle?", options: ["12", "14", "7"], answer: 0 },
    { q: "A triangle with all equal sides is…", options: ["Equilateral", "Isosceles", "Scalene"], answer: 0 },
  ],
  teen: [
    { q: "Area of a triangle with base 6, height 4?", options: ["12", "24", "10"], answer: 0 },
    { q: "Sum of interior angles of a pentagon?", options: ["540°", "360°", "720°"], answer: 0 },
    { q: "Circumference of a circle, r = 7 (use π≈22/7)?", options: ["44", "22", "154"], answer: 0 },
    { q: "A 3-4-? right triangle hypotenuse is…", options: ["5", "6", "7"], answer: 0 },
    { q: "Area of a circle, r = 3 (π≈3.14)?", options: ["28.3", "18.8", "9.4"], answer: 0 },
    { q: "Angles on a straight line add to…", options: ["180°", "360°", "90°"], answer: 0 },
  ],
  adult: [
    { q: "Interior angle of a regular hexagon?", options: ["120°", "108°", "135°"], answer: 0 },
    { q: "Volume of a cube with edge 3?", options: ["27", "9", "18"], answer: 0 },
    { q: "Area of a trapezoid, bases 4 & 6, height 5?", options: ["25", "30", "20"], answer: 0 },
    { q: "Diagonal of a unit square?", options: ["√2", "2", "1.5"], answer: 0 },
    { q: "Sum of exterior angles of any polygon?", options: ["360°", "180°", "720°"], answer: 0 },
    { q: "Surface area of a cube, edge 2?", options: ["24", "8", "16"], answer: 0 },
  ],
};

function shuffledQuestion(age: Age): { q: Q; order: number[] } {
  const bank = QUESTIONS[age];
  const q = bank[Math.floor(Math.random() * bank.length)];
  const order = q.options.map((_, i) => i).sort(() => Math.random() - 0.5);
  return { q, order };
}

export default function GeometryBlocks() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("tween");
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [score, setScore] = useState(0);
  const [lines, setLines] = useState(0);
  const [level, setLevel] = useState(1);
  const [best, setBest] = useState(0);
  const [bombs, setBombs] = useState(0);
  const [quiz, setQuiz] = useState<{ q: Q; order: number[] } | null>(null);
  const [quizFlash, setQuizFlash] = useState<"ok" | "bad" | "">("");

  const stateRef = useRef({
    grid: emptyGrid(),
    piece: randomPiece(),
    next: randomPiece(),
    dropAcc: 0,
    dropInterval: 0.8,
    score: 0,
    lines: 0,
    level: 1,
    bombs: 0,
    over: false,
    ageNow: "tween" as Age,
    flash: 0,
  });

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_geoblocks_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  const collides = (grid: Cell[][], p: Piece, nx: number, ny: number, m: Matrix): boolean => {
    for (let i = 0; i < m.length; i++) {
      for (let j = 0; j < m[i].length; j++) {
        if (!m[i][j]) continue;
        const gx = nx + j;
        const gy = ny + i;
        if (gx < 0 || gx >= COLS || gy >= ROWS) return true;
        if (gy >= 0 && grid[gy][gx]) return true;
      }
    }
    return false;
  };

  const lockPiece = useCallback(() => {
    const s = stateRef.current;
    const { grid, piece } = s;
    for (let i = 0; i < piece.m.length; i++) {
      for (let j = 0; j < piece.m[i].length; j++) {
        if (!piece.m[i][j]) continue;
        const gy = piece.y + i;
        const gx = piece.x + j;
        if (gy >= 0 && gy < ROWS && gx >= 0 && gx < COLS) grid[gy][gx] = piece.color;
      }
    }
    // Clear full lines.
    let cleared = 0;
    for (let r = ROWS - 1; r >= 0; r--) {
      if (grid[r].every((c) => c !== 0)) {
        grid.splice(r, 1);
        grid.unshift(Array<Cell>(COLS).fill(0));
        cleared += 1;
        r += 1; // re-check same row index after unshift
      }
    }
    if (cleared > 0) {
      const points = [0, 100, 300, 500, 800][cleared] * s.level;
      s.score += points;
      s.lines += cleared;
      s.level = Math.floor(s.lines / 8) + 1;
      s.dropInterval = Math.max(0.12, 0.8 - (s.level - 1) * 0.07);
      setScore(s.score); setLines(s.lines); setLevel(s.level);
      s.flash = 0.4;
    }
    // Spawn next.
    s.piece = s.next;
    s.next = randomPiece();
    if (collides(grid, s.piece, s.piece.x, s.piece.y, s.piece.m)) {
      s.over = true;
    }
  }, []);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const s = stateRef.current;
    s.grid = emptyGrid();
    s.piece = randomPiece();
    s.next = randomPiece();
    s.dropAcc = 0;
    s.dropInterval = 0.8;
    s.score = 0; s.lines = 0; s.level = 1; s.bombs = 0; s.over = false; s.flash = 0;
    s.ageNow = age;
    setScore(0); setLines(0); setLevel(1); setBombs(0);
    setOver(false); setRunning(true);
    setQuiz(shuffledQuestion(age)); setQuizFlash("");

    const surface = new Surface(canvas);
    const particles = new Particles();

    const move = (dx: number) => {
      if (s.over) return;
      const p = s.piece;
      if (!collides(s.grid, p, p.x + dx, p.y, p.m)) p.x += dx;
    };
    const softDrop = () => {
      if (s.over) return;
      const p = s.piece;
      if (!collides(s.grid, p, p.x, p.y + 1, p.m)) { p.y += 1; s.score += 1; setScore(s.score); }
      else lockPiece();
    };
    const rotate = () => {
      if (s.over) return;
      const p = s.piece;
      const rm = rotateCW(p.m);
      for (const kick of [0, -1, 1, -2, 2]) {
        if (!collides(s.grid, p, p.x + kick, p.y, rm)) { p.m = rm; p.x += kick; return; }
      }
    };
    const hardDrop = () => {
      if (s.over) return;
      const p = s.piece;
      let dist = 0;
      while (!collides(s.grid, p, p.x, p.y + 1, p.m)) { p.y += 1; dist += 1; }
      s.score += dist * 2; setScore(s.score);
      lockPiece();
    };

    const kd = (e: KeyboardEvent) => {
      if (["ArrowLeft", "ArrowRight", "ArrowDown", "ArrowUp", " "].includes(e.key)) e.preventDefault();
      if (e.key === "ArrowLeft") move(-1);
      else if (e.key === "ArrowRight") move(1);
      else if (e.key === "ArrowDown") softDrop();
      else if (e.key === "ArrowUp") rotate();
      else if (e.key === " ") hardDrop();
    };
    window.addEventListener("keydown", kd);
    (canvas as unknown as { __ctrl?: Record<string, () => void> }).__ctrl = {
      left: () => move(-1), right: () => move(1), down: softDrop, rotate, drop: hardDrop,
    };

    const finish = () => {
      loop.stop();
      try {
        const b = Math.max(s.score, Number(localStorage.getItem("aoep_geoblocks_best") || 0));
        localStorage.setItem("aoep_geoblocks_best", String(b));
        setBest(b);
      } catch { /* */ }
      setOver(true); setRunning(false);
      cleanup();
    };

    const loop = new GameLoop((dt) => {
      const { ctx } = surface;
      const W = surface.width, H = surface.height;

      if (!s.over) {
        s.dropAcc += dt;
        if (s.dropAcc >= s.dropInterval) {
          s.dropAcc = 0;
          const p = s.piece;
          if (!collides(s.grid, p, p.x, p.y + 1, p.m)) p.y += 1;
          else lockPiece();
        }
      }
      if (s.over) { finish(); return; }
      s.flash = Math.max(0, s.flash - dt);

      // Board geometry.
      const pad = 8;
      const cell = Math.floor(Math.min((W - pad * 2) / COLS, (H - pad * 2) / ROWS));
      const boardW = cell * COLS;
      const boardH = cell * ROWS;
      const ox = Math.floor((W - boardW) / 2);
      const oy = Math.floor((H - boardH) / 2);

      // Background.
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, "#0b0720"); grad.addColorStop(1, "#160a2e");
      ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);

      // Board frame + grid lines.
      ctx.fillStyle = "rgba(255,255,255,0.03)";
      roundRect(ctx, ox - 3, oy - 3, boardW + 6, boardH + 6, 8); ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,0.05)";
      ctx.lineWidth = 1;
      for (let c = 0; c <= COLS; c++) {
        ctx.beginPath(); ctx.moveTo(ox + c * cell, oy); ctx.lineTo(ox + c * cell, oy + boardH); ctx.stroke();
      }
      for (let r = 0; r <= ROWS; r++) {
        ctx.beginPath(); ctx.moveTo(ox, oy + r * cell); ctx.lineTo(ox + boardW, oy + r * cell); ctx.stroke();
      }

      const drawCell = (gx: number, gy: number, color: number, alpha = 1) => {
        if (color <= 0) return;
        ctx.globalAlpha = alpha;
        ctx.fillStyle = COLORS[color];
        roundRect(ctx, ox + gx * cell + 1, oy + gy * cell + 1, cell - 2, cell - 2, 4);
        ctx.fill();
        ctx.globalAlpha = alpha * 0.35;
        ctx.fillStyle = "#ffffff";
        roundRect(ctx, ox + gx * cell + 3, oy + gy * cell + 3, cell - 6, Math.max(2, cell / 4), 3);
        ctx.fill();
        ctx.globalAlpha = 1;
      };

      // Settled cells.
      for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) drawCell(c, r, s.grid[r][c]);
      }

      // Ghost piece.
      const p = s.piece;
      let gy = p.y;
      while (!collides(s.grid, p, p.x, gy + 1, p.m)) gy += 1;
      for (let i = 0; i < p.m.length; i++) {
        for (let j = 0; j < p.m[i].length; j++) {
          if (p.m[i][j] && gy + i >= 0) drawCell(p.x + j, gy + i, p.color, 0.18);
        }
      }
      // Active piece.
      for (let i = 0; i < p.m.length; i++) {
        for (let j = 0; j < p.m[i].length; j++) {
          if (p.m[i][j] && p.y + i >= 0) drawCell(p.x + j, p.y + i, p.color);
        }
      }

      // Line-clear flash.
      if (s.flash > 0) {
        ctx.fillStyle = `rgba(255,255,255,${s.flash * 0.4})`;
        ctx.fillRect(ox, oy, boardW, boardH);
      }

      particles.update(dt); particles.draw(ctx);
    });

    const cleanup = () => {
      loop.stop();
      surface.dispose();
      window.removeEventListener("keydown", kd);
    };
    (canvas as unknown as { __cleanup?: () => void }).__cleanup = cleanup;
    loop.start();
  }, [age, lockPiece]);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  const ctrl = () => (canvasRef.current as unknown as { __ctrl?: Record<string, () => void> } | null)?.__ctrl;

  function answerQuiz(optionIdx: number) {
    if (!quiz) return;
    const s = stateRef.current;
    if (optionIdx === quiz.q.answer) {
      s.bombs += 1; setBombs(s.bombs);
      s.score += 40 * s.level; setScore(s.score);
      setQuizFlash("ok");
    } else {
      setQuizFlash("bad");
    }
    setTimeout(() => {
      setQuiz(shuffledQuestion(s.ageNow));
      setQuizFlash("");
    }, 550);
  }

  function useBomb() {
    const s = stateRef.current;
    if (s.bombs <= 0 || s.over) return;
    // Clear the lowest non-empty row.
    for (let r = ROWS - 1; r >= 0; r--) {
      if (s.grid[r].some((c) => c !== 0)) {
        s.grid.splice(r, 1);
        s.grid.unshift(Array<Cell>(COLS).fill(0));
        break;
      }
    }
    s.bombs -= 1; setBombs(s.bombs);
    s.score += 60 * s.level; setScore(s.score);
    s.flash = 0.4;
  }

  const btnStyle: React.CSSProperties = {
    background: "#1e1b3a", color: "#fff", border: "1px solid #3a2f66",
    borderRadius: 10, padding: "12px 16px", fontSize: 18, cursor: "pointer", minWidth: 54,
  };

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>📐 Geometry Blocks</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>
      <p className="muted">
        Real Tetris with a geometry brain. Stack and clear lines with ← → to move,
        ↑ to rotate, ↓ to soft-drop, space to hard-drop. Answer geometry questions to
        earn <strong>line bombs</strong> that blast the bottom row.
      </p>

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

      <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 1fr) minmax(220px, 260px)", gap: 14, alignItems: "start" }}>
        {/* Board */}
        <div style={{ position: "relative", width: "100%", aspectRatio: "1 / 2", borderRadius: 14, overflow: "hidden", border: "1px solid #2d1b4e" }}>
          <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }} />
          {!running && (
            <div style={{
              position: "absolute", inset: 0, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", gap: 12,
              background: "rgba(11,7,32,0.72)", color: "#fff", textAlign: "center", padding: 16,
            }}>
              {over && <div style={{ fontSize: 22, fontWeight: 700 }}>Game over · Score {score}</div>}
              <button onClick={start} style={{ background: "#7c3aed", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
                {over ? "Play again" : "▶ Play"}
              </button>
            </div>
          )}
        </div>

        {/* Side panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="card" style={{ margin: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
              <span className="muted">Score</span><strong>{score}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
              <span className="muted">Lines</span><strong>{lines}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
              <span className="muted">Level</span><strong>{level}</strong>
            </div>
            <button onClick={useBomb} disabled={bombs <= 0 || !running}
              style={{ marginTop: 8, width: "100%", background: bombs > 0 ? "#f59e0b" : "#3a3a3a", color: "#111", fontWeight: 700, opacity: bombs > 0 && running ? 1 : 0.5 }}>
              💣 Use line bomb ({bombs})
            </button>
          </div>

          <div className="card" style={{
            margin: 0,
            borderColor: quizFlash === "ok" ? "#34d399" : quizFlash === "bad" ? "#f87171" : "var(--border)",
            transition: "border-color 0.2s",
          }}>
            <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>📐 Geometry challenge · earn a 💣</div>
            {quiz ? (
              <>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>{quiz.q.q}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {quiz.order.map((oi) => (
                    <button key={oi} onClick={() => answerQuiz(oi)} disabled={!!quizFlash}
                      style={{ textAlign: "left" }}>
                      {quiz.q.options[oi]}
                    </button>
                  ))}
                </div>
                {quizFlash === "ok" && <div style={{ color: "#16a34a", marginTop: 6, fontSize: 13 }}>✓ Correct! +bomb</div>}
                {quizFlash === "bad" && <div style={{ color: "#b00", marginTop: 6, fontSize: 13 }}>✗ Not quite — new one coming</div>}
              </>
            ) : <div className="muted">Press Play to start.</div>}
          </div>

          {/* Touch controls */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
            <button style={btnStyle} onClick={() => ctrl()?.rotate?.()}>⟳</button>
            <button style={btnStyle} onClick={() => ctrl()?.drop?.()}>⤓</button>
            <button style={btnStyle} onClick={() => ctrl()?.down?.()}>↓</button>
            <button style={btnStyle} onClick={() => ctrl()?.left?.()}>←</button>
            <button style={btnStyle} onClick={() => ctrl()?.down?.()}>↓</button>
            <button style={btnStyle} onClick={() => ctrl()?.right?.()}>→</button>
          </div>
        </div>
      </div>
    </main>
  );
}
