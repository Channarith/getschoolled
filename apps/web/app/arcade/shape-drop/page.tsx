"use client";

// Shape Drop — Tetris-style geometry quiz. Falling tetrominoes; answer the
// shape question to lock a clear (particles + score). Wrong / timeout = junk
// that fills the well. Age scales fall speed and question difficulty.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  GameLoop, Particles, Surface, clamp, rand, roundRect,
} from "../../lib/gameEngine2d";

type Age = "kids" | "tween" | "teen" | "adult";

type Cell = { c: number; r: number };
type PieceDef = { name: string; color: string; cells: Cell[] };

const PIECES: PieceDef[] = [
  { name: "I", color: "#22d3ee", cells: [{ c: 0, r: 0 }, { c: 1, r: 0 }, { c: 2, r: 0 }, { c: 3, r: 0 }] },
  { name: "O", color: "#fbbf24", cells: [{ c: 0, r: 0 }, { c: 1, r: 0 }, { c: 0, r: 1 }, { c: 1, r: 1 }] },
  { name: "T", color: "#a78bfa", cells: [{ c: 0, r: 0 }, { c: 1, r: 0 }, { c: 2, r: 0 }, { c: 1, r: 1 }] },
  { name: "L", color: "#fb923c", cells: [{ c: 0, r: 0 }, { c: 0, r: 1 }, { c: 0, r: 2 }, { c: 1, r: 2 }] },
  { name: "S", color: "#4ade80", cells: [{ c: 1, r: 0 }, { c: 2, r: 0 }, { c: 0, r: 1 }, { c: 1, r: 1 }] },
];

type Quiz = { prompt: string; options: string[]; answer: number; explain: string };

const QUIZ_BANK: Record<Age, Quiz[]> = {
  kids: [
    { prompt: "How many squares in every tetromino?", options: ["3", "4", "5", "8"], answer: 1, explain: "Tetra = four." },
    { prompt: "A square has how many sides?", options: ["3", "4", "5", "6"], answer: 1, explain: "Four equal sides." },
    { prompt: "Rotate a square 90°. Looks…", options: ["The same", "Like a triangle", "Like a circle", "Broken"], answer: 0, explain: "Squares look the same every 90°." },
    { prompt: "Which shape has 3 sides?", options: ["Triangle", "Square", "Circle", "Hexagon"], answer: 0, explain: "Tri = three." },
  ],
  tween: [
    { prompt: "Perimeter of a 2×2 O-piece (unit cells)?", options: ["4", "6", "8", "16"], answer: 2, explain: "4 sides × 2 = 8." },
    { prompt: "I-piece is a straight bar of…", options: ["3", "4", "5", "6"], answer: 1, explain: "Four unit squares." },
    { prompt: "Sum of angles in a triangle?", options: ["90°", "180°", "270°", "360°"], answer: 1, explain: "Always 180°." },
    { prompt: "S and Z pieces are…", options: ["Reflections", "Circles", "Pentominoes", "Identical"], answer: 0, explain: "Mirror images." },
  ],
  teen: [
    { prompt: "Which tiles the plane with no gaps?", options: ["Squares", "Regular pentagons alone", "Circles", "Hearts"], answer: 0, explain: "Squares tessellate." },
    { prompt: "Area of a 3×4 rectangle?", options: ["7", "12", "14", "34"], answer: 1, explain: "3×4 = 12." },
    { prompt: "T-piece tip points down; rotate 180°. Tip points…", options: ["Up", "Down", "Left", "Right"], answer: 0, explain: "180° reverses direction." },
    { prompt: "A right angle measures…", options: ["45°", "90°", "180°", "360°"], answer: 1, explain: "Right = 90°." },
  ],
  adult: [
    { prompt: "Interior angle sum of a convex quadrilateral?", options: ["180°", "270°", "360°", "540°"], answer: 2, explain: "(n−2)×180° = 360°." },
    { prompt: "Rotational order of a square?", options: ["2", "3", "4", "6"], answer: 2, explain: "Looks same at 90°, 180°, 270°, 360°." },
    { prompt: "Which tetromino has reflection symmetry but not 180° rotational?", options: ["T", "O", "I", "S"], answer: 0, explain: "T reflects across its stem; 180° looks different." },
    { prompt: "Unit-square diagonal length of one cell?", options: ["1", "√2", "2", "π"], answer: 1, explain: "Pythagoras: √(1²+1²)=√2." },
  ],
};

function rotateCells(cells: Cell[]): Cell[] {
  // Rotate 90° CW around origin, then normalize to min c/r = 0.
  const rot = cells.map(({ c, r }) => ({ c: -r, r: c }));
  const minC = Math.min(...rot.map((x) => x.c));
  const minR = Math.min(...rot.map((x) => x.r));
  return rot.map(({ c, r }) => ({ c: c - minC, r: r - minR }));
}

function pickQuiz(age: Age, level: number): Quiz {
  const bank = QUIZ_BANK[age];
  return bank[Math.floor(rand(0, bank.length)) + (level % bank.length) * 0] ?? bank[0];
}

export default function ShapeDropPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("tween");
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [score, setScore] = useState(0);
  const [best, setBest] = useState(0);
  const [quizUi, setQuizUi] = useState<Quiz | null>(null);
  const stateRef = useRef({
    score: 0, lines: 0, level: 0, lives: 3, over: false,
    cols: 10, rows: 16, grid: [] as (string | null)[][],
    piece: null as { def: PieceDef; cells: Cell[]; c: number; r: number } | null,
    fallAcc: 0, fallEvery: 0.7, quiz: null as Quiz | null, quizOpen: false,
    shake: 0, t: 0, answered: false,
  });

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_shape_drop_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  const answerQuiz = useCallback((idx: number) => {
    const s = stateRef.current;
    if (!s.quizOpen || !s.quiz || !s.piece) return;
    const ok = idx === s.quiz.answer;
    s.quizOpen = false;
    s.answered = true;
    setQuizUi(null);
    if (ok) {
      s.score += 25 + s.level * 5;
      setScore(s.score);
      // Lock piece & clear full rows.
      const { def, cells, c, r } = s.piece;
      for (const cell of cells) {
        const gc = c + cell.c, gr = r + cell.r;
        if (gr >= 0 && gr < s.rows && gc >= 0 && gc < s.cols) s.grid[gr][gc] = def.color;
      }
      let cleared = 0;
      s.grid = s.grid.filter((row) => {
        const full = row.every((x) => x);
        if (full) cleared += 1;
        return !full;
      });
      while (s.grid.length < s.rows) s.grid.unshift(Array(s.cols).fill(null));
      if (cleared) {
        s.lines += cleared;
        s.score += cleared * 40;
        s.level = Math.floor(s.lines / 4);
        s.fallEvery = Math.max(0.22, 0.7 - s.level * 0.06 - (age === "adult" ? 0.12 : age === "kids" ? -0.05 : 0));
        setScore(s.score);
      }
      s.piece = null;
    } else {
      s.lives -= 1;
      s.shake = 0.4;
      // Drop piece as junk faster.
      if (s.piece) s.piece.r += 2;
      if (s.lives <= 0) {
        s.over = true;
        setOver(true);
        setRunning(false);
        try {
          const b = Math.max(s.score, Number(localStorage.getItem("aoep_shape_drop_best") || 0));
          localStorage.setItem("aoep_shape_drop_best", String(b));
          setBest(b);
        } catch { /* */ }
      }
    }
  }, [age]);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const s = stateRef.current;
    s.score = 0; s.lines = 0; s.level = 0; s.lives = 3; s.over = false;
    s.grid = Array.from({ length: s.rows }, () => Array(s.cols).fill(null));
    s.piece = null; s.fallAcc = 0;
    s.fallEvery = age === "kids" ? 0.95 : age === "tween" ? 0.75 : age === "teen" ? 0.55 : 0.42;
    s.quiz = null; s.quizOpen = false; s.answered = false; s.shake = 0; s.t = 0;
    setScore(0); setOver(false); setRunning(true); setQuizUi(null);

    const surface = new Surface(canvas);
    const particles = new Particles();

    const spawn = () => {
      const def = PIECES[Math.floor(rand(0, PIECES.length))];
      s.piece = { def, cells: def.cells.map((x) => ({ ...x })), c: 3, r: 0 };
      s.quiz = pickQuiz(age, s.level);
      s.quizOpen = true;
      s.answered = false;
      setQuizUi(s.quiz);
    };
    spawn();

    const collides = (c: number, r: number, cells: Cell[]) => {
      for (const cell of cells) {
        const gc = c + cell.c, gr = r + cell.r;
        if (gc < 0 || gc >= s.cols || gr >= s.rows) return true;
        if (gr >= 0 && s.grid[gr][gc]) return true;
      }
      return false;
    };

    const lockJunk = () => {
      if (!s.piece) return;
      const { def, cells, c, r } = s.piece;
      for (const cell of cells) {
        const gc = c + cell.c, gr = r + cell.r;
        if (gr < 0) {
          s.over = true; setOver(true); setRunning(false);
          return;
        }
        if (gr < s.rows && gc >= 0 && gc < s.cols) s.grid[gr][gc] = "#475569";
      }
      s.piece = null;
      s.quizOpen = false;
      setQuizUi(null);
      if (!s.over) spawn();
    };

    const kd = (e: KeyboardEvent) => {
      if (!s.piece || s.over) return;
      if (e.key === "ArrowLeft" && !collides(s.piece.c - 1, s.piece.r, s.piece.cells)) s.piece.c -= 1;
      if (e.key === "ArrowRight" && !collides(s.piece.c + 1, s.piece.r, s.piece.cells)) s.piece.c += 1;
      if (e.key === "ArrowDown" && !collides(s.piece.c, s.piece.r + 1, s.piece.cells)) s.piece.r += 1;
      if (e.key === "ArrowUp" || e.key === "x" || e.key === "X") {
        const rot = rotateCells(s.piece.cells);
        if (!collides(s.piece.c, s.piece.r, rot)) s.piece.cells = rot;
      }
      if (e.key >= "1" && e.key <= "4" && s.quizOpen) answerQuiz(Number(e.key) - 1);
    };
    window.addEventListener("keydown", kd);

    const loop = new GameLoop((dt) => {
      if (s.over) return;
      const { ctx } = surface;
      const W = surface.width, H = surface.height;
      s.t += dt;
      s.shake = Math.max(0, s.shake - dt * 3);
      s.fallAcc += dt;

      if (s.piece && !s.quizOpen) {
        // After answering wrong, piece keeps falling until lock.
        if (s.fallAcc >= s.fallEvery * 0.45) {
          s.fallAcc = 0;
          if (!collides(s.piece.c, s.piece.r + 1, s.piece.cells)) s.piece.r += 1;
          else lockJunk();
        }
      } else if (s.piece && s.quizOpen) {
        // Slow auto-fall while quiz is open — pressure.
        if (s.fallAcc >= s.fallEvery * 1.6) {
          s.fallAcc = 0;
          if (!collides(s.piece.c, s.piece.r + 1, s.piece.cells)) s.piece.r += 1;
          else {
            s.lives -= 1;
            s.shake = 0.35;
            lockJunk();
            if (s.lives <= 0) {
              s.over = true; setOver(true); setRunning(false);
            }
          }
        }
      } else if (!s.piece && !s.over) {
        spawn();
      }

      // After correct answer, piece was nulled — spawn already handled.
      if (s.answered && !s.piece && !s.over) {
        s.answered = false;
        particles.burst(W * 0.5, H * 0.35, "#a78bfa", 22, { speed: 200 });
        spawn();
      }

      const pad = 12;
      const boardW = Math.min(W - pad * 2, H * 0.55);
      const cell = boardW / s.cols;
      const boardH = cell * s.rows;
      const ox = (W - boardW) / 2;
      const oy = (H - boardH) / 2 + 8;
      const sx = (Math.random() - 0.5) * s.shake * 10;
      const sy = (Math.random() - 0.5) * s.shake * 10;

      ctx.clearRect(0, 0, W, H);
      const g = ctx.createLinearGradient(0, 0, W, H);
      g.addColorStop(0, "#0f172a"); g.addColorStop(1, "#1e1b4b");
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

      ctx.save();
      ctx.translate(sx, sy);
      // Well
      ctx.fillStyle = "rgba(15,23,42,0.85)";
      roundRect(ctx, ox - 4, oy - 4, boardW + 8, boardH + 8, 10);
      ctx.fill();
      ctx.strokeStyle = "#334155"; ctx.lineWidth = 2;
      ctx.stroke();

      for (let r = 0; r < s.rows; r++) {
        for (let c = 0; c < s.cols; c++) {
          const col = s.grid[r][c];
          if (!col) continue;
          ctx.fillStyle = col;
          roundRect(ctx, ox + c * cell + 1, oy + r * cell + 1, cell - 2, cell - 2, 3);
          ctx.fill();
        }
      }
      if (s.piece) {
        ctx.fillStyle = s.piece.def.color;
        ctx.globalAlpha = s.quizOpen ? 0.95 : 0.7;
        for (const cellP of s.piece.cells) {
          const x = ox + (s.piece.c + cellP.c) * cell + 1;
          const y = oy + (s.piece.r + cellP.r) * cell + 1;
          roundRect(ctx, x, y, cell - 2, cell - 2, 3);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      }
      particles.update(dt); particles.draw(ctx);

      ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 15px system-ui, sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(`Score ${s.score}`, 14, 22);
      ctx.textAlign = "center";
      ctx.fillText(`Lines ${s.lines} · Lv ${s.level + 1}`, W / 2, 22);
      ctx.textAlign = "right";
      ctx.fillText("♥".repeat(Math.max(0, s.lives)), W - 14, 22);
      ctx.restore();
    });

    const cleanup = () => {
      loop.stop();
      surface.dispose();
      window.removeEventListener("keydown", kd);
    };
    (canvas as unknown as { __cleanup?: () => void }).__cleanup = cleanup;
    loop.start();
  }, [age, answerQuiz]);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>📐 Shape Drop</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted">
        Tetris-style geometry: answer the shape question to lock and clear lines.
        Move with ← →, rotate ↑, soft-drop ↓, or tap answers 1–4.
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

      <div style={{ position: "relative", width: "100%", aspectRatio: "3 / 4", maxHeight: 640, borderRadius: 14, overflow: "hidden", border: "1px solid #334155" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }} />
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "rgba(15,23,42,0.78)", color: "#fff",
          }}>
            {over && <div style={{ fontSize: 22, fontWeight: 700 }}>Game over · Score {score}</div>}
            <button onClick={start} style={{ background: "#0ea5e9", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Play again" : "▶ Play"}
            </button>
          </div>
        )}
        {running && quizUi && (
          <div style={{
            position: "absolute", left: 10, right: 10, bottom: 10,
            background: "rgba(15,23,42,0.92)", border: "1px solid #475569",
            borderRadius: 12, padding: 12, color: "#f8fafc",
          }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>{quizUi.prompt}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {quizUi.options.map((opt, i) => (
                <button key={opt} onClick={() => answerQuiz(i)}
                  style={{ flex: "1 1 40%", padding: "8px 10px", borderRadius: 8, border: "1px solid #64748b", background: "#1e293b", color: "#fff", cursor: "pointer" }}>
                  {i + 1}. {opt}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
